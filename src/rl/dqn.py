from __future__ import annotations

# MLX currently exposes dynamic layer attributes that strict mypy cannot model.
# mypy: disable-error-code="name-defined,misc,attr-defined"
import json
import random
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, ClassVar

import numpy as np
from numpy.typing import NDArray

from src.core.actions import EngineAction, EngineActionType
from src.core.agents import Agent, AgentClass, Orientation
from src.core.casualties import LivingState
from src.core.engine import SimulationEngine
from src.core.geometry import are_adjacent
from src.core.grid import Coordinate
from src.core.types import CellStatus, TransportStatus

try:
    import mlx.core as mx
    from mlx import nn
    from mlx import optimizers as optim
except ImportError:  # MLX is intentionally platform-gated in pyproject.toml.
    mx = None  # type: ignore[assignment]
    nn = None  # type: ignore[assignment]
    optim = None  # type: ignore[assignment]


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPOSITORY_ROOT / "agents"
ACTION_NAMES = ("MOVE_FORWARD", "TURN_LEFT", "TURN_RIGHT", "INTERACT", "WAIT")
ACTION_COUNT = len(ACTION_NAMES)


@dataclass(frozen=True)
class CheckpointMetadata:
    name: str
    algorithm: str
    backend: str
    grid_size: int
    input_size: int
    hidden_size: int
    action_names: tuple[str, ...]
    episodes_trained: int
    mean_rescued_last_20: float
    mean_reward_last_20: float
    held_out_episodes: int
    held_out_living_rescue_rate: float
    held_out_success_rate: float
    description: str


def backend_status() -> dict[str, object]:
    """Describe the accelerated backend without failing on non-Apple hosts."""
    if mx is None:
        return {
            "available": False,
            "backend": "unavailable",
            "device": "MLX requires Apple Silicon; install the platform dependency",
        }
    metal_available = bool(mx.metal.is_available())
    return {
        "available": metal_available,
        "backend": "mlx",
        "device": "Apple Metal GPU" if metal_available else "MLX CPU",
        "version": getattr(mx, "__version__", "unknown"),
    }


def observation_size(grid_size: int) -> int:
    """Seven map channels, compact state, and planner-guidance features."""
    return 7 * grid_size * grid_size + 13


def encode_engine(engine: SimulationEngine, agent: Agent | None = None) -> NDArray[np.float32]:
    """Encode full simulator state into the fixed DQN feature vector."""
    size = engine.grid.N
    if agent is None:
        agent = controlled_ugv(engine)
    status = engine.grid.status_grid[:, :, 0].astype(np.float32).T / 2.0
    smoke = engine.grid.smoke_grid[:, :, 0].astype(np.float32).T
    agent_map = np.zeros((size, size), dtype=np.float32)
    casualty_health = np.zeros((size, size), dtype=np.float32)
    casualty_decay = np.zeros((size, size), dtype=np.float32)
    casualty_covered = np.zeros((size, size), dtype=np.float32)
    hospital = np.zeros((size, size), dtype=np.float32)

    if agent is not None and agent.coord.z == 0:
        agent_map[agent.coord.y, agent.coord.x] = 1.0
    for casualty in engine.casualties.values():
        if casualty.coord.z != 0 or casualty.id in engine.rescued_casualty_ids:
            continue
        y, x = casualty.coord.y, casualty.coord.x
        alive = casualty.living_state is LivingState.ALIVE
        casualty_health[y, x] = casualty.health / 100.0 if alive else -1.0
        casualty_decay[y, x] = min(float(casualty.decay_rate), 1.0)
        casualty_covered[y, x] = float(casualty.is_covered)
    for zone in engine.zones:
        if zone.get("zone_type") != "FIELD_HOSPITAL":
            continue
        for cell in zone.get("cells", []):
            if int(cell["z"]) == 0:
                hospital[int(cell["y"]), int(cell["x"])] = 1.0

    orientation = np.zeros(4, dtype=np.float32)
    scalars = np.zeros(13, dtype=np.float32)
    if agent is not None:
        scalars[0] = agent.coord.x / max(1, size - 1)
        scalars[1] = agent.coord.y / max(1, size - 1)
        scalars[2] = float(agent.payload is not None)
        orientation[list(Orientation).index(agent.orientation)] = 1.0
    scalars[3:7] = orientation
    scalars[7] = engine.rescued_count / max(1, len(engine.casualties))
    scalars[8 + heuristic_action(engine)] = 1.0
    maps = (
        status,
        smoke,
        agent_map,
        casualty_health,
        casualty_decay,
        casualty_covered,
        hospital,
    )
    return np.concatenate([*(channel.reshape(-1) for channel in maps), scalars]).astype(
        np.float32,
        copy=False,
    )


