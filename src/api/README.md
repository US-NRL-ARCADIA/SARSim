# src/api

Owns transport, request/response models, serialization, and API-facing engine/session access.

## Module ownership

- `models.py`: Pydantic API models
- `serializers.py`: engine-to-API translation helpers
- `state.py`: current engine instance management and scenario loading helpers
- `scenarios.py`: API-facing scenario seeding helpers
- `server.py`: FastAPI app and route definitions

## Rules

- Keep simulation rules out of this package.
- Translate API requests into core actions.
- Serialize core state into stable response models.
- Expose scenario loading, telemetry, and event-streaming behavior without moving simulation rules into the API layer.
- If behavior is wrong, inspect `src/core/` first.
