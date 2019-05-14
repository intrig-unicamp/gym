import logging
from collections import namedtuple
from gym.common.temporal import Scheduler

logger = logging.getLogger(__name__)


class Mailing(Scheduler):
    def __init__(self):
        Scheduler.__init__(self)
        self.msg = namedtuple('msg', 'prefix data waiting ack')
        self.msgs = {}

    def create_msg(self, prefix):
        msg = self.msg(prefix=prefix, data={}, waiting={}, ack={})
        return msg

    def add_recvd(self, data, prefix):
        _id = data.get_id()
        msg = self.create_msg(prefix)
        msg.data[_id] = data
        self.msgs[_id] = msg

    def add_ack(self, data, prefix):
        msg_id = self.get_ack_id(data, prefix)
        data_id = data.get_id()
        if msg_id:
            msg = self.msgs[msg_id]
            msg.ack[(prefix,data_id)] = data
            self.msgs[msg_id] = msg
            logger.debug('msg %s added ack %s', msg_id, data_id)
            return True
        logger.debug('msg %s NOT added ack', data_id)
        return False

    def add_waiting(self, msg_id, data, prefix):
        data_id = data.get_id()
        if msg_id in self.msgs:
            msg = self.msgs[msg_id]
            msg.waiting[(prefix,data_id)] = data
            self.msgs[msg_id] = msg
            logger.debug('msg %s added waiting %s', msg_id, data_id)
            return True
        logger.debug('msg %s NOT added waiting', data_id)
        return False

    def get_ack_id(self, data, prefix):
        data_id = data.get_id()
        for msg_id in self.msgs.keys():
            msg = self.msgs[msg_id]
            if (prefix,data_id) in msg.waiting.keys():
                logger.debug('msg_id %s is in waiting of msg', msg_id)
                return msg_id
        logger.debug('msg_id %s is NOT in waiting of any msg', data.get_id())
        return None

    def check(self, msg_id):
        if msg_id in self.msgs.keys():
            msg = self.msgs[msg_id]
            sents = msg.waiting.keys()
            recvds = msg.ack.keys()
            if len(sents) == len(recvds):
                sents.sort()
                recvds.sort()
                ids = zip(sents, recvds)
                return all([True if _id[0] == _id[-1] else False for _id in ids])
        return False

    def get_acks(self, data, prefix):
        msg_id = self.get_ack_id(data, prefix)
        if msg_id:
            logger.debug('msg %s has ack waiting', msg_id)
            if self.check(msg_id):
                logger.debug('msg %s has all acks == waiting', msg_id)
                msg = self.msgs[msg_id]
                acks = msg.ack.values()
                msg_data = msg.data[msg_id]
                return msg_data, acks
            else:
                logger.debug('msg %s does not have all acks == waiting', msg_id)
        return None

    def acks(self, data, prefix):
        msg_id = self.get_ack_id(data, prefix)
        if msg_id:
            msg = self.msgs[msg_id]
            acks = msg.ack.keys()
            waitings = msg.waiting.keys()
            return (waitings, acks)
        return []

    def get_prefix(self, msg_id):
        if msg_id in self.msgs.keys():
            msg = self.msgs[msg_id]
            return msg.prefix
        return None

    def clear_recvd(self, data):
        data_id = data.get_id()
        if data_id in self.msgs.keys():
            del self.msgs[data_id]

    def input(self, frame):
        logger.debug("input_mail")
        msg = frame.get('input')
        prefix = frame.get('prefix')
        acks = False
        if msg.reply():
            logger.debug("add_ack %s", msg.get_id())
            self.add_ack(msg, prefix)
            logger.debug("acks so far %s", self.acks(msg, prefix))
            if self.get_acks(msg, prefix):
                acks = True
        else:
            logger.debug("add_recvd %s", msg.get_id())
            self.add_recvd(msg, prefix)
        return acks

    def get_reply(self, frame):
        msg = frame.get('input')
        prefix = frame.get('prefix')
        entrypoint_id = self.get_ack_id(msg, prefix)
        acks = self.get_acks(msg, prefix)
        self.clear_batch(entrypoint_id)
        return acks

    def output(self, frame, outputs):
        logger.debug("output_mail")
        entry_id = frame.get('id')
        if not self.has_entry(entry_id):
            model = outputs.get('model')
            if model is 'parallel':
                dispatches = self.out_parallel(frame, outputs)
            elif model is 'serial':
                dispatches = self.out_serial(frame, outputs)
            else:
                dispatches = []
                logger.debug("unkown outputs model %s", model)
        else:
            dispatches = outputs
        return dispatches

    def out_parallel(self, frame, outputs):
        dispatches = []
        messages = outputs.get('messages')
        reply = outputs.get('reply')
        for output_pack in messages:
            (prefix, output) = output_pack
            msg_id = frame.get('id')
            if reply:
                # output.set('id', msg_id)
                msg_prefix = self.get_prefix(output.get_id())
                logger.debug("clear_recvd %s - output reply %s", msg_id, output.get_id())
                self.clear_recvd(output)
                dispatches.append((msg_prefix, output))
            else:
                logger.debug("add_waiting %s - output %s", msg_id, output.get_id())
                self.add_waiting(msg_id, output, prefix)
                dispatches.append((prefix, output))
        return dispatches

    def out_serial(self, frame, outputs):
        dispatches = []
        messages = outputs.get('messages')
        reply = outputs.get('reply')
        messages.reverse()
        for output_pack in messages:
            (prefix, output) = output_pack
            if reply:
                self.clear_recvd(output)
            else:
                msg_id = frame.get('id')
                self.add_waiting(msg_id, output, prefix)
        output_initial = messages[0]
        (prefix_initial, output_initial) = output_initial
        dispatches.append((prefix_initial, output_initial))
        self.enqueue(frame, messages)
        return dispatches

    def has_next(self, frame):
        msg = frame.get('input')
        prefix = frame.get('prefix')
        entrypoint_id = self.get_ack_id(msg, prefix)
        if self.has_entry(entrypoint_id):
            if not self.is_finished(entrypoint_id):
                return True
        return False

    def get_next_outputs(self, frame):
        outputs = []
        msg = frame.get('input')
        prefix = frame.get('prefix')
        entrypoint_id = self.get_ack_id(msg, prefix)
        next_msg = self.get_next(entrypoint_id, msg)
        frame.set('id', entrypoint_id)
        logger.info('next_msg %s', next_msg)
        outputs.append(next_msg)
        return outputs
