import os
import logging
logger = logging.getLogger(__name__)

from gym.common.entity import Component, set_ev_handler
from gym.common.messages import Report, Task, Deploy, Built, Result
from gym.player.vnfbd import VNFBD
from gym.player.vnfpp import VNFPP
from gym.player.vnfbr import VNFBR
from gym.common.events import EventResult

from gym.common.process import Loader
from gym.player.store import Storage

from gym.player.plugins.containernet import Environment as cnetenv


ETC_REL_PATH = '../etc/db/vnf-bd/'



class Assistants:
    def __init__(self):
        self._managers = {}
        self._agents = {}
        self._monitors = {}
        self._agents_metrics = {}
        self._monitors_metrics = {}
        self._full_info = {}

    def clear(self):
        self._managers.clear()
        self._agents.clear()
        self._monitors.clear()
        self._agents_metrics.clear()
        self._monitors_metrics.clear()
        self._full_info.clear()

    def get_manager_agent_metrics(self, manager):
        manager_id = manager['uuid']
        if 'features' in manager:
            if 'agents' in manager['features']:
                for agent in manager['features']['agents']:
                    agent_id = agent['uuid']
                    self.add_manager_component(manager_id, 'agent', agent_id)
                    if agent_id not in self._agents:
                        self._agents[agent_id] = {}
                        self._agents[agent_id]['host'] = agent['features']['environment']['host']
                        self._agents[agent_id]['id'] = agent_id
                    if 'probers' in agent['features']:
                        self._agents[agent_id]['probers'] = {}
                        for prober in agent['features']['probers'].values():
                            metrics = prober['metrics']
                            parameters = list(prober['parameters'].keys())
                            prober_id = prober['id']
                            if prober_id not in self._agents[agent_id]['probers']:
                                self._agents[agent_id]['probers'][prober_id] = {'metrics': metrics, 'parameters':parameters}
                            value = {'manager':manager_id, 'agent':agent_id, 'prober':prober_id, 'parameters':parameters}
                            for metric in metrics:
                                if metric not in self._agents_metrics:
                                    self._agents_metrics[metric] = [value]
                                else:
                                    if value not in self._agents_metrics[metric]:
                                        self._agents_metrics[metric].append(value)

    def get_manager_monitor_metrics(self, manager):
        manager_id = manager['uuid']
        if 'features' in manager:
            if 'monitors' in manager['features']:
                for monitor in manager['features']['monitors']:
                    monitor_id = monitor['uuid']
                    self.add_manager_component(manager_id, 'monitor', monitor_id)
                    if monitor_id not in self._monitors:
                        self._monitors[monitor_id] = {}
                        self._monitors[monitor_id]['host'] = monitor['features']['environment']['host']
                        self._monitors[monitor_id]['id'] = monitor_id
                    if 'listeners' in monitor['features']:
                        self._monitors[monitor_id]['listeners'] = {}
                        for listener in monitor['features']['listeners'].values():
                            metrics = listener['metrics']
                            parameters = list(listener['parameters'].keys())
                            listener_id = listener['id']
                            if listener_id not in self._monitors[monitor_id]['listeners']:
                                self._monitors[monitor_id]['listeners'][listener_id] = {'metrics': metrics, 'parameters':parameters}
                            value = {'manager': manager_id, 'monitor': monitor_id, 'listener': listener_id, 'parameters':parameters}
                            for metric in metrics:
                                if metric not in self._monitors_metrics:
                                    self._monitors_metrics[metric] = [value]
                                else:
                                    if value not in self._monitors_metrics[metric]:
                                        self._monitors_metrics[metric].append(value)

    def add_manager_component(self, manager_id, type, component_id):
        if manager_id not in self._managers:
            self._managers[manager_id] = {'id':manager_id, 'agents': [], 'monitors': []}
        if type == 'agent':
            if component_id not in self._managers[manager_id]['agents']:
                self._managers[manager_id]['agents'].append(component_id)
        if type == 'monitor':
            if component_id not in self._managers[manager_id]['monitors']:
                self._managers[manager_id]['monitors'].append(component_id)

    def fill_members(self, managers):
        for manager in managers:
            self.get_manager_agent_metrics(manager)
            self.get_manager_monitor_metrics(manager)
        self.fill_full_structure()

    def fill_full_structure(self):
        for manager_id in self._managers:
            self._full_info[manager_id] = {"agents": [], "monitors": []}
            monitors = self._managers[manager_id].get("monitors")
            agents = self._managers[manager_id].get("agents")
            for monitor_id in monitors:
                monitor_info = self._monitors.get(monitor_id)
                self._full_info[manager_id]["monitors"].append(monitor_info)
            for agent_id in agents:
                agent_info = self._agents.get(agent_id) 
                self._full_info[manager_id]["agents"].append(agent_info)

    def satisfy_structure(self, vnfbd):
        logger.debug('satisfy_structure')
        for manager_id in self._managers.keys():
            manager_info = self._full_info.get(manager_id)
            selected_components = vnfbd.satisfy_scenario(manager_info)
            if selected_components:
                logger.debug('manager_id satisfied %s', manager_id)
                # logger.debug('selected_components %s', selected_components)
                return manager_id, selected_components
        return None

    def managers(self):
        return self._managers

    def agents(self):
        return self._agents

    def monitors(self):
        return self._monitors

    def agents_metrics(self):
        return self._agents_metrics

    def monitors_metrics(self):
        return self._monitors_metrics

    def metrics(self):
        metrics = dict(self._monitors_metrics.items() + self._agents_metrics.items())
        return metrics


