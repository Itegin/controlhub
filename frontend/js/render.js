export function renderWorkspace(workspace, onTileClick) {
  const grid = document.getElementById("grid");

  grid.style.setProperty("--cols", workspace.grid_cols);
  grid.style.setProperty("--rows", workspace.grid_rows);

  grid.innerHTML = "";

  for (const item of workspace.items) {
    const tile = document.createElement("div");
    tile.className = "tile";
    tile.dataset.itemId = item.id;

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
