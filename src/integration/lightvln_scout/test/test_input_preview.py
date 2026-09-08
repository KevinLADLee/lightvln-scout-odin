"""The ROS preview must carry the bytes that actually crossed the WebSocket."""

import asyncio
import base64
import time

import cv2
import numpy as np
from aiohttp import web

from lightvln_scout.image_processing import ImagePreprocessor, ScoutFrameEncoder
from vln_client.vln_client import VlnClient


class Logger:
    def info(self, message):
        pass

    def warning(self, message):
        pass


def test_completed_request_exposes_exact_sent_jpeg():
    async def scenario():
        received = []

        async def handler(request):
            socket = web.WebSocketResponse()
            await socket.prepare(request)
            async for message in socket:
                data = message.json()
                if data['action'] == 'login':
                    await socket.send_json({'action': 'login', 'data': {'rc': 0}})
                elif data['action'] == 'next':
                    received.append(base64.b64decode(data['data']['image']))
                    await socket.send_json({'action': 'next', 'data': {
                        'rc': 0, 'seq': data['data']['seq'], 'actions': [],
                        'pointing': {'frame_size': [448, 256]},
                    }})
            return socket

        application = web.Application()
        application.router.add_get('/', handler)
        runner = web.AppRunner(application)
        await runner.setup()
        site = web.TCPSite(runner, '127.0.0.1', 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        encoder = ScoutFrameEncoder(ImagePreprocessor())
        client = VlnClient(logger=Logger(), server_url=f'ws://127.0.0.1:{port}',
                           frame_encoder=encoder)
        try:
            client.start('follow the target')
            deadline = time.monotonic() + 3
            while not client.snapshot().connected and time.monotonic() < deadline:
                await asyncio.sleep(0.01)
            assert client.snapshot().connected
            assert client.offer_frame(
                stamp_sec=11, stamp_nanosec=22, width=140, height=160, step=420,
                rgb=np.zeros((160, 140, 3), dtype=np.uint8).tobytes(),
            )
            results = []
            deadline = time.monotonic() + 3
            while not results and time.monotonic() < deadline:
                await asyncio.sleep(0.01)
                results = client.take_results()
            assert len(results) == len(received) == 1
            assert encoder.take_jpeg(results[0].frame) == received[0]
            assert encoder.take_jpeg(results[0].frame) is None
            assert results[0].frame.stamp_sec == 11
            decoded = cv2.imdecode(np.frombuffer(received[0], np.uint8), cv2.IMREAD_COLOR)
            assert decoded.shape[:2] == (256, 448)
        finally:
            await asyncio.to_thread(client.close)
            await runner.cleanup()
    asyncio.run(scenario())
