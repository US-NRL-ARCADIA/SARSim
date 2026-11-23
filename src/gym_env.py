from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from enum import IntEnum
from typing import Any, ClassVar, cast

import gymnasium as gym
import numpy as np
from gymnasium import spaces
from numpy.typing import NDArray

from src.core.actions import EngineAction, EngineActionType
from src.core.agents import AgentClass, Orientation
from src.core.casualties import LivingState, TriageState
from src.core.engine import SimulationEngine
from src.core.grid import Coordinate
from src.core.perception import (
    FieldOfViewConeFilter,
    MiniGridThreeWideFilter,
    PerceptionFilter,
)
from src.core.types import TransportStatus
from src.utils.generator import generate_scenario
from src.utils.serializer import ScenarioDefinition, build_engine_from_scenario_definition

GymAction = dict[str, int | NDArray[np.integer[Any]]]
GymObservation = dict[
    str,
    NDArray[np.float32] | NDArray[np.int64] | NDArray[np.int8],
]


class SARSimAction(IntEnum):
    """Stable integer action names exposed through ``action_space``."""

    NOOP = 0
    MOVE_FORWARD = 1
    TRIAGE = 2
    CLEAR_DEBRIS = 3
    RETRIEVE_BODY = 4
    LOAD_CASUALTY = 5
    UNLOAD_CASUALTY = 6
    TRANSFER_CASUALTY = 7
    BREACH_ENTRYWAY = 8
    ASCEND = 9
    DESCEND = 10
    TURN_LEFT = 11
    TURN_RIGHT = 12


_GYM_TO_ENGINE_ACTION = {
    SARSimAction.MOVE_FORWARD: EngineActionType.MOVE_FORWARD,
    SARSimAction.TRIAGE: EngineActionType.TRIAGE,
    SARSimAction.CLEAR_DEBRIS: EngineActionType.CLEAR_DEBRIS,
    SARSimAction.RETRIEVE_BODY: EngineActionType.RETRIEVE_BODY,
    SARSimAction.LOAD_CASUALTY: EngineActionType.LOAD_CASUALTY,
    SARSimAction.UNLOAD_CASUALTY: EngineActionType.UNLOAD_CASUALTY,
    SARSimAction.TRANSFER_CASUALTY: EngineActionType.TRANSFER_CASUALTY,
    SARSimAction.BREACH_ENTRYWAY: EngineActionType.BREACH_ENTRYWAY,
    SARSimAction.ASCEND: EngineActionType.ASCEND,
    SARSimAction.DESCEND: EngineActionType.DESCEND,
    SARSimAction.TURN_LEFT: EngineActionType.TURN_LEFT,
    SARSimAction.TURN_RIGHT: EngineActionType.TURN_RIGHT,
}

_CASUALTY_ACTIONS = {
    SARSimAction.TRIAGE,
    SARSimAction.RETRIEVE_BODY,
    SARSimAction.LOAD_CASUALTY,
}
_COORDINATE_ACTIONS = {
    SARSimAction.CLEAR_DEBRIS,
    SARSimAction.BREACH_ENTRYWAY,
}

_ORIENTATION_INDEX = {value: index for index, value in enumerate(Orientation)}
_AGENT_CLASS_INDEX = {value: index for index, value in enumerate(AgentClass)}
_TRIAGE_INDEX = {value: index for index, value in enumerate(TriageState)}
_LIVING_INDEX = {value: index for index, value in enumerate(LivingState)}
_TRANSPORT_INDEX = {value: index for index, value in enumerate(TransportStatus)}


