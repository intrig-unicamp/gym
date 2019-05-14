import logging
import time
import json
from gym.common.defs.tools import PROBER_IPERF3
from gym.agent.probers.prober import Prober

logger = logging.getLogger()


class ProberIperf3(Prober):
    PARAMETERS = {
        'port':'-p',
        'duration':'-t',
        'protocol':'-u',
        'server':'-s',
        'client':'-c',
        'rate':'-b'
    }

    METRICS = [
        'bandwidth',
    ]

    def __init__(self):
        Prober.__init__(self, id=PROBER_IPERF3, name="iperf3",
                        parameters=ProberIperf3.PARAMETERS,
                        metrics=ProberIperf3.METRICS)
        self._command = 'iperf3'

    def options(self, opts):
        options = self.serialize(opts)
        opts = []
        stop = False
        timeout = 0
        
        info = options.get('info', None)
        if info:
            opts.extend(['info', info])

        server = options.get('-s', None)
        client = options.get('-c', False)
        
        if server:
            opts.extend( ['-c', server] )                
            time.sleep(0.5)
        if not client or client == 'false' or client == 'False':
            opts.extend( ['-s'] )                
            stop = True
        
        port = options.get('-p', '9030')
        opts.extend( ['-p', port] )                
        
        timeout = float(options.get('-t', 0))
        if timeout and not stop:
            opts.extend( ['-t', str(timeout)] )
            timeout = 0

        proto = options.get('-u', None)
        if proto == 'udp':
            if not stop:
                opts.extend(['-u'])

        rate = options.get('-b', None)
        if rate and not stop:
            opts.extend( ['-b', rate] )
            
        opts.extend(['-f','m'])
        opts.append('-J')
        return opts, stop, timeout

    def parser(self, out):
        _eval = {}
        try:
            out = json.loads(out)
        except ValueError:
            logger.debug('iperf3 json output could not be decoded')
            out = {}
        else:
            end = out.get("end", None)
            if end:
                if 'sum_sent' in end:
                    _eval = end.get('sum_sent')
                if 'sum' in end:
                    _eval = end.get('sum')
        finally:
            return _eval


if __name__ == '__main__':
    app = ProberIperf3()
    print(app.main())
