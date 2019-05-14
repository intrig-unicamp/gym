import sys
import json
import asyncio
import aiohttp
from aiohttp import web
from urllib.parse import urlparse


class SimpleWebServer:
    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self.app = web.Application(loop=self.loop)

    async def check_ack(self):
        asyncio.sleep(1)
        print("Closing WebServer")

    def save_post(self, data):
        print("Saving post data into vnf-br.json")
        filename = "./vnf-br.json"
        with open(filename, 'w') as outfile:
            json.dump(data, outfile, indent=4, sort_keys=True)
            return True
        return False

    async def post(self, request):
        from_id = request.match_info['id']
        print("Received msg from id", from_id)
        reply = web.HTTPOk(text="Ack")
        try:
            raw_data = await request.read()        
            payload = raw_data.decode(encoding='UTF-8')
            data = json.loads(payload)
            self.save_post(data)
        except Exception as e:
            print("Could not save data to file")
            print(e)
            reply = web.HTTPBadRequest()
        finally:
            self.app.loop.create_task(self.check_ack())
            return reply

    def run(self, url):
        self.app.add_routes([web.route("POST", "/{id}", self.post)])
        url_parsed = urlparse(url)
        host, port = url_parsed.hostname, url_parsed.port
        print("Waiting for Player VNF-BR")
        web.run_app(self.app, host=host, port=port)


if __name__ == "__main__":
    app = SimpleWebServer()
    app.run("http://127.0.0.1:7879")