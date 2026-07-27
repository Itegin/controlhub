# ControlHub Technical Audit — 2026-07-27

## Summary

The core execute→agent→result and state→broadcast pipelines work and are
reasonably careful (WAL-mode SQLite, idempotent startup fixups, exponential
reconnect backoff on the agent, defensive per-connection try/except in the
hub). The most serious gap is that a fire-and-forget request has no timeout
anywhere in the stack — if the agent never replies, the client tile hangs
forever with no error, and nothing server- or client-side ever notices. Two
asyncio.gather() usages (one in the Windows agent) can leave a sibling task
running briefly against a dead connection instead of being cancelled
cleanly. The frontend has essentially no state-update handling yet — `ws.js`
silently drops every `state` and `agent_status` message, so all of the
Evening 2 tile-coloring work is still ahead, not partially done. One
intentional debug log (`agent.py:35`) is confirmed still in place from Day
2/3, and malformed `item.params` JSON would crash a handler on both backend
and frontend rather than degrading gracefully. No `CLAUDE.md` exists in this
repo (checked working tree and full git history), so there was nothing to
diff the directory tree against — noted below as its own finding.

---

## Directory tree

```
.
├── agents/windows/
│   ├── .env, .env.example
│   ├── agent.py
│   ├── poller.py
│   ├── test_mic.py               (standalone manual script, not part of the app)
│   ├── requirements.txt
│   └── handlers/
│       ├── __init__.py           (empty)
│       ├── audio.py
│       └── process.py
├── backend/
│   ├── Dockerfile, requirements.txt
│   └── app/
│       ├── main.py
│       ├── db.py
│       ├── models.py
│       ├── state.py
│       ├── api/                  (empty, no files — see Finding 4)
│       └── ws/
│           ├── __init__.py       (empty)
│           ├── hub.py
│           ├── agent.py
│           └── client.py
├── frontend/
│   ├── index.html, manifest.webmanifest
│   ├── icons/apple-touch-icon.png
│   ├── css/ (base.css, grid.css, button.css)
│   └── js/ (app.js, api.js, render.js, ws.js)
├── docs/                         (empty, no files — see Finding 4)
├── data/                         (gitignored, sqlite db lives here at runtime)
├── deploy.sh, check.sh
├── docker-compose.yml
├── .env.example
├── gen_icon.py
└── README.md
```

No `CLAUDE.md` was found to diff this against — see Finding 4.

---

## High priority

### 1. No timeout on the execute round-trip — a dead agent hangs the tile forever
**File:** `backend/app/ws/client.py:34-70` (`_handle_execute`)
**What's wrong:** `_handle_execute` sends the command to the agent via
`hub.send_to_agent(...)` and returns immediately. There is no `req_id`
tracking, no `asyncio.wait_for`, and no code path that ever emits a
`{"status": "timeout"}` result. Confirmed by grep — no `wait_for`, `timeout`,
or pending-request map exists anywhere in `backend/`. The only way a client
ever gets a `result` message is if the agent actually sends one back
(`agents/windows/agent.py:47-52`); if the agent hangs, crashes mid-handler,
or the handler itself blocks, no error is ever produced.
**Why it matters:** This is a real, everyday failure mode, not a theoretical
one — a hung `subprocess.Popen` call, a COM call that blocks in
`handle_audio_mute_toggle`, or a dropped agent connection between "hello"
and the next `receive_json` all silently strand the tile in a pending state
with no way for the user to know something went wrong.
**Confirmed also missing client-side:** `frontend/js/app.js:26` and
`frontend/js/ws.js:57-59` — `onResult` just does `console.log`; there's no
per-`req_id` timer on the frontend either. The gap is missing on *both*
ends, not just the backend.
**Suggested fix:** Track `req_id -> (asyncio.Future, timestamp)` in
`_handle_execute`, await it with `asyncio.wait_for(..., timeout=5)`, and on
`TimeoutError` broadcast a `{"status": "timeout"}` result. `agent_ws` would
need to resolve the matching future when a `result` message arrives instead
of (or in addition to) broadcasting directly.

