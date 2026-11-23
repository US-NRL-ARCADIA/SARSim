# Minimal-dependency branch plan

## Completed foundation

- [x] Create the `minimal-python-ui` branch.
- [x] Replace npm/React with browser-native static files served by FastAPI.
- [x] Vendor GoldenLayout and its license for an offline customizable workspace.
- [x] Move scenario editing into the same workspace as simulation controls.
- [x] Remove the Pygame editor and SDL/Pygame dependency chain.
- [x] Remove unused gRPC, protobuf, aiohttp, and websockets declarations.
- [x] Add a real registered Gymnasium environment (`SARSim-v0`).
- [x] Adopt uv exclusively and add `uv.lock`.
- [x] Reduce startup to one command and one process.

## Architecture decisions

The simulation remains Python because replacing it with Node would add a second
runtime and conflict with the branch's minimal-setup objective. FastAPI is a thin
transport over the existing tested engine; Gymnasium calls the engine directly.
The browser necessarily executes JavaScript, but those files are ready to serve
and require no JavaScript package manager or build tool.

## Follow-up candidates

1. Add scenario property forms for metadata and entity attributes beyond grid painting.
2. Add browser-level tests for GoldenLayout dragging and editor paint workflows.
3. Add vectorized/PettingZoo adapters if multi-agent training requires them.
4. Add optional persistence for workspace-independent scenario storage.
