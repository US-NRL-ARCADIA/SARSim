# SARSim

**DISTRIBUTION STATEMENT A. Approved for public release: distribution is unlimited.**

SARSim is a search-and-rescue simulation environment for agent training,
scenario authoring, and human-in-the-loop experimentation in a discrete 3D grid.

## What is included

- Python simulation engine for UGV/UAV movement, casualties, hazards, buildings,
  field hospitals, actions, events, sensors, and temporal objectives
- full-state, FOV-cone, and MiniGrid-style Gymnasium environments registered as
  `SARSim-v0`, `SARSim-FOV-v0`, and `SARSim-MiniGrid-v0`
- FastAPI transport for interactive and remote clients
- separate Simulation and Scenario editor workspace modes in one browser UI
- draggable, resizable, independently persistent panels powered by vendored
  GoldenLayout
- interactive Three.js views of live and authored 3D scenes

The browser frontend is committed as static HTML/CSS/JavaScript. It has no npm,
Node.js, transpiler, or build step. The old Pygame editor and its SDL packages
have also been removed.

## Requirements

- [uv](https://docs.astral.sh/uv/) — the only dependency manager used by SARSim
- Git (only needed to clone the repository)

uv installs the correct Python version and all locked packages automatically.

## Install

```sh
git clone https://github.com/US-NRL-ARCADIA/SARSim.git
cd SARSim
uv sync --frozen --no-dev
```

Or use the bootstrap script, which installs uv when needed:

```sh
curl -LsSf https://raw.githubusercontent.com/US-NRL-ARCADIA/SARSim/main/install.sh | bash
```

## Run

```sh
./run.sh
# equivalent: uv run --frozen --no-dev sarsim
```

Open <http://127.0.0.1:8000>. The same Python process serves the API and UI.
Interactive API documentation is at <http://127.0.0.1:8000/docs>.

No second terminal, frontend development server, npm install, or build is needed.

SARSim Studio uses the NRL operations-console visual identity. Select an agent
in **Mission controls**, then use **W/A/S/D** for cardinal movement and
**Space** for the applicable action directly ahead (clear, triage, retrieve,
load, transfer, or breach). Press **C** to cycle control through every agent;
the 2D map follows the selected agent's z-level. Keyboard shortcuts are
suspended while focus is in a form control or JSON editor.

## Gymnasium

```python
import gymnasium as gym
import src  # registers all SARSim Gymnasium environments

env = gym.make("SARSim-v0", max_episode_steps=500)
observation, info = env.reset(seed=42)

action = {
    "action_type": 1,       # SARSimAction.MOVE_FORWARD
    "agent": 0,
    "target_casualty": 0,
    "target_coord": [0, 0, 0],
}
observation, reward, terminated, truncated, info = env.step(action)
```

`SARSimEnv` is a normal `gymnasium.Env` with Dict action/observation spaces,
fixed-size NumPy observations, deterministic reset seeding, reward signals, and
separate `terminated`/`truncated` results. Named actions are available from
`src.gym_env.SARSimAction`. Pass an authored scenario dictionary to
`SARSimEnv(scenario=scenario)` for a fixed training environment.

### Partially observable environments

Use `SARSim-FOV-v0` for current-visibility, per-agent observations:

```python
env = gym.make(
    "SARSim-FOV-v0",
    max_episode_steps=500,
    fov_range=4,
    fov_angle_degrees=90.0,
)
observation, info = env.reset(seed=42)
```

The FOV environment preserves the same action space and reward rules. Its
observation contains `grid[observer, z, y, x, channel]`, `visibility`,
`observer_mask`, and observer-specific `agents` and `casualties` tables. Grid
channels are cell status, smoke density, and intact-building occupancy. Hidden
cells and entities are zeroed; use `visibility` to distinguish an unknown cell
from a visible empty cell. Each agent sees only the cone on its current z-level.
Any positive smoke density, an impassable wall, or an intact building cell
blocks cells behind it. The blocking cell remains visible. This first filter has
no exploration memory: cells become unknown as soon as they leave the cone.

`SARSim-MiniGrid-v0` uses the same masked observation contract but exposes a
three-cell-wide, agent-relative corridor. Its depth is configured with
`sensor_range`; walls, buildings, and any positive smoke density occlude cells
behind them.

```python
env = gym.make("SARSim-MiniGrid-v0", sensor_range=4)
```

## Scenario editor

Use the header switch to move between mutually exclusive **Simulation** and
**Scenario editor** modes. Editor mode dedicates the full workspace to separate
GoldenLayout panels for placement tools, the scenario map, cell properties,
scenario settings, and JSON source. It can paint walls, debris, smoke,
casualties, agents, buildings, extraction zones, and field hospitals on any
z-level. The JSON panel can import the active runtime, open/download scenario
files, format source, validate without mutating runtime state, and load the
authored scenario into Simulation mode. Bundled `editor/*.json` scenarios can
be selected and loaded directly from **Mission controls**, and both maps include
a legend for agents, casualties, terrain, hazards, buildings, and zones.

Selecting an editor cell opens contextual properties for casualty health,
decay, and cover; agent class and orientation; building integrity and collapse;
cell status; and smoke density. The separate Scenario settings panel manages
active zones, difficulty, rescue constraints, and scheduled smoke events;
Editor tools provides deterministic scenario regeneration. Together they
preserve the capabilities of the former desktop editor. Building cells can be
stacked at the same x/y coordinate across z-levels to author multi-story towers.
Scenario settings also selects `FULL`, `FOV_CONE`, or `MINIGRID_3` perception
and configures its range and cone angle. During simulation, the controlled
agent's current visibility masks both the world-aligned 2D map and the 3D scene;
switching agents with **C** immediately switches the rendered sensor view.

## 3D viewer

The center stack includes **3D scene** in Simulation mode and **3D preview** in
Scenario editor mode. Both render every z-level with terrain, debris, smoke,
zones, buildings, casualties, UGVs, UAVs, orientation, and payload state. Drag
to orbit, Shift-drag or right-drag to pan, scroll to zoom, or use the
isometric/top/fit presets. Clicking an entity synchronizes the corresponding
map or properties selection.

The bundled **Vertical City Mass Rescue**, **Transit Hub Progressive
Collapse**, and **Harbor Refinery Emergency** scenarios are dense 3D showcases
with mixed UGV/UAV teams, stackable buildings, collapse damage, smoke, debris,
casualties, scheduled events, extraction areas, and field hospitals.

Three.js r187 and its MIT license are vendored under `src/ui/vendor/`; no CDN,
npm installation, frontend build, or network connection is required at runtime.

GoldenLayout lets users drag tabs, resize panels, maximize views, add duplicate
panels, and save their preferred workspace locally. Simulation and editor
layouts are persisted independently. GoldenLayout is vendored, so the
application remains usable offline.

## Development

```sh
uv sync --frozen
uv run pytest
uv run ruff check .
uv run mypy src
```

Runtime dependencies are deliberately small: NumPy, Gymnasium, FastAPI, and
Uvicorn. Development tools live in uv's `dev` dependency group.

## Layout

- `src/core/` — simulation model
- `src/api/` — HTTP/WebSocket transport and static UI serving
- `src/gym_env.py` — Gymnasium environment
- `src/utils/` — scenario generation and serialization
- `src/ui/` — packaged, ready-to-serve dependency-free browser workspace
- `editor/*.json` — example scenarios
- `tests/` — regression suite
