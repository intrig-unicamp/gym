import random
import json
import logging
from datetime import datetime

from gym.common.info import Content
from gym.common.temporal import Time

logger = logging.getLogger(__name__)


class Message(Content):
    def __init__(self, id=None, request=True, reply=False, data=None):
        Content.__init__(self)
        self.id = self.create_msg_id() if not id else id
        self._request = request
        self._reply = reply
        self._from = None
        self._to = None
        self._prefix = None
        self._call = 'post'

    def call(self, call):
        self._call = call
    
    def get_call(self):
        return self._call

    def sender(self, address, prefix):
        self._from = address
        self._prefix = prefix

    def to(self, to, prefix=None):
        self._to = to
        if prefix:
            self._prefix = prefix

    def set_prefix(self, prefix):
        self._prefix = prefix

    def get_prefix(self):
        return self._prefix

    def get_from(self):
        return self._from

    def get_to(self):
        return self._to

    def get_id(self):
        return self.id

    def set_id(self, _id):
        self.id = _id

    def reply(self):
        return self._reply

    def create_msg_id(self):
        _id = random.randint(1, random.randint(1000, 10000))
        return str(_id)

    @classmethod
    def parse(cls, msg_json, rpc_map):
        obj = None
        try:
            json_ = json.loads(msg_json)            
        except ValueError as e:
            logger.warning("Invalid json msg %s", e) # invalid json
        else:
            if 'method' in json_.keys():
                if json_['method'] in rpc_map:
                    cls = rpc_map[json_['method']]
                    obj = cls._parse(msg_json, rpc_map)
            if 'response' in json_.keys():
                if json_['response'] in rpc_map:
                    cls = rpc_map[json_['response']]
                    obj = cls._parse(msg_json, rpc_map)
            if not obj:
                logger.info("Message cannot be parsed with rpc_map - content: %s", json_)
        return obj

    def default(self, o):
        if hasattr(o, 'to_json'):
            return json.loads(o.to_json())
        elif hasattr(o, 'items'):
            return o.items()
        else:
            return o.__dict__

    @classmethod
    def _parse(cls, msg, rpc_map=None):
        obj = cls.from_json(msg)
        if hasattr(obj, 'result'):
            _items = obj.result.items()
        elif hasattr(obj, 'params'):
            _items = obj.params.items()
        else:
            return obj
        for (k, v) in _items:
            k_temp = None
            if 's' == k[-1]:
                k_temp = k[:-1]
            if k in rpc_map:
                subobj = obj._parse_sub(obj, k, v, rpc_map)
                if subobj:
                    obj.set(k, subobj)
            elif k_temp in rpc_map:
                subobj = obj._parse_sub(obj, k_temp, v, rpc_map)
                if subobj:
                    obj.set(k, subobj)
            elif k in obj.keys():
                obj.set(k, v)
        return obj

    def _parse_sub(self, obj, k, v, rpc_map):
        vs = None
        sub_cls = rpc_map[k]
        if k in ['time', 'error']:
            vs = sub_cls._parse(json.dumps(v), rpc_map)
        else:
            if type(v) is list:
                vs = []
                for item in v:
                    if type(item) is dict:
                        o_act = sub_cls._parse(json.dumps(item), rpc_map)
                        vs.append(o_act)
                    elif type(item) is list:
                        vss = []
                        for i in item:
                            o_act = sub_cls._parse(json.dumps(i), rpc_map)
                            vss.append(o_act)
                        vs.append(vss)
            elif type(v) is dict:
                vs = {}
                for id_act, j_act in v.items():
                    o_act = sub_cls._parse(json.dumps(j_act), rpc_map)
                    vs[id_act] = o_act
            else:
                pass
        return vs

    def cfg(self, fields, contents):
        for field in fields:
            if field in contents.keys() and field in self.keys():
                self.set(field, contents.get(field))
             

class Request(Message):
    def __init__(self, method, id=None):
        Message.__init__(self, id=id, request=True)
        self.method = method
        self.params = {}
        self._keys = ['id', 'method', 'params']

    def get_type(self):
        return self.method

    def items(self, dic=True):
        self.params = self._set_params()
        return self._items(dic=dic, filter_keys=True)

    def _set_params(self):
        params = self._items(dic=True, filter_keys=False)
        for item in self._keys:
            del params[item]
        return params


