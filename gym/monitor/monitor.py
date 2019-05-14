import os
import logging

from gym.common.process import Actuator
from gym.common.entity import Component
from gym.common.messages import Evaluation, Snapshot, Error

logger = logging.getLogger(__name__)


class Monitor(Component):
    FILES = 'listeners'
    FILES_PREFIX = 'listener_'
    FILES_SUFFIX = 'py'
    CLASS_PREFIX = 'Listener'

    def __init__(self, info, in_q, out_q):
        Component.__init__(self, "monitor", in_q, out_q, info)
        self.actuator = Actuator()
        self.cfg_acts()
        logger.info("Monitor Started: id %s - url %s", info.get("id"), info.get("url"))

    def cfg_acts(self):
        logger.info("Loading Listeners")
        folder = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            Monitor.FILES)

        cfg = {
            "folder": folder,
            "prefix": Monitor.FILES_PREFIX,
            "sufix": Monitor.FILES_SUFFIX,
            "full_path": True,
        }
        self.actuator.cfg(cfg)

    def snapshot(self, _id, evals):
        logger.info('Snapshot')
        snapshot = Snapshot(id=_id)
        snapshot.set('evaluations', evals)
        feats = self.identity.get('features')
        host = feats.get('environment').get('host')
        identity = self.identity.get('identity')
        snapshot.set('host', host)
        snapshot.set('component', identity)
        snapshot.set('role', 'monitor')
        logger.debug(snapshot.to_json())
        return snapshot

    def evaluations(self, evals):
        logger.info('Evaluations')
        evaluations = []
        for eval_id, (ack, runner_id, out) in evals.items():
            evaluation = Evaluation(id=eval_id)
            if ack:
                evaluation.set('type', 'listener')
                evaluation.set('tool', runner_id)
                evaluation.set('metrics', out)
                if type(out) is list:
                    evaluation.set('series', True)
            else:
                error = Error(data=out)
                evaluation.set('error', error)
            evaluations.append(evaluation)
        return evaluations

    def instruction(self, msg):
        logger.info('Instruction')
        logger.debug(msg.to_json())
        evals = self.actuator.act(msg)
        evaluations = self.evaluations(evals)
        snap = self.snapshot(msg.get('id'), evaluations)
        self.stamp_output(msg, snap)
        outputs = [snap]
        self.exit(outputs)

    def _profile(self):
        logger.info("Monitor Profile - Listeners")
        listeners = self.actuator.get_acts()
        profile = {'listeners':listeners}
        return profile

    def _handle(self, msg):
        what = msg.get_type()
        if what == 'instruction':
            self.instruction(msg)
        else:
            logger.debug('unknown msg-type %s', what)

