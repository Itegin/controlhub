const tbody = document.getElementById("items-tbody");
const form = document.getElementById("item-form");
const paramsError = document.getElementById("params-error");

const fields = {
  id: document.getElementById("field-id"),
  workspaceId: document.getElementById("field-workspace-id"),
  label: document.getElementById("field-label"),
  icon: document.getElementById("field-icon"),
  color: document.getElementById("field-color"),
  activeColor: document.getElementById("field-active-color"),
  alertColor: document.getElementById("field-alert-color"),
  falseColor: document.getElementById("field-false-color"),
  kind: document.getElementById("field-kind"),
  type: document.getElementById("field-type"),
  target: document.getElementById("field-target"),
  stateKey: document.getElementById("field-state-key"),
  row: document.getElementById("field-row"),
  col: document.getElementById("field-col"),
  width: document.getElementById("field-width"),
  height: document.getElementById("field-height"),
  params: document.getElementById("field-params"),
};

// Used to pre-select the workspace picker for new items -- whichever
// workspace loaded first (position=0, i.e. "Home" today).
let defaultWorkspaceId = null;

// Studio Mode has no login UI, so the agent token is collected once via a
// plain prompt() and kept in memory only for the rest of this page load --
// never localStorage/sessionStorage, per this project's convention of
// avoiding browser storage APIs. Resetting on reload is an accepted
// tradeoff for a desktop-only admin page, not an oversight.
let agentToken = null;

function getAgentToken() {
  if (agentToken === null) {
    agentToken = prompt("Agent token (X-Agent-Token) for Studio Mode:") || "";
  }
  return agentToken;
}

async function loadItems() {
  const response = await fetch("/api/workspaces");
  const workspaces = await response.json();
  defaultWorkspaceId = workspaces[0] ? workspaces[0].id : null;
  populateWorkspaceSelect(workspaces);
  // Kept as the raw params string here (unlike the dashboard's
  // fetchWorkspaces in api.js, which parses it) -- the form's textarea
  // and the CRUD endpoints both want the JSON string form directly.
  const items = workspaces.flatMap((workspace) => workspace.items);
  renderTable(items);
}

function populateWorkspaceSelect(workspaces) {
  fields.workspaceId.innerHTML = "";
  for (const workspace of workspaces) {
    const option = document.createElement("option");
    option.value = workspace.id;
    option.textContent = workspace.name;
    fields.workspaceId.appendChild(option);
  }
}

function renderTable(items) {
  tbody.innerHTML = "";
  for (const item of items) {
    const tr = document.createElement("tr");

    for (const value of [item.label, item.type, item.target, `${item.row},${item.col}`]) {
      const td = document.createElement("td");
      td.textContent = value;
      tr.appendChild(td);
    }

    const actionsTd = document.createElement("td");

    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.textContent = "Edit";
    editBtn.addEventListener("click", () => openForm(item));

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "danger";
    deleteBtn.textContent = "Delete";
    deleteBtn.addEventListener("click", () => deleteItem(item));

    actionsTd.append(editBtn, deleteBtn);
    tr.appendChild(actionsTd);

    tbody.appendChild(tr);
  }
}

// Used only to pre-fill the active/alert color pickers -- malformed
// params shouldn't block opening the form (the params textarea itself
// still shows the raw string, errors included, for the user to fix).
function parseParamsLoosely(paramsString) {
  try {
    return JSON.parse(paramsString) || {};
  } catch {
    return {};
  }
}

function openForm(item) {
  paramsError.hidden = true;

  if (item) {
    fields.id.value = item.id;
    fields.workspaceId.value = item.workspace_id;
    fields.label.value = item.label;
    fields.icon.value = item.icon || "";
    fields.color.value = item.color || "#2a2f38";
    fields.kind.value = item.kind;
    fields.type.value = item.type;
    fields.target.value = item.target;
    fields.stateKey.value = item.state_key || "";
    fields.row.value = item.row;
    fields.col.value = item.col;
    fields.width.value = item.width;
    fields.height.value = item.height;
    // active_color/alert_color live inside params, not their own DB
    // columns -- pre-fill from there, falling back to the same
    // hardcoded teal/red the dashboard itself falls back to, so an
    // untouched item's picker reflects what's actually rendering now.
    const existingParams = parseParamsLoosely(item.params);
    // Pretty-print for readability; fall back to the raw string if it
    // somehow isn't valid JSON so a malformed value is still visible/editable.
    try {
      fields.params.value = JSON.stringify(JSON.parse(item.params), null, 2);
    } catch {
      fields.params.value = item.params;
    }
    fields.activeColor.value = existingParams.active_color || "#0d9488";
    fields.alertColor.value = existingParams.alert_color || "#dc2626";
    // Unlike active/alert (which fall back to a fixed hardcoded color when
    // unset), the false-state fallback is item.color itself -- a
    // per-item, not fixed, value. Pre-filling with that same value (not
    // a fixed constant) means saving unchanged writes back the color
    // that was already rendering, so untouched items stay visually
    // identical even though false_color now has a concrete value in params.
    fields.falseColor.value = existingParams.false_color || item.color || "#2a2f38";
  } else {
    form.reset();
    fields.id.value = "";
    fields.workspaceId.value = defaultWorkspaceId ?? "";
    fields.color.value = "#2a2f38";
    fields.activeColor.value = "#0d9488";
    fields.alertColor.value = "#dc2626";
    fields.falseColor.value = "#2a2f38";
    fields.width.value = 1;
    fields.height.value = 1;
    fields.params.value = "{}";
  }

  form.hidden = false;
}

