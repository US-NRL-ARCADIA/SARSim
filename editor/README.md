# SARSim Editor

This is a standalone desktop scenario editor for SARSim.

## Primary documentation

For full usage instructions, JSON mapping details, and guided walkthroughs, see:

- `docs/scenario_editor_user_guide.md`

## Goals

The editor is intended to support research-grade scenario authoring rather than web deployment.
It targets the scenario-definition schema documented in `docs/scenario_schema.md`.

## Current capabilities

- open a generated scenario at startup
- paint:
  - walls
  - debris
  - smoke
  - casualties
  - agents
  - zone cells
  - building cells
- inspect selected cells and authored content
- switch z-levels
- create and cycle zones
- author `FIELD_HOSPITAL` and `EXTRACTION` zones
- save to `editor/last_scenario.json`
- load from `editor/last_scenario.json`
- validate by rebuilding a `SimulationEngine`

## Launch

```sh
./.venv/bin/python editor/app.py
```

## Quick reference

### Tools
- `0`: clear
- `1`: wall
- `2`: debris
- `3`: smoke
- `4`: casualty
- `5`: agent
- `6`: zone
- `7`: building
- `8`: select

### Zone controls
- `Z`: cycle active zone type
- `N`: create new zone
- `P`: cycle active zone

### General controls
- `[` / `]`: change z-level
- `S`: save
- `L`: load
- `G`: regenerate
- `V`: validate
- `O`: cycle selected agent orientation
- `C`: toggle selected agent class
- `H` / `J`: selected casualty health -/+
- `D`: increase selected casualty decay
- `F`: toggle selected casualty cover
- `I` / `K`: selected building integrity +/-
- `X`: toggle selected building collapsed state
- `M`: cycle scenario difficulty
- `B`: toggle the optional rescue-count temporal constraint
- `T`: cycle the rescue deadline (with the constraint enabled)
- `Y`: cycle the rescue target (with the constraint enabled)
- `E`: add scheduled event at selected cell
- `R`: remove last scheduled event
- `Up` / `Down`: scroll details panel
- `Page Up` / `Page Down`: scroll details panel faster
- `Esc`: quit

## Notes

This is a lightweight desktop authoring tool.
For the complete workflow from editor to backend to browser UI, see:

- `docs/scenario_editor_user_guide.md`
- `docs/scenario_workflow.md`
