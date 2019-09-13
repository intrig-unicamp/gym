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
import time
import signal

# LOG = logging.getLogger(os.path.basename(__file__))
LOG = logging.getLogger(__name__)

setLogLevel('info')

logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("docker").setLevel(logging.WARNING)

# wait between start scripts are triggered
TRIGGER_DELAY = 10


class Experiment:
    def __init__(self, run_id, topo, cli_mode=False):
        self.run_id = run_id
        self.topo = topo
        self.cli_mode = cli_mode
        self.net = None
        self.nodes = {}
        self.switches = {}
        self.config_sw_links = {}
        self.nodes_info = {}
        LOG.debug("Experiment Instance Created - %s", self.run_id)

    def _create_network(self):
        self.net = Containernet(controller=Controller)
        self.net.addController('c0')
        LOG.info("Created network: %r" % self.net)

    def _add_container(self, node):
        
        def calculate_cpu_cfs_values(cpu_resources):
            vcpus = cpu_resources.get("vcpus", 1)
            cpu_bw = cpu_resources.get("cpu_bw", 1.0)

            cpu_bw_p = 100000*vcpus
            cpu_bw_q = int(cpu_bw_p*cpu_bw)
            return cpu_bw_p, cpu_bw_q

        resources = node.get("resources")
        cpu_resources = resources.get("cpu")
        
        cpu_bw_p, cpu_bw_q = calculate_cpu_cfs_values(cpu_resources)
        cpu_cores = cpu_resources.get("pinning", "")

        memory = resources.get("memory")
        volumes = resources.get("storage").get("volumes", [])
        if volumes:
            volumes = volumes.split(',')

        mng_ip = node.get("mng_intf", None)

        container = self.net.addDocker(node.get("id"),
           ip=mng_ip,
           dimage=node.get("image"),
           volumes=volumes,
           cpu_period=cpu_bw_p,
           cpu_quota=cpu_bw_q,
           cpuset_cpus=str(cpu_cores),
           mem_limit=str(memory.get("size", 1024)) + "m",
           memswap_limit=0)
        
        LOG.debug("Added container: %s", node.get("id"))
        return container
    
    def _add_nodes(self):
        nodes = self.topo.get("nodes")

        for node_id, node in nodes.items():
            image_format = node.get("image_format")
            
            if image_format == "docker":
                added_node = self._add_container(node)
                self.nodes[node_id] = added_node
            
            elif image_format == "process":
                node_rels = node.get("relationships")
                if node_rels:
                    self.nodes[node_id] = None
                    LOG.info("Added node process: node_id %s", node_id)

            else:
                LOG.info("Node %s not added, unknown format %s", node_id, image_format)

    def _add_switches(self):
        switches = self.topo.get("switches")
        
        for sw_name in switches:
            s = self.net.addSwitch(sw_name)
            self.switches[sw_name] = s

    def add_link_sw(self, sw, dst, intf_dst, params_dst):
        link_status = self.net.addLink(sw, dst,
                                       intfName2=intf_dst, params2=params_dst)
        LOG.debug("Added link src %s, dst %s, intf_dst %s, params_dst %s", sw, dst, intf_dst, params_dst)
        return link_status

    def add_link_direct(self, src, dst, intf_src, intf_dst, params_src, params_dst):
        link_status = self.net.addLink(src, dst,
                                        intfName1=intf_src, intfName2=intf_dst,
                                        params1=params_src, params2=params_dst)
        LOG.debug("Added link src %s - dst %s, intf_src %s - intf_dst %s", src, dst, intf_src, intf_dst)                                                                            
        return link_status

    def _add_links(self):
        links = self.topo.get("links")
    
        for link_id, link in links.items():
            link_type = link.get("type")
            if link_type == "E-LAN":
                src = link.get("src")
                dst = link.get("dst")
                intf_dst = link.get("intf_dst")
                params_dst = link.get("params_dst", {})
                src_node = self.switches.get(src)
                dst_node = self.nodes.get(dst)
                stats = self.add_link_sw(src_node, dst_node, intf_dst, params_dst)
                LOG.info("Link %s added, type %s, status %s", link_id, link_type, stats)

            elif link_type == "E-Flow":
                src = link.get("src")
                dst = link.get("dst")
                intf_dst = link.get("intf_dst")
                params_dst = link.get("params_dst", {})
                src_node = self.switches.get(src)
                dst_node = self.nodes.get(dst)
                stats = self.add_link_sw(src_node, dst_node, intf_dst, params_dst)
                LOG.info("Link %s added, type %s, status %s", link_id, link_type, stats)

                if src not in self.config_sw_links:
                    self.config_sw_links[src] = []
                self.config_sw_links[src].append(stats)

            elif link_type == "E-Line":
                src = link.get("src")
                dst = link.get("dst")
                intf_src = link.get("intf_src")
                intf_dst = link.get("intf_dst")
                params_src = link.get("params_src", None)
                params_dst = link.get("params_dst", None)
                src_node = self. nodes.get(src)
                dst_node = self.nodes.get(dst)
                stats = self.add_link_direct(src_node, dst_node, intf_src, intf_dst, params_src, params_dst)
                LOG.info("Link %s added, type %s, status %s", link_id, link_type, stats)
            
            else:
                LOG.info("Link %s not added, unknown type %s", link_id, link_type)

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
        LOG.info("Config switch flow dpctl output %s", ack)

    def _get_sw_port(self, sw, port_name):
        cmd = "find interface name={0}"
        cmd = cmd.format(port_name)
        cmd_args = cmd.split(' ')
        stats_port = sw.vsctl(*cmd_args)
        regex='ofport\s+:\s+([0-9]+)'
        of_ports = re.findall(regex, stats_port)
        of_port = of_ports.pop()
        return of_port

    def _config_map_ports_sw(self, switch_links, sw_id, adjs):
        maps = []
        sw = self.switches.get(sw_id)
        sw_links = switch_links.get(sw_id)
        default = {'src': None, 'dst': None}

        for stats in adjs:
            sw_port = stats.intf1.name
            host_port = stats.intf2.name
            port_num = self._get_sw_port(sw, sw_port)
            for sw_link in sw_links:
                src = sw_link.get("src")
                dst = sw_link.get("dst")
                if host_port == src:
                    default['src'] = port_num
                if host_port == dst:
                    default['dst'] = port_num
        maps.append(default)
        return maps

    def _config_switches(self):
        switch_links = self.topo.get("port_maps")

        if self.config_sw_links:
            LOG.info("Configuring switches flow entries")
            for sw_id,adjs in self.config_sw_links.items():
                map_sw_ports = self._config_map_ports_sw(switch_links, sw_id,adjs)
                for map_ports in map_sw_ports:
                    self._config_sw_flow(sw_id, map_ports)

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
        
    def _format_workflow(self, workflow, node_info):
        implementation = workflow.get("implementation")
        parameters = workflow.get("parameters")
        fmt_kwargs = {}
        
        if parameters:
            kwargs = { param.get("input"):param.get("value") for param in parameters }
            
            for k,v in kwargs.items():
                args = v.split(":")
                call = args[0]
                if call == "get_attrib":
                    attrib = args[1]
                    if attrib == "ip":
                        fmt_kwargs[k] = node_info.get(attrib)
                else:
                    fmt_kwargs[k] = v

            LOG.info("Format workflow entrypoint kwargs %s", fmt_kwargs)
            entrypoint = implementation.format(**fmt_kwargs)
        else:
            entrypoint = implementation
            
        return entrypoint
    
    def _new_process(self, entrypoint):
        p = None
        LOG.info("Creating new host process: %s", entrypoint)
        try:
            args = entrypoint.split(" ")
            p = subprocess.Popen(args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                )            
        except OSError as e:
            LOG.info('ERROR: process could not be started %s', e)
        else:
            LOG.info('Process started: pid %s', p.pid)
        finally:    
            return p

    def _start_lifecycle(self):
        nodes_topo = self.topo.get("nodes")
        
        for node_id, node in nodes_topo.items():
            image_format = node.get("image_format")
            workflows = node.get("lifecycle")                
            start_workflows = [ workflow for workflow in workflows if workflow.get("workflow") == "start" ]    
            
            if image_format == "docker": 
                for workflow in start_workflows:
                    node_instance = self.nodes.get(node_id)
 
                    if node_instance:
                        node_info = self.get_host_ips(node_instance)
                        self.nodes_info[node_id] = node_info
                        entrypoint = self._format_workflow(workflow, node_info)

                        if entrypoint:
                            node_instance.cmd(entrypoint)
                            LOG.debug("Node %s, format %s, workflow start %s ", node_id, image_format, entrypoint)

            elif image_format == "process":
                node_rels = node.get("relationships")

                for rel in node_rels:
                    relationship = rel.get("type")
                    target = rel.get("target")

                    if relationship == "HostedOn":
                        node_instance = self.nodes.get(target)
                        
                        if node_instance:
                            node_info = self.get_host_ips(node_instance)
                            self.nodes_info[node_id] = node_info
                            entrypoint = self._format_workflow(workflow, node_info)

                            if entrypoint:
                                node_instance.cmd(entrypoint)
                                LOG.debug("Node %s, format %s, relationship %s, target %s, workflow start %s ", node_id, image_format, relationship, target, entrypoint)

                    if relationship == "AttachesTo":
                        node_ip = self.get_host_ip()
                        node_info = {'ip': node_ip}
                        self.nodes_info[node_id] = node_info
                        entrypoint = self._format_workflow(workflow, node_info)

                        node_instance = self._new_process(entrypoint)
                        self.nodes[node_id] = node_instance

                        target_id = "host-" + target
                        LOG.debug("Node %s, format %s, relationship %s, target %s, workflow start %s ", node_id, image_format, relationship, target_id, entrypoint)
        
        time.sleep(TRIGGER_DELAY)

    def start(self, cli_mode=False):
        self._create_network()
        self._add_nodes()
        self._add_switches()
        self._add_links()
        self._start_network()
        self._config_switches()
        self._start_lifecycle()
        LOG.info("Experiment %s running." % (self.run_id))
        # if cli_mode:  # interactive mode vs. experiment mode
            # CLI(self.net)
        return self.nodes_info

    def _stop_network(self):
        if self.net:
            self.net.stop()
            LOG.info("Stopped network: %r" % self.net)

    def _stop_processes(self):
        LOG.info("stopping processes")
        nodes_topo = self.topo.get("nodes")
        
        for node_id in self.nodes:
            node_req = nodes_topo.get(node_id, None)
        
            if node_req:
                image_format = node_req.get("image_format")
                
                if image_format == "process":
                    node_rels = node_req.get("relationships")

                    for rel in node_rels:
                        relationship = rel.get("type")
                        target = rel.get("target")

                        if relationship == "AttachesTo":                    
                            node_process = self.nodes[node_id]
                        
                            if node_process.poll() is None:
                                # os.killpg( node_process.pid, signal.SIGHUP )
                                node_process.terminate()
                                node_process.wait()

                            LOG.info('Node %s process %s stopped return code %s', node_id, node_process.pid, node_process.returncode)
                            node_process = None
                            self.nodes[node_id] = None

    def mn_cleanup(self):
        if self.net:
            self.net.stop()
        clean.cleanup()

    def stop(self):
        self._stop_network()
        self._stop_processes()
        self.mn_cleanup()
        self.topo_parsed = {}
        self.nodes = {}
        self.switches = {}
        self.config_sw_links = {}
        self.nodes_info = {}
        self.net = None



