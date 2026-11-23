from __future__ import annotations

import gymnasium as gym
import numpy as np
from gymnasium.utils.env_checker import check_env

import src  # noqa: F401 - importing the package registers SARSim-v0
from src.gym_env import SARSimAction, SARSimEnv, SARSimFOVEnv, SARSimMiniGridEnv


def _fov_scenario() -> dict[str, object]:
    return {
        "grid": {
            "N": 7,
            "Z": 1,
            "cells": [
                {"coord": {"x": 3, "y": 3, "z": 0}, "status": "IMPASSABLE"},
            ],
            "smoke": [
                {"coord": {"x": 2, "y": 2, "z": 0}, "density": 0.01},
            ],
        },
        "agents": [
            {
                "id": "A1",
                "coord": {"x": 1, "y": 3, "z": 0},
                "orientation": "EAST",
                "agent_class": "UGV",
            },
            {
                "id": "A2",
                "coord": {"x": 4, "y": 3, "z": 0},
                "orientation": "WEST",
                "agent_class": "UGV",
            },
        ],
        "casualties": [
            {
                "id": "C1",
                "coord": {"x": 2, "y": 3, "z": 0},
                "health": 90.0,
                "decay_rate": 0.0,
                "is_covered": False,
                "triage_state": "UNKNOWN",
                "transport_status": "ON_GROUND",
                "living_state": "ALIVE",
            },
            {
                "id": "C2",
                "coord": {"x": 4, "y": 3, "z": 0},
                "health": 80.0,
                "decay_rate": 0.0,
                "is_covered": False,
                "triage_state": "UNKNOWN",
                "transport_status": "ON_GROUND",
                "living_state": "ALIVE",
            },
        ],
        "buildings": [
            {
                "id": "B1",
                "cells": [
                    {
                        "coord": {"x": 2, "y": 4, "z": 0},
                        "integrity": 1.0,
                        "collapsed": False,
                    },
                ],
            },
        ],
    }


def test_registered_environment_passes_gymnasium_checker() -> None:
    env = gym.make("SARSim-v0", max_episode_steps=3)
    check_env(env.unwrapped)
    observation, info = env.reset(seed=7)

    assert env.observation_space.contains(observation)
    assert info["tick"] == 0
    assert info["agent_ids"]

    observation, reward, terminated, truncated, info = env.step({
        "action_type": int(SARSimAction.NOOP),
        "agent": 0,
        "target_casualty": 0,
        "target_coord": np.array([0, 0, 0], dtype=np.int64),
    })

    assert env.observation_space.contains(observation)
    assert reward == -0.1
    assert terminated is False
    assert truncated is False
    assert info["tick"] == 1
    env.close()


def test_registered_fov_environment_masks_each_agents_current_view() -> None:
    env = gym.make(
        "SARSim-FOV-v0",
        scenario=_fov_scenario(),
        max_agents=3,
        max_casualties=3,
        fov_range=4,
    )
    observation, info = env.reset(seed=7)

    assert env.observation_space.contains(observation)
    assert info["perception_filter"] == "fov_cone"
    assert observation["grid"].shape == (3, 1, 7, 7, 3)
    assert observation["visibility"].shape == (3, 1, 7, 7)
    assert observation["observer_mask"].tolist() == [1, 1, 0]

    a1_visibility = observation["visibility"][0, 0]
    assert a1_visibility[3, 1] == 1  # observer cell
    assert a1_visibility[3, 3] == 1  # wall itself
    assert a1_visibility[3, 4] == 0  # behind the wall
    assert a1_visibility[2, 2] == 1  # smoke itself
    assert a1_visibility[1, 3] == 0  # behind even light smoke
    assert a1_visibility[4, 2] == 1  # building itself
    assert a1_visibility[5, 3] == 0  # behind the building
    assert a1_visibility[3, 0] == 0  # behind the observer
    assert observation["grid"][0, 0, 4, 2, 2] == 1.0

    assert observation["agents"][0, 0, 0] == 1.0  # A1 sees itself
    assert observation["agents"][0, 1, 0] == 0.0  # A2 is behind the wall
    assert observation["agents"][1, 1, 0] == 1.0  # A2 sees itself
    assert observation["casualties"][0, 0, 0] == 1.0
    assert observation["casualties"][0, 1, 0] == 0.0

    action = {
        "action_type": int(SARSimAction.TURN_LEFT),
        "agent": 0,
        "target_casualty": 0,
        "target_coord": np.array([0, 0, 0], dtype=np.int64),
    }
    next_observation, _, _, _, _ = env.step(action)
    assert next_observation["visibility"][0, 0, 3, 2] == 0
    assert env.unwrapped.engine.telemetry_log == []
    env.close()


