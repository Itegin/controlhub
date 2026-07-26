import logging

from fastapi import WebSocket, WebSocketDisconnect

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
    except WebSocketDisconnect:
        pass
    finally:
        hub.unregister_client(ws)
        logger.info("Client disconnected")
