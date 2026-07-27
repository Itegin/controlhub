const tbody = document.getElementById("items-tbody");
const form = document.getElementById("item-form");
const paramsError = document.getElementById("params-error");

const fields = {
  id: document.getElementById("field-id"),
  workspaceId: document.getElementById("field-workspace-id"),
  label: document.getElementById("field-label"),
  icon: document.getElementById("field-icon"),
  color: document.getElementById("field-color"),
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

// This app has only ever had one workspace ("Home"); the create form has
// no workspace picker (not in the original field list), so new items go
// to whichever workspace loaded first rather than a hardcoded id.
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
  // Kept as the raw params string here (unlike the dashboard's
  // fetchWorkspaces in api.js, which parses it) -- the form's textarea
  // and the CRUD endpoints both want the JSON string form directly.
  const items = workspaces.flatMap((workspace) => workspace.items);
  renderTable(items);
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
    fields.params.value = item.params;
  } else {
    form.reset();
    fields.id.value = "";
    fields.workspaceId.value = defaultWorkspaceId ?? "";
    fields.color.value = "#2a2f38";
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

document.getElementById("new-item-btn").addEventListener("click", () => openForm(null));
document.getElementById("cancel-btn").addEventListener("click", closeForm);

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const paramsValue = fields.params.value;
  try {
    JSON.parse(paramsValue);
  } catch (err) {
    paramsError.textContent = `Params must be valid JSON: ${err.message}`;
    paramsError.hidden = false;
    return;
  }
  paramsError.hidden = true;

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
