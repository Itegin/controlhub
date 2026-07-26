import logging
import os

from fastapi import WebSocket, WebSocketDisconnect

from app.state import update_state
from app.ws.hub import hub

logger = logging.getLogger("controlhub.ws")


async def agent_ws(ws: WebSocket) -> None:
    await ws.accept()

    hello = await ws.receive_json()
    if hello.get("type") != "hello":
        await ws.close(code=4001)
        return

    # Check the token before registering the agent so a bad/missing token
    # never makes it into the hub, even for an instant.
    token = hello.get("token")
    if token != os.environ.get("AGENT_TOKEN"):
        await ws.close(code=4001)
        return

    name = hello.get("agent", "windows")
    hub.register_agent(name, ws)
    logger.info("Agent '%s' connected", name)
    await hub.broadcast_to_clients({"type": "agent_status", "agent": name, "status": "online"})

    try:
        while True:
            message = await ws.receive_json()
            logger.info("Agent '%s' sent: %s", name, message)
            if message.get("type") == "result":
                await hub.broadcast_to_clients(message)
            elif message.get("type") == "state":
                changed = update_state(message["data"])
                # Skip the broadcast entirely when nothing changed (e.g. a
                # heartbeat resending the same value) to avoid spamming clients.
                if changed:
                    logger.info("State changed: %s", changed)
                    await hub.broadcast_to_clients({"type": "state", "data": changed})
    except WebSocketDisconnect:
        pass
    finally:
        hub.unregister_agent(name)
        logger.info("Agent '%s' disconnected", name)
        await hub.broadcast_to_clients({"type": "agent_status", "agent": name, "status": "offline"})
