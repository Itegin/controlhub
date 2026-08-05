import asyncio
import json
import os
import sys

import win32api
import win32event
import winerror
from dotenv import load_dotenv
from websockets import ConnectionClosed
from websockets.asyncio.client import connect

from handlers.audio import (
    handle_audio_mute_toggle,
    handle_audio_switch,
    handle_audio_volume_set,
    handle_list_devices,
)
from handlers.process import handle_force_stop, handle_launch_app, handle_process_toggle
from handlers.screenshot import handle_screenshot
from poller import poll_loop

load_dotenv()

SERVER_IP = os.environ["SERVER_IP"]
AGENT_TOKEN = os.environ["AGENT_TOKEN"]
AGENT_NAME = os.environ.get("AGENT_NAME", "windows")
# Previously hardcoded 8000 here -- SERVER_PORT was documented in
# .env.example but never actually read anywhere, in violation of
# CLAUDE.md's own "SERVER_PORT must be read from .env, never hardcoded"
# constraint. Fixed here since the screenshot upload below needs the same
# value and must not become a second hardcoded copy of it.
SERVER_PORT = os.environ.get("SERVER_PORT", "8000")
SERVER_URL = f"ws://{SERVER_IP}:{SERVER_PORT}/ws/agent"

MAX_BACKOFF = 30
SINGLETON_MUTEX_NAME = "Global\\ITDeckAgentSingleton"

HANDLERS = {
    "launch_app": handle_launch_app,
    "audio_mute_toggle": handle_audio_mute_toggle,
    "audio_volume_set": handle_audio_volume_set,
    "audio_switch": handle_audio_switch,
    "list_devices": handle_list_devices,
    "screenshot": handle_screenshot,
    "process_toggle": handle_process_toggle,
    "force_stop": handle_force_stop,
}


async def _receive_loop(ws) -> None:
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

        # force_stop is the one handler that needs more than its own
        # params: it derives a process name from the ORIGINAL item's type
        # (see handle_force_stop), which backend/app/ws/client.py sends
        # alongside the (possibly overridden) cmd specifically for this.
        if cmd == "force_stop":
            result = handler(message["params"], message.get("item_type"))
        else:
            result = handler(message["params"])
        await ws.send(json.dumps({
            "type": "result",
            "req_id": message["req_id"],
            "item_id": message.get("item_id"),
            **result,
        }))


async def run() -> None:
    async with connect(SERVER_URL) as ws:
        await ws.send(json.dumps({
            "type": "hello",
            "agent": AGENT_NAME,
            "version": "0.1.0",
            "token": AGENT_TOKEN,
        }))
        print(f"Connected to {SERVER_URL}")

        async def send_state(snapshot: dict) -> None:
            await ws.send(json.dumps({"type": "state", "data": snapshot}))

        # Both run for the lifetime of this connection; if either raises
        # (e.g. the socket drops mid-send) gather propagates it up to main()'s
        # reconnect loop, which tears down and retries the whole connection.
        await asyncio.gather(_receive_loop(ws), poll_loop(send_state))


async def main() -> None:
    # Named mutex, not a lock file: Windows releases it automatically if the
    # owning process dies, so there's no stale-lock cleanup to write. This
    # guards against the Scheduled Task autostart and a manual launch both
    # running at once -- two agents silently overwriting each other's
    # WebSocket registration on the backend caused a day of contradictory
    # VPN-state bugs.
    win32event.CreateMutex(None, False, SINGLETON_MUTEX_NAME)
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        print("Another instance is already running -- exiting.")
        sys.exit(1)

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
