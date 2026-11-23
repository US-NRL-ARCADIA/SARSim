# SARSim handoff

## Current architecture

SARSim now has one installation and one application process:

1. `uv` installs Python 3.12 and packages from `uv.lock`.
2. FastAPI hosts the simulation API and browser workspace on port 8000.
3. The workspace in `src/ui/` uses vendored GoldenLayout and plain JavaScript.
4. The visual scenario editor is a workspace panel, not a desktop app.
5. `src/gym_env.py` provides the registered `SARSim-v0` Gymnasium environment.

There is no npm/build step, React app, Pygame process, SDL package, or Node runtime.

## Run and verify

```sh
uv sync --frozen
uv run pytest
uv run ruff check .
uv run mypy src
uv run --frozen --no-dev sarsim
```

Open <http://127.0.0.1:8000>. API docs are at `/docs`.

## Important files

- `src/core/` — simulation engine and domain model
- `src/api/server.py` — API, editor validation/export, and static UI serving
- `src/gym_env.py` — Gymnasium spaces and episode semantics
- `src/cli.py` — unified application command
- `src/ui/app.js` — UI, integrated editor, and GoldenLayout workspace
- `src/ui/vendor/` — vendored GoldenLayout and Three.js runtimes, CSS, and licenses
- `editor/*.json` — scenario examples (not an executable editor)
- `uv.lock` — reproducible Python dependency graph

## API additions

- `GET /scenario/current` exports runtime state as an editable scenario.
- `POST /scenario/validate` validates without replacing runtime state.
- `GET /health` provides a process readiness check.
- `/` serves SARSim Studio; `/ui/*` serves its static files.
- Simulation keyboard controls are WASD, Space, and C to cycle the controlled
  agent. Initial and runtime agent co-occupancy is rejected by the engine.

Existing state, action, step, reset, telemetry, scenario loading, and event
stream routes remain compatible.
