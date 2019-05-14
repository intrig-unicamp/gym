import logging
import json
import argparse
import subprocess
import time

logger = logging.getLogger(__name__)


class Processor:
    def __init__(self):
        self.process = None

    def start_process(self, args, stop=False, timeout=60):
        try:
            p = subprocess.Popen(args,
                stdin = subprocess.PIPE,
                stdout = subprocess.PIPE,
                stderr = subprocess.PIPE,
                )
            self.process = p
            logger.info('process started %s', p.pid)
            if stop:
                if self.stop_process(timeout):
                    out, err = p.communicate()
                    return (p.returncode, out, err)
                else:
                    self.process = None
                    return (-1, None, None)
            else:
                out, err = p.communicate()
                logger.info('process stopped %s', self.process.pid)
                self.process = None
                return (p.returncode, out, err)
        except OSError:
            self.process = None
            return (-1, None, None)

    def stop_process(self, timeout):
        import ast
        timeout = float(ast.literal_eval(timeout))
        if self.process:
            time.sleep(timeout)
            self.process.kill()
            logger.info('process stopped %s', self.process.pid)
            self.process = None
            return True
        return False


class Launcher:
    def __init__(self, parameters=None, default=None):
        self._settings = None
        self._parameters = parameters
        self.default_parameters = default
        self.parser = argparse.ArgumentParser(description='Listener')
        self.add_args()

    def add_args(self):
        if self._parameters:
            for param in self._parameters:
                arg = '--' + param
                self.parser.add_argument(arg,
                                        action="store",
                                        required=False)
        if self.default_parameters:
            for param in self.default_parameters:
                arg = '--' + param
                self.parser.add_argument(arg, 
                                        action="store_true",
                                        required=False)

    def parse_args(self):
        self._settings = self.parser.parse_args()
        return self._settings


class Listener:
    PARAMS = {
        "info": "info",
    }

    def __init__(self, id, name, parameters, metrics):
        self.id = id
        self.name = name
        self.parameters = parameters
        self.metrics = metrics
        self._output = {}
        self._command = None
        self._default_params = Listener.PARAMS
        self._parameters = dict(list(self.parameters.items()) + list(self._default_params.items()))
        self._launcher = Launcher(parameters=parameters, default=self._default_params)
        self._processor = Processor()

    def info(self):
        inf = self.items(dic=True)
        return inf

    def items(self, dic=False):
        if dic:
            return dict([(i, self.__dict__[i]) for i in self.__dict__.keys() if i[:1] != '_'])
        else:
            return [i for i in self.__dict__.keys() if i[:1] != '_']

    def serialize(self, opts):
        kwargs = dict(opts._get_kwargs())
        kwargs = {key:value for (key, value) in kwargs.items() if value}
        options = {}
        for k, v in kwargs.items():
            if k in self._parameters:
                options[self._parameters[k]] = v
            else:
                logger.info("serialize option not found %s", k)
        return options

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
        raise NotImplementedError

    def listen(self, args):
        cmd = []
        cmd.append(self._command)
        opts, stop, timeout = self.options(args)

        if "info" in opts:
            self._output = self.info()
            return True

        if self._command:
            cmd.extend(opts)
            ret, out, err = self._processor.start_process(cmd, stop, timeout)
        else:
            ret = 0
            err = None
            out = self.monitor(opts)

        if ret == 0:
            logger.info("process executed %s", ret)
            self._output = self.parser(out)
        elif stop and ret == -9:
            logger.info("process executed and stopped %s", ret)
            self._output = self.parser(out)
        else:
            logger.info("process error %s, %s", out, err)
            self._output = {"error": err}
        
    def monitor(self, opts):
        return {}

    def to_json(self, value):
        return json.dumps(value, sort_keys=True, indent=4)

    def main(self):
        settings = self._launcher.parse_args()
        self.listen(settings)
        output = self.to_json(value=self._output)
        return output