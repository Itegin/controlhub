import asyncio
import logging
import os
import secrets
import time

from fastapi import APIRouter, Header, HTTPException

from app.agent_requests import create_future, discard_future
from app.ws.hub import hub

logger = logging.getLogger("controlhub.api")

router = APIRouter()

# Same budget as the WebSocket execute path (app.ws.client): every command
# sent to an agent resolves within 5s -- ok, error, or timeout.
AGENT_REQUEST_TIMEOUT = 5.0


def _check_agent_token(x_agent_token: str | None) -> None:
    # Same shared-secret gate as backend/app/api/items.py and workspaces.py:
    # this route makes a connected agent do work and hands its answer back to
    # the caller, so it gets the same gate as the rest of the Studio surface.
    expected_token = os.environ.get("AGENT_TOKEN")
    # "not expected_token" guards against AGENT_TOKEN being unset entirely:
    # without it, a missing env var (None) would equal a missing header
    # (None) and silently let an unauthenticated request through.
    if not expected_token or x_agent_token != expected_token:
        raise HTTPException(status_code=401, detail="missing or invalid X-Agent-Token")


def _generate_req_id() -> str:
    # Same shape as frontend/js/ws.js's generateReqId() -- millisecond
    # timestamp plus a short random suffix -- because ids from both sources
    # share one req_id keyspace once they reach the agent. The "api-" prefix
    # makes a server-issued id impossible to confuse with a client-issued one.
    return f"api-{int(time.time() * 1000)}-{secrets.token_hex(4)}"


@router.post("/api/agents/{agent_name}/list_devices")
async def list_devices(agent_name: str, x_agent_token: str | None = Header(None)) -> dict:
    _check_agent_token(x_agent_token)

    # Checked before sending rather than left to the timeout: the agent link
    # is a single persistent socket, so "not in hub.agents" is already a
    # definitive answer -- same reasoning as _handle_execute in ws/client.py.
    if agent_name not in hub.agents:
        raise HTTPException(status_code=404, detail="agent offline")

    req_id = _generate_req_id()
    # Registered before the send, not after: the agent could reply before
    # this coroutine is scheduled again, and a reply arriving with no future
    # registered is silently dropped.
    fut = create_future(req_id)

    sent = await hub.send_to_agent(agent_name, {"cmd": "list_devices", "params": {}, "req_id": req_id})
    if not sent:
        # The socket died between the membership check above and the send;
        # send_to_agent already dropped it from the hub. No point parking for
        # 5s on a reply that can no longer come.
        discard_future(req_id)
        raise HTTPException(status_code=404, detail="agent offline")

    try:
        result = await asyncio.wait_for(fut, timeout=AGENT_REQUEST_TIMEOUT)
    except asyncio.TimeoutError:
        discard_future(req_id)
        logger.warning("Agent '%s' did not answer list_devices req_id=%s in time", agent_name, req_id)
        raise HTTPException(status_code=504, detail="agent did not respond in time")

    # Returned verbatim, deliberately. A 4xx/5xx from this endpoint means the
    # *request* failed (agent offline, no reply in time); the agent handler's
    # own {"status": "error", ...} is a successful round-trip reporting a
    # failed operation, and passes through as a normal 200 -- the same
    # distinction ws/client.py already draws between "agent offline" and a
    # result the agent actually sent back.
    return result