def controlled_ugv(engine: SimulationEngine) -> Agent | None:
    return next(
        (
            engine.agents[agent_id]
            for agent_id in sorted(engine.agents)
            if engine.agents[agent_id].agent_class is AgentClass.UGV
        ),
        None,
    )


if nn is not None:

    class QNetwork(nn.Module):
        def __init__(self, input_size: int, hidden_size: int, action_count: int) -> None:
            super().__init__()
            self.layers = [
                nn.Linear(input_size, hidden_size),
                nn.ReLU(),
                nn.Linear(hidden_size, hidden_size),
                nn.ReLU(),
                nn.Linear(hidden_size, action_count),
            ]

        def __call__(self, value: Any) -> Any:
            for layer in self.layers:
                value = layer(value)
            return value

else:

    class QNetwork:  # type: ignore[no-redef]
        def __init__(self, *_: object, **__: object) -> None:
            raise RuntimeError("MLX is not available on this host")


class ReplayBuffer:
    def __init__(self, capacity: int, seed: int) -> None:
        self._items: deque[
            tuple[NDArray[np.float32], int, float, NDArray[np.float32], bool, bool]
        ] = deque(maxlen=capacity)
        self._rng = random.Random(seed)

    def __len__(self) -> int:
        return len(self._items)

    def append(
        self,
        state: NDArray[np.float32],
        action: int,
        reward: float,
        next_state: NDArray[np.float32],
        done: bool,
        demonstration: bool,
    ) -> None:
        self._items.append((state, action, reward, next_state, done, demonstration))

    def sample(
        self,
        count: int,
    ) -> tuple[
        NDArray[np.float32],
        NDArray[np.int32],
        NDArray[np.float32],
        NDArray[np.float32],
        NDArray[np.float32],
        NDArray[np.float32],
    ]:
        batch = self._rng.sample(list(self._items), count)
        states, actions, rewards, next_states, dones, demonstrations = zip(
            *batch,
            strict=True,
        )
        return (
            np.stack(states),
            np.asarray(actions, dtype=np.int32),
            np.asarray(rewards, dtype=np.float32),
            np.stack(next_states),
            np.asarray(dones, dtype=np.float32),
            np.asarray(demonstrations, dtype=np.float32),
        )


class DQNPolicy:
    """MLX DQN policy and its context-sensitive SAR rescue action adapter."""

    action_names: ClassVar[tuple[str, ...]] = ACTION_NAMES

    def __init__(self, grid_size: int, hidden_size: int = 128, seed: int = 0) -> None:
        if mx is None or nn is None:
            raise RuntimeError("MLX is not available; training requires Apple Silicon")
        self.grid_size = grid_size
        self.input_size = observation_size(grid_size)
        self.hidden_size = hidden_size
        mx.random.seed(seed)
        self.model = QNetwork(self.input_size, hidden_size, ACTION_COUNT)
        mx.eval(self.model.parameters())

    def action_values(self, observation: NDArray[np.float32]) -> NDArray[np.float32]:
        values = self.model(mx.array(observation[None, :]))
        return np.asarray(values[0], dtype=np.float32)

    def select_action(self, observation: NDArray[np.float32]) -> int:
        return int(np.argmax(self.action_values(observation)))

    def select_engine_action(self, engine: SimulationEngine) -> int:
        """Select a safety-constrained Q action with planner guidance."""
        observation = encode_engine(engine)
        values = self.action_values(observation)
        agent = controlled_ugv(engine)
        if agent is None:
            return 4
        if interaction_action(engine, agent, "mask-probe") is None:
            values[3] = -np.inf
        if engine.rescued_count < len(engine.casualties):
            values[4] = -np.inf
        q_action = int(np.argmax(values))
        guidance = heuristic_action(engine)
        # A learned override must be decisive. This prevents compounding motion
        # errors while still allowing Q-learning to depart from the shortest
        # route when casualty utility provides a strong reason.
        if q_action != guidance and values[q_action] - values[guidance] < 5.0:
            return guidance
        return q_action

    def save(self, metadata: CheckpointMetadata) -> dict[str, object]:
        AGENTS_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = _safe_checkpoint_name(metadata.name)
        weights_path = AGENTS_DIR / f"{safe_name}.safetensors"
        metadata_path = AGENTS_DIR / f"{safe_name}.json"
        self.model.save_weights(str(weights_path))
        metadata_path.write_text(
            json.dumps(asdict(metadata), indent=2) + "\n",
            encoding="utf-8",
        )
        return checkpoint_summary(metadata_path)

    @classmethod
    def load(cls, name: str) -> DQNPolicy:
        metadata_path = AGENTS_DIR / f"{_safe_checkpoint_name(name)}.json"
        raw = json.loads(metadata_path.read_text(encoding="utf-8"))
        policy = cls(
            grid_size=int(raw["grid_size"]),
            hidden_size=int(raw["hidden_size"]),
        )
        policy.model.load_weights(str(metadata_path.with_suffix(".safetensors")))
        mx.eval(policy.model.parameters())
        return policy

    def engine_action(self, engine: SimulationEngine, action: int) -> EngineAction | None:
        agent = controlled_ugv(engine)
        if agent is None:
            return None
        action_id = f"dqn-{engine.current_tick}-{ACTION_NAMES[action].lower()}"
        if action == 0:
            return EngineAction(action_id, agent.id, EngineActionType.MOVE_FORWARD)
        if action == 1:
            return EngineAction(action_id, agent.id, EngineActionType.TURN_LEFT)
        if action == 2:
            return EngineAction(action_id, agent.id, EngineActionType.TURN_RIGHT)
        if action == 3:
            return interaction_action(engine, agent, action_id)
        return None

    def step_engine(self, engine: SimulationEngine) -> dict[str, object]:
        if engine.grid.N != self.grid_size:
            raise ValueError(
                f"agent requires a {self.grid_size}x{self.grid_size} scenario; "
                f"active scenario is {engine.grid.N}x{engine.grid.N}"
            )
        action_index = self.select_engine_action(engine)
        action = self.engine_action(engine, action_index)
        if action is not None:
            engine.queue_action(action)
        engine.tick()
        return {
            "action": ACTION_NAMES[action_index],
            "tick": engine.current_tick,
            "rescued_count": engine.rescued_count,
        }


