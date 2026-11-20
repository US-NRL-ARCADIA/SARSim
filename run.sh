#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON="$ROOT_DIR/.venv/bin/python"
UI_DIR="$ROOT_DIR/ui"

add_to_path() {
  [ -d "$1" ] || return 0
  case ":$PATH:" in
    *":$1:"*) ;;
    *) PATH="$1:$PATH" ;;
  esac
}

# A Homebrew installation can be valid even when the shell that launches this
# script has not loaded brew's profile entry. Locate Node/npm in both standard
# Homebrew prefixes instead of requiring the user to repair PATH manually.
for brew_command in /opt/homebrew/bin/brew /usr/local/bin/brew; do
  if [ -x "$brew_command" ]; then
    add_to_path "$(dirname -- "$brew_command")"
    node_prefix=$("$brew_command" --prefix node 2>/dev/null || true)
    [ -z "$node_prefix" ] || add_to_path "$node_prefix/bin"
  fi
done
export PATH

if [ ! -x "$PYTHON" ]; then
  echo "Python environment not found. Follow the Fresh installation section in README.md." >&2
  echo "Be sure to upgrade pip before installing: .venv/bin/python -m pip install --upgrade pip setuptools wheel" >&2
  exit 1
fi
if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo "Node.js or npm was not found, including in the standard Homebrew locations." >&2
  echo "Run the installer again to detect and install it: bash \"$ROOT_DIR/install.sh\"" >&2
  exit 1
fi
node_major=$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || true)
case "$node_major" in
  ''|*[!0-9]*|0|1|2|3|4|5|6|7|8|9|10|11|12|13|14|15|16|17|18|19)
    echo "Node.js 20 or newer is required; found: $(node --version 2>/dev/null || echo unknown)" >&2
    echo "Run the installer again to upgrade it: bash \"$ROOT_DIR/install.sh\"" >&2
    exit 1
    ;;
esac
if [ ! -x "$UI_DIR/node_modules/.bin/react-scripts" ]; then
  echo "UI dependencies not found; installing them from package-lock.json."
  npm --prefix "$UI_DIR" ci
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
