import logging
import gevent
import json 
import requests
from urlparse import urlparse
from flask import Flask, request, make_response
from flask_restful import Api, Resource
from gevent.pywsgi import WSGIServer
from gevent.queue import Empty, Queue

import signal
from time import sleep
import subprocess
from multiprocessing import Process
from multiprocessing import Queue as MQueue


from topos.topo import Experiment


logger = logging.getLogger(__name__)


class Resources(Resource):
    settings = {
        'content-type':'application/json'
    }
    api = Api()

    def __init__(self, **kwargs):
        self.handlers = kwargs['handlers']
        self.content_type = kwargs['content-type']
        Resources.settings['content-type'] = self.content_type
        Resources.api = kwargs['api']

    def parse_path(self, path):
        prefix, call = '', ''
        if path:
            try:
                prefix, call = path.rsplit('/', 1)
            except:
                prefix = path
                call = ""
            call = call.replace('-', '_')
            prefix = prefix.replace('-', '_')
        return prefix, call

    @api.representation(settings['content-type'])
    def post(self, path=None):
        method = 'post'
        prefix, call = self.parse_path(path)
        data = request.data
        address = request.remote_addr
        handler = self.handlers[method]
        ack, reply = handler((address, prefix, call, data))
        code = 200 if ack else 500
        resp = make_response(reply, code)
        resp.headers['Content-Type'] = self.content_type
        return resp

    @api.representation(settings['content-type'])
    def get(self, path=None):
        method = 'get'
        prefix, call = self.parse_path(path)
        data = request.data
        address = request.remote_addr
        handler = self.handlers[method]
        ack, reply = handler((address, prefix, call, data))
        code = 200 if ack else 500
        resp = make_response(reply, code)
        resp.headers['Content-Type'] = self.content_type
        return resp

    @api.representation(settings['content-type'])
    def put(self, path=None):
        method = 'put'
        prefix, call = self.parse_path(path)
        data = request.data
        address = request.remote_addr
        handler = self.handlers[method]
        ack, reply = handler((address, prefix, call, data))
        code = 200 if ack else 500
        resp = make_response(reply, code)
        resp.headers['Content-Type'] = self.content_type
        return resp

    @api.representation(settings['content-type'])
    def delete(self, path=None):
        method = 'delete'
        prefix, call = self.parse_path(path)
        data = request.data
        address = request.remote_addr
        handler = self.handlers[method]
        ack, reply = handler((address, prefix, call, data))
        code = 200 if ack else 500
        resp = make_response(reply, code)
        resp.headers['Content-Type'] = self.content_type
        return resp


class WebServer():
    def __init__(self, url, handlers,
                 content_type='application/json'):
        self.path = "/<path:path>"
        self.prefix = '/'
        self.app = app = Flask(__name__)
        self.api = Api(app)
        self.url = url
        self.host = urlparse(self.url).hostname
        self.port = urlparse(self.url).port
        self.resource = {
            'class': Resources,
            'path': self.path,
            'prefix': self.prefix,
        }
        self.settings = {
            'handlers': handlers,
            'content-type': content_type,
            'api': self.api,
        }
        self.server = None

    def add_resources(self, resource, **kwargs):
        self.api.add_resource(resource['class'], resource['path'], resource['prefix'],
                              resource_class_kwargs=kwargs)

    def init(self, debug=False, reloader=False):
        self.add_resources(self.resource, **self.settings)
        self.server = WSGIServer((self.host, self.port), self.app)
        self.server.serve_forever()


class WebClient():
    headers = {'Content-Type': 'application/json'}

    def send_msg(self, _type, url, message, **kwargs):
        response = None
        try:
            if _type == 'post':
                response = requests.post(url, headers=WebClient.headers, data=message, **kwargs)
            elif _type == 'put':
                response = requests.put(url, headers=WebClient.headers, data=message, **kwargs)
            elif _type == 'get':
                response = requests.get(url, headers=WebClient.headers, data=message, **kwargs)
            else:
                response = requests.delete(url, headers=WebClient.headers, data=message, **kwargs)
        except requests.RequestException as exception:
            logger.info('Requests fail - exception %s', exception)
            response = None
        finally:
            reply = self.__process_msg_response(response)
            logger.info('Requests - response %s', response)
            if reply:
                return reply.text
            return reply

    def __process_msg_response(self, response):
        try:
            if response:
                response.raise_for_status()
        except Exception as exception:
            logging.info("Response exception %s", exception)
            response = None
        finally:
            return response