class Controller(Component):
    def __init__(self, role, in_q, out_q, info):
        Component.__init__(self, role, in_q, out_q, info)
        self.assistants = Assistants()
        self._vnfbd_layout = {}
        self._vnfpps = {}        
        self._vnfbds = {}
        self._vnfbd_ids = {}
        self._vnfbd_instances = {}
        self._vnfbd_vnfpp = {}
        self._loader = Loader()
        self._etc_folder = ETC_REL_PATH
        self._vnfbd_db = {}
        self.cnet_plugin = None
        self.current_vnfbd_instance = None
        self._load_vnfdbs()

    def _update_path(self):
        _filepath = os.path.normpath(os.path.join(
            os.path.dirname(__file__),
            self._etc_folder))
        return _filepath

    def _load_vnfdbs(self):
        _path = self._update_path()
        logger.info('Load vnf-db in folder: %s', _path)
        files = self._loader.load_files(_path, 'vnf-bd-')
        for filename in files:
            _id = filename.split('-')[-1].split('.')[0]          
            self._vnfbd_db[_id] = filename
            
        logger.info("vnf-bds loaded %s", list(self._vnfbd_db.items()))

    def clean(self, vnfbd):
        vnfbd_id = vnfbd.get_id()
        vnfpp_id = self._vnfbd_vnfpp.get(vnfbd_id)
        
        logger.info("cleaning vnf-bd id %s", vnfbd_id)
        del self._vnfbd_layout[vnfbd_id]
        del self._vnfbds[vnfbd_id]
        del self._vnfbd_vnfpp[vnfbd_id]
        del self._vnfpps[vnfpp_id]
        self.current_vnfbd_instance = None

    def end_layout(self):
        vnfbd_instance_id = self.current_vnfbd_instance.get_id()
        vnfbd_id = self._vnfbd_ids.get(vnfbd_instance_id, None)

        if self.current_vnfbd_instance.deployed():
            self.deploy(self.current_vnfbd_instance, "stop")

        if vnfbd_id:
            vnfbd = self._vnfbds.get(vnfbd_id)
            layout = self._vnfbd_layout.get(vnfbd_id)

            result = Result()
            result.set("layout", layout)

            logger.info("generating result - end layout")
            self.send_event(EventResult(result))
            self.clean(vnfbd)

    def vnfbr(self, vnfbd, vnfpp):
        logger.info("generating vnf-br")
        vnfbd_id = vnfbd.get_id()
        layout = self._vnfbd_layout.get(vnfbd_id)
        layout_id = layout.get("id")
        
        vnfbr = VNFBR(layout_id)
        vnfbr.set_attrib("vnfbd", vnfbd)
        vnfbr.set_attrib("vnfpp", vnfpp)
        logger.debug(vnfbr.to_json())
        vnfbr.compile()

        result = Result()
        result.set("vnfbr", vnfbr)
        result.set("layout", layout)
        self.send_event(EventResult(result))
        self.clean(vnfbd)

    def finish(self, vnfbd):
        logger.info("Finishing vnf-bd - generating vnf-pp")
        
        vnfbd_instance = self.get_vnfbd_instance(vnfbd)
        if vnfbd_instance:
            if vnfbd_instance.deployed():
                self.deploy(vnfbd_instance, "stop")
    
        self.unregister_vnfbd_instance(vnfbd)
        vnfbd_id = vnfbd.get_id()
        vnfpp_id = self._vnfbd_vnfpp.get(vnfbd_id)
        vnfpp = self._vnfpps.get(vnfpp_id)
        layout = self._vnfbd_layout.get(vnfbd_id)
        layout_id = layout.get_id()
        vnfpp.compile(layout_id=layout_id)
        self.vnfbr(vnfbd, vnfpp)

    def digest(self, report):
        logger.info("digest report")
        report_id = report.get_id()
        #Get report_id has the same id as vnfbd_instance derived from vnfbd_id (self._vnfbd_ids stores such mapping)
        vnfbd_id = self._vnfbd_ids.get(report_id, None)

        if vnfbd_id:
            logger.info("Digest report id %s from vnf-bd id %s", report_id, vnfbd_id)
            vnfpp_id = self._vnfbd_vnfpp.get(vnfbd_id)
            vnfpp = self._vnfpps.get(vnfpp_id)
            vnfbd = self._vnfbds.get(vnfbd_id)
            vnfbd_instance = self.get_vnfbd_instance(vnfbd)
            vnfpp.add_report(vnfbd_instance, report)
            # vnfbd = self._vnfbds.get(vnfbd_id)
            self.check(vnfbd)
             
        else:
            logger.info("could not find associated vnfbd for vnfbd_instance_id %s", report_id)
            
    def task(self, vnfbd_instance):
        vnfbd_id = vnfbd_instance.get_id()
        structure = self.assistants.satisfy_structure(vnfbd_instance)

        if structure:
            logger.info("Creating task for vnf-bd id %s", vnfbd_id)
            manager_id, manager_components = structure
         
            task = Task(id=vnfbd_id)
            
            test = vnfbd_instance.get_test()
            trials = vnfbd_instance.get_trials()
            task.set("test", test)
            task.set("trials", trials)            
            logger.debug("test %s - trials %s", test, trials)

            agents = manager_components.get("agents", {})
            for agent_id, probers in agents.items():        
                task.add_agent(agent_id, probers)

            monitors = manager_components.get("monitors", {})
            for monitor_id, listeners in monitors.items():        
                task.add_monitor(monitor_id, listeners)

            peer = self.peers.get_by("uuid", manager_id)
            task.to(peer.get_address(), prefix=peer.get_prefix())
            
            logger.debug(task.to_json())
            outputs = [task]
            self.exit(outputs)
        else:
            logger.info("could not create task for vnf-bd id %s - structure %s", vnfbd_id, structure)            
    
    def register_vnfbd_instance(self, vnfbd, vnfbd_instance):
        vnfbd_id = vnfbd.get_id()
        vnfbd_instance_id = vnfbd_instance.get_id()
        if vnfbd_id not in self._vnfbd_instances:
            self._vnfbd_instances[vnfbd_id] = {}
        logger.debug("Registering vnfbd instance id %s belong to main vnfbd id %s", vnfbd_instance_id, vnfbd_id)
        self._vnfbd_instances[vnfbd_id][vnfbd_instance_id] = vnfbd_instance
        self._vnfbd_ids[vnfbd_instance_id] = vnfbd_id

    def unregister_vnfbd_instance(self, vnfbd):
        vnfbd_id = vnfbd.get_id()
        if vnfbd_id in self._vnfbd_instances:
            for vnfbd_instance_id in self._vnfbd_instances[vnfbd_id]:
                del self._vnfbd_ids[vnfbd_instance_id]
            del self._vnfbd_instances[vnfbd_id]
            return True
        return False

    def get_vnfbd_instance(self, vnfbd):
        vnfbd_id = vnfbd.get_id()
        vnfbd_instance_id = vnfbd.get_current_input_id()
        if vnfbd_id in self._vnfbd_instances:
            if vnfbd_instance_id in self._vnfbd_instances[vnfbd_id]:
                vnfbd_instance = self._vnfbd_instances[vnfbd_id][vnfbd_instance_id]
                return vnfbd_instance
        return None               

    def load_plugin(self, entrypoint_plugin, environment_topology):
        plugin_type = entrypoint_plugin.get("type")

        if plugin_type == "containernet":
            self.cnet_plugin = cnetenv(entrypoint_plugin, environment_topology)
            deploy_scenario = self.cnet_plugin.build()

            params = entrypoint_plugin.get("parameters")
            entrypoint_ls = [param.get("value") for param in params if param.get("input") == "entrypoint"]
            if entrypoint_ls:
                entrypoint = entrypoint_ls.pop()
                logger.info("Environment set plugin %s - entrypoint %s", plugin_type, entrypoint)
                return entrypoint, deploy_scenario
        return None, None
    
    def deploy(self, vnfbd_instance, request):
        callback = self.identity.get('url')
        instance_id = vnfbd_instance.get_id() 

        plugin, topology = vnfbd_instance.get_deployment()
        entrypoint, scenario = self.load_plugin(plugin, topology)

        deploy = Deploy()
        deploy.set("scenario", scenario)
        deploy.set("callback", callback)
        deploy.set("request", request)
        deploy.set("instance", instance_id)
        deploy.to(entrypoint, prefix=instance_id)
        outputs = [deploy]
        
        logger.info("deploying vnf-bd instance: id %s - request %s", instance_id, request)
        self.exit(outputs)
    
    def load_vnfbd(self, filename, inputs):
        logger.info("build vnf-bd filename %s", filename)
        vnfbd = VNFBD()       
        
        if vnfbd.load(filename, inputs=inputs):
            vnfbd_id = vnfbd.get_id()
        
            if vnfbd_id in self._vnfbds:
                logger.info("fail loaded vnf-bd instance %s - already in place/execution", vnfbd_id)
                return None
            else:
                vnfbd.multiplex_parameters(inputs)
                self._vnfbds[vnfbd_id] = vnfbd
                vnfpp = VNFPP()
                vnfpp.set_id(vnfbd_id)
                vnfpp.parse_inputs(vnfbd.get_inputs())
                self._vnfpps[vnfpp.get_id()] = vnfpp
                self._vnfbd_vnfpp[vnfbd_id] = vnfpp.get_id() 
                logger.info("loaded vnf-bd instance id %s, and respective vnfpp created", vnfbd_id)
                return vnfbd
       
        else:
            logger.info("vnf-bd not loaded %s", filename)
            return None
       
    def instantiate(self, vnfbd):
        vnfbd_instance_inputs = vnfbd.next_input()
        vnfbd_instance = VNFBD()
        vnfbd_instance.load(vnfbd.filename(), inputs=vnfbd_instance_inputs)
        vnfbd_instance.set_id(vnfbd_instance_inputs.get("id"))
        vnfbd_instance.set_test_id(vnfbd_instance_inputs.get("test"))
        self.register_vnfbd_instance(vnfbd, vnfbd_instance)
        self.current_vnfbd_instance = vnfbd_instance
        return vnfbd_instance

    def check(self, vnfbd):
        if vnfbd.has_next_input():
            vnfbd_instance = self.instantiate(vnfbd)

            if vnfbd.environment_deploy():            
                logger.info("deploying vnf-bd")
                self.deploy(vnfbd_instance, "start")                
            else:
                logger.info("deploying vnf-bd")
                self.task(vnfbd_instance)
        else:
            logger.info("no more tests for vnf-bd: id %s", vnfbd.get_id())
            self.finish(vnfbd)

    def init(self, layout):
        vnfbd_layout = layout.get("vnf_bd")
        vnfbd_id = vnfbd_layout.get('id')
        vnfbd_inputs = vnfbd_layout.get('inputs', {})
        logger.info('starting vnf-bd: id %s', vnfbd_id)

        if vnfbd_id in self._vnfbd_db:
            filename = self._vnfbd_db[vnfbd_id]
            vnfbd = self.load_vnfbd(filename, vnfbd_inputs)

            if vnfbd:
                logger.debug("starting vnf-bd: %s", vnfbd.to_json())
                self._vnfbd_layout[vnfbd_id] = layout
                self.check(vnfbd)
            else:
                logger.debug("processing layout ended for vnf-bd: id %s", vnfbd_id)

        else:
            logger.debug("vnf-bd id not registered in db %s", self._vnfbd_db.keys())

    def ack(self, built):
        self.current_vnfbd_instance.ack_deploy()
        proceedings = self.current_vnfbd_instance.get("proceedings")

        if proceedings.get("agents"):
            agents = [ agent.get("host").get("node") for agent in proceedings.get("agents") ]
        else:
            agents = []

        if proceedings.get("monitors"):
            monitors = [ monitor.get("host").get("node") for monitor in proceedings.get("monitors") ] 
        else:
            monitors = []
        
        if proceedings.get("managers"):
            managers = [ manager.get("host").get("node") for manager in proceedings.get("managers") ] 
        else:
            managers = []

        ack_info = built.get("info")
        for host,info in ack_info.items():
            if host in agents:
                info["role"] = "agent"
            if host in monitors:
                info["role"] = "monitor"
            if host in managers:
                info["role"] = "manager"

        return built

    def follow(self):
        if self.current_vnfbd_instance:
            self.current_vnfbd_instance.ack_info()
            self.task(self.current_vnfbd_instance)


