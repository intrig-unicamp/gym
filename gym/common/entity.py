import logging
import asyncio

from gym.common.profiler.profiler import Profiler
from gym.common.identity import Peers, Identity
from gym.common.mailing import Mailing
from gym.common.messages import Message, rpc_map, Hello, Info
from gym.common.events import EventBase, EventGreetings, EventMsg


logger = logging.getLogger(__name__)


def set_ev_handler(ev_cls, dispatchers=None):
    def _set_ev_cls_dec(handler):
        if 'callers' not in dir(handler):
            handler.callers = {}
        
        if not isinstance(ev_cls, list):
            ev_cls_list = [ev_cls]
        else:
            ev_cls_list = ev_cls

        for e in ev_cls_list:
            handler.callers[e] = [dispatchers]
        return handler
    return _set_ev_cls_dec


class Messenger():
    def __init__(self, in_q, out_q):
        self.in_q = in_q
        self.out_q = out_q
        self.event_handlers = {}
        self._scheduled_ids = 900
        self._agenda = {}
        self._waiting = {}
        self._finished = {}
        self._in_mapping_out = {}

    def schedule_event(self, trigger, event):
        assert(issubclass(trigger, EventBase))
        assert(isinstance(event, EventBase))
        
        sched_id = self._scheduled_ids
        self._agenda[sched_id] = {
            'trigger': trigger,
            'event': event
        }
        self._scheduled_ids += 1
        trigger_name = trigger.name if isinstance(trigger, EventBase) else trigger.__name__
        logger.debug("Event %s scheduled for %s", event.name, trigger_name)

    def check_agenda(self, trigger):
        events = []
        sched_events = []
        if isinstance(trigger, EventBase):
            events = [ ev_id for (ev_id,ev) in self._agenda.items() if trigger.name == ev.get("trigger").__name__ ] 
        elif issubclass(trigger, EventBase):
            events = [ ev_id for (ev_id,ev) in self._agenda.items() if trigger.__name__ == ev.get("trigger").__name__ ] 

        for ev_id in events:
            ev = self._agenda.get(ev_id)
            sched_events.append(ev)
            del self._agenda[ev_id]
        return sched_events

    def sched_mapping(self, input, outputs):
        input_id = (input.get_prefix(), input.get_id()) 
        logger.debug("sched_mapping input_id %s", input_id)
        if input_id not in self._waiting:
            self._waiting[input_id] = input
        self.set_mapping(input_id, outputs)

    def set_mapping(self, input_id, outputs):
        if input_id in self._waiting:
            self._in_mapping_out[input_id] = {'wait': {}, 'ack': {}}
            for output in outputs:
                output_id = (output.get_prefix(), output.get_id())
                self._in_mapping_out[input_id]['wait'][output_id] = output

    def get_input_id(self, reply):
        reply_id = (reply.get_prefix(), reply.get_id())
        input_ids = list(self._in_mapping_out.keys())
        for input_id in input_ids:
            wait_ids = list(self._in_mapping_out[input_id]['wait'].keys())
            ack_ids = list(self._in_mapping_out[input_id]['ack'].keys())
            if reply_id in wait_ids or reply_id in ack_ids:
                return input_id
        return None       

    def ack_reply(self, reply):
        input_id = self.get_input_id(reply)
        if input_id:
            reply_id = (reply.get_prefix(), reply.get_id())
            self._in_mapping_out[input_id]['ack'][reply_id] = reply
            return True                
        return False

    def check_all_acks(self, reply):
        input_id = self.get_input_id(reply)
        if input_id:
            wait_ids = list(self._in_mapping_out[input_id]['wait'].keys())
            ack_ids = list(self._in_mapping_out[input_id]['ack'].keys())
            if len(wait_ids) == len(ack_ids):
                wait_ids.sort()
                ack_ids.sort()
                ids = zip(wait_ids, ack_ids)
                logger.debug("all ids %s", ids)
                ack_all = all([True if _id[0] == _id[-1] else False for _id in ids])
                logger.debug("ack_all %s", ack_all)
                return ack_all

    def get_acks(self, input_id):
        acks = self._in_mapping_out[input_id]['ack'].values()
        return acks

    def clear_mapping(self, input_id):
        del self._waiting[input_id]
        del self._in_mapping_out[input_id]

    def get_input(self, input_id):
        input = self._waiting.get(input_id, None)
        return input

    def send_event(self, ev):
        self.in_q.put_nowait(ev)

    def exit(self, outputs):
        if outputs:
            logger.debug("Exiting outputs %s", outputs)         
            self.out_q.put_nowait(outputs)
        else:
            logger.debug("Nothing to exit as outputs")         

    def register_handler(self, ev_cls, handler):
        assert callable(handler)
        self.event_handlers.setdefault(ev_cls, [])
        self.event_handlers[ev_cls].append(handler)
        logger.debug("Event handler registered: ev %s, handler %s",
                        ev_cls, handler.__name__)

    def unregister_handler(self, ev_cls, handler):
        assert callable(handler)
        self.event_handlers[ev_cls].remove(handler)
        if not self.event_handlers[ev_cls]:
            del self.event_handlers[ev_cls]

    def get_handlers(self, ev):
        ev_cls = ev.__class__
        handlers = self.event_handlers.get(ev_cls, [])
        # if state is None:
        return handlers

    async def _event_loop(self):
        logger.debug("Event Loop Started")
        while True:
            try:
                ev = self.in_q.get_nowait()
            except asyncio.QueueEmpty:
                await asyncio.sleep(0.5)
                # continue
            else:
                logger.debug("event_loop got ev %s", ev)
                handlers = self.get_handlers(ev)
                if handlers:
                    for handler in handlers:
                        try:
                            logger.debug("event_loop handler %s", handler)
                            handler(ev)
                        except Exception as e:
                            logger.debug("Excenption on event_loop handler: %s", e)
                            logger.exception(e)
                            # Normal exit.
                            # Propagate upwards, so we leave the event loop.
                            raise
                        except:
                            logger.debug("event loop handler raised an exception")
                else:
                    scheduled_events = self.check_agenda(ev)
                    if scheduled_events:
                        logger.info("Scheduled triggers for event %s", ev.__name__)
                        for event in scheduled_events:
                            event_call = event.get("event")
                            logger.info("calling event %s", event_call.name)
                            self.send_event(event_call)


