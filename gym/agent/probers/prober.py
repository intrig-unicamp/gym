import logging
import json
import argparse
import subprocess
import time
from datetime import datetime

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
        # import ast
        # timeout = float(ast.literal_eval(timeout))
        logger.info('stopping process after %s', timeout)
        if self.process:
            #if process stop, usually server, so waits one second more
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
        self.parser = argparse.ArgumentParser(description='Prober')
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


class Prober:
    PARAMS = {
        "info": "info",
    }

    def __init__(self, id, name, parameters, metrics):
        self.id = id
        self.name = name
        self.parameters = parameters
        self.metrics = metrics
        self._type = "prober"
        self._call = ""
        self._tstart = None
        self._tstop = None
        self._output = {}
        self._command = None
        self._default_params = Prober.PARAMS
        self._parameters = dict(list(self.parameters.items()) + list(self._default_params.items()))
        self._launcher = Launcher(parameters=parameters, default=self._default_params)
        self._processor = Processor()

    def options(self, opts):
        raise NotImplementedError

    def parser(self, out):
        raise NotImplementedError

    def items(self, dic=False):
        if dic:
            return dict([(i, self.__dict__[i]) for i in self.__dict__.keys() if i[:1] != '_'])
        else:
            return [i for i in self.__dict__.keys() if i[:1] != '_']

    def info(self):
        inf = self.items(dic=True)
        return inf
        
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

    def source(self):
        source = {
            "id": self.id,
            "type": self._type,
            "name": self.name,
            "call": self._call,
        }
        return source

    def timestamp(self):
        ts = {
            "start": self._tstart,
            "stop": self._tstop,
        }
        return ts

    def probe(self, opts):
        cmd = []
        cmd.append(self._command)
        opts, stop, timeout = self.options(opts)

        if "info" in opts:
            self._output = self.info()
            return
        
        cmd.extend(opts)

        self._call = " ".join(cmd)

        self._tstart = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        ret, out, err = self._processor.start_process(cmd, stop, timeout)
        self._tstop = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%fZ')

        output = out.decode('UTF-8')
        error = err.decode('UTF-8')
        
        if ret == 0:
            logger.info("process executed %s", ret)
            metrics = self.parser(output)
        elif stop and ret == -9:
            logger.info("process executed and stopped %s", ret)
            metrics = self.parser(output)
        else:
            logger.info("process error %s, %s", output, error)
            metrics = {"error": error}   

        self._output = {
            "metrics": metrics, 
            "timestamp": self.timestamp(),
            "source": self.source(),
        }

    def to_json(self, value):
        return json.dumps(value, sort_keys=True, indent=4)

    def main(self):
        settings = self._launcher.parse_args()
        self.probe(settings)
        output = self.to_json(self._output)
        return output