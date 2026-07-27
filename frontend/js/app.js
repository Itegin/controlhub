import { fetchWorkspaces } from "./api.js";
import { renderWorkspace, renderError, setWorkspaceName, updateTileState, setAgentOffline } from "./render.js";
import { sendExecute, onResult, onStateChange, onAgentStatus } from "./ws.js";

async function init() {
  try {
    const workspaces = await fetchWorkspaces();
    const workspace = workspaces[0];

    if (!workspace) {
      renderError("No workspaces found");
      return;
    }

    setWorkspaceName(workspace.name);
    renderWorkspace(workspace, sendExecute);
  } catch (err) {
    renderError("Failed to load");
  }
}

init();

// Day 3 will drive a pending/success/error state on the tile itself; for
// now this just proves the execute -> agent -> result round trip works.
onResult((result) => console.log("result:", result));

onStateChange((data) => updateTileState(data));
onAgentStatus(({ status }) => setAgentOffline(status === "offline"));

// iOS Safari only applies :active styles on tap if some element has a touch
// listener attached; this empty listener exists solely to enable that.
document.body.addEventListener('touchstart', function(){}, {passive: true});
