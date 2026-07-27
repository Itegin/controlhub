export function renderWorkspace(workspace, onTileClick) {
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

    tile.style.gridColumn = `${item.col + 1} / span ${item.width}`;
    tile.style.gridRow = `${item.row + 1} / span ${item.height}`;
    tile.style.setProperty("--tile-color", item.color);

    const label = document.createElement("div");
    label.className = "label";
    label.textContent = item.label;
    tile.appendChild(label);

    if (item.kind === "action") {
      tile.addEventListener("click", () => onTileClick(item.id));
    }

    grid.appendChild(tile);
  }
}

export function updateTileState(stateData) {
  for (const [key, value] of Object.entries(stateData)) {
    const tiles = document.querySelectorAll(`.tile[data-state-key="${CSS.escape(key)}"]`);

    // TEMPORARY CONVENTION: a state key prefixed "mic" renders as an alert
    // (red) instead of a neutral "active" (teal) -- an active mic mute is
    // something the user should notice, not just a toggle that's "on". This
    // is a naming heuristic, not a real taxonomy, and it doesn't scale past
    // one or two special cases. Revisit with an explicit field (e.g. an
    // item.state_style column) once there's more than mic.muted driving it.
    const activeClass = key.startsWith("mic") ? "state-alert" : "state-active";

    for (const tile of tiles) {
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

export function setWorkspaceName(name) {
  const nameEl = document.getElementById("workspace-name");
  nameEl.textContent = name;
}
