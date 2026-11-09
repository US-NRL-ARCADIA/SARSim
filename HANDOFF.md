# SARSim Handoff

## Purpose

This document is a concise handoff guide for the software engineer taking over the current SARSim codebase.

It summarizes:
- what is implemented now
- where the important code lives
- how to run and validate the system
- what documentation to read first
- what limitations and next steps are most relevant

## Current system components

SARSim currently includes three main user-facing pieces plus the shared backend:

1. **Backend simulation engine and API**
   - simulation core in `src/core/`
   - FastAPI transport layer in `src/api/`

2. **React simulator/control console**
   - browser UI in `ui/`

3. **Standalone Pygame scenario editor**
   - desktop authoring tool in `editor/`

4. **Documentation and tests**
   - docs in `docs/`
   - regression coverage in `tests/`

## Implemented capabilities

### Backend / engine
Current implemented behavior includes:
- discrete 3D grid simulation
- UGV/UAV movement and orientation
- casualty health decay and triage
- building integrity, collapse, debris, and breach behavior
- queued engine actions
- event logging
- scenario-definition loading
- telemetry generation for agent observation/belief
- zone loading from scenario definitions
- field hospital casualty transfer bookkeeping

### API
Current API capabilities include:
- `GET /state`
- `POST /actions`
- `POST /step`
- `POST /init/dev`
- `POST /scenario/load`
- `POST /scenario/load-from-path`
- `GET /telemetry`
- `POST /reset`
- `WS /events/stream`

Important current API behavior:
- `GET /state` returns:
  - `tick`
  - `agents`
  - `casualties`
  - `buildings`
  - `zones`
  - `grid_cells`
  - `events`
- `/state.events` is capped to the most recent 200 events
- `WS /events/stream` is a live incremental stream after connection, not a replay endpoint

### Field hospital workflow
Current field hospital behavior:
- `TRANSFER_CASUALTY` transfers a carried casualty into adjacent or colocated `FIELD_HOSPITAL` zone care
- hospital care is tracked by zone id in engine state
- zone API records expose:
  - `casualty_count_under_care`
  - `casualty_ids_under_care`
- if a casualty is later picked up again with `LOAD_CASUALTY`, that casualty is removed from the hospital roster

### React UI
Current React control console capabilities include:
- initialize dev scenario
- reset scenario
- refresh state
- step one tick
- run/pause loop
- load authored scenarios from dropdown path selection
- load authored scenarios from pasted JSON
- select agents, casualties, casualty stacks, and zones
- inspect selection details
- inspect recent events
- inspect field hospital under-care counts and IDs
- issue actions including:
  - move forward
  - turn left / turn right
  - ascend / descend
  - triage
  - clear debris
  - breach entryway
  - retrieve body
  - load casualty
  - unload casualty
  - transfer casualty to field hospital

### Scenario editor
Current Pygame editor capabilities include:
- paint walls
- paint debris
- paint smoke
- place casualties
- place agents
- place building cells
- place zone cells
- select cells for inspection
- create and cycle active zones
- author `FIELD_HOSPITAL` and `EXTRACTION` zones
- save/load scenario-definition JSON
- validate by rebuilding a `SimulationEngine`
- inspect selected-cell details in the side panel
- use example scenario JSON files in `editor/`

## Important directories and files

### Backend core
- `src/core/engine.py` — main simulation engine state and tick loop
- `src/core/actions.py` — action enum and action model
- `src/core/action_handlers.py` — action execution
- `src/core/interactions.py` — triage, debris, breach, load/unload, hospital transfer logic
- `src/core/agents.py` — movement/orientation helpers
- `src/core/casualties.py` — casualty state and health logic
- `src/core/buildings.py` — building/collapse logic
- `src/core/events.py` — event types and event records

### API layer
- `src/api/server.py` — FastAPI routes and WebSocket stream
- `src/api/models.py` — Pydantic request/response models
- `src/api/serializers.py` — engine-to-API serialization
- `src/api/state.py` — global engine instance and scenario loading helpers
- `src/api/scenarios.py` — dev scenario seeding

### Scenario serialization
- `src/utils/serializer.py` — engine snapshot serialization and scenario-definition serialization/building

### React UI
- `ui/src/App.tsx` — main control console
- `ui/src/GridView.tsx` — grid rendering and selection behavior
- `ui/src/types.ts` — frontend state models
- `ui/src/App.css` — layout/styling

### Editor
- `editor/app.py` — standalone Pygame editor
- `editor/*.json` — example authored scenarios

### Tests
- `tests/test_api.py`
- `tests/test_engine.py`
- `tests/test_entities.py`
- `tests/test_events.py`
- `tests/test_utils.py`

## Docs to read first

Recommended reading order:
1. `README.md`
2. `docs/project_overview.md`
3. `docs/core_simulation.md`
4. `docs/api_and_state.md`
5. `docs/http_api_reference.md`
6. `docs/research_user_quickstart.md`
7. `docs/scenario_editor_user_guide.md`
8. `docs/scenario_schema.md`

## How to run

## Backend
From project root:

```sh
./.venv/bin/python run_server.py
```

Default local API:
- `http://127.0.0.1:8000`

## Tests
From project root:

```sh
./.venv/bin/python -m pytest
```

## React UI
From `ui/`:

```sh
npm install
npm start
```

The UI expects the backend at:
- `http://localhost:8000`

## Scenario editor
From project root:

```sh
./.venv/bin/python editor/app.py
```

## Suggested validation workflow

1. Run backend tests:
```sh
./.venv/bin/python -m pytest
```

2. Start backend:
```sh
./.venv/bin/python run_server.py
```

3. Start React UI:
```sh
cd ui
npm install
npm start
```

4. Load an example scenario in the UI:
- `editor/field_hospital_transport_scenario.json`
- `editor/editor_field_hospital_demo.json`
- `editor/editor_all_tools_demo.json`

5. Start the editor separately if needed:
```sh
./.venv/bin/python editor/app.py
```

## Recent logical change groups

Recent work was split into these logical commits:

- `516a82e` — backend/API/core support for scenario loading, telemetry, and field hospital transport
- `5a32cfc` — React UI expansion for scenarios, events, zones, and hospitals
- `c97e070` — editor workflow improvements and example scenarios
- `6dc47b4` — docs audit and alignment
- `8a3187e` — ignore local editor scratch scenario

## Known limitations

Current limitations include:
- backend uses a single global in-memory engine instance
- no persistence layer
- no multi-session simulation management
- WebSocket event stream is live-only after connection
- `/state` only exposes the most recent 200 events
- React UI action targeting is still intentionally simple and selection-driven
- editor is usable but still rough compared with a polished production authoring tool
- many scenario schema fields are represented structurally before they are deeply consumed by engine logic

## Recommended next tasks

Good next engineering tasks:
1. continue API/documentation alignment checks as features evolve
2. improve React UI action targeting and mission workflow ergonomics
3. expand scenario metadata/objective/evaluation consumption in the engine
4. improve editor property editing and scenario metadata editing
5. decide whether to formalize persistence/replay/session management
6. add more end-to-end tests across API + UI-visible workflows

## Notes on local-only files

`editor/last_scenario.json` is intentionally ignored in `.gitignore` as a local scratch scenario file and should generally not be committed.