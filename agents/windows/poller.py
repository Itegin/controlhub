import asyncio

from handlers.audio import get_mic_muted

POLL_INTERVAL_SECONDS = 1


async def poll_loop(send_state_callback) -> None:
    while True:
        try:
            snapshot = {"mic.muted": get_mic_muted()}
        except Exception as exc:
            # Transient audio-stack errors (device swap mid-read, etc.)
            # shouldn't kill the agent's connection; just skip this tick.
            print(f"Poll error: {exc}")
        else:
            # Sent unconditionally every tick; the backend (app.state.update_state)
            # is what dedupes into change-only broadcasts, so no diffing here.
            await send_state_callback(snapshot)

        await asyncio.sleep(POLL_INTERVAL_SECONDS)