def interaction_action(
    engine: SimulationEngine,
    agent: Agent,
    action_id: str,
) -> EngineAction | None:
    """Resolve the DQN's compact INTERACT intent against current world state."""
    if agent.payload is not None and _is_at_hospital(engine, agent.coord):
        return EngineAction(action_id, agent.id, EngineActionType.TRANSFER_CASUALTY)

    adjacent = [] if agent.payload is not None else [
        casualty
        for casualty in engine.casualties.values()
        if casualty.id not in engine.rescued_casualty_ids
        and casualty.transport_status != TransportStatus.LOADED
        and are_adjacent(agent.coord, casualty.coord)
    ]
    if adjacent:
        casualty = min(adjacent, key=_casualty_priority)
        if casualty.is_covered:
            return EngineAction(
                action_id,
                agent.id,
                EngineActionType.CLEAR_DEBRIS,
                target_coord=casualty.coord,
            )
        action_type = (
            EngineActionType.LOAD_CASUALTY
            if casualty.living_state is LivingState.ALIVE
            else EngineActionType.RETRIEVE_BODY
        )
        return EngineAction(
            action_id,
            agent.id,
            action_type,
            target_casualty_id=casualty.id,
        )

    ahead = _coordinate_ahead(agent)
    if not engine.grid.is_in_bounds(ahead):
        return None
    if engine.grid.get_cell_status(ahead) is CellStatus.PASSABLE:
        return EngineAction(
            action_id,
            agent.id,
            EngineActionType.CLEAR_DEBRIS,
            target_coord=ahead,
        )
    if _building_at(engine, ahead):
        return EngineAction(
            action_id,
            agent.id,
            EngineActionType.BREACH_ENTRYWAY,
            target_coord=ahead,
        )
    return None


def heuristic_action(engine: SimulationEngine) -> int:
    """Shortest-path rescue demonstrator used to seed useful replay data."""
    agent = controlled_ugv(engine)
    if agent is None:
        return 4
    if interaction_action(engine, agent, "probe") is not None:
        return 3

    if agent.payload is not None:
        goals = _hospital_approach_cells(engine)
    else:
        casualties = [
            casualty
            for casualty in engine.casualties.values()
            if casualty.id not in engine.rescued_casualty_ids
            and casualty.transport_status != TransportStatus.LOADED
        ]
        if not casualties:
            return 4
        target = min(casualties, key=_casualty_priority)
        goals = _adjacent_ground_cells(engine, target.coord)
    next_coord = _next_path_step(engine, agent.coord, goals)
    if next_coord is None:
        return 4
    desired = _orientation_to(agent.coord, next_coord)
    if desired is agent.orientation:
        return 0
    orientations = list(Orientation)
    delta = (orientations.index(desired) - orientations.index(agent.orientation)) % 4
    return 2 if delta in (1, 2) else 1


def list_checkpoints() -> list[dict[str, object]]:
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    checkpoints: list[dict[str, object]] = []
    for path in sorted(AGENTS_DIR.glob("*.json")):
        try:
            checkpoints.append(checkpoint_summary(path))
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
            continue
    return checkpoints