### 2. `asyncio.gather()` in the Windows agent does not cancel the sibling task on either exit path
**File:** `agents/windows/agent.py:68-71`
```python
await asyncio.gather(_receive_loop(ws), poll_loop(send_state))
```
**What's wrong, verified two ways:**
- If `_receive_loop` raises (bad JSON, unknown handler exception surfacing
  through `result = handler(message["params"])` at line 46, etc.),
  `gather()` propagates that exception immediately but does **not** cancel
  `poll_loop`. `poll_loop` (`agents/windows/poller.py:8-21`) has no exception
  handling around its own `await send_state_callback(snapshot)` (line 19),
  so it keeps running — and calling `ws.send()` on the same object — until
  its own send raises `ConnectionClosed`, which is silently swallowed
  because nothing is awaiting that task's result anymore (an "exception was
  never retrieved" style leak).
- The reverse direction is worse: `websockets`' async iteration
  (`async for raw in ws` in `_receive_loop`, `agent.py:28`) returns
  **normally, with no exception**, on a clean server-side close (code 1000).
  In that case `gather()` does not return either, because `gather()` waits
  for *all* awaitables to finish — and `poll_loop`'s `while True` never
  exits on its own. It keeps polling and sending on a closed socket for up
  to `POLL_INTERVAL_SECONDS` (1 second, `poller.py:5`) until its own
  `ws.send()` finally raises and `gather()` unblocks.
**Why it matters:** This is exactly the zombie-task pattern flagged before
implementation — confirmed real from reading `gather()`'s documented
semantics against this code. The "~1 poll tick" bound is reasoned from
source (tied to `POLL_INTERVAL_SECONDS`, `poller.py:5`), not something I
observed at runtime under an actual dropped connection — I did not verify
this by forcing a live disconnect, so treat the exact timing as a
reasoned estimate, not a measurement.
**Suggested fix:** Wrap both coroutines as real `asyncio.Task`s, use
`asyncio.wait(..., return_when=FIRST_COMPLETED)`, and explicitly `.cancel()`
(and `await`) whichever task is still running before returning from `run()`.

### 3. Frontend has no `state` / `agent_status` handling at all — Evening 2 work has not started
**File:** `frontend/js/ws.js:16-23`
```js
socket.addEventListener("message", (event) => {
  const message = JSON.parse(event.data);
  if (message.type === "result") { ... }
});
```
**What's wrong:** Only `message.type === "result"` is handled. Every `state`
message (mic mute changes) and every `agent_status` message (online/offline)
the backend broadcasts (`backend/app/ws/agent.py:30,45,51`) is parsed and
then silently discarded — there is no `onStateUpdate`/`onAgentStatus`
export, no callback registry for it, and `render.js` has no function to
update an already-rendered tile at all (`frontend/js/render.js` only exports
`renderWorkspace`, `renderError`, `setWorkspaceName` — all initial-render-only).
`button.css` has no muted/offline classes and no color transition rule at
all (only `transform` is transitioned, `frontend/css/button.css:8`).
**Additional gap not mentioned in the ask:** `renderWorkspace`
(`render.js:9-28`) never stores `item.state_key` on the tile's dataset —
only `item.id` (`render.js:12`). So even once a `state` listener exists,
there's currently no DOM hook to look up "which tile shows `mic.muted`"
without also touching the tile-creation loop.
**Why it matters:** This confirms precisely what's missing before Evening 2
starts: nothing is partially built here — the WS message is thrown away
before it ever reaches rendering code.
**Suggested fix:** Add an `onStateUpdate` callback registry in `ws.js`
mirroring `onResult`; store `state_key` in the tile's dataset in
`render.js`; add `.tile[data-muted="true"]` / `.tile.offline` rules plus a
`transition: background-color 200ms` in `button.css`.

### 4. No `CLAUDE.md` exists anywhere in the repository
**Checked:** working tree (`find . -iname CLAUDE.md`) and full git history
(`git log --all --full-history -- '**/CLAUDE.md'`) — zero hits in either.
`docs/` and `backend/app/api/` are also both present but completely empty.
**Why it matters:** The audit was asked to diff the actual tree against
CLAUDE.md's description; there is nothing to diff against, which itself is
a documentation gap worth closing before the codebase grows further —
especially since `backend/app/api/` being an empty placeholder directory
suggests a REST API layer was planned (for creating/editing items) but
never started, and nothing records that intent anywhere else.
**Suggested fix:** Run `/init` (or write one by hand) capturing at minimum
the actual module layout and the message-shape contracts between
client↔backend↔agent, since points 1, 3, and 6 below all hinge on that
shape being stable.

---

## Medium priority

