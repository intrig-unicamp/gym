#!/usr/bin/env python
# coding=utf-8

import logging
from gym.agent.probers.prober import Prober
from gym.common.defs.tools import PROBER_PING

logger = logging.getLogger(__name__)


class ProberPing(Prober):
    PARAMETERS = {
        'interval':'-i',
        'duration':'-w',
        'packets':'-c',
        'frame_size':'-s',
        'target':'target',
    }

    METRICS = [
        'latency',
        'frame_loss'
    ]

    def __init__(self):
        Prober.__init__(self, id=PROBER_PING, name="ping",
                        parameters=ProberPing.PARAMETERS,
                        metrics=ProberPing.METRICS)
        self._command = 'ping'

    def options(self, opts):
        options = self.serialize(opts)
        opts = []
        stop = False
        timeout = 0
        for k, v in options.items():
            if k == 'target':
                continue
            else:
                opts.extend([k, v])
        if 'target' in options:
            opts.append(options['target'])
        return opts, stop, timeout

    def parser(self, out):
        _eval = {}
        lines = [line for line in out.split('\n') if line.strip()]
        if len(lines) > 1:
            rtt_indexes = [i for i, j in enumerate(lines) if 'rtt' in j]
            if not rtt_indexes:
                rtt_indexes = [i for i, j in enumerate(lines) if 'round-trip' in j]
            if rtt_indexes:
                rtt_index = rtt_indexes.pop()
                rtt_line = lines[rtt_index].split(' ')
                loss_line = lines[rtt_index-1].split(' ')
                rtts = rtt_line[3].split('/')
                rtt_units = rtt_line[4]
                if 'time' in loss_line:
                    pkt_loss = loss_line[-5][0]
                    pkt_loss_units = loss_line[-5][-1]
                else: 
                    pkt_loss = loss_line[-3][0]
                    pkt_loss_units = loss_line[-3][-1]
                
                _eval = {
                    'latency':{
                        'rtt_min': float(rtts[0]),
                        'rtt_avg': float(rtts[1]),
                        'rtt_max': float(rtts[2]),
                        'rtt_mdev': float(rtts[3]),
                        'units': rtt_units},
                    'frame_loss':{
                        'frames': float(loss_line[0]),
                        'frame_loss': float(pkt_loss),
                        'units': pkt_loss_units,
                    }
                }    
        return _eval


if __name__ == '__main__':
    app = ProberPing()
    print(app.main())