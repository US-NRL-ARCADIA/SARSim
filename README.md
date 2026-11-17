# SARSim

**DISTRIBUTION STATEMENT A. Approved for public release: distribution is unlimited.**

SARSim is a search-and-rescue simulation backend for experimenting with agents, casualties, terrain hazards, and building interactions in a discrete grid world.

## Current scope

The current implementation includes:
- a 3D spatial grid
- UGV/UAV agent movement and orientation
- casualty health decay, triage, transport, unloading, and field-hospital transfer behavior
- building integrity, collapse, debris, and breach behavior
- zones, including `FIELD_HOSPITAL` semantics
- a tick-based simulation engine with queued actions and events
- a FastAPI backend for state, telemetry, scenario loading, actions, stepping, reset, and event streaming
- a React control console and a standalone Pygame scenario editor

## Requirements

- Git
- Python 3.11 or newer; Python 3.12 is recommended and is the version used in CI
- Node.js 20 or newer with npm (required for the browser UI)
- macOS or Linux for the provided shell scripts

Do not use the `python3` bundled with macOS. It is commonly Python 3.9 and is
too old for this project. Follow one of the prerequisite installation sections
below before cloning SARSim.

### macOS: install all prerequisites

These steps work on both Apple Silicon and Intel Macs.

1. Install Apple's Command Line Tools. Run:

```sh
if ! xcode-select -p >/dev/null 2>&1; then
  xcode-select --install
fi
```

If an installer window opens, finish it before running the next command. If the
tools are already installed, this command makes no changes.

