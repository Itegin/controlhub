import asyncio

# Deliberately separate from app.pending, which solves a different problem:
# pending.py only ever *broadcasts* a synthetic "timeout" result to every
# client and never hands a value back to one specific caller. This module is
# the request/response half -- an HTTP handler parks on a Future keyed by
# req_id and gets that agent's actual reply dict back.
_futures: dict[str, asyncio.Future] = {}


def create_future(req_id: str) -> asyncio.Future:
    # get_running_loop(), not get_event_loop(): this is only ever called from
    # inside a request handler, so a loop is always running, and binding the
    # future to that loop is what lets resolve_future() (running in the
    # agent's WebSocket task on the same loop) complete it.
    future = asyncio.get_running_loop().create_future()
    _futures[req_id] = future
    return future


def resolve_future(req_id: str, result: dict) -> None:
    # Called for *every* result an agent sends, and the vast majority --
    # ordinary execute/set_value replies -- have no future registered, so an
    # unknown req_id is a silent no-op, not an error.
    future = _futures.pop(req_id, None)
    # A late or duplicate result can arrive after the waiter already gave up
    # (timeout cancelled the future), so re-check done() before setting:
    # set_result() on a cancelled/completed future raises InvalidStateError.
    if future is not None and not future.done():
        future.set_result(result)


def discard_future(req_id: str) -> None:
    # Used by a waiter that timed out, so an agent replying minutes later
    # doesn't find a stale entry still sitting in the dict.
    _futures.pop(req_id, None)
