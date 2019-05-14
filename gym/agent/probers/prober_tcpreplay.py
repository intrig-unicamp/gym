import os
import logging
import time
import json
from gym.common.defs.tools import PROBER_TCPREPLAY
from gym.agent.probers.prober import Prober

logger = logging.getLogger()


class ProberTcpReplay(Prober):
    PARAMETERS = {
        'interface':'-i',
        'duration':'--duration',
        'speed':'-t',
        'timing':'-T',
        'preload':'-K',
        'loop':'-l',
        'pcap':'-f'
    }

    METRICS = [
        'bandwidth',
    ]

    def __init__(self):
        Prober.__init__(self, id=PROBER_TCPREPLAY, name="tcpreplay",
                        parameters=ProberTcpReplay.PARAMETERS,
                        metrics=ProberTcpReplay.METRICS)
        self._command = 'tcpreplay'
        self._instances_folder = '/mnt/pcaps/'

    def options(self, opts):
        options = self.serialize(opts)
        opts = []
        stop = False
        timeout = 0

        for k,v in options.items():
            if k == '-t':
                opts.extend([k])
            elif k == '-K':
                opts.extend([k])
            else:
                if k != '-f':
                    opts.extend([k,v])

        opts.append('-q')
        
        if '-f' in options:
            pcap_value = options.get('-f')
            pcap_path = self.filepath(pcap_value)
            opts.append(pcap_path)
        return opts, stop, timeout

    def filepath(self, filename):
        _filepath = os.path.normpath(os.path.join(
            # os.path.dirname(__file__),
            self._instances_folder, filename))
        return _filepath

    def parser(self, output):
        eval_info = None
        lines = output.split('\n')
        if len(lines) > 1:
            actual = [line for line in lines if 'Actual' in line]
            actual_info = actual.pop().split()
            eval_info = {
                'packets': int(actual_info[1]),
                'time': float(actual_info[-2]),
            }
        return eval_info


if __name__ == '__main__':
    app = ProberTcpReplay()
    print(app.main())
