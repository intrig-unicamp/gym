import logging
logger = logging.getLogger(__name__)

import os
import math
import yaml
import sys
import json 
import time
import flatten_json
from datetime import datetime
from subprocess import check_output

from gym.monitor.listeners.listener import Listener
from gym.common.defs.tools import LISTENER_SURICATA


class SuricataStats:
    STATS_LOG = "/usr/local/var/log/suricata/stats.log"
    EVE_LOG = "/usr/local/var/log/suricata/eve.json"
    NET_PATH = "/sys/class/net"

    def get_seconds(self, tm):
        hms = tm.split(":")
        return (int(hms[0]) * 3600) + (int(hms[1]) * 60) + int(hms[2])

    def get_difference(self, values):
        return [x - values[i - 1] for i, x in enumerate(values)][1:]

    def get_median(self, values):
        tmp = []

        for value in values:
            tmp.append(value)

        tmp.sort()
        length = len(tmp)

        if length == 0:
            return 0.0

        median = int(length / 2)

        if length % 2 == 1:
            return tmp[median]
        else:
            return ((tmp[median - 1] + tmp[median]) * 1.0) / 2

    def get_stdev(self, values):
        tmp = []

        for value in values:
            tmp.append(value)

        tmp.sort()
        length = len(tmp)

        if length == 0:
            return 0.0

        avg = (sum(tmp) * 1.0) / length

        dev = []
        for x in tmp:
            dev.append(x - avg)

        sqr = []
        for x in dev:
            sqr.append(x * x)

        if len(sqr) <= 1:
            return 0.0

        mean = sum(sqr) / len(sqr)

        return math.sqrt(sum(sqr) / (len(sqr) - 1))

    def get_median_filtered(self, values):
        if len(values) == 0:
            return 0.0

        tmp = []

        for value in values:
            tmp.append(value)

        tmp.sort()

        med_tmp = self.get_median(tmp)
        std_tmp = self.get_stdev(tmp)

        for t in tmp:
            if t < (med_tmp - (std_tmp * 0.34)):
                tmp.remove(t)
            elif t > (med_tmp + (std_tmp * 0.34)):
                tmp.remove(t)

        length = len(tmp)

        if length == 0:
            return 0.0

        median = int(length / 2)

        if length % 2 == 1:
            return tmp[median]
        else:
            return ((tmp[median - 1] + tmp[median]) * 1.0) / 2

    def suri_status(self):
        os.system("sync")
        os.system("sync")
        os.system("sync")

        source = open(self.STATS_LOG, "r")
        lines = source.read().splitlines()
        source.close()

        raw_times_inc = []
        raw_frames_inc = []
        raw_drops_inc = []
        raw_packets_inc = []
        raw_bytes_inc = []

        raw_times = 0.0
        raw_frames = 0.0
        raw_drops = 0.0
        raw_packets = 0.0
        raw_bytes = 0.0

        flag = 0
        for index in range(len(lines)):
            line = lines[index].split()

            if line[0] == "Date:":
                raw_times = self.get_seconds(line[3])
                flag += 1
            if line[0] == "capture.kernel_packets":
                raw_frames = int(line[4]) * 1.0
                flag += 1
            elif line[0] == "capture.kernel_drops":
                raw_drops = int(line[4]) * 1.0
                flag += 1
            elif line[0] == "decoder.pkts":
                raw_packets = int(line[4]) * 1.0
                flag += 1
            elif line[0] == "decoder.bytes":
                raw_bytes = int(line[4]) * 1.0
                flag += 1

            if flag == 5:
                raw_times_inc.append(raw_times)
                raw_frames_inc.append(raw_frames)
                raw_drops_inc.append(raw_drops)
                raw_packets_inc.append(raw_packets)
                raw_bytes_inc.append(raw_bytes)

                raw_times = 0.0
                raw_frames = 0.0
                raw_drops = 0.0
                raw_packets = 0.0
                raw_bytes = 0.0

                flag = 0

        time_diff = self.get_difference(raw_times_inc)
        frames_diff = self.get_difference(raw_frames_inc)
        drops_diff = self.get_difference(raw_drops_inc)
        packets_diff = self.get_difference(raw_packets_inc)
        bytes_diff = self.get_difference(raw_bytes_inc)

        frames_end = []
        drops_end = []
        packets_end = []
        bytes_end = []

        delete = 0
        for index in range(len(frames_diff)):
            if delete > 2 and frames_diff[index] > 0:
                try:
                    frames_end.append(frames_diff[index] / time_diff[index])
                    drops_end.append(drops_diff[index] / time_diff[index])
                    packets_end.append(packets_diff[index] / time_diff[index])
                    bytes_end.append(bytes_diff[index] / time_diff[index])
                except BaseException:
                    pass
            delete += 1

        f = self.get_median_filtered(frames_end)
        d = self.get_median_filtered(drops_end)
        p = self.get_median_filtered(packets_end)
        b = self.get_median_filtered(bytes_end)

        if f == 0.0:
            p, b, d = 0.0, 0.0, 0.0
        
        result = dict()
        result["packets"] = p
        result["bytes"] = b
        result["dropped"] = d
        result["drops"] = d/f if f != 0.0 else 0.0
        
        return result


    def collect_intf_statistics(self):
        r = dict()
        intf_list = os.listdir(self.NET_PATH)
        for intf_name in intf_list:
            stat_files = os.listdir(os.path.join(self.NET_PATH, intf_name, "statistics"))
            for fn in stat_files:
                with open(os.path.join(self.NET_PATH, intf_name, "statistics", fn), "r") as f:
                    data = -1
                    try:
                        data = float(f.read())
                    except:
                        pass
                    r["stat__" + intf_name + "__" + fn] = data
        return r

    def eve_status(self):
        METRIC_PREFIX = "suricata_eve_"

        data = dict()
        try:
            # efficiently get and parse last line from EVE_FILE
            line = check_output(['tail', '-1', self.EVE_LOG])
            data = json.loads(line.decode("utf-8"))
        except Exception:
            pass
        finally:
            data_flat = flatten_json.flatten(data)
            data_flat = {METRIC_PREFIX + k: v for k, v in data_flat.items()}
            return data_flat

    def status(self):
        suri_stats = self.suri_status()
        intfs_stats = self.collect_intf_statistics()
        suri_stats.update(intfs_stats)
        return suri_stats

    def final_status(self):
        eve_stats = {}
        try:
            suri_stats = self.suri_status()
            eve_stats = self.eve_status()
            eve_stats.update(suri_stats)
        except Exception:
            pass
        finally:
            return eve_stats


