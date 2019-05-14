import logging
logger = logging.getLogger(__name__)

import os 
import json 

from gym.common.es.es import ES


class StorageES:
    def __init__(self):
        self.es = ES()

    def _parse(self, item):
        _index = item.get('where', None)
        _type = item.get('what', None)
        _id = item.get('id', None)
        _body = item.get('body', None)
        if all([_index, _type, _id]):
            return (_index, _type, _id, _body)
        else:
            return None

    def add(self, commit):
        parsed = self._parse(commit)
        if parsed:
            _index, _type, _id, _body = parsed
            ok = self.es.add(index=_index, type=_type, id=_id, body=_body)
            return ok
        return False

    def remove(self, commit):
        parsed = self._parse(commit)
        if parsed:
            _index, _type, _id, _ = parsed
            ok = self.es.delete(index=_index, type=_type, id=_id)
            return ok
        return False

    def retrieve(self, commit):
        parsed = self._parse(commit)
        if parsed:
            _index, _type, _id, _ = parsed
            data = self.es.get(index=_index, type=_type, id=_id)
            return data
        return None

    def store(self, vnfbr):
        logger.debug("Elasticsearch Store VNF-BR")
        index_id = vnfbr.get_id()
        vnfbr_json = vnfbr.to_json()
        commit = {'where': index_id, 'what': 'vnfbr', 'id': 1, 'body': vnfbr_json}
        
        if self.add(commit):
            logger.info('ok: vnfbr %s stored', index_id)
        else:
            logger.info('error: vnfbr NOT %s stored', index_id)


class StorageDisk:
    def __init__(self):
        self.filename = None
        self.folder = "./vnfbr/"
        # self.folder = "../../vnfbr/"

    def filepath(self, filename):
        if not os.path.exists(os.path.dirname(self.folder)):
            os.makedirs(os.path.dirname(self.folder))
        # filepath = os.path.join(os.path.dirname(__file__), self.folder, filename)
        filepath = os.path.join(self.folder, filename)
        return filepath

    def load(self, filename):
        filename = self.filepath(filename)
        with open(filename, 'r') as infile:
            data = json.load(infile)
            return data

    def save(self, commit):
        filename = commit.get("filename")
        filepath = self.filepath(filename)
        data = json.loads(commit.get("data"))
        with open(filepath, 'w') as outfile:
            json.dump(data, outfile, indent=4, sort_keys=True)
            return True
        return False

    def store(self, vnfbr):
        logger.debug("Disk Store VNF-BR")
        index_id = vnfbr.get_id()
        vnfbr_json = vnfbr.to_json()
        commit = {'filename': 'vnfbr-' + str(index_id), 'data': vnfbr_json}
        
        if self.save(commit):
            logger.info('ok: vnfbr %s stored', index_id)
        else:
            logger.info('error: vnfbr NOT %s stored', index_id)


class Storage:
    MODES = {
        "disk": StorageDisk,
        "elastic": StorageES,
    }
    
    def __init__(self, defaults=['disk']):
        self.modes = []
        self.load_modes(defaults)

    def load_modes(self, modes):
        for mode in modes:
            if mode in Storage.MODES:
                if mode not in self.modes:
                    self.modes.append(Storage.MODES[mode])
        logger.info("Storage modes set %s", self.modes)

    def store(self, vnfbr):
        for storage in self.modes:
            db = storage()
            db.store(vnfbr)
        return True
