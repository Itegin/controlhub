let currentOverlay = null;

// options: {label, action, destructive?}[]. destructive is an addition
// beyond the base {label, action} shape -- it's what contextmenu.css's
// "red text for destructive rows" rule needs to key off of.
export function showContextMenu(item, options) {
  dismissContextMenu();

  const overlay = document.createElement("div");
  overlay.className = "context-overlay";
  // Only the dimmed backdrop itself dismisses -- row clicks already
  // dismiss+act in their own handler below, and would double-fire here
  // too since click events bubble up from a row to the overlay.
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) {
      dismissContextMenu();
    }
  });

  const panel = document.createElement("div");
  panel.className = "context-panel";

  const header = document.createElement("div");
  header.className = "context-header";
  header.textContent = item.label;
  panel.appendChild(header);

  for (const option of options) {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "context-row";
    if (option.destructive) {
      row.classList.add("destructive");
    }
    row.textContent = option.label;
    row.addEventListener("click", () => {
      dismissContextMenu();
      option.action();
    });
    panel.appendChild(row);
  }

  overlay.appendChild(panel);
  document.body.appendChild(overlay);
  currentOverlay = overlay;

  // Deferred a frame so the initial opacity:0 (set in CSS) paints before
  // switching to opacity:1 -- otherwise the browser can coalesce both
  // into a single frame and the transition never plays.
  requestAnimationFrame(() => {
    overlay.classList.add("visible");
  });
}

export function dismissContextMenu() {
  if (currentOverlay) {
    currentOverlay.remove();
    currentOverlay = null;
  }
}