class ListenerSuricata(Listener):
    PARAMETERS = {
        'interface': 'interface',
        'duration': 'duration',
    }

    METRICS = {
        'suricata_metrics': 'suricata_metrics',
    }

    def __init__(self):
        Listener.__init__(self, id=LISTENER_SURICATA, name='Suricata',
                          parameters=ListenerSuricata.PARAMETERS,
                          metrics=ListenerSuricata.METRICS)
        self._command = ''
        self._suricata_stats = SuricataStats()


    def _stats(self, interface):
        cmd = "cat /proc/net/dev | grep " + interface + " | awk '{print $2,$3,$5,$10,$11,$13}'"
        stats = check_output(['bash', '-c', cmd])
        stats_split = stats.split()
        stats_dict = {
            'query_size': float(stats_split[0]),
            'query_pkts': float(stats_split[1]),
            'query_drop': float(stats_split[2]),
            'reply_size': float(stats_split[3]),
            'reply_pkts': float(stats_split[4]),
            'reply_drop': float(stats_split[5]),
        }
        return stats_dict

    def process_diffs(self, stats_diffs, duration):
        pkt_overhead = 42
        stats_diffs_extra = {
            'answered': 100*(stats_diffs['reply_pkts']/stats_diffs['query_pkts']),
            'query_rate': stats_diffs['query_pkts'] / duration,
            'reply_rate': stats_diffs['reply_pkts'] / duration,
            'query_avglen': (stats_diffs['query_size'] / stats_diffs['query_pkts']) - pkt_overhead,
            'reply_avglen': (stats_diffs['reply_size'] / stats_diffs['reply_pkts']) - pkt_overhead,
        }
        stats_diffs.update(stats_diffs_extra)

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

    def stats_diff(self, interface, duration):
        stats_before = self._stats(interface)
        time.sleep(duration)
        stats_after = self._stats(interface)
        stats_diffs = list(map(lambda x,y: x-y, stats_after.values(), stats_before.values()))
        stats_diff = dict(zip(stats_before.keys(), stats_diffs))

        self.process_diffs(stats_diff, duration)
        
        suri_status = self._suricata_stats.status()
        stats_diff.update(suri_status)
        return stats_diff

    def monitor(self, opts):
        results = {}
        duration = None
        interface = None

        if 'duration' in opts:
            duration = float(opts['duration'])
        
        if 'interface' in opts:
            interface = opts['interface']

        if duration and interface:
            # try:
            #     stats_diff = self.stats_diff(interface, duration)
            # except Exception:
            #     stats_diff = {}

            stats_diff = {}
            time.sleep(duration+1)                        
            eve_status = self._suricata_stats.final_status()
            stats_diff.update(eve_status)
            
            current = datetime.now()
            _time = {'timestamp': current.strftime('%Y-%m-%dT%H:%M:%S.%fZ')}
            results.update(_time)
            results.update(stats_diff)
        return results

    def parser(self, out):
        return out


if __name__ == '__main__':
    opts = {
        'interface': 'wlp2s0',
        'duration':2,
    }
    #
    # app = ListenerDNS()
    # print app.monitor(opts)
    #

    app = ListenerSuricata()
    print(app.main())
