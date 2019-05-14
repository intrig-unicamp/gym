import os
import json
import logging
import subprocess
import time
from multiprocessing import Process, Queue

logger = logging.getLogger(__name__)


class Loader:
    def __init__(self):
        self._files = []
        self._classes = {}
        self._modules = []

    def get_modules(self):
        return self._modules

    def get_classes(self):
        return self._classes

    def get_files(self):
        return self._files

    def loading(self, root, file, full_path):
        p = os.path.join(root, file)
        if full_path:
            file_path = os.path.abspath(p)
            self._files.append(file_path)
        else:
            self._files.append(file)

    def load_files(self, folder, file_begin_with, endswith=None, full_path=False):
        for root, dirs, files in os.walk(folder):
            for file in files:
                if file.startswith(file_begin_with):
                    if endswith:
                        if file.endswith(endswith):
                            self.loading(root, file, full_path)
                    else:
                        self.loading(root, file, full_path)
        return self._files

    def load_classes(self, folder, file_begin_with, class_begin_with):
        files = self.load_files(folder, file_begin_with)
        files = [f.split('.')[0] for f in files if f.endswith('.py')]
        self._modules = [__import__(f) for f in files]
        for m in self._modules:
            classes = [c for c in dir(m) if c.startswith(class_begin_with)]
            if classes:
                for c in classes:
                    self._classes[c] = getattr(m, c)
        return self._classes


class Processor:
    def __init__(self):
        self.process = None

    def start_process(self, args, queue, stop=False, timeout=60):
        return_code = 0
        out, err = '', None
        try:
            p = subprocess.Popen(args,
                stdin = subprocess.PIPE,
                stdout = subprocess.PIPE,
                stderr = subprocess.PIPE,
                )
            self.process = p
            logger.debug('process started %s', p.pid)
            if stop:
                if self.stop_process(timeout):
                    out, err = p.communicate()
                    return_code = p.returncode
                else:
                    return_code = -1
                    err = 'ERROR: Process not defined'
            else:
                out, err = p.communicate()
                return_code = p.returncode
        except OSError:
            return_code = -1
            err = 'ERROR: exception OSError'
        finally:
            logger.debug('process stopped')
            if return_code != 0:
                queue_answer = err
                logger.error(err)
            else:
                queue_answer = out
            self.process = None
            queue.put(return_code)
            queue.put(queue_answer)
            queue.put('STOP')
            queue.close()
            return return_code

    def stop_process(self, timeout):
        if self.process:
            time.sleep(timeout)
            self.process.kill()
            logger.debug('Timeout for pid %s', self.process.pid)
            self.process = None
            return True
        return False


class Multiprocessor:
    def __init__(self):
        self.processes = {}
        self.processor = Processor()

    def make_process(self,  cmd, stop, timeout):
        q = Queue()
        p = Process(target=self.processor.start_process, args=(cmd, q, stop, timeout))
        return (p,q)

    def start_processes(self, cmds, stop, timeout):
        self.processes = {}
        for _id,cmd in cmds.items():
            self.processes[_id] = self.make_process(cmd, stop, timeout)
        logger.debug('Starting processes %s', self.processes)
        for (p,q) in self.processes.values():
            p.start()

    def check_processes(self):
        logger.debug("checking processes")
        any_alive = True
        while any_alive:
            any_alive = any([p.is_alive() for (p,q) in self.processes.values()])
            all_queued = all([not q.empty() for (p, q) in self.processes.values()])
            time.sleep(0.05)
            if all_queued and any_alive:
                break
        return True

    def dump_queues(self, queue):
        return_code = queue.get_nowait()
        result = ""
        for i in iter(queue.get_nowait, 'STOP'):
            if type(i) is bytes:
                i_dec = i.decode("utf-8") 
            else:
                i_dec = i
            result += i_dec
        return return_code,result

    def get_processes_queue(self):
        outs = {}
        for _id, (p, q) in self.processes.items():
            try:
                exitcode, _res = self.dump_queues(q)
            except Exception as e:
                logger.debug("Process id %s dump queue exception %s", _id, e)
            else:
                p.terminate()
                outs[_id] = (exitcode, _res)
        return outs

    def run(self, cmds, stop=False, timeout=60):
        self.start_processes(cmds, stop, timeout)
        _outputs = {}
        if self.check_processes():
            _outputs = self.get_processes_queue()
        return _outputs


