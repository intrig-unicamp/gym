class EventBase(object):
    def __init__(self):
        super(EventBase, self).__init__()
        self.name = self.__class__.__name__

class EventMsg(EventBase):
    def __init__(self, msg):
        super(EventMsg, self).__init__()
        self.msg = msg

class EventInfo(EventBase):
    def __init__(self, msg):
        super(EventInfo, self).__init__()
        self.msg = msg

class EventGreetings(EventBase):
    def __init__(self, msg, hello=None):
        super(EventGreetings, self).__init__()
        self.msg = msg
        self.hello = hello
        
class EventTasks(EventBase):
    def __init__(self, vnfbd):
        super(EventTasks, self).__init__()
        self.vnfbd = vnfbd

class EventBR(EventBase):
    def __init__(self, layout, vnfbr):
        super(EventBR, self).__init__()
        self.layout = layout
        self.vnfbr = vnfbr

class EventVNFPP(EventBase):
    def __init__(self, vnfpp):
        super(EventVNFPP, self).__init__()
        self.vnfpp = vnfpp
