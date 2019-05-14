import platform as pl
import psutil as ps

from gym.common.profiler.info.info import Info

class Environment(Info):
    def __init__(self):
        Info.__init__(self, 1, "environment")
        self.info = {}

    def extract_info(self):
        self.info = self._node()

    def _node(self):
        resource = self._get_node_resources()
        id = self._get_node_info()
        id.update(resource)
        return id

    def _get_node_info(self):
        info = {}
        system, node, release, version, machine, processor = pl.uname()
        info['system'] = system
        info['host'] = node
        info['release'] = release
        info['version'] = version
        info['machine'] = machine
        info['processor'] = processor
        return info

    def _get_node_cpu(self):
        cpu = {}
        cpu['logical'] = ps.cpu_count(logical=True)
        cpu['cores'] = ps.cpu_count(logical=False)
        return cpu

    def _get_node_mem(self):
        mem = {}
        mem['pyshical'] = ps.virtual_memory().total
        mem['swap'] = ps.swap_memory().total
        return mem

    def _get_node_storage(self):
        storage = {}
        total = ps.disk_usage('/').total
        percent = ps.disk_usage('/').percent
        
        storage = {
            "total": total,
            "percent": percent,
        }
        return storage

    def _get_node_net(self):
        net = {}
        addrs = ps.net_if_addrs()      
        for face in addrs:
            face_addrs = [addr for addr in addrs[face] if addr.family==2]
            if face_addrs:
                face_addr = face_addrs.pop()
                net[face] = {
                    'address': face_addr.address
                }
        return net

    def _get_node_resources(self):
        resources = {}
        resources['cpu'] = self._get_node_cpu()
        resources['memory'] = self._get_node_mem()
        resources['disk'] = self._get_node_storage()
        resources['network'] = self._get_node_net()
        return resources

if __name__ == "__main__":
    info = Environment()
    print(info.profile())