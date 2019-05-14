import logging
logger = logging.getLogger(__name__)

import psutil as ps
import os

from gym.monitor.listeners.listener import Listener
from gym.common.defs.tools import LISTENER_PROCESS

import time
from datetime import datetime
from subprocess import check_output, CalledProcessError


class ListenerProcess(Listener):
    PARAMETERS = {
        'interval': 'interval',
        'name': 'name',
        'pid': 'pid',
        'duration': 'duration',
    }

    METRICS = {
        'cpu': 'cpu',
        'memory': 'memory',
        'disk': 'disk',
        'bandwidth': 'bandwidth',
    }

    def __init__(self):
        Listener.__init__(self, id=LISTENER_PROCESS, name='Host',
                          parameters=ListenerProcess.PARAMETERS,
                          metrics=ListenerProcess.METRICS)
        self._first = True
        self._command = None

    def _get_process_info(self):
        info = {}
        info['name'] = self._p.name()
        info['exe'] = self._p.exe()
        info['cwd'] = self._p.cwd()
        info['status'] = self._p.status()
        info['username'] = self._p.username()
        info['create_time'] = self._p.create_time()
        return info

    def _get_process_cpu(self, tm, prev_info):
        cpu_stats = {}
        cpu_stats["cpu_num"] = self._p.cpu_num()

        # cpu_affinity
        affinity = self._p.cpu_affinity()

        cpu_stats["cpu_affinity"] = ""
        for index in range(len(affinity)):
            if cpu_stats["cpu_affinity"] == "":
                cpu_stats["cpu_affinity"] = str(affinity[index])
            else:
                cpu_stats["cpu_affinity"] = cpu_stats["cpu_affinity"] + "," + str(affinity[index])

        # cpu_percent
        cpu_stats["cpu_percent"] = self._p.cpu_percent(interval=0.5)

        # user_time, system_time
        cpu_times = self._p.cpu_times()
        user_time, system_time = cpu_times.user, cpu_times.system

        if self._first == False:
            cpu_stats["user_time"] = (user_time - prev_info["user_time"]) / (tm - prev_info["time"])
            cpu_stats["system_time"] = (system_time - prev_info["system_time"]) / (tm - prev_info["time"])

        cpu_stats["user_time"] = user_time
        cpu_stats["system_time"] = system_time
        cpu_stats["num_threads"] = self._p.num_threads() * 1.0

        return cpu_stats
        # cpu = {}
        # cpu['percent'] = self._p.cpu_percent()
        # cpu['affinity'] = self._p.cpu_affinity()
        # cpu['cputimes'] = self._p.cpu_times().__dict__
        # cpu['nice'] = self._p.nice()
        # ts = self._p.threads()
        # ts = [t.__dict__ for t in ts]
        # cpu['threads'] = ts
        # return cpu

    def _get_process_mem(self):
        mem_stats = {}
        mem_stats["mem_percent"] = self._p.memory_percent()
        return mem_stats

        # mem = {}
        # mem['percent'] = self._p.memory_percent()
        # mem['swap'] = self._p.memory_info().__dict__

    def _get_process_storage(self, tm, prev_info):
        io_stats = {}
        # if os.getuid() == 0:
        io_counters = self._p.io_counters()

        if self._first == False:
            io_stats["read_count"] = (io_counters.read_count * 1.0 - prev_info["read_count"]) / (tm - prev_info["time"])
            io_stats["read_bytes"] = (io_counters.read_bytes * 1.0 - prev_info["read_bytes"]) / (tm - prev_info["time"])
            io_stats["write_count"] = (io_counters.write_count * 1.0 - prev_info["write_count"]) / (tm - prev_info["time"])
            io_stats["write_bytes"] = (io_counters.write_bytes * 1.0 - prev_info["write_bytes"]) / (tm - prev_info["time"])
            io_stats["write_chars"] = (io_counters.write_chars * 1.0 - prev_info["write_chars"]) / (tm - prev_info["time"])
            io_stats["read_chars"] = (io_counters.read_chars * 1.0 - prev_info["read_chars"]) / (tm - prev_info["time"])

        io_stats["read_count"] = io_counters.read_count * 1.0
        io_stats["read_bytes"] = io_counters.read_bytes * 1.0
        io_stats["write_count"] = io_counters.write_count * 1.0
        io_stats["write_bytes"] = io_counters.write_bytes * 1.0
        io_stats["read_chars"] = io_counters.read_chars * 1.0
        io_stats["write_chars"] = io_counters.write_chars * 1.0
        # else:
        #     io_stats["read_count"] = "0.0"
        #     io_stats["read_bytes"] = "0.0"
        #     io_stats["write_count"] = "0.0"
        #     io_stats["write_bytes"] = "0.0"

        return io_stats
            # storage = {}
        # of = self._p.open_files()
        # of = [f.__dict__ for f in of]
        # storage['open_files'] = of
        # storage['num_fds'] = self._p.num_fds()
        # storage['io_counters'] = self._p.io_counters().__dict__
        # return storage

    def _get_process_net(self):
        net = {}
        conns = self._p.connections()
        conns = [c.__dict__ for c in conns]
        net['connections'] = conns
        net['connections'] = []
        return net

    def _get_process_stats(self, tm, measurement):
        resources = {}
        cpu = self._get_process_cpu(tm, measurement)
        mem = self._get_process_mem()
        disk = self._get_process_storage(tm, measurement)
        # net = self._get_process_net()
        resources.update(cpu)
        resources.update(mem)
        resources.update(disk)
        # resources.update(net)
        return resources

    def options(self, opts):
        options = self.serialize(opts)
        opts = {}
        stop = False
        timeout = 0
        for k, v in options.items():
            if k == 'stop':
                stop = True
            if k == 'duration':
                timeout = v
            opts[k] = v
        return opts, stop, timeout

    def get_pid(self, name):
        pidlist = []
        try:
            pidlist = list(map(int, check_output(["pidof", name]).split()))
        except  CalledProcessError:
            pidlist = []
        finally:
            if pidlist:
                pid = pidlist.pop()
            else:
                pid = None
            return pid

    def monitor(self, opts):
        results = []
        interval = 1
        pid = None
        if 'interval' in opts:
            interval = float(opts['interval'])

        if 'duration' in opts:
            t = float(opts.get('duration'))
        else:
            return results

        if 'pid' in opts:
            pid = int(opts['pid'])
        elif 'name' in opts:
            name = str(opts['name'])
            pid = self.get_pid(name)
        else:
            return results

        if not pid:
            logger.debug("pid not found")
            return results
        if not ps.pid_exists(pid):
            return results

        self._p = ps.Process(pid)
        stats = self._get_process_info()
        measurement = {}
        measurement["time"] = 0.0
        past = datetime.now()
        while True:
            current = datetime.now()
            _time = {'timestamp': current.strftime('%Y-%m-%dT%H:%M:%S.%fZ')}
            seconds = (current-past).total_seconds()
            if seconds > t:
                break
            else:
                tm = time.time()
                measurement = self._get_process_stats(tm, measurement)
                measurement["time"] = tm
                measurement.update(stats)
                self._first = False
                current = datetime.now()
                _time = {'timestamp': current.strftime('%Y-%m-%dT%H:%M:%S.%fZ')}
                measurement.update(_time)
                results.append(measurement)
                time.sleep(interval)
        return results

    def parser(self, out):
        return out


if __name__ == '__main__':
    opts = {
        'interval':1,
        'duration':2,
        'target':9371,
    }

    # process_listener = ListenerProcess()
    # measures = process_listener.monitor(opts)
    # for v in measures:
    #     print v

    app = ListenerProcess()
    print(app.main())
