# Scenario examples

This directory contains authored scenario JSON examples. The old Pygame editor
has been replaced by **Scenario editor** mode in SARSim Studio, so SDL and
Pygame are no longer required.

Start it with `uv run --frozen --no-dev sarsim`, open <http://127.0.0.1:8000>,
then choose **Scenario editor** in the header. Dedicated GoldenLayout panels
provide labeled placement tools, the map, selected-cell properties, scenario
settings, and JSON source. Select a cell to edit casualty health/decay/cover,
agent class/orientation, building integrity/collapse, cell status, and smoke
density. Building cells can be placed on every z-level, so repeated placement
at the same x/y coordinate creates a stackable multi-story structure.

The central **3D preview** tab shows the complete authored scene across all
z-levels and supports orbit, pan, zoom, camera presets, and entity selection.

The properties column also manages zones, scenario difficulty, rescue-count
constraints, scheduled smoke events, and the scenario's full, FOV-cone, or
MiniGrid three-wide sensor regime. **Regenerate** reproduces the former
desktop editor's deterministic seeded generator. **Open JSON**, **Save JSON**,
**Validate**, and **Run scenario** provide the complete authoring workflow while
the visual editor and Scenario JSON panel remain synchronized.