### 5. `item.params` malformed JSON is unhandled on both backend and frontend
**Files:** `backend/app/ws/client.py:66` and `frontend/js/api.js:10`
```python
"params": json.loads(item["params"]),   # client.py:66, no try/except
```
```js
item.params = JSON.parse(item.params);  // api.js:10, no try/catch
```
**What's wrong:** Neither call is guarded. On the backend, a bad row would
raise `json.JSONDecodeError` inside `_handle_execute`, uncaught by the
`except WebSocketDisconnect` in `client_ws` (`client.py:27`) — it propagates
out of the handler for that one connection. On the frontend it's worse in
blast radius: `fetchWorkspaces()` throws for *all* workspaces on a single
bad item, which `app.js:17-19` catches only as a generic "Failed to load" —
the whole grid fails to render, not just one tile.
**Why it matters:** Today this is low-*probability* (there is no API to
create/edit items yet — `params` is only ever written by the hardcoded,
valid JSON literals in `db.py`'s `fixup_*` functions), but it's a landmine
for the moment an editing API is added, and the failure mode (whole-app
white-screen on the frontend) is disproportionate to the cause (one bad
row).
**Suggested fix:** Wrap both in try/except; on the backend, return a
`{"status": "error", "message": "invalid params"}` result instead of
letting the handler crash; on the frontend, skip/flag the individual item
rather than aborting the whole fetch.

**Related, same class, found while checking this handler:**
`backend/app/ws/agent.py:40` — `update_state(message["data"])` indexes
`"data"` directly with no `.get()`/guard. A `state` message that omits
`data` raises `KeyError` inside the agent's main loop, which — same as
Finding 1's absence of a timeout — kills that connection for the one bad
message. Same fix shape as above: use `message.get("data", {})` or wrap
and emit nothing on a malformed state message rather than dropping the
connection.

### 6. `client.py`'s message shape has no room for a slider-type ("set_value") action yet
**File:** `frontend/js/ws.js:44-55` (`sendExecute`) and
`backend/app/ws/client.py:25-26,34-70`
**What's wrong:** `sendExecute(itemId)` sends only
`{cmd: "execute", item_id, req_id}` — there's no field for a live value.
`client_ws` only branches on `message.get("cmd") == "execute"`
(`client.py:25`), and `_handle_execute` always forwards the item's static,
DB-stored `params` unchanged (`client.py:66`) — there is no path for a
runtime value (e.g. a slider position) to reach the outgoing agent message
at all.
**Why it matters:** `HANDLERS` in `agents/windows/agent.py:21-24` is
confirmed a plain dict (good, extensible), but a Volume slider needs a
continuous value that doesn't exist in the DB row and isn't part of today's
message shape on either the client→backend or backend→agent leg. Building
three more handlers (Volume, Spotify, VPN) on the assumption that today's
shape holds would require reworking this mid-flight if Volume is among
them.
**Suggested fix:** Before building Volume, extend the client→backend
message to carry an optional `value`, and have `_handle_execute` merge it
into (or override) the forwarded `params` — decide this shape now rather
than retrofitting it after Spotify/VPN are already built against the old one.

### 7. `client_ws` registers before entering try/finally — a failure in the initial state push skips cleanup
**File:** `backend/app/ws/client.py:13-20`
```python
await ws.accept()
hub.register_client(ws)          # line 15 — registered here
logger.info("Client connected")
await ws.send_json({"type": "state", "data": get_state()})  # line 19 — not yet inside try
try:
    ...
finally:
    hub.unregister_client(ws)
```
**What's wrong:** If the client disconnects between `accept()` and the
initial `send_json` (line 19), that exception propagates before the
`try/finally` block even starts, so `hub.unregister_client` is never
called for that path.
**Why it matters — but bounded:** This is not an unbounded leak: the dead
`ws` sits in `hub.clients` until the *next* `broadcast_to_clients` call,
which has its own internal try/except and self-heals by discarding failed
sockets (`backend/app/ws/hub.py:29-33`). So the practical impact is a
delayed cleanup (until the next state change or execute result), not a
permanent one — worth fixing for correctness but not urgent. Note this is
reasoned from the code, not observed under a live "disconnect at exactly
the wrong instant" test — I did not reproduce this race in a running
process.
**Suggested fix:** Move `hub.register_client(ws)` and the initial
`send_json` inside the `try` block (or start the `try` right after
`accept()`).

### 8. `SERVER_PORT` is defined in `.env.example` but read nowhere in the codebase
**Files:** `.env.example:2` defines `SERVER_PORT=8000`;
`agents/windows/agent.py:17` hardcodes port 8000:
```python
SERVER_URL = f"ws://{SERVER_IP}:8000/ws/agent"
```
**Confirmed via grep:** `SERVER_PORT` appears in exactly one file in the
whole repo — `.env.example`. It is never read by `os.environ` anywhere.
**Why it matters:** This is exactly the class of env/config drift already
causing outages this week — the example file documents a variable that
does nothing, and changing the backend's exposed port (`docker-compose.yml:5`,
`backend/Dockerfile:10-11`) would silently break the agent with no error
message pointing at the real cause.
**Suggested fix:** Either wire `agent.py` to read `SERVER_PORT` (with a
default of 8000), or delete it from `.env.example` so it stops implying a
config knob that doesn't exist.

