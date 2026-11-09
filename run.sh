#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON="$ROOT_DIR/.venv/bin/python"
UI_DIR="$ROOT_DIR/ui"

if [ ! -x "$PYTHON" ]; then
  echo "Python environment not found. Set it up with: python3.12 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]'" >&2
  exit 1
fi
if [ ! -x "$UI_DIR/node_modules/.bin/react-scripts" ]; then
  echo "UI dependencies not found. Set them up with: cd ui && npm ci" >&2
  exit 1
fi

api_pid=
ui_pid=
cleanup() {
  trap - INT TERM EXIT
  [ -z "$api_pid" ] || kill "$api_pid" 2>/dev/null || true
  [ -z "$ui_pid" ] || kill -TERM "$ui_pid" 2>/dev/null || true
  [ -z "$api_pid" ] || wait "$api_pid" 2>/dev/null || true
  [ -z "$ui_pid" ] || wait "$ui_pid" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

cd "$ROOT_DIR"

echo "Starting SARSim API at http://127.0.0.1:8000"
"$PYTHON" "$ROOT_DIR/run_server.py" &
api_pid=$!

echo "Starting SARSim UI at http://localhost:3000"
cd "$UI_DIR"
npm start &
ui_pid=$!

wait "$api_pid"
