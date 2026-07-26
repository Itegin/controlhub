export async function fetchWorkspaces() {
  const response = await fetch("/api/workspaces");
  if (!response.ok) {
    throw new Error(`Failed to fetch workspaces: ${response.status}`);
  }
  const workspaces = await response.json();

  for (const workspace of workspaces) {
    for (const item of workspace.items) {
      item.params = JSON.parse(item.params);
    }
  }

  return workspaces;
}
