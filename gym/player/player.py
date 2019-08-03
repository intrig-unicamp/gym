import os
import logging
logger = logging.getLogger(__name__)

from gym.common.entity import Component, set_ev_handler
from gym.common.messages import Report, Task, Deploy, Built, VNFBR
from gym.player.vnfbd import VNFBD
from gym.player.vnfpp import VNFPP
from gym.common.events import EventTasks, EventInfo, EventGreetings, EventVNFPP, EventBR

from gym.common.process import Loader
from gym.player.store import Storage


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
        self._load_vnfdbs()

    def _update_path(self):
        _filepath = os.path.normpath(os.path.join(
            os.path.dirname(__file__),
            self._etc_folder))
        return _filepath

    def _load_vnfdbs(self):
        _path = self._update_path()
        logger.debug('Load vnfdbs - path %s', _path)
        files = self._loader.load_files(_path, 'vnf-bd-')
        logger.debug("vnfbd files %s", files)
        for filename in files:
            # vnfbd = VNFBD()
            logger.debug("vnfbd loading %s", filename)
            _id = filename.split('-')[-1].split('.')[0]          
            # if vnfbd.load(filename):
            #     _id = vnfbd.get('id')
            self._vnfbd_db[_id] = filename
            # else:
            #     logger.debug("could not load vnfbd %s", filename)
        logger.info("vnfbds ids loaded %s", list(self._vnfbd_db.keys()))
        logger.debug("vnfbds loaded %s", list(self._vnfbd_db.items()))

    def clear_instances(self, vnfbd):
        vnfbd_id = vnfbd.get_id()
        vnfpp_id = self._vnfbd_vnfpp.get(vnfbd_id)
        
        del self._vnfbd_layout[vnfbd_id]
        del self._vnfbds[vnfbd_id]
        del self._vnfbd_vnfpp[vnfbd_id]
        del self._vnfpps[vnfpp_id]

    def build_vnfbr(self, vnfbd, vnfpp):
        logger.info("build_vnfbr")
        vnfbr = VNFBR()
        vnfbr.set("vnfbd", vnfbd)
        vnfbr.set("vnfpp", vnfpp)
        vnfpp_id = vnfpp.get_id()
        vnfbd_id = vnfbd.get_id()
        layout = self._vnfbd_layout.get(vnfbd_id)
        self.send_event(EventBR(layout, vnfbr))
        self.clear_instances(vnfbd)

    def build_vnfpp(self, vnfbd):
        logger.info("build_vnfpp")
        self.check_orchestration(vnfbd)        
        self.unregister_vnfbd_instance(vnfbd)
        vnfbd_id = vnfbd.get_id()
        vnfpp_id = self._vnfbd_vnfpp.get(vnfbd_id)
        vnfpp = self._vnfpps.get(vnfpp_id)
        layout = self._vnfbd_layout.get(vnfbd_id)
        layout_id = layout.get_id()
        vnfpp.compile(layout_id=layout_id)
        self.build_vnfbr(vnfbd, vnfpp)

    def digest(self, report):
        logger.info("digest report")
        report_id = report.get_id()
        #Get report_id has the same id as vnfbd_instance derived from vnfbd_id (self._vnfbd_ids stores such mapping)
        vnfbd_id = self._vnfbd_ids.get(report_id, None)
        if vnfbd_id:
            logger.info("Digest report from vnfbd_instance_id %s instance of %s", report_id, vnfbd_id)
            vnfpp_id = self._vnfbd_vnfpp.get(vnfbd_id)
            vnfpp = self._vnfpps.get(vnfpp_id)
            vnfbd = self._vnfbds.get(vnfbd_id)
            vnfbd_instance = self.get_vnfbd_instance(vnfbd)
            vnfpp.add_report(vnfbd_instance, report)
            # vnfbd = self._vnfbds.get(vnfbd_id)
            self.process_vnfbd(vnfbd) 
            return True          
        else:
            logger.info("could not find associated vnfbd for vnfbd_instance_id %s", report_id)
            return False

    def task(self, vnfbd_instance, manager_id, manager_components):
        task_id = vnfbd_instance.get_id()
        logger.info("task for vnfdb instance %s", task_id)
        task = Task(id=task_id)

        vnfbd_procs = vnfbd_instance.get_procedures()
        trials = vnfbd_procs.get("repeat").get("trials", 0)
        test_id = vnfbd_instance.get_test_id()
        task.set("trials", trials)
        task.set("test", test_id)
        logger.debug("Trials %s", trials)

        agents = manager_components.get("agents", {})
        for agent_id, probers in agents.items():        
            task.add_agent(agent_id, probers)

        monitors = manager_components.get("monitors", {})
        for monitor_id, listeners in monitors.items():        
            task.add_monitor(monitor_id, listeners)

        logger.info("addressing task")
        peer = self.peers.get_by("uuid", manager_id)
        task.to(peer.get_address(), prefix=peer.get_prefix())
        return task

    def build_task(self, vnfbd):
        logger.info("build_task")
        tasks_structure = self.assistants.satisfy_structure(vnfbd)
        if tasks_structure:
            manager_id, manager_components = tasks_structure
            task = self.task(vnfbd, manager_id, manager_components)
            logger.debug(task.to_json())
            outputs = [task]
            self.exit(outputs)
        else:
            logger.debug("tasks_structure not built %s", tasks_structure)

    def check_orchestration(self, vnfbd):
        logger.info("check_orchestration")
        vnfbd_instance = self.get_vnfbd_instance(vnfbd)
        if vnfbd_instance:
            if vnfbd_instance.deployed():
                vnfbd_instance_callback = self.identity.get('url')
                outputs = self.build_deploy(vnfbd_instance, vnfbd_instance_callback, "stop", continuous_deploy=False)
                self.exit(outputs)

    def build_deploy(self, vnfbd_instance, vnfbd_instance_callback, vnfbd_request, continuous_deploy=True):
        vnfbd_instance_id = vnfbd_instance.get_id() 
        entrypoint, vnfbd_instance_deployment = vnfbd_instance.get_deployment()
        deploy = Deploy()
        deploy.set("scenario", vnfbd_instance_deployment)
        deploy.set("callback", vnfbd_instance_callback)
        deploy.set("request", vnfbd_request)
        deploy.set("instance", vnfbd_instance_id)
        deploy.set("continuous", continuous_deploy)
        deploy.to(entrypoint, prefix=vnfbd_instance_id)
        outputs = [deploy]
        
        if vnfbd_request == "start":
            self.schedule_event(EventInfo, EventTasks(vnfbd_instance))
            logger.info("Deploy START of VNFBD instance %s created - Scheduled Tasks", vnfbd_instance_id)
        if vnfbd_request == "stop":
            logger.info("Deploy STOP of VNFBD instance %s created", vnfbd_instance_id)
        return outputs 

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

    def build_orchestration(self, vnfbd):
        logger.info("vnfbd_orchestration")
        outputs = []
        vnfbd_instance_inputs = vnfbd.next_input()
        vnfbd_instance = VNFBD()
        vnfbd_instance.load(vnfbd.filename(), inputs=vnfbd_instance_inputs)
        vnfbd_instance.set_id(vnfbd_instance_inputs.get("id"))
        vnfbd_instance.set_test_id(vnfbd_instance_inputs.get("test_id"))
        self.register_vnfbd_instance(vnfbd, vnfbd_instance)
        vnfbd_instance_callback = self.identity.get('url')
        outputs = self.build_deploy(vnfbd_instance, vnfbd_instance_callback, "start")
        return outputs
    
    def build_vnfbd(self, filename, inputs):
        vnfbd = VNFBD()
        logger.info("build vnfbd %s", filename)
        if vnfbd.load(filename, inputs=inputs):
            vnfbd_id = vnfbd.get_id()
            if vnfbd_id in self._vnfbds:
                logger.info("fail loaded vnfbd instance %s - already in place/execution", vnfbd_id)
                return None
            else:
                vnfbd.multiplex_parameters(inputs)
                self._vnfbds[vnfbd_id] = vnfbd
                vnfpp = VNFPP()
                vnfpp.set_id(vnfbd_id)
                vnfpp.parse_inputs(vnfbd.get_inputs())
                self._vnfpps[vnfpp.get_id()] = vnfpp
                self._vnfbd_vnfpp[vnfbd_id] = vnfpp.get_id() 
                logger.info("loaded vnfbd instance %s and respective vnfpp created", vnfbd_id)
                logger.debug(vnfbd.to_json())
                return vnfbd
        
    def process_vnfbd(self, vnfbd):
        logger.debug("process_vnfbd")
        outputs = []
        if vnfbd.requires_orchestration():
            if vnfbd.has_next_input():
                outputs = self.build_orchestration(vnfbd)
                self.exit(outputs)
            else:
                logger.info("No more deploys for VNFBD %s", vnfbd.get_id())
                self.build_vnfpp(vnfbd)
        else:
            if vnfbd.has_next_input():
                vnfbd_instance_inputs = vnfbd.next_input()
                vnfbd_instance = VNFBD()
                vnfbd_instance.load(vnfbd.filename(), inputs=vnfbd_instance_inputs)
                vnfbd_instance.set_id(vnfbd_instance_inputs.get("id"))
                vnfbd_instance.set_test_id(vnfbd_instance_inputs.get("test_id"))
                self.register_vnfbd_instance(vnfbd, vnfbd_instance)
                self.build_task(vnfbd_instance)
            else:
                logger.info("No more inputs for VNFBD %s", vnfbd.get_id())
                self.build_vnfpp(vnfbd)

    def init_layout(self, layout):
        logger.info("init_layout")
        vnfbd_layout = layout.get("vnf_bd")
        vnfbd_id = vnfbd_layout.get('id')
        vnfbd_inputs = vnfbd_layout.get('inputs', {})
        logger.debug('VNF-BD: id %s - inputs %s', vnfbd_id, vnfbd_inputs)
        if vnfbd_id in self._vnfbd_db:
            filename = self._vnfbd_db[vnfbd_id]
            vnfbd = self.build_vnfbd(filename, vnfbd_inputs)
            if vnfbd:
                self._vnfbd_layout[vnfbd_id] = layout
                self.process_vnfbd(vnfbd)
                return True
        else:
            logger.debug("vnfbd id not in db %s", self._vnfbd_db.keys())
        return False


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
        deploy = ack.get("deploy")
        
        for _, component in deploy.items():
            component_type = component.get("type")
            component_type = self.check_component_type(component_type)
            if component_type:
                component_address = component.get("management").get("ip")
                contact = self.frmt_contact(component_address, component_type)
                if component_type in contacts:
                    contacts[component_type].append(contact)   
        greets = self.frmt_greetings(contacts)
        logger.debug("greetings after info - %s", greets)
        self.event = {'contacts': greets}
        return self.event


