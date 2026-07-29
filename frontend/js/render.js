import { attachLongPress } from "./longpress.js";

const SLIDER_THROTTLE_MS = 100;

// Literal, module-authored SVG markup only -- never build a key from
// item.icon and interpolate untrusted content into innerHTML. Missing keys
// render no icon rather than falling back to any kind of text/placeholder.
const ICONS = {
  lightbulb: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18h6"/><path d="M10 22h4"/><path d="M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.2 1 2.3h6c0-1.1.4-1.8 1-2.3A7 7 0 0 0 12 2Z"/></svg>`,
  music: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>`,
  moon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8Z"/></svg>`,
  terminal: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>`,
  mic: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>`,
  speaker: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M18.5 5.5a9 9 0 0 1 0 13"/></svg>`,
  headphones: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3Z"/><path d="M3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3Z"/></svg>`,
  "audio-switch": `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>`,
  camera: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2Z"/><circle cx="12" cy="13" r="4"/></svg>`,
};

export function renderWorkspace(workspace, onTileClick, onSliderChange, onTileLongPress) {
  const grid = document.getElementById("grid");

  grid.style.setProperty("--cols", workspace.grid_cols);
  grid.style.setProperty("--rows", workspace.grid_rows);

  grid.innerHTML = "";

  for (const item of workspace.items) {
    const tile = document.createElement("div");
    tile.className = "tile";
    tile.dataset.itemId = item.id;
    tile.dataset.kind = item.kind;
    if (item.state_key) {
      tile.dataset.stateKey = item.state_key;
    }
    // Explicit per-item styling choice (teal "active" vs red "alert"),
    // read from the DB row instead of guessed from the state key's name.
    tile.dataset.activeStyle = (item.params && item.params.active_style) || "normal";

    tile.style.gridColumn = `${item.col + 1} / span ${item.width}`;
    tile.style.gridRow = `${item.row + 1} / span ${item.height}`;
    tile.style.setProperty("--tile-color", item.color);

    const isSlider = item.kind === "action" && item.width >= 2 && item.type === "audio_volume_set";

    if (isSlider) {
      tile.classList.add("tile-slider");
      const fillBar = document.createElement("div");
      fillBar.className = "fill-bar";
      tile.appendChild(fillBar);
    }

    if (ICONS[item.icon]) {
      const icon = document.createElement("div");
      icon.className = "icon";
      icon.innerHTML = ICONS[item.icon];
      tile.appendChild(icon);
    }

    const label = document.createElement("div");
    label.className = "label";
    label.textContent = item.label;
    tile.appendChild(label);

    if (isSlider) {
      // Sliders own their pointerdown/move/up stream via
      // attachSliderHandlers above; attaching long-press's independent
      // pointer listeners to the same element would double-handle every
      // event, so only non-slider action tiles get long-press.
      attachSliderHandlers(tile, item, onSliderChange);
    } else if (item.kind === "action") {
      attachLongPress(tile, () => onTileLongPress(item), () => onTileClick(item.id));
    }

    grid.appendChild(tile);
  }
}

// Pointer Events (not an overlaid <input type="range">) because the fill
// itself is a plain styled div driven by --fill-percent, not a native
// track/thumb -- an <input> would still need JS glue to sync its value
// into that custom property on every input event, plus fighting
// -webkit-appearance to make it invisible, for no less code than this.
function attachSliderHandlers(tile, item, onSliderChange) {
  let lastSent = 0;

  function valueFromEvent(event) {
    const rect = tile.getBoundingClientRect();
    const ratio = (event.clientX - rect.left) / rect.width;
    return Math.round(Math.min(1, Math.max(0, ratio)) * 100);
  }

  function applyValue(value, { force = false } = {}) {
    tile.style.setProperty("--fill-percent", `${value}%`);
    const now = Date.now();
    if (force || now - lastSent >= SLIDER_THROTTLE_MS) {
      lastSent = now;
      onSliderChange(item.id, value);
    }
  }

  tile.addEventListener("pointerdown", (event) => {
    tile.setPointerCapture(event.pointerId);
    applyValue(valueFromEvent(event));
  });

  tile.addEventListener("pointermove", (event) => {
    if (!tile.hasPointerCapture(event.pointerId)) return;
    applyValue(valueFromEvent(event));
  });

  function release(event) {
    if (!tile.hasPointerCapture(event.pointerId)) return;
    // Force: the drag's final value must always reach onSliderChange even
    // if it lands inside the throttle window of the last move.
    applyValue(valueFromEvent(event), { force: true });
    tile.releasePointerCapture(event.pointerId);
  }

  tile.addEventListener("pointerup", release);
  tile.addEventListener("pointercancel", release);
}

export function updateTileState(stateData) {
  for (const [key, value] of Object.entries(stateData)) {
    const tiles = document.querySelectorAll(`.tile[data-state-key="${CSS.escape(key)}"]`);

    for (const tile of tiles) {
      if (typeof value === "number") {
        tile.style.setProperty("--fill-percent", `${value}%`);
        continue;
      }
      const activeClass = tile.dataset.activeStyle === "alert" ? "state-alert" : "state-active";
      tile.classList.toggle(activeClass, Boolean(value));
    }
  }
}

export function setAgentOffline(isOffline) {
  // Only one agent exists today, so "every actionable tile" and "this
  // agent's tiles" are the same set -- revisit with a target-aware
  // selector (matching item.target) once a second agent exists.
  const tiles = document.querySelectorAll('.tile[data-kind="action"]');
  for (const tile of tiles) {
    tile.classList.toggle("tile-offline", isOffline);
  }
}

export function renderError(message) {
  const grid = document.getElementById("grid");
  grid.innerHTML = "";
  const errorEl = document.createElement("div");
  errorEl.className = "error-message";
  errorEl.textContent = message;
  grid.appendChild(errorEl);
}
