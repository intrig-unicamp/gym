import logging
import time
from gym.common.defs.tools import PROBER_IPERF
from gym.agent.probers.prober import Prober

logger = logging.getLogger()


class ProberIperf(Prober):
    PARAMETERS = {
        'port':'-p',
        'duration':'-t',
        'protocol':'-u',
        'server':'-s',
        'client':'-c',
    }

    METRICS = [
        'bandwidth',
    ]

    def __init__(self):
        Prober.__init__(self, id=PROBER_IPERF, name="iperf",
                        parameters=ProberIperf.PARAMETERS,
                        metrics=ProberIperf.METRICS)
        self._command = 'iperf'

    def options(self, opts):
        options = self.serialize(opts)
        opts = []
        stop = False
        timeout = 0
        if '-c' in options:
            time.sleep(0.5)
        for k,v in options.items():
            if k == '-s':
                stop = True
            if k == '-t':
                timeout = float(v)
            if k == '-u' or k == '-s':
                opts.extend([k])
            else:
                opts.extend([k,v])
        opts.extend(['-f','m'])
        return opts, stop, timeout

    def parser(self, out):
        eval = {}
        lines = [line for line in out.split('\n') if line.strip()]
        if len(lines) == 7:
            bandwidth = lines[-1].split(' ')[-2]
            units = lines[-1].split(' ')[-1]
            eval = {
                'bandwidth': {
                    'value': float(bandwidth),
                    'units': units,
                }
            }
        elif len(lines) == 11 or len(lines) == 8:
            bandwidth = lines[-1].split(' ')[-13]
            units = lines[-1].split(' ')[-12]
            eval = {
                'bandwidth':{
                    'value': float(bandwidth),
                    'units': units,
                }
            }
        return eval


if __name__ == '__main__':
    app = ProberIperf()
    print(app.main())
