#!/usr/bin/python
from mininet.net import Containernet
from mininet.node import Controller, Docker, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink, Link
from mininet import clean

import psutil        

from multiprocessing import Process
import exceptions
import subprocess
import re
import os
import yaml
import shutil
import logging
# import coloredlogs
import time
LOG = logging.getLogger(os.path.basename(__file__))
# LOG = logging.getLogger(__name__)

# experiment logs
# coloredlogs.install(level="DEBUG")
# mininet logs
setLogLevel('info')
# others
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("docker").setLevel(logging.WARNING)


# wait between start scripts are triggered
TRIGGER_DELAY = 30


class Experiment:
    def __init__(self, run_id, parameter, cli_mode=False):
        self.run_id = run_id
        self.scenario = parameter
        self.cli_mode = cli_mode
        self.net = None
        self.nodes = {}
        self.switches = {}
        self.containers = []
        self.switch_links = {}
        self.config_sw_links = {}
        # LOG.info("Switch mode: %s" % str(self.switch_mode))
        LOG.debug("Scenario Built")
        self.topo_parsed = {}

    def __repr__(self):
        return "run_%06d" % (self.run_id)

    def start(self, cli_mode=False):
        # split down experiments in small steps that can be overwritten subclasses
        self._create_network()
        self._add_containers()
        self._add_switches()
        self._add_links()
        self._start_network()
        self._config_switches()
        LOG.info("Experiment %s running." % (self.run_id))
        host_info = self.hosts_management_info()
        self._trigger_container_scripts(host_info)
        if cli_mode:  # interactive mode vs. experiment mode
            CLI(self.net)
        return host_info
            # else:
        #     self._wait_experiment()

    def stop(self):
        # time.sleep(3)
        # self._trigger_container_scripts(cmd="./stop.sh")
        self._stop_network()
        self._stop_processes()
        self.mn_cleanup()
        self.topo_parsed = {}

    def _stop_processes(self):
        LOG.info("stopping processes")
        nodes_topo = self.topo_parsed.get("nodes")
        for node_id in self.nodes:
            node_req = nodes_topo.get(node_id, None)
            if node_req:
                image_format = node_req.get("image_format")
                if image_format == "process":
                    node_process = self.nodes[node_id]
                    # LOG.info("stopping processes node_id %s alive %s", node_id, node_process.is_alive())
                    # node_process.terminate()
                    # LOG.info('node_id %s process stopped %s', node_id, node_process.is_alive())
                    node_process.kill()
                    LOG.info('node_id %s process stopped %s', node_id, node_process)

    def mn_cleanup(self):
        # mininet cleanup
        clean.cleanup()

    def _create_network(self):
        self.net = Containernet(controller=Controller)
        self.net.addController('c0')
        LOG.info("Created network: %r" % self.net)

    def _add_containers(self):
        nodes = self.topo_parsed.get("nodes")
        self.add_nodes(nodes)

    def _add_switches(self):
        switches = self.topo_parsed.get("switches")
        self.add_switches(switches)

    def _add_links(self):
        links = self.topo_parsed.get("links")
        self.add_links(links)

    def _start_network(self):
        if self.net:
            self.net.start()
            LOG.info("Started network: %r" % self.net)

    def _config_sw_flow(self, sw_id, params):
        LOG.info("_config_sw_flow %s", params)
        cmd = "add-flow in_port={src},actions=output:{dst}".format(**params)
        cmd_args = cmd.split(' ')
        sw = self.switches.get(sw_id)
        ack = sw.dpctl(*cmd_args)
        # LOG.info("ack %s", ack)

    def _get_sw_port(self, sw, port_name):
        # LOG.info("_get_sw_port %s", port_name)
        cmd = "find interface name={0}"
        cmd = cmd.format(port_name)
        cmd_args = cmd.split(' ')
        stats_port = sw.vsctl(*cmd_args)
        regex='ofport\s+:\s+([0-9]+)'
        of_ports = re.findall(regex, stats_port)
        of_port = of_ports.pop()
        return of_port

    def _config_map_ports_sw(self, sw_id, adjs):
        # LOG.info("_config_map_ports_sw sw_id %s, adjs %s", sw_id, adjs)
        maps = []
        sw = self.switches.get(sw_id)
        sw_links = self.switch_links.get(sw_id)
        # LOG.info("sw_links %s", sw_links)
        default = {'src': None, 'dst': None}

        for stats in adjs:
            sw_port = stats.intf1.name
            host_port = stats.intf2.name
            # LOG.info("sw link port1 %s port2 %s", sw_port, host_port)
            port_num = self._get_sw_port(sw, sw_port)
            for sw_link in sw_links:
                src = sw_link.get("src")
                dst = sw_link.get("dst")
                if host_port == src:
                    default['src'] = port_num
                    # LOG.info("default['src'] %s = host_port %s port_num %s", sw_port, host_port, port_num)
                if host_port == dst:
                    default['dst'] = port_num
                    # LOG.info("default['dst'] %s = host_port %s port_num %s", sw_port, host_port, port_num)
        maps.append(default)
        # LOG.info("maps %s", maps)
        return maps

    def _config_switches(self):
        LOG.info("_config_switches")
        for sw_id,adjs in self.config_sw_links.items():
            map_sw_ports = self._config_map_ports_sw(sw_id,adjs)
            for map_ports in map_sw_ports:
                self._config_sw_flow(sw_id, map_ports)

    def format_host_entrypoint(self, node_id, entrypoint, hosts_info, configuration, node_id_info=None):
        node_id_info = node_id_info if node_id_info else node_id
        node_info = hosts_info.get(node_id_info)

        node_ip = node_info.get("management").get("ip")
        fmt_kwargs = {'host_id': node_id, 'host_ip': node_ip}
        if configuration:
            fmt_kwargs['configuration'] = configuration
        LOG.info("fmt_kwargs %s", fmt_kwargs)
        fmt_entrypoint = entrypoint.format(**fmt_kwargs)
        return fmt_entrypoint

    def _trigger_container_scripts(self, hosts_info):
        # time.sleep(TRIGGER_DELAY)
        nodes_topo = self.topo_parsed.get("nodes")
        for node_id, node_instance in self.nodes.items():
            node_req = nodes_topo.get(node_id, None)
            if node_req:
                entrypoint = node_req.get("entrypoint")
                configuration = node_req.get("configuration")
                image_format = node_req.get("image_format")
                if image_format == "docker":
                    if node_id in hosts_info:
                        entrypoint = self.format_host_entrypoint(node_id, entrypoint, hosts_info, configuration)
                    if entrypoint:
                        node_instance.cmd(entrypoint)
                        LOG.debug("Triggered %r in container %r" % (entrypoint, node_instance))
        
        # Start monitor entrypoint inside docker containers            
        nodes_topo = self.topo_parsed.get("nodes")
        for node_id, node_req in nodes_topo.items():
            image_format = node_req.get("image_format")
            node_type = node_req.get("type")        
            if image_format == "process" and node_type == "monitor":
                    habitat = node_req.get("habitat")
                    if habitat:
                        location = habitat.get("location")
                        target = habitat.get("target")
                        if location == "internal":
                            node_host_instance = self.nodes.get(target, None)
                            if node_host_instance:
                                entrypoint = node_req.get("entrypoint")
                                entrypoint = self.format_host_entrypoint(node_id, entrypoint, hosts_info, None, node_id_info=target)
                                node_host_instance.cmd(entrypoint)
                                LOG.debug("Triggered %r in container %r" % (entrypoint, node_host_instance))

                                mngnt_ips = self.get_host_ips(node_host_instance)
                                hosts_info[node_id] = {
                                    'management':  mngnt_ips,
                                    'type': node_type,
                                }

        time.sleep(TRIGGER_DELAY)

    def _stop_network(self):
        if self.net:
            self.net.stop()
            LOG.info("Stopped network: %r" % self.net)

    def wait_experiment(self, wait_time):
        LOG.info("Experiment %s running. Waiting for %d seconds." % (self.run_id , wait_time))
        time.sleep(wait_time)
        LOG.info("Experiment done.")

    def _new_container(self, name, ip, image, vcpus=None, cpu_cores=None, cpu_bw=None, mem=None, volumes=None, environment=None):
        """
        Helper method to create and configure a single container.
        """
        def calculate_cpu_cfs_values(vcpus, cpu_bw):
            vcpus = 1 if not vcpus else vcpus
            cpu_bw_p = 100000*vcpus
            cpu_bw_q = int(cpu_bw_p*cpu_bw)
            return cpu_bw_p, cpu_bw_q

        # translate cpu_bw to period and quota
        cpu_bw_p, cpu_bw_q = calculate_cpu_cfs_values(vcpus, cpu_bw)
        # create container
        c = self.net.addDocker(name,
           ip=ip,
           dimage=image,
        #    volumes=[os.path.join(os.getcwd(), self.out_path) + "share_" + name + ":/mnt/share:rw"],
           volumes=volumes,
           cpu_period=cpu_bw_p,
           cpu_quota=cpu_bw_q,
           cpuset_cpus=str(cpu_cores) if cpu_cores else '',
           mem_limit=str(mem) + "m",
           memswap_limit=0,
           environment=environment)
        # bookkeeping
        self.containers.append(c)
        LOG.debug("Started container: %r" % str(c))
        return c

    def _parse_topo(self, topo):
        topo_parsed = {}

        nodes = topo.get("nodes")
        links = topo.get("links")

        topo_parsed["nodes"] = {}
        for node in nodes:
            node_id = node.get("id")
            node_image = node.get("image")
            node_entrypoint = node.get("entrypoint")
            node_type = node.get("type")
            node_config = node.get("configuration", None)
            image_format = node.get("image_format")
            habitat = node.get("habitat", None)
            volumes = node.get("volumes", [])
            
            if volumes:
                volumes = volumes.split(',')
            
            topo_parsed["nodes"][node_id] = {
                "image_format": image_format,
                "image": node_image,
                "interfaces": {},
                "entrypoint": node_entrypoint,
                "type": node_type,
                "volumes": volumes,
                "configuration": node_config,
                "habitat": habitat,
            }
            interfaces = node.get("connection_points")
            faces = {}
            if interfaces:
                for intf in interfaces:
                    intf_id = intf.get("id")
                    faces[intf_id] = intf
            topo_parsed["nodes"][node_id]["interfaces"] = faces

        topo_parsed["links"] = {}
        topo_parsed["switches"] = []

        for link in links:
            link_id = link.get("id")
            link_type = link.get("type")


            if link_type == "E-Flow":
                link_network = link.get("network")
                if link_network not in topo_parsed["switches"]:
                    topo_parsed["switches"].append(link_network)

                adjacencies = link.get("connection_points")
                src, src_inft = adjacencies[0].split(":")
                dst, dst_intf = adjacencies[1].split(":")

                if link_network not in self.switch_links: 
                    self.switch_links[link_network] = []
                self.switch_links[link_network].append({'src':src_inft, 'dst':link_network})
                self.switch_links[link_network].append({'src':link_network, 'dst':dst_intf})

                link_id_num = 0
                for (host,host_inft) in [(src,src_inft), (dst,dst_intf)]:
                    params_dst = {}                    
                    if host_inft in topo_parsed["nodes"][host]["interfaces"]:
                        face = topo_parsed["nodes"][host]["interfaces"].get(host_inft)
                        params_dst["ip"] = face.get("address", "")                  
                        link_id_parsed = link_id + str(link_id_num)
                        topo_parsed["links"][link_id_parsed] = {
                            'type': link_type,
                            'src': link_network,
                            'dst': host,
                            'intf_dst': host_inft,
                            'params_dst': params_dst,
                        }
                    link_id_num += 1
                LOG.info("sw_links %s", self.switch_links)

            elif link_type == "E-LAN":
                link_network = link.get("network")
                if link_network not in topo_parsed["switches"]:
                    topo_parsed["switches"].append(link_network)

                adjacencies = link.get("connection_points")
                link_id_num = 0
                for adj in adjacencies:
                    dst, dst_intf = adj.split(":")

                    params_dst = {}
                    if dst_intf in topo_parsed["nodes"][dst]["interfaces"]:
                        face = topo_parsed["nodes"][dst]["interfaces"].get(dst_intf)
                        params_dst["ip"] = face.get("address", "")
                        link_id_parsed = link_id + str(link_id_num)
                        topo_parsed["links"][link_id_parsed] = {
                            'type': link_type,
                            'src': link_network,
                            'dst': dst,
                            'intf_dst': dst_intf,
                            'params_dst': params_dst,
                        }
                        link_id_num += 1

            elif link_type == "E-Line":
                adjacencies = link.get("connection_points")
                src, src_inft = adjacencies[0].split(":")
                dst, dst_intf = adjacencies[1].split(":")

                params_dst = {}
                if dst_intf in topo_parsed["nodes"][dst]["interfaces"]:
                    face = topo_parsed["nodes"][dst]["interfaces"].get(dst_intf)
                    params_dst["ip"] = face.get("address", "")

                params_src = {}
                if src_inft in topo_parsed["nodes"][src]["interfaces"]:
                    face = topo_parsed["nodes"][src]["interfaces"].get(src_inft)
                    params_src["ip"] = face.get("address", "")

                topo_parsed["links"][link_id] = {
                    'type': link_type,
                    'src': src,
                    'intf_src': src_inft,
                    'dst': dst,
                    'intf_dst': dst_intf,
                    'params_src': params_src,
                    'params_dst': params_dst,
                }
            else:
                LOG.info("unknown link type %s", link_type)
        return topo_parsed

    def _parse_requirements(self, topo, reqs):
        for req in reqs:
            req_id = req.get("id")
            req_res = req.get("resources")
            if req_id in topo["nodes"]:
                vcpus = req_res.get("cpu").get("vcpus", None)
                cpu_cores = req_res.get("cpu").get("cpu_cores", None)
                cpu_bw = req_res.get("cpu").get("bw", None)
                mem = req_res["memory"]["size"]
                node_res = {
                    "vcpus": vcpus,
                    "cpu_bw": cpu_bw,
                    "cpu_cores": cpu_cores,
                    "mem": mem,
                }
                topo["nodes"][req_id].update(node_res)

    def build(self):
        topo = self.scenario.get("topology")
        topo_parsed = self._parse_topo(topo)
        reqs = self.scenario.get("requirements")
        self._parse_requirements(topo_parsed, reqs)
        self.topo_parsed = topo_parsed
        print(topo_parsed)

    def add_nodes(self, nodes):
        for node_id, node in nodes.items():
            image_format = node.get("image_format")
            if image_format == "docker":
                added_node = self._new_container(
                    node_id,
                    node.get("addr_input", None),
                    node.get("image"),
                    vcpus=node.get("vcpus", None),
                    cpu_cores=node.get("cpu_cores", None),
                    cpu_bw=node.get("cpu_bw"),
                    mem=node.get("mem"),
                    volumes=node.get("volumes"),
                    environment=node.get("environment", None)
                )
                self.nodes[node_id] = added_node
            elif image_format == "process":
                node_type = node.get("type")
                if node_type == "monitor":
                    habitat = node.get("habitat")
                    if habitat:
                        location = habitat.get("location")
                        if location == "internal":
                            pass
                        elif location == "external":
                            added_node = self._new_process(node_id, node.get("entrypoint"))
                            self.nodes[node_id] = added_node
                            LOG.info("Added node process: habitat external node_type %s process, node_id %s", node_type, node_id)
                        else:
                            LOG.info("Node monitor without location process, node_id %s", node_id)
                    else:
                        LOG.info("Node monitor without habitat process, node_id %s", node_id)
                else:
                    LOG.info("Add node process external node_type %s process, node_id %s", node_type, node_id)
                    added_node = self._new_process(node_id, node.get("entrypoint"))
                    self.nodes[node_id] = added_node
            else:
                LOG.info("unknown node_id %s image_format %s", node_id, image_format)

    def get_host_ip(self):
        intf = "docker0"
        intfs =  psutil.net_if_addrs()
        intf_info = intfs.get(intf, None)
        if intf_info:
            for address in intf_info:
                if address.family == 2:
                    host_address = address.address
                    return host_address
        return None        

    def process_args(self, cmd):
        args = cmd.split(" ")
        # p = subprocess.Popen(args,
        #                 stdin=subprocess.PIPE,
        #                 stdout=subprocess.PIPE,
        #                 stderr=subprocess.PIPE,
        #                 )
        subprocess.call(args)

    def _new_process(self, node_id, entrypoint):
        p = None
        node_ip = self.get_host_ip()
        fmt_kwargs = {'host_id': node_id, 'host_ip': node_ip}
        cmd_entrypoint = entrypoint.format(**fmt_kwargs)
        LOG.info("New process: node_id %s - process args %s", node_id, cmd_entrypoint)
        try:
            # p = Process(target=self.process_args, args=(cmd_entrypoint,))
            # p.daemon = True
            # p.start()
            args = cmd_entrypoint.split(" ")
            p = subprocess.Popen(args,
                # stdin = subprocess.PIPE,
                # stdout = subprocess.PIPE,
                # stderr = subprocess.PIPE,
                )            
        except OSError as e:
            LOG.info('ERROR: process could not be started %s', e)
        else:
            # LOG.info('node_id %s - cmd %s - pid %s - alive %s', node_id, cmd_entrypoint, p.pid, p.is_alive())
            LOG.info('node_id %s - cmd %s - pid %s', node_id, cmd_entrypoint, p.pid)
        finally:    
            return p

    def add_switches(self, switches):
        for sw_name in switches:
            s = self.net.addSwitch(sw_name)
            self.switches[sw_name] = s

    def add_links(self, links):
        for link_id, link in links.items():
            link_type = link.get("type")
            if link_type == "E-LAN":
                src = link.get("src")
                dst = link.get("dst")
                intf_dst = link.get("intf_dst")
                params_dst = link.get("params_dst", {})
                src_node = self.switches.get(src)
                dst_node = self.nodes.get(dst)
                self.add_link_sw(src_node, dst_node, intf_dst, params_dst)

            if link_type == "E-Flow":
                src = link.get("src")
                dst = link.get("dst")
                intf_dst = link.get("intf_dst")
                params_dst = link.get("params_dst", {})
                src_node = self.switches.get(src)
                dst_node = self.nodes.get(dst)
                stats = self.add_link_sw(src_node, dst_node, intf_dst, params_dst)
                
                if src not in self.config_sw_links:
                    self.config_sw_links[src] = []
                self.config_sw_links[src].append(stats)

            if link_type == "E-Line":
                src = link.get("src")
                dst = link.get("dst")
                intf_src = link.get("intf_src")
                intf_dst = link.get("intf_dst")
                params_src = link.get("params_src", None)
                params_dst = link.get("params_dst", None)
                src_node = self. nodes.get(src)
                dst_node = self.nodes.get(dst)
                self.add_link_direct(src_node, dst_node, intf_src, intf_dst, params_src, params_dst)
        LOG.info("config_sw_links %s ", self.config_sw_links)

    def add_link_sw(self, sw, dst, intf_dst, params_dst):
        link_status = self.net.addLink(sw, dst,
                                       intfName2=intf_dst, params2=params_dst)
        LOG.info("adding link dst %s, intf_dst %s, params_dst %s, status %s", dst, intf_dst, params_dst, link_status)
        return link_status

    def add_link_direct(self, src, dst, intf_src, intf_dst, params_src, params_dst):
        self.net.addLink(src, dst,
                         intfName1=intf_src, intfName2=intf_dst,
                         params1=params_src, params2=params_dst)

    def get_host_ips(self, host):
        intf = 'eth0'
        config = host.cmd( 'ifconfig %s 2>/dev/null' % intf)
        # LOG.info("get host %s config ips %s", host, config)
        if not config:
            LOG.info('Error: %s does not exist!\n', intf)
        ips = re.findall( r'\d+\.\d+\.\d+\.\d+', config )
        if ips:
            # LOG.info("host intf ips %s", ips)
            ips_dict = {'ip': ips[0], 'broadcast': ips[1], 'mask': ips[2]}
            return ips_dict
        return None
        
    def hosts_management_info(self):
        info = {}
        nodes = self.topo_parsed.get("nodes")
        for host_id,host in self.nodes.items():
            node_info = nodes.get(host_id)
            image_format = node_info.get("image_format")
            if image_format == "docker":
                mngnt_ips = self.get_host_ips(host)
                info[host_id] = {
                    'management':  mngnt_ips,
                    'type': node_info.get("type"),
                }
            if image_format == "process":
                node_info = nodes.get(host_id)
                node_type = node_info.get("type")
                if node_type == "monitor":
                    habitat = node_info.get("habitat")
                    if habitat:
                        location = habitat.get("location")
                        if location == "internal":
                            pass
                        if location == "external":
                            node_ip = self.get_host_ip()
                            mngnt_ips = {'ip': node_ip}
                            info[host_id] = {
                                'management':  mngnt_ips,
                                'type': node_info.get("type"),
                            }          
        return info


if __name__ == "__main__":

    # regex='ofport\s+:\s+([[:digit:]]+)'
    # regex='ofport\s+:\s+([0-9]+)'
    # of_ports = re.findall(regex, stats_port)
    # print (of_ports)    
    exp = Experiment(1, None, False)
    p = exp._new_process('d4', "gym-monitor --id {host_id} --url http://{host_ip}:8987 &")
    