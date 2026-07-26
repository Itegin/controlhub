const MAX_BACKOFF = 30000;

let socket = null;
let backoff = 1000;
const resultCallbacks = [];

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

export function onResult(callback) {
  resultCallbacks.push(callback);
}
