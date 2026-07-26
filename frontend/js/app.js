import { fetchWorkspaces } from "./api.js";
import { renderWorkspace, renderError, setWorkspaceName } from "./render.js";

async function init() {
  try {
    const workspaces = await fetchWorkspaces();
    const workspace = workspaces[0];

    if (!workspace) {
      renderError("No workspaces found");
      return;
    }

    setWorkspaceName(workspace.name);
    renderWorkspace(workspace);
  } catch (err) {
    renderError("Failed to load");
  }
}

init();
