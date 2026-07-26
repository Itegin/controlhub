import asyncio
import json
import os

from dotenv import load_dotenv
from websockets import ConnectionClosed
from websockets.asyncio.client import connect

load_dotenv()

SERVER_IP = os.environ["SERVER_IP"]
AGENT_TOKEN = os.environ["AGENT_TOKEN"]
SERVER_URL = f"ws://{SERVER_IP}:8000/ws/agent"

MAX_BACKOFF = 30


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
