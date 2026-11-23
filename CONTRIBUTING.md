# Contributor guide

## Tooling

Use [uv](https://docs.astral.sh/uv/) for Python installation, dependency
management, environments, and command execution. Do not add pip, requirements
files, npm, or frontend build steps.

```sh
uv sync --frozen
uv run ruff check .
uv run mypy src
uv run pytest
```

## Organization

- `src/core/` owns physics, entities, actions, sensors, and events. It must not
  import API, Gymnasium, or UI modules.
- `src/api/` owns HTTP/WebSocket transport and serves the static UI.
- `src/gym_env.py` adapts the core engine to Gymnasium.
- `src/utils/` owns scenario serialization and generation.
- `src/ui/` is browser-native HTML/CSS/JavaScript. Third-party browser runtime files
  must be vendored with licenses; no Node-based build chain is permitted.
- `editor/` contains example scenario JSON only. The executable editor is a UI panel.

Use type hints on public Python APIs, dataclasses for simple state objects, and
enums for discrete domain states. Add focused pytest coverage for behavior
changes and keep Ruff, mypy, and the full test suite passing.
