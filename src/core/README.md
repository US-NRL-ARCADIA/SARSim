# src/core

Owns simulation state and rules.

## Module ownership

- `grid.py`: spatial grid and coordinate primitives
- `types.py`: shared domain enums and status types
- `agents.py`: agent state and movement/orientation logic
- `casualties.py`: casualty state and health/cover logic
- `buildings.py`: building state and collapse behavior
- `interactions.py`: agent-to-world and agent-to-casualty interactions
- `actions.py`: engine action definitions
- `events.py`: engine event definitions
- `action_handlers.py`: action execution logic
- `engine.py`: tick orchestration and world-state ownership
- `sensors.py`: perception helpers

## Rules

- Keep simulation behavior in `src/core/`.
- Do not import from `src/api/` here.
- Prefer adding new actions via `actions.py` + `action_handlers.py`.
- Prefer adding new domain rules in the most specific module rather than `engine.py`.
