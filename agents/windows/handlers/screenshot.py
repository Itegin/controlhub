import os

import mss
import mss.tools
import requests


def _capture_primary_monitor_png() -> bytes:
    with mss.MSS() as sct:
        # monitors[0] is the combined virtual screen across every display,
        # not a single monitor. is_primary isn't guaranteed to land on
        # monitors[1] -- Windows lets any monitor be set as primary, and
        # mss lists them in OS enumeration order, not primary-first -- so
        # search for the flagged one; fall back to index 1 only if a given
        # mss/platform combination ever doesn't populate the flag.
        monitor = next((m for m in sct.monitors[1:] if m.get("is_primary")), sct.monitors[1])
        shot = sct.grab(monitor)
        return mss.tools.to_png(shot.rgb, shot.size)


def handle_screenshot(params: dict) -> dict:
    try:
        png_bytes = _capture_primary_monitor_png()
    except Exception as e:
        return {"status": "error", "message": str(e)}

    try:
        # Read here, not at module level: agent.py imports this module
        # before it calls load_dotenv(), so SERVER_IP/SERVER_PORT/AGENT_TOKEN
        # wouldn't be populated yet if read at import time in this file.
        server_ip = os.environ["SERVER_IP"]
        server_port = os.environ.get("SERVER_PORT", "8000")
        # Same AGENT_TOKEN the agent already sends in its WebSocket "hello"
        # (see agent.py's `run()`), reused here as a lightweight shared
        # secret for this HTTP route -- not a separate credential, and not
        # a full auth system, just enough to keep the upload endpoint from
        # accepting anonymous writes from anything else on the LAN.
        agent_token = os.environ["AGENT_TOKEN"]

        response = requests.post(
            f"http://{server_ip}:{server_port}/api/screenshot",
            files={"file": ("screenshot.png", png_bytes, "image/png")},
            headers={"X-Agent-Token": agent_token},
            timeout=5,
        )
        response.raise_for_status()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
