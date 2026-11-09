# SARSim

**DISTRIBUTION STATEMENT A. Approved for public release: distribution is unlimited.**

SARSim is a search-and-rescue simulation backend for experimenting with agents, casualties, terrain hazards, and building interactions in a discrete grid world.

## Current scope

The current implementation includes:
- a 3D spatial grid
- UGV/UAV agent movement and orientation
- casualty health decay, triage, transport, unloading, and field-hospital transfer behavior
- building integrity, collapse, debris, and breach behavior
- zones, including `FIELD_HOSPITAL` semantics
- a tick-based simulation engine with queued actions and events
- a FastAPI backend for state, telemetry, scenario loading, actions, stepping, reset, and event streaming
- a React control console and a standalone Pygame scenario editor

## Requirements

- Python 3.12+ recommended
- local development currently uses macOS and `.venv`

## Setup

```sh
python3 -m venv .venv
./.venv/bin/python -m pip install -e ".[dev]"
```

If editable install support is not yet configured for your environment, install dependencies using the project's current workflow instead.

## Running tests

```sh
./.venv/bin/python -m pytest
```

## Running the server

```sh
./.venv/bin/python run_server.py
```

The development server starts a FastAPI app on `http://127.0.0.1:8000`.

## Running the UI and server together

After completing the setup steps above and installing the UI dependencies with
`cd ui && npm ci`, start both services from the project root with:

```sh
./run.sh
```

The API is available at `http://127.0.0.1:8000` and the UI at
`http://localhost:3000`. Press Ctrl+C to stop both services.
Useful endpoints include:
- `GET /state`
- `POST /actions`
- `POST /step`
- `POST /init/dev`
- `POST /scenario/load`
- `POST /scenario/load-from-path`
- `GET /telemetry`
- `POST /reset`
- `WS /events/stream`

## Running the standalone scenario editor

```sh
./.venv/bin/python editor/app.py
```

The editor is a standalone desktop application built with Pygame.
Current capabilities include:
- generate a scenario-definition map
- paint walls, debris, smoke, casualties, agents, zone cells, and building cells
- author and cycle zones, including `FIELD_HOSPITAL`
- inspect selected cells and authored content
- switch z-levels
- save/load the current scenario as JSON
- validate the scenario by rebuilding an engine from it

## Project layout

- `src/core/`: simulation model, domain types, actions, and engine logic
- `src/api/`: FastAPI server, API models, serializers, and engine state access
- `tests/`: pytest suite
- `docs/`: concise project documentation
- `ui/`: frontend client

## Documentation

Start here for quick orientation:
- `docs/project_overview.md`
- `docs/code_organization.md`
- `docs/core_simulation.md`
- `docs/api_and_state.md`
- `docs/http_api_reference.md`
- `docs/researcher_api_quick_reference.md`
- `docs/scenario_editor_user_guide.md`
- `docs/testing_and_conventions.md`
- `docs/tech_stack.md`
- `docs/domain_invariants.md`

## Notes

- The backend currently uses an in-memory global simulation engine.
- `GET /state` includes recent event history, while `WS /events/stream` provides live incremental events after connection.
- The codebase is structured so core simulation behavior stays in `src/core/`, while transport and serialization stay in `src/api/`.
- Tests are intended to serve as executable documentation for current behavior.