class Executor:
    def __init__(self):
        self._multi_processor = Multiprocessor()
        self._exe = {'py': '/usr/bin/python3',
                     'sh': 'sh',
                     'pl': 'perl',
                     'java': 'java'}

    def _parse_cmd(self, cmd):
        if type(cmd) is list:
            cmd = [str(c) for c in cmd]
        else:
            cmd = cmd.split(' ')
        return cmd

    def _parse_type(self, cmd):
        type = 'sh'
        _cmd = self._parse_cmd(cmd)
        _cmd = _cmd[0]
        if len(_cmd.split('.')) > 1:
            if _cmd.split('.')[-1] in self._exe:
                type = self._exe[_cmd.split('.')[-1]]
            else:
                type = None
        else:
            type = None
        return type

    def _cmd_exec_local(self, cmd):
        # logger.debug('_exec_local')
        _type = self._parse_type(cmd)
        if type(cmd) is list:
            cmd = [str(c) for c in cmd]
            cmd = ' '.join(cmd)
        if _type:
            cmd = _type + ' ' + cmd
        cmd = self._parse_cmd(cmd)
        logger.debug(cmd)
        return cmd

    def _cmd_exec_remote(self, cmd, host, user):
        # logger.debug('_exec_remote')
        ssh = ''.join(['ssh ', user, '@', host])
        _type = self._parse_type(cmd)
        if type(cmd) is list:
            cmd = [str(c) for c in cmd]
            cmd = ' '.join(cmd)
        if _type:
            cmd = ssh + _type + ' < ' + cmd
        else:
            cmd = ssh + ' ' + cmd
        cmd = self._parse_cmd(cmd)
        logger.debug(cmd)
        return cmd

    def _output(self, ret, out):
        if ret == 0:
            return 'ok',out
        else:
            return None,out

    def _build_cmd(self, cmds, remote=False, host=None, user=None):
        built_cmds = {}
        for _id, cmd in cmds.items():
            if remote and host and user:
                _cmd = self._cmd_exec_remote(cmd, host, user)
            else:
                _cmd = self._cmd_exec_local(cmd)
            built_cmds[_id] = _cmd
        return built_cmds

    def _parse_outputs(self, outputs):
        parsed_outs = {}
        for _id,output in outputs.items():
            (ret, out) = output
            # logger.debug('ret %s, output %s', ret, out)
            parsed_outs[_id] = self._output(ret, out)
        return parsed_outs

    def run(self, cmds, **kwargs):
        stop = False
        timeout = 0
        remote = False
        host = None
        user = None
        if 'stop' in kwargs:
            stop = kwargs['stop']
        if 'timeout' in kwargs:
            timeout = kwargs['timeout']
        if 'remote' in kwargs:
            remote = kwargs['remote']
            if 'host' in kwargs and 'user' in kwargs:
                host = kwargs['host']
                user = kwargs['user']
            else:
                logger.debug("No user or host provided for remote exec")
                raise Exception

        _built_cmds = self._build_cmd(cmds, remote=remote, host=host, user=user)
        _outputs = self._multi_processor.run(_built_cmds, stop, timeout)
        _outs = self._parse_outputs(_outputs)
        return _outs


class Actuator(Executor):
    def __init__(self):
        Executor.__init__(self)
        self.stimulus = {}
        self.evals = {}
        self.acts = {}
        self._cfg = None
        self._loader = Loader()
        
    def get_acts(self):
        return self.acts

    def cfg(self, cfg):
        self._cfg = cfg
        self._load_acts()

    def _load_acts(self):
        files = self._loader.load_files(
            self._cfg.get("folder"),
            self._cfg.get("prefix"),
            self._cfg.get("suffix"),
            self._cfg.get("full_path")
        )
        
        for file in files:
            cmd = {1:[file, '--info']}
            output = self.run(cmd)
            for _, (ack, out) in output.items():
                if ack:
                    act_info = json.loads(out)
                    if act_info.get('id', None):
                        act_info['file'] = file
                        self.acts[act_info['id']] = act_info
                else:
                    logger.debug("Could not load act %s", cmd)

    def _parse_act_args(self, stimulus, act):
        stimulus_args = stimulus.get('parameters')
        args = []
        for k,v in stimulus_args.items():
            if v and str(v) != 'None':
                arg = '--'+k
                args.append(arg)
                args.append(v)
        return args

    def _parse_act_cmd(self, stimulus):
        act_cmd = None
        if stimulus['id'] in self.acts:
            act = self.acts[stimulus['id']]
            args = self._parse_act_args(stimulus, act)
            act_cmd = [act['file']]
            act_cmd.extend(args)
        return act_cmd

    def _load_instruction(self, inst):
        actions = inst.get('actions')
        for _,action in actions.items():
            self.stimulus[action.get('id')] = action.get('stimulus')

    def _exec_stimulus(self):
        self.evals = {}
        act_cmds = {}
        for _id,stimulus in self.stimulus.items():
            act_cmds[_id] = self._parse_act_cmd(stimulus)
        if act_cmds:
            outputs = self.run(act_cmds)
            self._check_outputs(outputs)

    def _check_outputs(self, outputs):
        for _id, output in outputs.items():
            ack, out = output
            stm = self.stimulus[_id]
            runner_id = stm.get('id')
            if ack:
                self.evals[_id] = (True, runner_id, json.loads(out))
            else:
                self.evals[_id] = (False, runner_id, out)

    def act(self, instruction):
        self.stimulus = {}
        self._load_instruction(instruction)
        self._exec_stimulus()
        return self.evals
