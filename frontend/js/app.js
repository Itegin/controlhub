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

// iOS Safari only applies :active styles on tap if some element has a touch
// listener attached; this empty listener exists solely to enable that.
document.body.addEventListener('touchstart', function(){}, {passive: true});
