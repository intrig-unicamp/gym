import logging
import json

from gym.common.entity import Component
from gym.common.messages import Action, Instruction, Report

logger = logging.getLogger(__name__)


class Tasks:
    def __init__(self):
        self._tasks = {}
        self._trials = {}

    def sched(self, task):
        task_id = task.get_id()
        if task_id not in self._tasks.keys():
            trials = task.get("trials")
            trials = int(trials) if trials else 0
            task_info = {
                "origin": task,
                "trials": trials,
                "acks": 0,
                "pack": []
            }
            self._tasks[task_id] = task_info
            logger.debug("Sched task trials: %s", trials)
            return True
        return False

    def ack(self, task, snaps):
        task_id = task.get_id()
        task_info = self._tasks.get(task_id, None)
        if task_info:
            task_info["acks"] += 1
            task_info["pack"].append(snaps)
            return True
        return False

    def next_trial(self, task):
        task_id = task.get_id()
        task_info = self._tasks.get(task_id, None)
        if task_info:
            if task_info["acks"] >= task_info["trials"]:
                return False
            else:
                return True
        return False

    def info(self, task):
        task_id = task.get_id()
        task_info = self._tasks.get(task_id, None)
        if task_info:
            return (task_info["acks"], task_info["trials"])

    def checkout(self, task):
        task_id = task.get_id()
        task_info = self._tasks.get(task_id, None)
        if task_info:
            pack = task_info.get("pack")
            origin = task_info.get("origin")
            del self._tasks[task_id]
            logger.debug("Task trials checkout - snaps pack len %s", len(pack))
            return (origin, pack)
        return None


class Manager(Component):
    def __init__(self, info, in_q, out_q):
        Component.__init__(self, "manager", in_q, out_q, info)
        self.tasks = Tasks()

    def check_ids(self, locals, requested):
        logger.debug("Verifying requested fit local components")
        local_ids = [identity.get('uuid') for identity in locals]
        req_ids = [req for req in requested.keys()]
        for req_id in req_ids:
            if req_id not in local_ids:
                logger.debug("Component ID requested %s not in locals %s", req_id, local_ids)
                return False
        logger.debug("All Component IDs requested match locals")
        return True

    def instructions(self, locals, requested, _type='agent'):
        logger.info("Instructions")
        instructions = []
        if self.check_ids(locals, requested):
            for req_id, req_tools in requested.items():
                identity = self.peers.get_by('uuid', str(req_id))
                identity_features = identity.get('features')
                runners = 'probers' if _type == 'agent' else 'listeners'
                identity_runners = identity_features[runners]
                inst = Instruction()
                # logger.info("Requested stimulus %s",info['stimulus'])
                # logger.info("identity_runners %s", identity_runners.keys())
                for stimulus in req_tools:
                    stm_id = str(stimulus['id'])
                    # stm_id = stimulus['id']
                    if stm_id in identity_runners.keys():
                        action = Action()
                        action.set('stimulus', stimulus)
                        inst.add_action(action)
                        # logger.debug('action added to instruction for stm_id %s', stm_id)
                        # logger.debug(action.to_json())
                    else:
                        logger.debug('stimulus of runner id %s not in component runners %s', stm_id, identity_runners)
                logger.debug(inst.to_json())
                peer = self.peers.get_by('uuid', str(req_id))
                inst.to(peer.get_address(), prefix=peer.get_prefix())
                instructions.append(inst)
            logger.info("Instructions built")
        else:
            logger.info("Could not build instructions")
        return instructions

    def task(self, msg):
        logger.info('Task')
        logger.debug(msg.to_json())
        outputs = []
        agents = self.peers.get_by('role', 'agent', all=True)
        monitors = self.peers.get_by('role', 'monitor', all=True)
        task_agents = msg.get('agents')
        task_monitors = msg.get('monitors')
        instruct_agents = []
        instruct_monitors = []
   
        if task_agents:
            instruct_agents = self.instructions(agents, task_agents, _type='agent')
            if instruct_agents:
                outputs.extend(instruct_agents)        
   
        if task_monitors:
            instruct_monitors = self.instructions(monitors, task_monitors, _type='monitor')
            if instruct_monitors:
                outputs.extend(instruct_monitors)
   
        if outputs:
            if self.tasks.sched(msg):
                logger.debug("New Task Trials - scheduled")
            else:
                logger.debug("Ongoing Task Trial - already scheduled")
            self.sched_mapping(msg, outputs)
        self.exit(outputs)

    def _process_snapshots(self, snaps):
        merge_snaps = []
        trial_id = 0
        for snap_pack in snaps:
            for snap in snap_pack:
                snap.set('trial', trial_id)
            
            merge_snaps.extend(snap_pack)
            trial_id += 1
        return merge_snaps

    def report(self, task, snaps):
        logger.info('Report')
        report = Report(id=task.get('id'))
        _snaps = self._process_snapshots(snaps)
        report.set('snapshots', _snaps)
        report.set('test', task.get('test'))
        logger.debug(report.to_json())  
        return report

    def task_status(self, task, snaps):
        logger.info("Task status:")
        ack = self.tasks.ack(task, snaps)
        if ack:
            has_next_trial = self.tasks.next_trial(task)
            if has_next_trial:
                trial, trials = self.tasks.info(task)
                logger.info("Next Trial: id %s - total %s", trial, trials)
                self.task(task)
            else:
                logger.info("All trials Ack")
                orig_task, snaps_pack = self.tasks.checkout(task)
                report = self.report(task, snaps_pack)
                self.stamp_output(orig_task, report)
                outputs = [report]
                self.exit(outputs)
        else:
            logger.info("Could not ack task trial - maybe not scheduled")

    def snapshot(self, snap):
        logger.info('Snapshot')
        logger.debug(snap.to_json())
        if self.ack_reply(snap):
            if self.check_all_acks(snap):
                logger.debug('All instructions ack')
                input_id = self.get_input_id(snap)
                task = self.get_input(input_id)
                snaps = self.get_acks(input_id)
                self.clear_mapping(input_id)
                self.task_status(task, snaps)
            else:
                logger.info("Not all snaps yet received")
        else:
            logger.info("Could not ack snap - check ids!")
        
    def status(self):
        logger.debug('status')
        self.environment()
        return self.identity.to_json()

    def _profile(self):
        agents = self.peers.get_by('role', 'agent', all=True)
        monitors = self.peers.get_by('role', 'monitor', all=True)
        profile = {
            'agents':agents,
            'monitors':monitors,
        }
        return profile

    def _handle(self, msg):
        what = msg.get_type()
        if what == 'task':
            self.task(msg)
        elif what == 'snapshot':
            self.snapshot(msg)
        else:
            logger.debug('unknown msg-type %s', what)