class Greets:
    def __init__(self):
        self.event = None
    
    def frmt_contact(self, address, contact_type):
        address_map = {
            'monitor': "http://{0}:8987",
            'agent': "http://{0}:8988",
            'manager': "http://{0}:8989"
        }
        contact_str = address_map.get(contact_type, None)
        if contact_str:
            contact_str = contact_str.format(address)
        return contact_str

    def frmt_greetings(self, contacts):
        greets = {}
        mngr = contacts.get("manager", [])
        if mngr:
            mngr = mngr.pop()        
            subcontacts = contacts.get("agent") + contacts.get("monitor")
            greets = [ {'address': mngr, "contacts": subcontacts} ]            
        return greets

    def check_component_type(self, component_type):
        gym_types = ["manager", "monitor", "agent"]
        
        if type(component_type) is list:
            has_type = [c for c in component_type if c in gym_types]
            if has_type:
                component_type = has_type.pop()
                return component_type
        else:
            if component_type in gym_types:
                return component_type
        return None

    def make(self, ack):
        contacts = {"manager": [], "agent": [], "monitor": []}
        info = ack.get("info")
        
        for _, component in info.items():
            component_type = component.get("role")
            component_type = self.check_component_type(component_type)
            if component_type:
                component_address = component.get("ip")
                contact = self.frmt_contact(component_address, component_type)
                if component_type in contacts:
                    contacts[component_type].append(contact)   
        
        greets = self.frmt_greetings(contacts)
        if greets:
            logger.debug("greetings after info - %s", greets)
            self.event = {'contacts': greets}
            return self.event
        else:
            logger.debug("greetings could not load manager contact")
            return None