class Player(Controller):
    def __init__(self, info, in_q, out_q):
        Controller.__init__(self, "player", in_q, out_q, info)
        self.greets = Greets()
        self.storage = Storage()
        
    def update_info(self):
        logger.debug('update_info')
        managers = self.peers.get_by('role', 'manager', all=True)
        mgrs = [peer.info() for peer in managers]
        logger.debug(mgrs)
        try:
            self.assistants.fill_members(mgrs)      
        except Exception as e:
            logger.debug(e)

    def built(self, msg):
        logger.info("build msg received %s", msg.to_json())
        ack = msg.get("ack")
        self.peers.clear()
        self.assistants.clear()
        logger.info("Identities and Assistants clear")

        if ack.get("running"):
            logger.info("Deploy Built running - making greetings")
            event = self.greets.make(ack)
            self.send_event(EventGreetings(event))
        else:
            logger.info("Deploy Built NOT running")
            logger.info("Finished vnfbd execution")

    def layout(self, layout):
        logger.info('layout')
        ack = self.init_layout(layout)
        logger.info("layout Processing Ack: %s", ack)

    def report(self, report):
        logger.info('report')
        logger.debug(report.to_json())
        ack = self.digest(report)
        logger.info("report digest %s", ack)

    @set_ev_handler(EventBR)
    def vnfbr(self, ev):
        logger.info("vnfbr")
        layout = ev.layout
        vnfbr = ev.vnfbr
        logger.debug(vnfbr.to_json())
        callback = layout.get("callback")
        vnfbr.set_id(layout.get_id())
        vnfbr.to(callback, prefix=layout.get_prefix())
        outputs = [vnfbr]
        self.exit(outputs)
        self.storage.store(vnfbr)
        logger.info("Finished vnfbd execution")

    @set_ev_handler(EventTasks)
    def vnfbd_tasks(self, ev):
        vnfbd = ev.vnfbd
        vnfbd.ack_deploy()
        self.build_task(vnfbd)

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
       