2. Check whether [Homebrew](https://brew.sh/) is installed:

```sh
brew --version
```

If that prints `command not found`, install Homebrew with its official command:

```sh
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

At the end of installation, Homebrew prints a `Next steps` command that adds
`brew` to the shell path. Run the command it prints. If needed, use the matching
commands below.

Apple Silicon Mac (`arm64`):

```sh
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> "$HOME/.zprofile"
eval "$(/opt/homebrew/bin/brew shellenv)"
```

Intel Mac (`x86_64`):

```sh
echo 'eval "$(/usr/local/bin/brew shellenv)"' >> "$HOME/.zprofile"
eval "$(/usr/local/bin/brew shellenv)"
```

To determine which Mac you have, run `uname -m`.

3. Install Git, Python 3.12, Node.js, and npm:

```sh
brew update
brew install git python@3.12 node
```

The Homebrew `node` package installs both the `node` command and the `npm`
command. Do not run a separate npm installer.

4. Confirm that every prerequisite is available:

```sh
git --version
python3.12 --version
node --version
npm --version
```

`python3.12 --version` must report Python 3.12.x, and `node --version` must
report v20 or newer. Do not continue until all four commands succeed.

### Ubuntu 24.04: install all prerequisites

For Ubuntu 24.04, install Git, Python 3.12, and the Python virtual-environment
module from Ubuntu, then install Node.js 22 (which includes npm) from NodeSource:

```sh
sudo apt-get update
sudo apt-get install -y git python3.12 python3.12-venv ca-certificates curl
curl -fsSL https://deb.nodesource.com/setup_22.x -o /tmp/nodesource_setup.sh
sudo -E bash /tmp/nodesource_setup.sh
sudo apt-get install -y nodejs
git --version
python3.12 --version
node --version
npm --version
```

Users of other Linux distributions must install the same prerequisite versions
with their distribution's package manager before continuing.

## Fresh installation

After **all four prerequisite version commands succeed**, run the following
commands from the directory where you want to clone SARSim. Copy the commands
exactly; commands after `cd SARSim` must be run from the repository root.

```sh
git clone https://github.com/US-NRL-ARCADIA/SARSim.git
cd SARSim

# Use Python 3.12 explicitly so macOS does not select its older system Python.
python3.12 -m venv .venv

# This upgrade is required. Older pip versions cannot install this
# pyproject.toml-based project in editable mode.
./.venv/bin/python -m pip install --upgrade pip setuptools wheel
./.venv/bin/python -m pip install -e ".[dev]"

# Install the browser UI dependencies from the committed lock file.
npm --prefix ui ci
```

The commands use the virtual environment's Python directly, so activating the
environment is optional. To activate it for an interactive shell, run:

```sh
source .venv/bin/activate
```

Verify the installation before starting the application:

```sh
./.venv/bin/python --version
./.venv/bin/python -m pytest
npm --prefix ui run build
```

The Python test suite and UI production build should both finish successfully.
`npm ci` currently reports warnings about deprecated transitive packages and an
npm audit summary. Those warnings do not mean installation failed. Do not run
`npm audit fix --force`, because it can replace locked dependencies with
breaking versions. The `npm ci` command must exit successfully, and the final
UI build must say that it compiled successfully.

### Fixing an older pip installation

If installation reports the following error:

```text
File "setup.py" or "setup.cfg" not found. Directory cannot be installed in editable mode
```

the virtual environment is using a version of pip that predates editable
`pyproject.toml` installs. Upgrade the packaging tools and retry:

```sh
./.venv/bin/python -m pip install --upgrade pip setuptools wheel
./.venv/bin/python -m pip install -e ".[dev]"
```

If pip then reports that the Python version is unsupported, the environment was
created with an older interpreter. Remove only the `.venv` directory, install
Python 3.12, and repeat the fresh installation commands with `python3.12`.

### Fixing `node: command not found` or `npm: command not found`

On macOS, install the Homebrew Node.js package and verify both commands:

```sh
brew install node
node --version
npm --version
```

If `brew` is also not found, complete the Homebrew installation and shell-path
steps in the macOS prerequisite section first. Then run the fresh installation
again starting with `npm --prefix ui ci`; the Python environment does not need
to be recreated.

## Running tests

```sh
./.venv/bin/python -m pytest
```

## Running the full application

After completing the fresh installation, start both services from the project
root with:

```sh
./run.sh
```

Leave that terminal open while using SARSim. Wait for the UI to report that it
compiled, then open `http://localhost:3000` in a browser. The API is available
at `http://127.0.0.1:8000`. Press Ctrl+C in the terminal to stop both services.

> **Open `http://localhost:3000` to use SARSim.** Port 8000 is the backend API
> and does not contain the browser application.

If startup reports that port 8000 or 3000 is already in use, another copy of
the application (or another service) is running. On macOS, identify it with:

```sh
lsof -nP -iTCP:8000 -sTCP:LISTEN
lsof -nP -iTCP:3000 -sTCP:LISTEN
```

Stop the listed process from the terminal where it was started, then run
`./run.sh` again.

## Running only the backend API

```sh
./.venv/bin/python run_server.py
```

This command starts **only the FastAPI backend** at `http://127.0.0.1:8000`; it
does not start the SARSim browser application. Interactive API documentation is
available at `http://127.0.0.1:8000/docs`.

Useful endpoints include:
- `GET /state`
- `POST /actions`
- `POST /step`
- `POST /init/dev`
- `POST /scenario/load`
- `POST /scenario/load-from-path`
- `GET /telemetry`
- `POST /reset`
- `WS /events/stream`

## Running the standalone scenario editor

```sh
./.venv/bin/python editor/app.py
```

The editor is a standalone desktop application built with Pygame.
Current capabilities include:
- generate a scenario-definition map
- paint walls, debris, smoke, casualties, agents, zone cells, and building cells
- author and cycle zones, including `FIELD_HOSPITAL`
- inspect selected cells and authored content
- switch z-levels
- save/load the current scenario as JSON
- validate the scenario by rebuilding an engine from it

## Project layout

- `src/core/`: simulation model, domain types, actions, and engine logic
- `src/api/`: FastAPI server, API models, serializers, and engine state access
- `tests/`: pytest suite
- `docs/`: concise project documentation
- `ui/`: frontend client

## Documentation

Start here for quick orientation:
- `docs/project_overview.md`
- `docs/code_organization.md`
- `docs/core_simulation.md`
- `docs/api_and_state.md`
- `docs/http_api_reference.md`
- `docs/researcher_api_quick_reference.md`
- `docs/scenario_editor_user_guide.md`
- `docs/testing_and_conventions.md`
- `docs/tech_stack.md`
- `docs/domain_invariants.md`

## Notes

- The backend currently uses an in-memory global simulation engine.
- `GET /state` includes recent event history, while `WS /events/stream` provides live incremental events after connection.
- The codebase is structured so core simulation behavior stays in `src/core/`, while transport and serialization stay in `src/api/`.
- Tests are intended to serve as executable documentation for current behavior.