### 9. Leftover Day 2/3 debug logging confirmed still present
**File:** `backend/app/ws/agent.py:35`
```python
logger.info("Agent raw message: %s", message)  # TODO: remove once state polling confirmed working end to end
```
This is a duplicate of the very next line (`agent.py:36`,
`logger.info("Agent '%s' sent: %s", name, message)`), explicitly marked
`TODO: remove` in the source. It is the only `TODO`/`FIXME`/`HACK` marker
anywhere in `backend/`, `agents/windows/`, or `frontend/` (verified by
repo-wide grep).
**Note for whoever removes it:** `check.sh:38` greps container logs for the
literal substring `'type': 'state'` to count state broadcasts — that
pattern is satisfied by line 36's log (`Agent '%s' sent: %s`), not line 35,
so deleting line 35 will **not** break `check.sh`.
**Suggested fix:** Delete `agent.py:35`.

Also present, not marked `TODO` but clearly informal/console-only, and worth
folding into a single logging decision rather than leaving as bare `print`:
- `agents/windows/agent.py:29` — `print(f"Received: {raw}")`, logs every
  inbound agent message unconditionally to stdout.
- `agents/windows/poller.py:15` — `print(f"Poll error: {exc}")`.
- `agents/windows/agent.py:63,83,85` — connect/disconnect/backoff prints.
These aren't bugs, but they're `print()` rather than the `logging` module
used everywhere on the backend side, so there's no way to silence or level
them independently once the agent runs unattended as a service.

---

## Low priority

- **`backend/app/db.py:4`** — `DB_PATH = Path("/app/data/controlhub.db")` is
  hardcoded, not read from an env var. Fine for the current single-target
  Docker deployment (matches the `docker-compose.yml:9` volume mount
  exactly), but it means the backend cannot be run directly on the Windows
  dev machine outside Docker without this exact path existing. Worth an
  env var (e.g. `DB_PATH`, defaulting to the current hardcoded value) only
  if local-outside-Docker runs become something you actually want.
- **`backend/app/models.py:8-33`** — `Item` and `Workspace` Pydantic models
  are defined but never actually used: `get_workspaces_with_items()`
  (`models.py:36-55`) returns plain `dict`s, and the endpoint
  (`backend/app/main.py:42-44`) declares `-> list[dict]`, not
  `response_model=list[Workspace]`. The models currently do nothing —
  either wire them in via `response_model` for real validation, or remove
  them; right now they're dead weight that looks like validation is
  happening when it isn't.
- **`backend/app/main.py:29`** — `@app.on_event("startup")` is deprecated
  as of the FastAPI version pinned in `requirements.txt` (0.115.0) in favor
  of the `lifespan` context manager. Not a functional bug today, just a
  deprecation warning waiting to become a removal.
- **`backend/app/ws/agent.py:15-25`** — the "hello"/token handshake (before
  `hub.register_agent`) is not inside any try/except. An agent that
  connects and disconnects before sending `hello` produces an unhandled
  `WebSocketDisconnect` traceback in server logs. Harmless (nothing was
  registered yet, no cleanup needed), but it's log noise that looks like a
  bug on casual inspection of `docker compose logs`.
- **`backend/app/api/`** — present, empty, unreferenced. Either a marker for
  planned work or leftover scaffolding; worth a one-line note in whatever
  replaces the missing `CLAUDE.md` so it's not mistaken for dead code to
  delete.
- **`backend/requirements.txt`** — `pydantic` is imported directly in
  `models.py:3` but not pinned in `requirements.txt` (it currently arrives
  transitively via `fastapi`). Works today, but an unrelated fastapi bump
  could change the pydantic version silently. Pin it explicitly since it's
  a direct import.
