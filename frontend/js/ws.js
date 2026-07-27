const MAX_BACKOFF = 30000;

let socket = null;
let backoff = 1000;
const resultCallbacks = [];
const stateChangeCallbacks = [];
const agentStatusCallbacks = [];
const workspaceUpdateCallbacks = [];

function connect() {
  socket = new WebSocket(`ws://${location.host}/ws/client`);

  socket.addEventListener("open", () => {
    // Connection succeeded, so the next disconnect should start backing off
    // from scratch again instead of continuing to climb.
    backoff = 1000;
  });

  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.type === "result") {
      for (const callback of resultCallbacks) {
        callback(message);
      }
    } else if (message.type === "state") {
      for (const callback of stateChangeCallbacks) {
        callback(message.data);
      }
    } else if (message.type === "agent_status") {
      for (const callback of agentStatusCallbacks) {
        callback({ agent: message.agent, status: message.status });
      }
    } else if (message.type === "workspace_update") {
      for (const callback of workspaceUpdateCallbacks) {
        callback();
      }
    }
  });

  socket.addEventListener("close", () => {
    setTimeout(connect, backoff);
    backoff = Math.min(backoff * 2, MAX_BACKOFF);
  });

  socket.addEventListener("error", () => {
    socket.close();
  });
}

connect();

// crypto.randomUUID() requires a secure context (HTTPS or localhost) and
// this app is accessed over plain http://<lan-ip>:8000 from the phone, so
// it would silently be undefined there. Use a manual id instead.
function generateReqId() {
  return Date.now() + "-" + Math.random().toString(36).slice(2);
}

export function sendExecute(itemId) {
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    return;
  }
  socket.send(
    JSON.stringify({
      cmd: "execute",
      item_id: itemId,
      req_id: generateReqId(),
    })
  );
}

export function sendSetValue(itemId, value) {
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    return;
  }
  socket.send(
    JSON.stringify({
      cmd: "set_value",
      item_id: itemId,
      value,
      req_id: generateReqId(),
    })
  );
}

export function onResult(callback) {
  resultCallbacks.push(callback);
}

export function onStateChange(callback) {
  stateChangeCallbacks.push(callback);
}

export function onAgentStatus(callback) {
  agentStatusCallbacks.push(callback);
}

export function onWorkspaceUpdate(callback) {
  workspaceUpdateCallbacks.push(callback);
}
