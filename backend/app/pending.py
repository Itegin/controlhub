import asyncio

_pending: dict[str, asyncio.Task] = {}


def track(req_id: str, timeout_seconds: float, on_timeout) -> None:
    async def _timer() -> None:
        await asyncio.sleep(timeout_seconds)
        # Only fire if still pending: resolve() may have already cancelled
        # this task, but a cancellation can lose the race against the sleep
        # completing, so re-check membership rather than trusting the cancel.
        if req_id in _pending:
            del _pending[req_id]
            await on_timeout(req_id)

    _pending[req_id] = asyncio.ensure_future(_timer())


def resolve(req_id: str) -> None:
    # A late or duplicate result (agent replies twice, or replies after its
    # own timer already fired) must never crash the caller, so unknown
    # req_ids are a silent no-op rather than a KeyError.
    task = _pending.pop(req_id, None)
    if task is not None:
        task.cancel()