- **Other hardcoded timeouts/intervals** — `agents/windows/poller.py:5`
  (`POLL_INTERVAL_SECONDS = 1`), `agents/windows/agent.py:19`
  (`MAX_BACKOFF = 30`), and `frontend/js/ws.js:1` (`MAX_BACKOFF = 30000`)
  are all hardcoded rather than env-driven. Unlike `DB_PATH` or
  `SERVER_PORT`, these are single-process-local tuning constants with no
  cross-machine consistency requirement, so leaving them as code constants
  is reasonable — flagging only so they're not mistaken for an oversight.
  Worth noting: `POLL_INTERVAL_SECONDS` is the same constant that bounds
  the zombie-task window in Finding 2, so a future change to it should
  double-check that finding still holds.

---

## Confirmed working — no action needed

- **`backend/app/ws/hub.py`** — no blocking calls anywhere in
  `broadcast_to_clients` or `send_to_agent`; both are pure `async`/`await`
  with per-connection try/except and self-healing discard on failure
  (`hub.py:25-45`). This was checked specifically because a single blocking
  call here would stall every connected client under load — it's clean.
- **`deploy.sh:43-44` and `check.sh:21-22`** — the `LC_ALL=C` fix for
  locale-independent `sort` (commit `9b20e49`) is present in **both**
  scripts, not just one.
- **Unused imports** — none found in any Python file across `backend/`,
  `agents/windows/`, or their `handlers/` package (checked every import
  against its usage).
- **`agents/windows/agent.py:21-24`** — `HANDLERS` is confirmed a plain
  `dict`, straightforward to extend with new command types.
- **`frontend/js/app.js:30`** — the iOS Safari `:active`-style fix (empty
  `touchstart` listener on `document.body`) is applied and was not, in
  fact, still pending.
- **`backend/app/ws/agent.py`'s main loop and `client.py`'s main loop** —
  both correctly use `finally` (not just an `except WebSocketDisconnect`)
  to unregister from the hub, so exceptions other than a clean disconnect
  still trigger cleanup for the steady-state loop (see Medium #7 for the
  one narrow pre-`try` window that's the exception to this).
- **`agents/windows/handlers/audio.py` and `process.py`** — both wrap their
  actual work in `try/except Exception` and return a structured
  `{"status": "error", "message": ...}` rather than raising into the
  handler dispatch loop.
- **`docker-compose.yml`** — frontend is correctly bind-mounted
  (`./frontend:/app/frontend`), which matches `backend/Dockerfile` *not*
  copying a `frontend/` directory into the image — this is intentional,
  not a missing `COPY`, since `main.py:62` mounts `StaticFiles(directory="frontend")`
  at the container path the volume provides.

---

## Utility proposed (per request): `scripts/token_fingerprint.py`

Given AGENT_TOKEN drift between the Windows agent's `.env` and the Debian
backend's `.env` has caused real outages this week, added a tiny script
that prints only the token's length and a truncated SHA-256 hash — never
the raw value — so the two sides can be compared by eye without pasting
secrets anywhere:

```
python scripts/token_fingerprint.py backend/.env
python scripts/token_fingerprint.py agents/windows/.env
```

It takes the `.env` path as an explicit argument on purpose — an earlier
draft relied on python-dotenv's default search, which resolves relative to
the *script's own* directory, not the caller's cwd. That silently pointed
both invocations at the same repo-root `.env` regardless of which side you
meant to check, so a real drift would have been invisible. Verified the
fix by pointing it directly at `agents/windows/.env` and confirming it
reads that file's token (not a shell-exported `AGENT_TOKEN`, not the
root `.env`) and prints the resolved absolute path so the operator can see
exactly which file was read.

One caveat worth keeping in mind: for the backend side this reads the
*host* file, not what the container process actually has loaded. Commit
`dbaaa25` ("add env_file to compose — was edited directly on server")
describes exactly a host/container divergence, which a host-side file read
would miss. To check what the container sees:

```
docker compose exec -T backend python -c \
  "import os,hashlib; t=os.environ.get('AGENT_TOKEN'); \
   print(f'length={len(t)} sha256_prefix={hashlib.sha256(t.encode()).hexdigest()[:12]}' if t else 'not set')"
```

Nothing beyond this was built — no drift-detection daemon, no automated
diffing — since that wasn't an observed problem.