def test_fov_environment_passes_gymnasium_checker() -> None:
    env = gym.make(
        "SARSim-FOV-v0",
        scenario=_fov_scenario(),
        max_agents=3,
        max_casualties=3,
    )
    assert isinstance(env.unwrapped, SARSimFOVEnv)
    check_env(env.unwrapped)
    env.close()


def test_fov_agent_inside_smoke_only_sees_its_own_cell() -> None:
    scenario = _fov_scenario()
    grid = scenario["grid"]
    assert isinstance(grid, dict)
    smoke = grid["smoke"]
    assert isinstance(smoke, list)
    smoke.append({"coord": {"x": 1, "y": 3, "z": 0}, "density": 0.01})
    env = SARSimFOVEnv(scenario=scenario, max_agents=3, max_casualties=3)

    observation, _ = env.reset(seed=4)

    assert int(observation["visibility"][0].sum()) == 1
    assert observation["visibility"][0, 0, 3, 1] == 1
    env.close()


def test_registered_minigrid_environment_has_three_wide_view() -> None:
    scenario = {
        "grid": {"N": 7, "Z": 1, "cells": [], "smoke": []},
        "agents": [{
            "id": "A1",
            "coord": {"x": 3, "y": 5, "z": 0},
            "orientation": "NORTH",
            "agent_class": "UGV",
        }],
        "casualties": [],
    }
    env = gym.make(
        "SARSim-MiniGrid-v0",
        scenario=scenario,
        max_agents=2,
        max_casualties=2,
        sensor_range=4,
    )

    observation, info = env.reset(seed=2)

    assert isinstance(env.unwrapped, SARSimMiniGridEnv)
    assert env.observation_space.contains(observation)
    assert info["perception_filter"] == "minigrid_3"
    assert int(observation["visibility"][0].sum()) == 12
    env.close()


def test_gym_action_moves_agent_and_truncates() -> None:
    scenario = {
        "grid": {"N": 4, "Z": 2, "cells": [], "smoke": []},
        "agents": [{
            "id": "A1",
            "coord": {"x": 1, "y": 2, "z": 0},
            "orientation": "NORTH",
            "agent_class": "UGV",
        }],
        "casualties": [],
    }
    env = SARSimEnv(scenario=scenario, max_episode_steps=1)
    observation, _ = env.reset(seed=1)
    assert env.observation_space.contains(observation)

    observation, _, terminated, truncated, info = env.step({
        "action_type": int(SARSimAction.MOVE_FORWARD),
        "agent": 0,
        "target_casualty": 0,
        "target_coord": np.array([0, 0, 0], dtype=np.int64),
    })

    assert terminated is False
    assert truncated is True
    assert observation["agents"][0, 2] == 1
    assert info["events"][-1]["event_type"] == "ACTION_COMPLETED"


def test_reset_rejects_scenario_that_breaks_fixed_space() -> None:
    env = SARSimEnv()
    oversized = {"grid": {"N": 11, "Z": 3}}

    try:
        env.reset(options={"scenario": oversized})
    except ValueError as exc:
        assert "grid dimensions" in str(exc)
    else:
        raise AssertionError("reset should reject incompatible dimensions")
