import asyncio
import os

from handlers.audio import get_muted, get_volume
from handlers.process import is_process_running

POLL_INTERVAL_SECONDS = 1


async def poll_loop(send_state_callback) -> None:
    while True:
        try:
            snapshot = {
                "mic.muted": get_muted("microphone"),
                "speaker.volume": get_volume("speaker"),
                "speaker.muted": get_muted("speaker"),
                "vpn.running": is_process_running(os.environ.get("VPN_PROCESS_NAME", "")),
            }
        except Exception as exc:
            # Transient audio-stack errors (device swap mid-read, etc.)
            # shouldn't kill the agent's connection; just skip this tick.
            print(f"Poll error: {exc}")
        else:
            # Sent unconditionally every tick; the backend (app.state.update_state)
            # is what dedupes into change-only broadcasts, so no diffing here.
            await send_state_callback(snapshot)

        await asyncio.sleep(POLL_INTERVAL_SECONDS)
