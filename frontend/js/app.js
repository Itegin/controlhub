import { fetchWorkspaces } from "./api.js";
import { renderWorkspace, renderError, updateTileState, setAgentOffline } from "./render.js";
import { sendExecute, sendSetValue, onResult, onStateChange, onAgentStatus, onWorkspaceUpdate } from "./ws.js";
import { showContextMenu } from "./contextmenu.js";

function handleTileLongPress(item) {
  showContextMenu(item, [
    {
      label: "Force Stop",
      destructive: true,
      action: () => sendExecute(item.id, { overrideType: "force_stop" }),
    },
    {
      label: "Cancel",
      action: () => {},
    },
  ]);
}

async function init() {
  try {
    const workspaces = await fetchWorkspaces();
    const requestedId = new URLSearchParams(window.location.search).get("workspace");
    const workspace =
      workspaces.find((w) => String(w.id) === requestedId) ?? workspaces[0];

    if (!workspace) {
      renderError("No workspaces found");
      return;
    }

    renderWorkspace(workspace, sendExecute, sendSetValue, handleTileLongPress);
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
// Studio Mode edits arrive as a bare signal, not the changed data itself --
// refetching and fully re-rendering is simplest and cheap enough here
// (edits are infrequent), same as init()'s own first load.
onWorkspaceUpdate(() => init());

// iOS Safari only applies :active styles on tap if some element has a touch
// listener attached; this empty listener exists solely to enable that.
document.body.addEventListener('touchstart', function(){}, {passive: true});