class Component(Messenger):
    def __init__(self, role, in_q, out_q, info):
        Messenger.__init__(self, in_q, out_q)
        self.peers = Peers()
        self.profiler = Profiler()
        self.identity = Identity(url=info.get("url"), uuid=info.get("id"), role=role)
        self.contacts = info.get("contacts", [])
        
    def get_jobs(self):
        inits, closes = [], []
        inits.append(self.start_background_tasks)
        closes.append(self.cleanup_background_tasks)
        return inits, closes

    async def start_background_tasks(self, app):
        app['greetings'] = app.loop.create_task(self.sched_greetings())
        app['event_loop'] = app.loop.create_task(self._event_loop())

    async def cleanup_background_tasks(self, app):
        app['event_loop'].cancel()
        await app['event_loop']

    def stamp_output(self, input, output):
        input_prefix = input.get_prefix()
        peer = self.peers.get_peer_by_prefix(input_prefix)
        if peer:
            peer_address = peer.get_address()
            output.to(peer_address)
        else:
            logger.debug("Could not stamp output - no peer found for prefix %s", input_prefix)

    def environment(self):
        logger.debug("Environment profile")
        profile = {}
        profile.update(self.profiler.profile())
        logger.debug(profile)
        environment = self._profile()
        if environment:
            profile.update(environment)
        self.identity.set('features', profile)
        return profile

    def _profile(self):
        return {}

    async def sched_greetings(self):
        await asyncio.sleep(1)
        if self.contacts:
            greets = {'contacts': self.contacts}
            logger.debug("Sched greetings to %s", greets)
            self.send_event(EventGreetings(greets))

    @set_ev_handler(EventGreetings)
    def greetings(self, ev):
        msg = ev.msg if hasattr(ev, "msg") else ev
        logger.info("making greetings - %s", msg)
        contacts = msg.get("contacts")
        if contacts:
            outputs = []
            for contact in contacts:
                if type(contact) is dict:
                    url = contact.get("address", None)
                    subcontacts = contact.get("contacts", [])
                else:
                    url = contact
                    subcontacts = []
                
                logger.info("greeting hello to %s", url)
                peer = self.peers.create(url)
                hello = Hello(
                    uuid=self.identity.get('uuid'),
                    prefix=peer.get("prefix"),
                    role=self.identity.get('role'),
                    url=self.identity.get('url'))

                if subcontacts:
                    greet_contacts = list(map(lambda contact: {"address": contact}, subcontacts))
                    hello.set("contacts", greet_contacts)

                hello.to(peer.get_address(), prefix=peer.get_prefix())
                logger.debug(hello.to_json())
                outputs.append(hello)
            
            if hasattr(ev, "hello"):
                if ev.hello:
                    self.sched_mapping(ev.hello, outputs)
            self.exit(outputs)

    @set_ev_handler(EventMsg)
    def handle(self, ev):
        msg = ev.msg
        what = msg.get_type()
        logger.debug("handle %s", what)
        if what == "hello":
            self.hello(msg)
        elif what == "info":
            self.info(msg)
        else:
            self._handle(msg)

    def _handle(self, msg):
        raise NotImplementedError

    def hello(self, msg):
        logger.info("hello")
        logger.debug(msg.to_json())
        outputs = []
        peer = self.peers.hello(msg)
        peer_contacts = msg.get("contacts")
        if peer_contacts:
            ev = {"contacts": peer_contacts}
            self.send_event(EventGreetings(ev, msg))
        else:
            info = self.create_info(peer, msg)
            outputs = [info]        
        self.exit(outputs)

    def create_info(self, peer, hello):
        info = Info(id=hello.get('id'))
        fields = ["uuid", "url", "role"]
        info.cfg(fields, self.identity)
        info.set('prefix', peer.get_prefix())
        features = self.environment()
        info.set('features', features)
        info.to(peer.get_address(), prefix=peer.get_prefix())
        logger.info("Info: msg-id %s, prefix %s", info.get_id(), info.get_prefix())
        logger.debug(info.to_json())
        return info

    def info(self, msg):
        logger.info("info")
        logger.debug(msg.to_json())
        if self.ack_reply(msg):
            if self.check_all_acks(msg):
                logger.debug('all hellos ack')
                input_id = self.get_input_id(msg)
                hello = self.get_input(input_id)
                rcvd_infos = self.get_acks(input_id)
                for rcvd_info in rcvd_infos:
                    self.ack_info(rcvd_info)
                
                input_prefix = hello.get_prefix()
                peer = self.peers.get_peer_by_prefix(input_prefix)
                info = self.create_info(peer, hello)
                self.stamp_output(hello, info)
                outputs = [info]
                self.clear_mapping(input_id)
                self.exit(outputs)
            else:
                logger.info("didn't received all infos yet")
        else:
            self.ack_info(msg)
        
    def ack_info(self, msg):
        ack = self.peers.info(msg)
        if ack:
            self.update_info()

    def update_info(self):
        pass