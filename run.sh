#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it from https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

cd "$ROOT_DIR"
echo "Starting SARSim Studio at http://127.0.0.1:8000"
exec uv run --frozen --no-dev sarsim
