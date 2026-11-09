# Contributor Guide

## Tech stack

- OS (dev): macOS
- Python: 3.14.6 (Homebrew) locally; CI uses Python 3.12.
- Virtual environment: `.venv` in project root.
- Package installation: always `python -m pip install ...`.

See `docs/tech_stack.md` for more details on the stack and dependencies.

## Code organization

- Core model (physics, entities, events) lives in `src/core/`.
  - **Rule:** No imports from `src/api` or `editor` inside `src/core`.
- API / controller (gRPC, WebSocket, SimulationEngine) lives in `src/api/`.
- Utilities (serialization, procedural generation, helpers) live in `src/utils/`.
- Editor UI lives under `editor/`.
- Tests mirror source layout:
  - `src/core/grid.py` → `tests/test_physics.py`
  - `src/core/entities.py` → `tests/test_entities.py` (Phase 2+)
  - `src/api/engine.py` → `tests/test_api.py`, `tests/test_concurrency.py`
  - `src/utils/serializer.py` → `tests/test_utils.py`

## Style and types

- Python 3.12+ features allowed; local dev is on 3.14.6.
- Type hints are required on all public functions and methods.
- Use `@dataclass` for simple stateful objects, including:
  - `Coordinate`
  - `Agent`
  - `Casualty`
  - `BuildingCell`
  - `Building`
  - `Event`
- Use enums instead of raw string literals for discrete states:
  - `Orientation`
  - `AgentClass`
  - `TriageState`
  - `LivingState`
  - Action types
  - Event types

## Testing

- Use `pytest`.
- New features must come with tests:
  - Core physics and movement → `tests/test_physics.py`.
  - Entity behavior (casualties, buildings, actions) → `tests/test_entities.py`.
  - API/engine and concurrency → `tests/test_api.py`, `tests/test_concurrency.py`.
  - Utilities (serialization, generation) → `tests/test_utils.py`.
- Prefer small, focused tests that encode the spec:
  - Movement constraints (UGV/UAV rules, co-occupancy).
  - Health decay and triage rules.
  - Multi-tick actions and busy timers.
  - Concurrency resolution strategies.

### Local workflow

Run these before committing:

```bash
source .venv/bin/activate
python -m ruff check .
python -m mypy src
python -m pytest
```

All three should pass before opening a PR.

## CI workflow

- GitHub Actions workflow in `.github/workflows/test-and-lint.yml` runs on push/PR:
  - `python -m ruff check .`
  - `python -m mypy src`
  - `python -m pytest`
- Contributions should keep CI green.

## AI-specific guidance

For generative model contributions:

- Avoid editing multiple unrelated modules in a single change.
- Do not import `src/api` or `editor` from `src/core`.
- Respect dataclass and enum usage; do not reintroduce stringly-typed states.
- Keep movement and physics logic pure in `src/core` (no networking or I/O).
- When adding new actions or events:
  - Define clear enums and dataclasses.
  - Add tests that demonstrate the state transitions end-to-end.

By following these guidelines, contributors (human and AI) can evolve SARSim rapidly while keeping the architecture clean and behavior well-tested.
