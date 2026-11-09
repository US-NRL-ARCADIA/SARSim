#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$PROJECT_DIR/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  echo "Project virtualenv not found at $PYTHON" >&2
  echo "Create it and install project dependencies before running the editor." >&2
  exit 1
fi

exec "$PYTHON" "$PROJECT_DIR/editor/app.py" "$@"