def checkpoint_summary(path: Path) -> dict[str, object]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    weights_path = path.with_suffix(".safetensors")
    return {
        "name": str(raw["name"]),
        "algorithm": str(raw["algorithm"]),
        "backend": str(raw["backend"]),
        "grid_size": int(raw["grid_size"]),
        "episodes_trained": int(raw["episodes_trained"]),
        "mean_rescued_last_20": float(raw["mean_rescued_last_20"]),
        "mean_reward_last_20": float(raw["mean_reward_last_20"]),
        "held_out_episodes": int(raw.get("held_out_episodes", 0)),
        "held_out_living_rescue_rate": float(raw.get("held_out_living_rescue_rate", 0.0)),
        "held_out_success_rate": float(raw.get("held_out_success_rate", 0.0)),
        "description": str(raw.get("description", "")),
        "ready": weights_path.is_file(),
        "weights_bytes": weights_path.stat().st_size if weights_path.is_file() else 0,
    }


def _safe_checkpoint_name(name: str) -> str:
    safe = "".join(character for character in name if character.isalnum() or character in "-_")
    if not safe or safe != name:
        raise ValueError("checkpoint name may contain only letters, numbers, '-' and '_'")
    return safe


def _coordinate_ahead(agent: Agent) -> Coordinate:
    delta = {
        Orientation.NORTH: (0, -1),
        Orientation.EAST: (1, 0),
        Orientation.SOUTH: (0, 1),
        Orientation.WEST: (-1, 0),
    }[agent.orientation]
    return Coordinate(agent.coord.x + delta[0], agent.coord.y + delta[1], agent.coord.z)


def _casualty_priority(casualty: Any) -> tuple[int, float, float, str]:
    survival_time = casualty.health / max(float(casualty.decay_rate), 0.001)
    deceased_rank = int(casualty.living_state is LivingState.DECEASED)
    return (deceased_rank, survival_time, casualty.health, casualty.id)


def _is_at_hospital(engine: SimulationEngine, coord: Coordinate) -> bool:
    for zone in engine.zones:
        if zone.get("zone_type") != "FIELD_HOSPITAL":
            continue
        for cell in zone.get("cells", []):
            hospital = Coordinate(int(cell["x"]), int(cell["y"]), int(cell["z"]))
            if coord == hospital or are_adjacent(coord, hospital):
                return True
    return False


def _hospital_approach_cells(engine: SimulationEngine) -> set[Coordinate]:
    cells: set[Coordinate] = set()
    for zone in engine.zones:
        if zone.get("zone_type") != "FIELD_HOSPITAL":
            continue
        for raw in zone.get("cells", []):
            coord = Coordinate(int(raw["x"]), int(raw["y"]), int(raw["z"]))
            cells.add(coord)
            cells.update(_adjacent_ground_cells(engine, coord))
    return cells


def _adjacent_ground_cells(engine: SimulationEngine, coord: Coordinate) -> set[Coordinate]:
    candidates = {
        Coordinate(coord.x - 1, coord.y, 0),
        Coordinate(coord.x + 1, coord.y, 0),
        Coordinate(coord.x, coord.y - 1, 0),
        Coordinate(coord.x, coord.y + 1, 0),
    }
    return {
        candidate
        for candidate in candidates
        if engine.grid.is_in_bounds(candidate)
        and engine.grid.get_cell_status(candidate) is not CellStatus.IMPASSABLE
    }


def _next_path_step(
    engine: SimulationEngine,
    start: Coordinate,
    goals: set[Coordinate],
) -> Coordinate | None:
    if start in goals:
        return None
    frontier = deque([start])
    previous: dict[Coordinate, Coordinate | None] = {start: None}
    occupied = {
        candidate.coord
        for candidate in engine.agents.values()
        if candidate.coord != start
    }
    goal: Coordinate | None = None
    while frontier:
        current = frontier.popleft()
        for neighbor in _adjacent_ground_cells(engine, current):
            if neighbor in previous or neighbor in occupied:
                continue
            previous[neighbor] = current
            if neighbor in goals:
                goal = neighbor
                frontier.clear()
                break
            frontier.append(neighbor)
    if goal is None:
        return None
    while previous[goal] != start:
        parent = previous[goal]
        if parent is None:
            return None
        goal = parent
    return goal


def _orientation_to(start: Coordinate, target: Coordinate) -> Orientation:
    if target.x > start.x:
        return Orientation.EAST
    if target.x < start.x:
        return Orientation.WEST
    if target.y > start.y:
        return Orientation.SOUTH
    return Orientation.NORTH


def _building_at(engine: SimulationEngine, coord: Coordinate) -> bool:
    key = (coord.x, coord.y, coord.z)
    return (
        engine.grid.get_cell_status(coord) is CellStatus.IMPASSABLE
        and any(key in building.cells for building in engine.buildings.values())
    )


def require_training_modules() -> tuple[Any, Any, Any]:
    if mx is None or nn is None or optim is None:
        raise RuntimeError("MLX training backend is unavailable on this host")
    return mx, nn, optim
