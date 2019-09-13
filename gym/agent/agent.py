import os
import logging
import json

from gym.common.process import Actuator
from gym.common.entity import Component
from gym.common.messages import Evaluation, Snapshot, Error

logger = logging.getLogger(__name__)


class Agent(Component):
    FILES = 'probers'
    FILES_PREFIX = 'prober_'
    FILES_SUFFIX = 'py'
    CLASS_PREFIX = 'Prober'

    def __init__(self, info, in_q, out_q):
        Component.__init__(self, "agent", in_q, out_q, info)
        self.actuator = Actuator()
        self.cfg_acts()
        logger.info("Agent Started: id %s - url %s", info.get("id"), info.get("url"))

    def cfg_acts(self):
        logger.info("Loading Probers")
        folder = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            Agent.FILES)

        cfg = {
            "folder": folder,
            "prefix": Agent.FILES_PREFIX,
            "sufix": Agent.FILES_SUFFIX,
            "full_path": True,
        }
        self.actuator.cfg(cfg)

    def origin(self):
        feats = self.identity.get('features')
        host = feats.get('environment').get('host')
        identity = self.identity.get('uuid')
        
        org = {
            "id": identity,
            "host": host,
            "role": "agent",
        }
        return org

    def snapshot(self, _id, evals):
        logger.info('Snapshot')
        snapshot = Snapshot(id=_id)
        origin = self.origin()
        snapshot.set('origin', origin)
        snapshot.set('evaluations', evals)
        logger.debug(snapshot.to_json())
        return snapshot

    def evaluations(self, evals):
        logger.info('Evaluations')
        evaluations = []
        for eval_id,(ack,runner_id,out) in evals.items():
            evaluation = Evaluation(id=eval_id)
            if ack:
                evaluation.set('source', out.get("source", None))
                evaluation.set('timestamp', out.get("timestamp", None))
                evaluation.set('metrics', out.get("metrics", None))
                # if type(out) is list:
                #     evaluation.set('series', True)
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
        snap.to(None, prefix=msg.get_prefix())
        self.stamp_output(msg, snap)
        outputs = [snap]
        self.exit(outputs)

    def _profile(self):
        logger.info("Agent Profile - Probers")
        probers = self.actuator.get_acts()
        logger.debug(probers)
        profile = {'probers': probers}
        return profile

    def _handle(self, msg):
        what = msg.get_type()
        if what == 'instruction':
            self.instruction(msg)
        else:
            logger.debug('unknown msg-type %s', what)
