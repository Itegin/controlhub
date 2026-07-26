import asyncio
import json
import os

from dotenv import load_dotenv
from websockets import ConnectionClosed
from websockets.asyncio.client import connect

from handlers.process import handle_launch_app

load_dotenv()

SERVER_IP = os.environ["SERVER_IP"]
AGENT_TOKEN = os.environ["AGENT_TOKEN"]
SERVER_URL = f"ws://{SERVER_IP}:8000/ws/agent"

MAX_BACKOFF = 30

HANDLERS = {"launch_app": handle_launch_app}


async def run() -> None:
    async with connect(SERVER_URL) as ws:
        await ws.send(json.dumps({
            "type": "hello",
            "agent": "windows",
            "version": "0.1.0",
            "token": AGENT_TOKEN,
        }))
        print(f"Connected to {SERVER_URL}")

        async for raw in ws:
            print(f"Received: {raw}")
            message = json.loads(raw)

            cmd = message.get("cmd")
            if cmd is None:
                continue

            handler = HANDLERS.get(cmd)
            if handler is None:
                await ws.send(json.dumps({
                    "type": "result",
                    "req_id": message["req_id"],
                    "status": "error",
                    "message": f"unknown command: {cmd}",
                }))
                continue

            result = handler(message["params"])
            await ws.send(json.dumps({
                "type": "result",
                "req_id": message["req_id"],
                "item_id": message.get("item_id"),
                **result,
            }))


async def main() -> None:
    backoff = 1
    while True:
        try:
            await run()
            # A clean return still means the connection ended (server closed
            # it normally); reset backoff since the connection had succeeded.
            backoff = 1
        except (ConnectionClosed, OSError) as exc:
            print(f"Disconnected ({exc})")

        print(f"Reconnecting in {backoff}s")
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, MAX_BACKOFF)


if __name__ == "__main__":
    asyncio.run(main())
