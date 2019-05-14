import logging
import argparse

from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

logger = logging.getLogger(__name__)


class Config:
    def __init__(self):
        self.config = None

    def parse(self, filename):
        data = {}
        with open(filename, 'r') as f:
            data = load(f, Loader=Loader)
        return data

    def get_config(self, argv=None):
        parser = argparse.ArgumentParser(
            description='Gym App')

        parser.add_argument('--id',
                            type=str,
                            help='Define the app id (default: None)')

        parser.add_argument('--url',
                            type=str,
                            help='Define the app url (host:port) (default: None)')

        parser.add_argument('--contacts',
                            nargs='+',
                            help='Define the app contacts (default: [])')

        parser.add_argument('--debug',
                            action='store_true',
                            help='Define the app logging mode (default: False)')

        parser.add_argument('--cfg',
                            type=str,
                            help='Define the cfg (id + url) (default: None)')

        self.cfg, unknown = parser.parse_known_args(argv)
        
        info = self.check_config()
        return info

    def cfg_args(self):
        cfgFile = self.cfg.cfg
        if cfgFile:
            cfg_data = self.parse(cfgFile)
            return cfg_data
        return None
            
    def check_config(self):
        _contacts = None

        if self.cfg.cfg:
            cfg_data = self.cfg_args()
            _id = cfg_data.get('id', None)
            _url = cfg_data.get('url', None)
            _contacts = cfg_data.get('contacts', None)
        else:
            _id, _url = self.cfg.id, self.cfg.url
            _contacts = self.cfg.contacts

        if _id and _url:
            logger.info("Init cfg: id %s - url %s", _id, _url)
            info = {
                "id": _id,
                "url": _url,
                "contacts": _contacts,
                "debug": self.cfg.debug
            }
            print("provided info", info)
            return info
        else:
            print("Init cfg NOT provided - both must exist: id and url (provided values: %s, %s)" % (_id, _url))
            return None