class SARSimEnv(gym.Env[GymObservation, GymAction]):
    """Gymnasium interface for the SARSim simulation engine.

    The fixed-size tensor observations are suitable for vectorized wrappers and
    contain masks in column zero of the agent and casualty tables. Actions use
    table indexes rather than domain IDs so every value is represented by a
    standard Gymnasium space.
    """

    metadata: ClassVar[dict[str, Any]] = {  # type: ignore[misc]
        "render_modes": ["ansi"],
        "render_fps": 4,
    }

    def __init__(
        self,
        scenario: ScenarioDefinition | None = None,
        *,
        max_agents: int = 8,
        max_casualties: int = 32,
        max_episode_steps: int | None = None,
        render_mode: str | None = None,
    ) -> None:
        super().__init__()
        if render_mode not in (None, "ansi"):
            raise ValueError("render_mode must be None or 'ansi'")

        initial_scenario = deepcopy(scenario) if scenario is not None else self._generate(0)
        grid = initial_scenario["grid"]
        self.grid_size = int(grid["N"])
        self.z_levels = int(grid["Z"])
        self.max_agents = max(max_agents, len(initial_scenario.get("agents", [])), 1)
        self.max_casualties = max(max_casualties, len(initial_scenario.get("casualties", [])), 1)
        self.max_episode_steps = max_episode_steps
        self.render_mode = render_mode
        self._scenario_template = deepcopy(scenario)
        self.engine = self._build_engine(initial_scenario)
        self._episode_steps = 0

        self.action_space = cast(spaces.Space[GymAction], spaces.Dict(
            {
                "action_type": spaces.Discrete(len(SARSimAction)),
                "agent": spaces.Discrete(self.max_agents),
                "target_casualty": spaces.Discrete(self.max_casualties),
                "target_coord": spaces.MultiDiscrete(
                    np.array([self.grid_size, self.grid_size, self.z_levels], dtype=np.int64)
                ),
            }
        ))
        self.observation_space = cast(spaces.Space[GymObservation], spaces.Dict(
            {
                "grid": spaces.Box(
                    low=0.0,
                    high=2.0,
                    shape=(self.z_levels, self.grid_size, self.grid_size, 2),
                    dtype=np.float32,
                ),
                "agents": spaces.Box(
                    low=0.0,
                    high=float(max(self.grid_size, self.z_levels, 1000)),
                    shape=(self.max_agents, 8),
                    dtype=np.float32,
                ),
                "casualties": spaces.Box(
                    low=0.0,
                    high=float(max(self.grid_size, self.z_levels, 1000)),
                    shape=(self.max_casualties, 10),
                    dtype=np.float32,
                ),
                "tick": spaces.Box(0, np.iinfo(np.int64).max, shape=(1,), dtype=np.int64),
                "rescued": spaces.Box(
                    0, self.max_casualties, shape=(1,), dtype=np.int64
                ),
            }
        ))

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[GymObservation, dict[str, Any]]:
        super().reset(seed=seed)
        scenario = (options or {}).get("scenario")
        if scenario is None:
            if self._scenario_template is None:
                generated_seed = int(self.np_random.integers(0, np.iinfo(np.int32).max))
                scenario = self._generate(generated_seed)
            else:
                scenario = deepcopy(self._scenario_template)
        self._validate_scenario_capacity(scenario)
        self.engine = self._build_engine(scenario)
        self._episode_steps = 0
        observation = self._observation()
        return observation, self._info()

    def step(
        self, action: GymAction
    ) -> tuple[GymObservation, float, bool, bool, dict[str, Any]]:
        if not self.action_space.contains(action):
            raise ValueError(f"Action is outside action_space: {action!r}")
        if self.engine.ended:
            raise RuntimeError("Episode has ended; call reset() before step()")

        rescued_before = self.engine.rescued_count
        deceased_before = self._deceased_count()
        event_count_before = len(self.engine.events)
        invalid_reason = self._queue_action(action)
        self.engine.tick()
        self._episode_steps += 1

        rescued_delta = self.engine.rescued_count - rescued_before
        deceased_delta = self._deceased_count() - deceased_before
        reward = -0.1 + rescued_delta * 100.0 - deceased_delta * 25.0
        if invalid_reason is not None:
            reward -= 1.0
        if self.engine.ended:
            reward += 25.0 if self.engine.success else -25.0

        terminated = self.engine.ended
        truncated = (
            not terminated
            and self.max_episode_steps is not None
            and self._episode_steps >= self.max_episode_steps
        )
        info = self._info()
        info["invalid_action"] = invalid_reason
        info["events"] = [
            {
                "tick": event.tick,
                "event_type": event.event_type.name,
                "message": event.message,
                "actor_id": event.actor_id,
                "payload": event.payload,
            }
            for event in self.engine.events[event_count_before:]
        ]
        return self._observation(), reward, terminated, truncated, info

    def render(self) -> str:
        agents = ", ".join(
            f"{agent.id}@({agent.coord.x},{agent.coord.y},{agent.coord.z})"
            for agent in self.engine.agents.values()
        )
        alive = len(self.engine.casualties) - self._deceased_count()
        return (
            f"tick={self.engine.current_tick} agents=[{agents}] "
            f"alive={alive} rescued={self.engine.rescued_count}"
        )

    def _queue_action(self, action: Mapping[str, object]) -> str | None:
        action_type = SARSimAction(int(cast(int, action["action_type"])))
        if action_type is SARSimAction.NOOP:
            return None

        agents = sorted(self.engine.agents)
        agent_index = int(cast(int, action["agent"]))
        if agent_index >= len(agents):
            return "agent index is not active"

        casualty_id: str | None = None
        if action_type in _CASUALTY_ACTIONS:
            casualties = sorted(self.engine.casualties)
            casualty_index = int(cast(int, action["target_casualty"]))
            if casualty_index >= len(casualties):
                return "target_casualty index is not active"
            casualty_id = casualties[casualty_index]

        target_coord: Coordinate | None = None
        if action_type in _COORDINATE_ACTIONS:
            raw_coord = np.asarray(action["target_coord"], dtype=np.int64)
            target_coord = Coordinate(
                x=int(raw_coord[0]), y=int(raw_coord[1]), z=int(raw_coord[2])
            )

        self.engine.queue_action(
            EngineAction(
                action_id=f"gym-{self._episode_steps}-{action_type.name.lower()}",
                actor_id=agents[agent_index],
                action_type=_GYM_TO_ENGINE_ACTION[action_type],
                target_casualty_id=casualty_id,
                target_coord=target_coord,
                start_tick=self.engine.current_tick,
            )
        )
        return None

    def _observation(self) -> GymObservation:
        grid = np.zeros(
            (self.z_levels, self.grid_size, self.grid_size, 2), dtype=np.float32
        )
        for x in range(self.grid_size):
            for y in range(self.grid_size):
                for z in range(self.z_levels):
                    grid[z, y, x, 0] = float(self.engine.grid.status_grid[x, y, z])
                    grid[z, y, x, 1] = float(self.engine.grid.smoke_grid[x, y, z])

        agents = np.zeros((self.max_agents, 8), dtype=np.float32)
        for index, agent_id in enumerate(sorted(self.engine.agents)):
            agent = self.engine.agents[agent_id]
            agents[index] = (
                1.0,
                agent.coord.x,
                agent.coord.y,
                agent.coord.z,
                _ORIENTATION_INDEX[agent.orientation],
                _AGENT_CLASS_INDEX[agent.agent_class],
                agent.busy_ticks_remaining,
                float(agent.payload is not None),
            )

        casualties = np.zeros((self.max_casualties, 10), dtype=np.float32)
        for index, casualty_id in enumerate(sorted(self.engine.casualties)):
            casualty = self.engine.casualties[casualty_id]
            transport = TransportStatus(casualty.transport_status)
            casualties[index] = (
                1.0,
                casualty.coord.x,
                casualty.coord.y,
                casualty.coord.z,
                casualty.health,
                casualty.decay_rate,
                float(casualty.is_covered),
                _TRIAGE_INDEX[casualty.triage_state],
                _LIVING_INDEX[casualty.living_state],
                _TRANSPORT_INDEX[transport],
            )

        return {
            "grid": grid,
            "agents": agents,
            "casualties": casualties,
            "tick": np.array([self.engine.current_tick], dtype=np.int64),
            "rescued": np.array([self.engine.rescued_count], dtype=np.int64),
        }

    def _validate_scenario_capacity(self, scenario: ScenarioDefinition) -> None:
        grid = scenario["grid"]
        if int(grid["N"]) != self.grid_size or int(grid["Z"]) != self.z_levels:
            raise ValueError("reset scenario grid dimensions must match the environment")
        if len(scenario.get("agents", [])) > self.max_agents:
            raise ValueError("reset scenario exceeds max_agents")
        if len(scenario.get("casualties", [])) > self.max_casualties:
            raise ValueError("reset scenario exceeds max_casualties")

    @staticmethod
    def _build_engine(scenario: ScenarioDefinition) -> SimulationEngine:
        engine = build_engine_from_scenario_definition(scenario)
        # Gym observations are constructed directly from engine state. Avoid
        # the browser-oriented radial/cone/belief/telemetry pass on every tick.
        engine.perception_enabled = False
        return engine

    def _info(self) -> dict[str, Any]:
        return {
            "tick": self.engine.current_tick,
            "agent_ids": sorted(self.engine.agents),
            "casualty_ids": sorted(self.engine.casualties),
            "rescued_count": self.engine.rescued_count,
            "success": self.engine.success,
        }

    def _deceased_count(self) -> int:
        return sum(
            casualty.living_state is LivingState.DECEASED
            for casualty in self.engine.casualties.values()
        )

    @staticmethod
    def _generate(seed: int) -> ScenarioDefinition:
        return generate_scenario(
            grid_size=10,
            z_depth=3,
            building_density=0.08,
            hazard_density=0.04,
            casualty_density=0.06,
            debris_density=0.05,
            seed=seed,
            agent_count=3,
        )