class Playground:
    def __init__(self, in_queue, out_queue):
        self.exp_topo = None
        self.running = False
        self.in_queue = in_queue
        self.out_queue = out_queue
        self.init()

    def init(self):
        # self.clear()
        self.mon_queue(self.in_queue)

    def mon_queue(self, q):
        logger.info("mon_queue started")
        while True:
            try:
                msg = q.get_nowait()
            except:
                sleep(1)
            else:
                cmd = msg.get("cmd")
                params = msg.get("params")
                
                logger.info("input - play - cmd %s", cmd)

                if cmd == "start":
                    reply = self.start(params)
                elif cmd == "stop":
                    reply = self.stop()
                else:
                    reply = {"msg": ""}

                self.out_queue.put(reply)

                if cmd == "stop":
                    break

    def start(self, msg):
        scenario = msg.get("scenario")
        instance = msg.get("instance")
        logger.info("received scenario %s", scenario)
        self.exp_topo = Experiment(instance, scenario)
        hosts_info = self.exp_topo.start()
        self.running = True
        logger.info("expo_topo running %s", self.running)
        logger.info("hosts info %s", hosts_info)
        ack = {
            'running': self.running,
            'instance': instance,
            'info': hosts_info, 
        }
        return ack

    def stop(self):
        self.exp_topo.stop()
        self.running = False
        logger.info("expo_topo running %s", self.running)
        ack = {'running': self.running}
        self.exp_topo = None
        return ack

    def alive(self):
        return self.running

    def clear(self):
        exp = Experiment(0, None)
        exp.mn_cleanup()
        logger.info("Experiments cleanup OK")


class Scenario:
    def __init__(self, url):
        self.handlers = {
            'post':self.post_handler,
            'put': self.put_handler,
            'delete': self.delete_handler,
        }
        self.server = WebServer(url, self.handlers)
        # self.playground = Playground()
        self.playing = None
        self.running_playground = False
        self.in_queue = MQueue()
        self.out_queue = MQueue()
        self._ids = 0
        self.in_q = Queue()
        self.client = WebClient()

    def put_handler(self, msg):
        address, prefix, request, data = msg
        logger.info("put_handler - address %s, prefix %s, request %s",
                    address, prefix, request)
        self.in_q.put(data)
        return True, 'Ack'

    def delete_handler(self, msg):
        return False, 'Nack'

    def post_handler(self, msg):
        address, prefix, request, data = msg
        logger.info("post_handler - address %s, prefix %s, request %s",
                    address, prefix, request)
        self.in_q.put(data)
        return True, 'Ack'
        
    def init(self):
        Playground(self.in_queue, self.out_queue)
        self.running_playground = False
        print("Finished Playground")

    def play(self):
        self.in_queue = MQueue()
        self.out_queue = MQueue()
        self.playing = Process(target=self.init)
        self.playing.start()
        self.running_playground = True

    def call(self, cmd, params):
        logger.info("cmd %s call", cmd)
        msg = {"cmd": cmd, "params": params}
        self.in_queue.put(msg)
        reply = self.out_queue.get()
        return reply

    def check_playground(self):
        self.playing.terminate()
        sleep(0.1)
        logger.info("playground alive %s", self.playing.is_alive())        
        logger.info("playground exitcode ok %s", self.playing.exitcode == -signal.SIGTERM)        
        self.running_playground = False
        self.playing = None
        self.in_queue = None
        self.out_queue = None

    def handle(self, msg):
        msg_id = msg.get("id")
        data = msg.get("params")
        cmd = data.get("request")
        continuous = data.get("continuous")
        callback = data.get("callback")
        prefix = data.get("prefix", "0")
        outputs = []
        built = dict()
        built["id"] = msg_id
        built["response"] = "built"
        built["to"] = callback + "/" + prefix
        result = {}
        logger.info("received msg: request %s, continuous %s, callback %s", cmd, continuous, callback)
        if continuous:
            if self.running_playground:
                stop_info = self.call("stop", None)
                self.check_playground()

        if cmd == "start":
            if self.running_playground:
                stop_info = self.call("stop", None)
                self.check_playground()

            self.play()
            start_info = self.call("start", data)
            result["ack"] = start_info
            self._ids += 1
            built["result"] = result
            outputs.append(built)

        elif cmd == "stop":
            if self.running_playground:
                stop_info = self.call("stop", None)
                self.check_playground()
                result["ack"] = stop_info
                built["result"] = result
                outputs.append(built)
        else:
            logger.info("Handle no cmd in request data")
        return outputs

    def serve(self):
        _jobs = self._create_jobs()
        gevent.joinall(_jobs)
        
    def _create_jobs(self):
        web_server_thread = gevent.spawn(self.server.init)
        msgs_loop = gevent.spawn(self._process_msgs)
        jobs = [web_server_thread, msgs_loop]
        return jobs

    def send(self, url, data, method='post'):
        logger.info("sending msg to %s - data %s", url, data)
        answer = self.client.send_msg(method, url, data)
        return answer

    def exit(self, outputs):
        if outputs:
            for output in outputs:
                url = output["to"]
                del output["to"]
                output_json = json.dumps(output)
                if url:
                    exit_reply = self.send(url, output_json)
                    logger.info("exit_reply %s", exit_reply)
                else:
                    logger.info("No callback provided for %s", output_json)
        else:
            logger.info("nothing to output")

    def _process_msgs(self):
        while True:
            try:
                data = self.in_q.get()
            except Empty:
                continue
            else:
                logger.info(data)
                # msg = Message.parse(data, rpc_map)                
                msg = json.loads(data)
                logger.info(msg)
                if msg:                
                    outputs = self.handle(msg)
                    self.exit(outputs)
                else:
                    logger.info("could not parse data %s", data)


if __name__ == "__main__":
    level = logging.DEBUG
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.setLevel(level)
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(level)
    logger = logging.getLogger(__name__)

    url = "http://0.0.0.0:7878"
    sc = Scenario(url)
    sc.serve()