class Hello(Request):
    def __init__(self, id=None, uuid=None, prefix=None, role=None, url=None):
        Request.__init__(self, id=id, method='hello')
        self.role = role
        self.uuid = uuid
        self.prefix = prefix
        self.url = url
        self.contacts = None


class Action(Request):
    def __init__(self):
        Request.__init__(self, 'action')
        self.stimulus = {}
        self.on_error = {
            "abort": True,
            "retry": 0,
        }


class Instruction(Request):
    def __init__(self):
        Request.__init__(self, 'instruction')
        self.actions = {}
        self.time = Time()

    def add_action(self, action):
        _id = action.get('id')
        if _id and _id not in self.actions:
            self.actions[_id] = action

    def rem_action(self, action):
        _id = action.get('id', 0)
        if _id and _id in self.actions:
            del self.actions[_id]


class Task(Request):
    def __init__(self, id=None):
        Request.__init__(self, method='task', id=id)
        self.agents = {}
        self.monitors = {}
        self.trials = 0
        self.test = 0
        self.time = Time()

    def add_agent(self, id, probers):
        self.agents[id] = probers

    def add_monitor(self, id, listeners):
        self.monitors[id] = listeners


class Layout(Request):
    def __init__(self):
        Request.__init__(self, method='layout')
        self._ids = 0
        self.vnf_bd = {}
        self.callback = None
        self.time = Time()


class Deploy(Request):
    def __init__(self):
        Request.__init__(self, method='deploy')
        self._ids = 0
        self.scenario = {}
        self.callback = None
        self.request = None
        self.continuous = False
        self.instance = None
        self.time = Time()


class Response(Message):
    def __init__(self, id, response='response'):
        Message.__init__(self, id, reply=True)
        self.timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        self.result = {}
        self.error = {}
        self._keys = ['id', 'result', 'response']
        self.response = response

    def get_type(self):
        return self.response

    def items(self, dic=True):
        self.result = self._set_result()
        return self._items(dic=dic, filter_keys=True)

    def _set_result(self):
        result = self._items(dic=True, filter_keys=False)
        for item in self._keys:
            del result[item]
        return result


class Info(Response):
    def __init__(self, id=0):
        Response.__init__(self, id, response='info')
        self.uuid = None
        self.prefix = None
        self.role = None
        self.url = None
        self.features = None


class Error(Content):
    def __init__(self, code=None, message=None, data=None):
        Content.__init__(self)
        self.code = code
        self.message = message
        self.data = data


class Evaluation(Response):
    def __init__(self, id=0):
        Response.__init__(self, id, response='evaluation')
        self.tool = None
        self.type = None
        self.series = False
        self.metrics = None


class Snapshot(Response):
    def __init__(self, id=0):
        Response.__init__(self, id, response='snapshot')
        self.host = None
        self.component = None
        self.role = None
        self.trial = 0
        self.evaluations = {}


class Report(Response):
    def __init__(self, id=0):
        Response.__init__(self, id, response='report')
        self.host = None
        self.component = None
        self.role = None
        self.test = 0
        self.snapshots = {}


class Built(Response):
    def __init__(self, id=0):
        Response.__init__(self, id, response='built')
        self.ack = {}


class VNFBR(Response):
    def __init__(self, id=0):
        Response.__init__(self, id, response='vnfbr')
        self.vnfbd = {}
        self.vnfpp = {}



rpc = {
    'hello':'info',
    'action':'evaluation',
    'instruction':'snapshot',
    'task':'report',
    'deploy':'built',
}

rpc_map = {
    'hello':Hello,
    'action':Action,
    'instruction':Instruction,
    'task':Task,
    'layout': Layout,
    'info':Info,
    'evaluation':Evaluation,
    'snapshot': Snapshot,
    'report': Report,
    'deploy': Deploy,
    'built': Built,
    'error': Error,
    'time': Time,
}