class SARSimFOVEnv(SARSimEnv):
    """Partially observable SARSim environment with a per-agent FOV cone.

    Every active agent receives its own current-visibility tensors. There is no
    memory of cells seen on previous ticks. Walls, intact building cells, and
    smoke block line of sight; the blocking cell itself remains visible.
    """

    def __init__(
        self,
        scenario: ScenarioDefinition | None = None,
        *,
        max_agents: int = 8,
        max_casualties: int = 32,
        max_episode_steps: int | None = None,
        render_mode: str | None = None,
        fov_range: int = 4,
        fov_angle_degrees: float = 90.0,
    ) -> None:
        self.perception_filter: PerceptionFilter = FieldOfViewConeFilter(
            max_range=fov_range,
            angle_degrees=fov_angle_degrees,
            smoke_obscures_at=0.0,
        )
        super().__init__(
            scenario=scenario,
            max_agents=max_agents,
            max_casualties=max_casualties,
            max_episode_steps=max_episode_steps,
            render_mode=render_mode,
        )
        table_high = float(max(self.grid_size, self.z_levels, 1000))
        self.observation_space = cast(spaces.Space[GymObservation], spaces.Dict(
            {
                "grid": spaces.Box(
                    low=0.0,
                    high=2.0,
                    shape=(
                        self.max_agents,
                        self.z_levels,
                        self.grid_size,
                        self.grid_size,
                        3,
                    ),
                    dtype=np.float32,
                ),
                "visibility": spaces.MultiBinary(
                    (self.max_agents, self.z_levels, self.grid_size, self.grid_size)
                ),
                "observer_mask": spaces.MultiBinary(self.max_agents),
                "agents": spaces.Box(
                    low=0.0,
                    high=table_high,
                    shape=(self.max_agents, self.max_agents, 8),
                    dtype=np.float32,
                ),
                "casualties": spaces.Box(
                    low=0.0,
                    high=table_high,
                    shape=(self.max_agents, self.max_casualties, 10),
                    dtype=np.float32,
                ),
                "tick": spaces.Box(
                    0,
                    np.iinfo(np.int64).max,
                    shape=(1,),
                    dtype=np.int64,
                ),
                "rescued": spaces.Box(
                    0,
                    self.max_casualties,
                    shape=(1,),
                    dtype=np.int64,
                ),
            }
        ))

    def _observation(self) -> GymObservation:
        grid = np.zeros(
            (
                self.max_agents,
                self.z_levels,
                self.grid_size,
                self.grid_size,
                3,
            ),
            dtype=np.float32,
        )
        visibility = np.zeros(
            (self.max_agents, self.z_levels, self.grid_size, self.grid_size),
            dtype=np.int8,
        )
        observer_mask = np.zeros(self.max_agents, dtype=np.int8)
        agents = np.zeros((self.max_agents, self.max_agents, 8), dtype=np.float32)
        casualties = np.zeros(
            (self.max_agents, self.max_casualties, 10), dtype=np.float32
        )

        agent_ids = sorted(self.engine.agents)
        casualty_ids = sorted(self.engine.casualties)
        intact_building_cells = {
            cell.coord
            for building in self.engine.buildings.values()
            for cell in building.cells.values()
            if not cell.collapsed
        }
        for observer_index, observer_id in enumerate(agent_ids):
            observer_mask[observer_index] = 1
            observer = self.engine.agents[observer_id]
            visible = self.perception_filter.visible_cells(self.engine, observer)

            for coord in visible:
                visibility[observer_index, coord.z, coord.y, coord.x] = 1
                grid[observer_index, coord.z, coord.y, coord.x, 0] = float(
                    self.engine.grid.status_grid[coord.x, coord.y, coord.z]
                )
                grid[observer_index, coord.z, coord.y, coord.x, 1] = float(
                    self.engine.grid.smoke_grid[coord.x, coord.y, coord.z]
                )
                grid[observer_index, coord.z, coord.y, coord.x, 2] = float(
                    coord in intact_building_cells
                )

            for entity_index, agent_id in enumerate(agent_ids):
                agent = self.engine.agents[agent_id]
                if agent.coord not in visible:
                    continue
                agents[observer_index, entity_index] = (
                    1.0,
                    agent.coord.x,
                    agent.coord.y,
                    agent.coord.z,
                    _ORIENTATION_INDEX[agent.orientation],
                    _AGENT_CLASS_INDEX[agent.agent_class],
                    agent.busy_ticks_remaining,
                    float(agent.payload is not None),
                )

            for entity_index, casualty_id in enumerate(casualty_ids):
                casualty = self.engine.casualties[casualty_id]
                if casualty.coord not in visible:
                    continue
                transport = TransportStatus(casualty.transport_status)
                casualties[observer_index, entity_index] = (
                    1.0,
                    casualty.coord.x,
                    casualty.coord.y,
                    casualty.coord.z,
                    casualty.health,
                    casualty.decay_rate,
                    float(casualty.is_covered),
                    _TRIAGE_INDEX[casualty.triage_state],
                    _LIVING_INDEX[casualty.living_state],
                    _TRANSPORT_INDEX[transport],
                )

        return {
            "grid": grid,
            "visibility": visibility,
            "observer_mask": observer_mask,
            "agents": agents,
            "casualties": casualties,
            "tick": np.array([self.engine.current_tick], dtype=np.int64),
            "rescued": np.array([self.engine.rescued_count], dtype=np.int64),
        }

    def _info(self) -> dict[str, Any]:
        info = super()._info()
        info["perception_filter"] = "fov_cone"
        return info


class SARSimMiniGridEnv(SARSimFOVEnv):
    """Partially observable environment with a three-cell-wide forward view."""

    def __init__(
        self,
        scenario: ScenarioDefinition | None = None,
        *,
        max_agents: int = 8,
        max_casualties: int = 32,
        max_episode_steps: int | None = None,
        render_mode: str | None = None,
        sensor_range: int = 4,
    ) -> None:
        super().__init__(
            scenario=scenario,
            max_agents=max_agents,
            max_casualties=max_casualties,
            max_episode_steps=max_episode_steps,
            render_mode=render_mode,
            fov_range=sensor_range,
        )
        self.perception_filter = MiniGridThreeWideFilter(max_range=sensor_range)

    def _info(self) -> dict[str, Any]:
        info = super()._info()
        info["perception_filter"] = "minigrid_3"
        return info
