import logging
import random
import json

logger = logging.getLogger(__name__)


class Identity:
    def __init__(self, url, uuid=None, role=None):
        self.url = url
        self.uuid = uuid
        self.role = role
        self.address = None
        self.prefix = None
        self._ack = False
        self.features = {}
        self.create_prefix()
        
    def create_prefix(self):
        prefix = random.randint(100, 10000)
        self.prefix = str(prefix)
        self._set_address()
    
    def _set_address(self):
        url = self.url if self.url[-1] == '/' else self.url + '/'
        self.address = url + str(self.prefix)

    def _items(self, dic=False, _keys=None):
        _keys = self.__dict__.keys() if not _keys else _keys
        if dic:
            return dict([(i, self.__dict__[i]) for i in _keys if i[:1] != '_'])
        else:
            return [i for i in _keys if i[:1] != '_']

    def keys(self):
        return self._items(dic=False)

    def get_prefix(self):
        return self.prefix

    def set_prefix(self, prefix):
        self.prefix = prefix
        self._set_address()

    def get_address(self):
        return self.address

    def get_url(self):
        return self.url

    def get(self, param):
        if param in self._items():
            value = getattr(self, param, None)
            return value
        return None

    def set(self, param, value):
        if param in self._items():
            setattr(self, param, value)
            return True
        return False

    def is_ack(self, url):
        return self._ack

    def ack(self):
        self._ack = True

    def info(self):
        return self._items(dic=True)

    def to_json(self, _items=None):
        if _items and type(_items) == dict:
            pass
        else:
            _items = self._items(dic=True)
        return json.dumps(_items, default=lambda o: o.__dict__,
                          sort_keys=True, indent=4)

    def cfg(self, fields, contents):
        for field in fields:
            if field in contents.keys() and field in self.keys():
                self.set(field, contents.get(field))
        if self.prefix:
            self._set_address()


class Peers:
    def __init__(self):
        self.peers = {}
        self._peer_prefixes = {}

    def hello(self, msg):
        peer_url = msg.get("url")
        peer = self.create(peer_url)
        fields = ["uuid", "prefix", "role", "contacts"]
        peer.cfg(fields, msg)
        logger.info("Peer Hello: uuid %s - role %s - prefix %s - contacts %s",
                    peer.get("uuid"), peer.get("role"), peer.get("prefix"), peer.get("contacts"))
        self.add_peer(peer)
        return peer

    def info(self, msg):
        peer_url = msg.get("url")
        peer = self.get_peer(peer_url)
        if peer:
            fields = ["uuid", "role", "features"]
            peer.cfg(fields, msg)
            peer.set("ack", True)
            peer_prefix = msg.get("prefix")
            self.update_peer_prefix(peer, peer_prefix)
            logger.info("Peer Info: uuid %s - role %s - prefix %s",
                        peer.get("uuid"), peer.get("role"), peer.get("prefix"))
            return True
        return False        

    def add_peer(self, peer):
        self.check_peer_prefix(peer)
        self.peers[peer.get("url")] = peer
        logger.debug("Peer added")

    def create(self, url):
        peer = Identity(url)
        self.add_peer(peer)
        return peer

    def clear(self):
        self._peer_prefixes.clear()
        self.peers.clear()

    def update_peer_prefix(self, peer, new_prefix):
        old_prefix = peer.get_prefix()
        peer.set_prefix(new_prefix)
        if old_prefix in self._peer_prefixes:
            del self._peer_prefixes[old_prefix]
            self._peer_prefixes[new_prefix] = peer

    def get_peer_by_prefix(self, prefix):
        peer = self._peer_prefixes.get(prefix, None)
        return peer

    def check_peer_prefix(self, peer):
        ack = False
        while not ack:
            peer_prefix = peer.get_prefix()
            ack = peer_prefix not in self._peer_prefixes
            if ack:
                self._peer_prefixes[peer_prefix] = peer
            else:
                peer.create_prefix()
        
    def del_peer(self, peer):
        if peer.get('url') in self.peers:
            del self.peers[peer.get('url')]

    def get_by(self, field, value, all=False):
        rels = []
        for _,peer in self.peers.items():
            if peer.get(field):
                if peer.get(field) == value:
                    if all:
                        rels.append(peer)
                    else:
                        return peer
        if all:
            return rels
        else:
            return None

    def get_peer(self, url):
        if url in self.peers:
            return self.peers.get(url)
        return None


if __name__ == "__main__":
    c = Identity(url="http://127.0.0.1:8080", role="manager", uuid="2")
    print(c.get("id"))
    print(c.get("prefix"))