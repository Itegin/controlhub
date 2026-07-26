import json
import logging

from fastapi import WebSocket, WebSocketDisconnect

from app.models import bump_press_count, get_item
from app.ws.hub import hub

logger = logging.getLogger("controlhub.ws")


async def client_ws(ws: WebSocket) -> None:
    await ws.accept()
    hub.register_client(ws)
    logger.info("Client connected")

    try:
        while True:
            message = await ws.receive_json()
            logger.info("Client sent: %s", message)
            if message.get("cmd") == "execute":
                await _handle_execute(message)
    except WebSocketDisconnect:
        pass
    finally:
        hub.unregister_client(ws)
        logger.info("Client disconnected")


async def _handle_execute(message: dict) -> None:
    req_id = message.get("req_id")
    item_id = message.get("item_id")

    item = get_item(item_id)
    if item is None:
        await hub.broadcast_to_clients(
            {"type": "result", "req_id": req_id, "status": "error", "message": "item not found"}
        )
        return

    bump_press_count(item_id)

    # Check connectivity before sending rather than waiting on a response
    # timeout: the agent link is a single persistent socket, so "not in
    # hub.agents" is already a definitive answer, not a transient race.
    if item["target"] not in hub.agents:
        await hub.broadcast_to_clients(
            {
                "type": "result",
                "req_id": req_id,
                "item_id": item_id,
                "status": "error",
                "message": "agent offline",
            }
        )
        return

    await hub.send_to_agent(
        item["target"],
        {
            "cmd": item["type"],
            "params": json.loads(item["params"]),
            "req_id": req_id,
            "item_id": item_id,
        },
    )
