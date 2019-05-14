import logging
logger = logging.getLogger(__name__)

import sys
import json
import argparse
import inspect
import asyncio
import aiohttp
from aiohttp import web
from urllib.parse import urlparse

from gym.common.messages import Message, rpc_map
from gym.common.events import EventMsg


class App():
    def __init__(self):
        self.handler = None
        self.routes = []
        self.cfg = None
        self.loop = asyncio.get_event_loop()
        self.app = web.Application(loop=self.loop)
        self.in_queue = asyncio.Queue()
        self.out_queue = asyncio.Queue()

    def _register_event_callers(self, cls):
        for _k, m in inspect.getmembers(cls, inspect.ismethod):
            # logger.debug('instance %s k %s m %s', cls, _k, m)
            if hasattr(m, 'callers'):
                for ev_cls, c in m.callers.items():
                    cls.register_handler(ev_cls, m)

    async def start_background_tasks(self, app):
        app['dispatch'] = app.loop.create_task(self._output_loop())

    async def cleanup_background_tasks(self, app):
        app['dispatch'].cancel()
        await app['dispatch']

    def config_app(self):
        (inits, closes) = self.handler.get_jobs()
        
        self.app.on_startup.append(self.start_background_tasks)      
        self.app.on_cleanup.append(self.cleanup_background_tasks)

        if inits:
            self.app.on_startup.extend(inits)
        if closes:
            self.app.on_cleanup.extend(closes)

    def route(self, mode, path, call):
        route = {"mode": mode, "path":path, "call": call}
        self.routes.append(route)

    def config_routes(self, routes):
        for route in self.routes:
            self.app.add_routes([web.route(
                route.get("mode"), 
                route.get("path"), 
                route.get("call"),
            )])
    
    def set_routes(self):
        raise Exception("Routes not set for App")

    def main(self, url):
        self.config_app()
        self.set_routes()
        self.config_routes(self.routes)
        self._register_event_callers(self.handler)
        url_parsed = urlparse(url)
        host, port = url_parsed.hostname, url_parsed.port
        web.run_app(self.app, host=host, port=port)
        
    def validate_payload(self, raw_data):
        payload = raw_data.decode(encoding='UTF-8')
        try:
            msg_parsed = Message.parse(payload, rpc_map)
        except ValueError:
            logger.error('Message payload is not json serialisable')
            msg_parsed = None
        return msg_parsed

    async def handle(self, request):
        raw_data = await request.read()        
        msg = self.validate_payload(raw_data)
        if msg:            
            logger.debug("Handle msg from %s prefix/identifier %s",
                        request.remote, request.match_info['identifier'])
            
            msg.sender(request.remote, request.match_info['identifier'])
            ev_msg = EventMsg(msg)
            self.in_queue.put_nowait(ev_msg)
            return web.HTTPOk(text="Ack")
        else:
            return web.HTTPError(text="Bad Payload")

    async def send(self, url, data):
        async def post(session, url, data):
            try:
                async with session.post(url, data=data) as response:
                    resp_text = await response.text()
                    logger.info("Http post sent to %s: status %s - response %s", url, response.status, resp_text)
                    return resp_text
            except OSError as err:
                logger.info("Could not establish connection with %s", url)
                logger.debug("Error message: %s", err)

        async with aiohttp.ClientSession() as session:
            html = await post(session, url, data)
            return html

    async def _output_loop(self):
        logger.debug("Output Loop Started")
        while True:
            try:
                outputs = self.out_queue.get_nowait()
            except asyncio.QueueEmpty:
                await asyncio.sleep(0.5)
                # continue
            else:
                if outputs:
                    for output in outputs:
                        url, data = output.get_to(), output.to_json()
                        if url:
                            await self.send(url, data)
                        else:
                            logger.debug("No url provided for %s", output)
                else:
                    logger.debug("Nothing to output")
