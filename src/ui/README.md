# SARSim browser workspace

This frontend is plain HTML, CSS, and JavaScript served by FastAPI. It has no
Node.js, npm, compilation, or build step. GoldenLayout 2.6 is vendored under
`vendor/` with its upstream license so the workspace works offline.

Run `uv run --frozen --no-dev sarsim` from the repository root and open
<http://127.0.0.1:8000>. The header switches between separate Simulation and
Scenario editor modes. Each mode has its own draggable, resizable, persistent
GoldenLayout workspace. Editor mode provides dedicated tools, map, cell
properties, scenario settings, and JSON panels without occupying space with
inactive simulation panels.

The central map stack also provides a Three.js **3D scene** for live simulation
and a **3D preview** for authored scenarios. Three.js is vendored locally, so
these views require no CDN or additional installation.

Mission controls lists the bundled `editor/*.json` scenarios. Select a runtime
agent and use W/A/S/D for cardinal movement or Space for the context-sensitive
action on the facing tile; C cycles the controlled agent. Shortcuts do not fire
while typing in a form control or the JSON editor. The simulation and editor
maps share the visible cell-type legend. Editor building placement remains on
the active z-level, allowing multi-story structures to be stacked vertically.

Scenario settings selects full observability, an occluded FOV cone, or a
MiniGrid-style three-cell-wide forward sensor. Partial regimes mask unseen
cells and entities in both the 2D simulation map and 3D scene according to the
currently controlled agent.
