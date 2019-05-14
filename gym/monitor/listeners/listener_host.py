import logging
logger = logging.getLogger(__name__)

import psutil as ps
import platform as pl

from gym.monitor.listeners.listener import Listener
from gym.common.defs.tools import LISTENER_HOST

import time
from datetime import datetime


class ListenerHost(Listener):
    PARAMETERS = {
        'interval': 'interval',
        'duration': 'duration',
    }

    METRICS = [
        'cpu',
        'memory',
        'disk',
        'network',
    ]

    def __init__(self):
        Listener.__init__(self, id=LISTENER_HOST, name='Host',
                          parameters=ListenerHost.PARAMETERS,
                          metrics=ListenerHost.METRICS)
        self._first = True
        self._command = None

    def _get_node_info(self):
        info = {}
        system, node, release, version, machine, processor = pl.uname()
        info['system'] = system
        info['node'] = node
        info['release'] = release
        info['version'] = version
        info['machine'] = machine
        info['processor'] = processor
        return info

    def _get_node_cpu(self, tm, prev_info):
        cpu_stats = {}
        cpu_stats["cpu_percent"] = ps.cpu_percent(interval=0.5)

        user, nice, system, idle, iowait, irq, softirq, steal, guest, guest_nice = ps.cpu_times()

        if self._first == False:
            cpu_stats["user_time"] = (user - prev_info["user_time"]) / (tm - prev_info["time"])
            cpu_stats["nice_time"] = (nice - prev_info["nice_time"]) / (tm - prev_info["time"])
            cpu_stats["system_time"] = (system - prev_info["system_time"]) / (tm - prev_info["time"])
            cpu_stats["idle_time"] = (idle - prev_info["idle_time"]) / (tm - prev_info["time"])
            cpu_stats["iowait_time"] = (iowait - prev_info["iowait_time"]) / (tm - prev_info["time"])
            cpu_stats["irq_time"] = (irq - prev_info["irq_time"]) / (tm - prev_info["time"])
            cpu_stats["softirq_time"] = (softirq - prev_info["softirq_time"]) / (tm - prev_info["time"])
            cpu_stats["steal_time"] = (steal - prev_info["steal_time"]) / (tm - prev_info["time"])
            cpu_stats["guest_time"] = (guest - prev_info["guest_time"]) / (tm - prev_info["time"])
            cpu_stats["guest_nice_time"] = (guest_nice - prev_info["guest_nice_time"]) / (tm - prev_info["time"])

        cpu_stats["user_time"] = user
        cpu_stats["nice_time"] = nice
        cpu_stats["system_time"] = system
        cpu_stats["idle_time"] = idle
        cpu_stats["iowait_time"] = iowait
        cpu_stats["irq_time"] = irq
        cpu_stats["softirq_time"] = softirq
        cpu_stats["steal_time"] = steal
        cpu_stats["guest_time"] = guest
        cpu_stats["guest_nice_time"] = guest_nice

        return cpu_stats
        # cpu = {}
        # cpu['logical'] = ps.cpu_count(logical=True)
        # cpu['cores'] = ps.cpu_count(logical=False)
        # cpu['cputimes'] = ps.cpu_times().__dict__
        # cpu['percent'] = ps.cpu_percent()
        # cpu['stats'] = ps.cpu_stats().__dict__
        # return cpu

    def _get_node_mem(self):
        mem_stats = {}

        vm = ps.virtual_memory()

        mem_stats["mem_percent"] = vm.percent

        mem_stats["total_mem"] = vm.total / (1024. * 1024.)
        mem_stats["available_mem"] = vm.available / (1024. * 1024.)
        mem_stats["used_mem"] = vm.used / (1024. * 1024.)
        mem_stats["free_mem"] = vm.free / (1024. * 1024.)
        mem_stats["active_mem"] = vm.active / (1024. * 1024.)
        mem_stats["inactive_mem"] = vm.inactive / (1024. * 1024.)
        mem_stats["buffers_mem"] = vm.buffers / (1024. * 1024.)
        mem_stats["cached_mem"] = vm.cached / (1024. * 1024.)
        mem_stats["shared_mem"] = vm.shared / (1024. * 1024.)
        mem_stats["slab_mem"] = vm.slab / (1024. * 1024.)

        return mem_stats
        # mem = {}
        # mem['virtual'] = ps.virtual_memory().__dict__
        # mem['swap'] = ps.swap_memory().__dict__
        # return mem

    def _get_node_storage(self, tm, prev_info):
        disk_stats = {}
        # read_count, write_count, read_bytes, write_bytes, read_time, write_time = ps.disk_io_counters()

        dio = ps.disk_io_counters()
        if self._first == False:
            disk_stats["read_count"] = (dio.read_count * 1.0 - prev_info["read_count"]) / (tm - prev_info["time"])
            disk_stats["read_bytes"] = (dio.read_bytes * 1.0 - prev_info["read_bytes"]) / (tm - prev_info["time"])
            disk_stats["write_count"] = (dio.write_count * 1.0 - prev_info["write_count"]) / (tm - prev_info["time"])
            disk_stats["write_bytes"] = (dio.write_bytes * 1.0 - prev_info["write_bytes"]) / (tm - prev_info["time"])

        disk_stats["read_count"] = dio.read_count * 1.0
        disk_stats["read_bytes"] = dio.read_bytes * 1.0
        disk_stats["write_count"] = dio.write_count * 1.0
        disk_stats["write_bytes"] = dio.write_bytes * 1.0

        return disk_stats
        # storage = {}
        # storage['partitions'] = {}
        # partitions = ps.disk_partitions()
        # for partition in partitions:
        #     partition_name,m,fst,o = partition
        #     storage['partitions'][partition_name] = ps.disk_usage(partition_name).total
        # storage['io_counters'] = ps.disk_io_counters(perdisk=False).__dict__
        # return storage

    def _get_node_net(self):
        net_stats = {}

        return net_stats
        # net = {}
        # stats = ps.net_if_stats()
        # counters = ps.net_io_counters(pernic=True)
        # for face in counters:
        #     counters[face] = counters[face].__dict__
        #     stats[face] = stats[face].__dict__
        # net['stats'] = stats
        # net['counters'] = counters
        # return net

    def _get_node_stats(self, tm, measurement):
        resources = {}
        cpu = self._get_node_cpu(tm, measurement)
        mem = self._get_node_mem()
        disk = self._get_node_storage(tm, measurement)
        net = self._get_node_net()
        resources.update(cpu)
        resources.update(mem)
        resources.update(disk)
        resources.update(net)
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

    def monitor(self, opts):
        results = []
        interval = 1
        t = 3
        if 'interval' in opts:
            interval = float(opts.get('interval', 1))
        
        if 'duration' in opts:
            t = float(opts.get('duration', 0))
        else:
            return results

        past = datetime.now()
        node_info = self._get_node_info()
        measurement = {}
        measurement["time"] = 0.0
        while True:
            current = datetime.now()
            _time = {'timestamp': current.strftime('%Y-%m-%dT%H:%M:%S.%fZ')}
            seconds = (current-past).total_seconds()
            if seconds > t:
                break
            else:
                tm = time.time()
                measurement = self._get_node_stats(tm, measurement)
                measurement.update(node_info)
                measurement["time"] = tm
                current = datetime.now()
                self._first = False
                # result = {str(current): measurement}
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
        'duration':20,
    }

    # host_listener = ListenerHost()
    # measures = host_listener.monitor(opts)
    # for v in measures:
    #     print v

    app = ListenerHost()
    print(app.main())