class Player(Controller):
    def __init__(self, info, in_q, out_q):
        Controller.__init__(self, "player", in_q, out_q, info)
        self.greets = Greets()
        self.storage = Storage()
        self.state = "available"
        
    def update_info(self):
        logger.debug('updating peers info')
        managers = self.peers.get_by('role', 'manager', all=True)
        mgrs = [peer.info() for peer in managers]
        # logger.debug(mgrs)
        try:
            self.assistants.fill_members(mgrs)      
        except Exception as e:
            logger.debug(e)
        finally:
            self.follow()
        
    def built(self, msg):
        logger.info("handling built message")
        logger.debug("%s", msg.to_json())
        
        self.peers.clear()
        self.assistants.clear()
        logger.info("player identities and assistants clear")

        built_ack = msg.get("ack")
        if built_ack.get("running"):
            logger.info("ack vnf-bd execution - deploy scenario started")           
            ack = self.ack(built_ack)
            event = self.greets.make(ack)
            if event:
                self.greetings(event)
            else:
                logger.info("finishing vnf-bd execution - no greetings possible")
                self.end_layout()
        else:
            logger.info("finished vnf-bd execution - deploy scenario stopped")

    def layout(self, layout):
        logger.info("handling layout message")
        logger.debug(layout.to_json())
        if self.state == "available":
            self.state = "busy"
            self.init(layout)
        else:
            logger.info("Layout not processed - vnf-bd in execution")

    def report(self, report):
        logger.info("handling report message")
        logger.debug(report.to_json())
        self.digest(report)

    @set_ev_handler(EventResult)
    def result(self, ev):
        logger.info("output vnf-br")        
        result = ev.result
        layout = result.get("layout")
        callback = layout.get("callback")
        result.set_id(layout.get_id())
        result.to(callback, prefix=layout.get_prefix())
        outputs = [result]
        self.exit(outputs)
        self.storage.store(result)
        logger.info("ended vnf-bd execution")
        self.state = "available"
        # self.queued()

    def status(self):
        logger.debug('status')
        self.environment()
        return self.identity.to_json()

    def _profile(self):
        managers = self.peers.get_by('role', 'manager', all=True)
        mgrs = [peer.info() for peer in managers]
        profile = {
            'managers': mgrs,
        }
        return profile

    def _handle(self, msg):
        what = msg.get_type()
        if what == 'built':
            self.built(msg)
        elif what == 'layout':
            self.layout(msg)
        elif what == 'report':
            self.report(msg)
        else:
            logger.info("unknown msg-type %s", what)
       
