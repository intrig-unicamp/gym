#!/usr/bin/env python
# coding=utf-8

import logging
from gym.agent.probers.prober import Prober
from gym.common.defs.tools import PROBER_SIPP

logger = logging.getLogger(__name__)


class ProberSipp(Prober):
    PARAMETERS = {
        'proxy':'',
        'scenario':'-sf',
        'subscribers':'-inf',
        'max_simult_calls':'-l',
        'rate_increase':'-rate_increase',
        'increase_interval':'-fd',
        'rate_max':'-rate_max',
        'output_file':">",
        'transport':'-t'
    }

    METRICS = [
        'calls',
    ]

    def __init__(self):
        Prober.__init__(self, id=PROBER_SIPP, name="sipp",
                        parameters=ProberSipp.PARAMETERS,
                        metrics=ProberSipp.METRICS)
        self._command = 'sipp'

    def parser(self, out):
        eval = {}
        # TODO: sipp parser
        return eval


if __name__ == '__main__':
    app = ProberSipp()
    print(app.main())