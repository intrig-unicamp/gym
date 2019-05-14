import os
import json
import logging
from gym.common.process import Actuator

logger = logging.getLogger(__name__)


class Profiler:
    FILES = 'info'
    FILES_PREFIX = 'info_'
    FILES_SUFFIX = 'py'

    def __init__(self):
        self.profiles = {}
        self._outputs = []
        self.actuator = Actuator()
        self.cfg_acts()
        
    def cfg_acts(self):
        logger.info("Loading Profile Infos")
        folder = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            Profiler.FILES)

        cfg = {
            "folder": folder,
            "prefix": Profiler.FILES_PREFIX,
            "sufix": Profiler.FILES_SUFFIX,
            "full_path": True,
        }
        self.actuator.cfg(cfg)



    def profile(self):
        self._outputs = self.actuator.get_acts()
        for value in self._outputs.values():
            name = value.get("name", None)
            if name:
                self.profiles[name] = value
            else:
                logger.info("Could not load profiler output %s", value)
        return self.profiles


if __name__ == "__main__":
    
    level = logging.DEBUG
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.setLevel(level)
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(level)
    logger = logging.getLogger(__name__)


    prfl = Profiler()
    msg = prfl.profile()
    print(msg)