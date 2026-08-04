import logging

from fastapi import WebSocket

logger = logging.getLogger("controlhub.ws")


class ConnectionHub:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()
        self.agents: dict[str, WebSocket] = {}

    def register_client(self, ws: WebSocket) -> None:
        self.clients.add(ws)

    def unregister_client(self, ws: WebSocket) -> None:
        self.clients.discard(ws)

    def register_agent(self, name: str, ws: WebSocket) -> None:
        if name in self.agents:
            logger.warning("Agent '%s' already registered, overwriting existing connection", name)
        self.agents[name] = ws

    def unregister_agent(self, name: str) -> None:
        self.agents.pop(name, None)

    async def broadcast_to_clients(self, message: dict) -> None:
        # Copy to a list first: a client disconnecting mid-broadcast would
        # otherwise mutate self.clients while we're iterating over it.
        for ws in list(self.clients):
            try:
                await ws.send_json(message)
            except Exception:
                logger.warning("Failed to send to client, dropping connection")
                self.clients.discard(ws)

    async def send_to_agent(self, name: str, message: dict) -> bool:
        ws = self.agents.get(name)
        if ws is None:
            return False
        try:
            await ws.send_json(message)
            return True
        except Exception:
            logger.warning("Failed to send to agent '%s', dropping connection", name)
            self.agents.pop(name, None)
            return False


# Single-user, single-process app: a module-level singleton is simplest and
# avoids wiring a DI container just to share one hub between routes.
hub = ConnectionHub()
