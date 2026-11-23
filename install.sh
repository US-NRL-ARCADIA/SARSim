#!/usr/bin/env bash
set -Eeuo pipefail

REPOSITORY_URL="${SARSIM_REPO_URL:-https://github.com/US-NRL-ARCADIA/SARSim.git}"
REPOSITORY_REF="${SARSIM_REF:-}"
INSTALL_DIR="${SARSIM_INSTALL_DIR:-}"

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
say() { printf '\n==> %s\n' "$*"; }

usage() {
  cat <<'EOF'
Install SARSim with uv (the only dependency manager used by this project).

Usage: bash install.sh [--install-dir PATH] [--repo URL] [--ref BRANCH_OR_TAG]
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --install-dir) [ "$#" -ge 2 ] || die "--install-dir requires a path"; INSTALL_DIR="$2"; shift 2 ;;
    --repo) [ "$#" -ge 2 ] || die "--repo requires a URL"; REPOSITORY_URL="$2"; shift 2 ;;
    --ref) [ "$#" -ge 2 ] || die "--ref requires a value"; REPOSITORY_REF="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown option: $1" ;;
  esac
done

[ "$(id -u)" -ne 0 ] || die "Do not run this installer with sudo."
command -v curl >/dev/null 2>&1 || die "curl is required"

is_checkout() {
  [ -f "$1/pyproject.toml" ] && [ -f "$1/src/ui/index.html" ] &&
    grep -q 'name = "sarsim"' "$1/pyproject.toml"
}

if [ -z "$INSTALL_DIR" ]; then
  if is_checkout "$PWD" || [ -z "$(ls -A "$PWD" 2>/dev/null)" ]; then
    INSTALL_DIR="$PWD"
  else
    INSTALL_DIR="$PWD/SARSim"
  fi
fi

if ! command -v uv >/dev/null 2>&1; then
  say "Installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi
command -v uv >/dev/null 2>&1 || die "uv installation completed but uv is not on PATH; open a new shell and retry"

if ! is_checkout "$INSTALL_DIR"; then
  command -v git >/dev/null 2>&1 || die "Git is required to clone SARSim"
  [ ! -e "$INSTALL_DIR" ] || [ -z "$(ls -A "$INSTALL_DIR" 2>/dev/null)" ] ||
    die "$INSTALL_DIR exists and is not an empty SARSim checkout"
  say "Cloning SARSim"
  if [ -n "$REPOSITORY_REF" ]; then
    git clone --branch "$REPOSITORY_REF" --single-branch "$REPOSITORY_URL" "$INSTALL_DIR"
  else
    git clone "$REPOSITORY_URL" "$INSTALL_DIR"
  fi
fi

say "Installing Python 3.12 and locked dependencies with uv"
cd "$INSTALL_DIR"
unset VIRTUAL_ENV
uv sync --frozen --no-dev --python 3.12

say "Verifying SARSim"
uv run --frozen --no-dev python -c 'import fastapi, gymnasium, numpy, src.core.engine'

cat <<EOF

SARSim is ready in $INSTALL_DIR

Start it with:
  cd "$INSTALL_DIR"
  ./run.sh

Then open http://127.0.0.1:8000
EOF