function closeForm() {
  form.hidden = true;
  paramsError.hidden = true;
}

async function deleteItem(item) {
  if (!confirm(`Delete "${item.label}"?`)) {
    return;
  }
  const response = await fetch(`/api/items/${item.id}`, {
    method: "DELETE",
    headers: { "X-Agent-Token": getAgentToken() },
  });
  if (!response.ok) {
    // Adding auth here means delete can now fail (e.g. wrong/empty token,
    // 401) in a way it never could before -- silently reloading the table
    // as if it worked would hide that from the user.
    const error = await response.json().catch(() => ({}));
    alert(`Delete failed (${response.status}): ${error.detail || "unknown error"}`);
    return;
  }
  await loadItems();
}

async function compactLayout() {
  const workspaceId = fields.workspaceId.value;
  if (!workspaceId) {
    return;
  }
  // The picker lives inside the (usually hidden) item form, so name the
  // workspace in the prompt -- the user is authorizing a non-undoable
  // rewrite of a target they can't necessarily see on screen.
  const workspaceName = fields.workspaceId.selectedOptions[0]?.textContent || workspaceId;
  if (!confirm(`Repack all tiles in "${workspaceName}" into the top-left? This rewrites their positions and can't be undone.`)) {
    return;
  }
  const response = await fetch(`/api/workspaces/${workspaceId}/compact`, {
    method: "POST",
    headers: { "X-Agent-Token": getAgentToken() },
  });
  if (!response.ok) {
    // Same handling as deleteItem(): a bad token (401) or missing
    // workspace (404) must surface, not silently reload as if it worked.
    const error = await response.json().catch(() => ({}));
    alert(`Compact failed (${response.status}): ${error.detail || "unknown error"}`);
    return;
  }
  // Same close-then-reload order as the submit handler. Mandatory here, not
  // cosmetic: an open form still holds the item's pre-compact row/col (and
  // loadItems() rebuilds the workspace <select>, resetting it to the first
  // option), so a Save afterwards would push the item back out of the packed
  // layout and into whichever workspace the reset dropdown landed on.
  closeForm();
  await loadItems();
}

document.getElementById("new-item-btn").addEventListener("click", () => openForm(null));
document.getElementById("compact-btn").addEventListener("click", compactLayout);
document.getElementById("cancel-btn").addEventListener("click", closeForm);

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  let paramsObj;
  try {
    paramsObj = JSON.parse(fields.params.value);
  } catch (err) {
    paramsError.textContent = `Params must be valid JSON: ${err.message}`;
    paramsError.hidden = false;
    return;
  }
  paramsError.hidden = true;

  // Merge the color pickers in last -- they're the source of truth for
  // active_color/alert_color/false_color, overriding whatever the raw
  // params textarea happened to have typed in for those same keys.
  paramsObj.active_color = fields.activeColor.value;
  paramsObj.alert_color = fields.alertColor.value;
  paramsObj.false_color = fields.falseColor.value;
  const paramsValue = JSON.stringify(paramsObj);

  const body = {
    workspace_id: Number(fields.workspaceId.value),
    row: Number(fields.row.value),
    col: Number(fields.col.value),
    width: Number(fields.width.value),
    height: Number(fields.height.value),
    label: fields.label.value,
    icon: fields.icon.value || null,
    color: fields.color.value,
    kind: fields.kind.value,
    type: fields.type.value,
    target: fields.target.value,
    params: paramsValue,
    state_key: fields.stateKey.value || null,
  };

  const id = fields.id.value;
  const url = id ? `/api/items/${id}` : "/api/items";
  const method = id ? "PUT" : "POST";

  const response = await fetch(url, {
    method,
    headers: {
      "Content-Type": "application/json",
      "X-Agent-Token": getAgentToken(),
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    paramsError.textContent = `Save failed (${response.status}): ${error.detail || "unknown error"}`;
    paramsError.hidden = false;
    return;
  }

  closeForm();
  await loadItems();
});

loadItems();
