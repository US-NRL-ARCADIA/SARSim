"""Top-level package for SARSim Python modules.

This package contains core simulation logic, APIs, utilities, and
other components under the `src` namespace.
"""
from __future__ import annotations

from gymnasium.envs.registration import register, registry

_ENVIRONMENTS = {
    "SARSim-v0": "src.gym_env:SARSimEnv",
    "SARSim-FOV-v0": "src.gym_env:SARSimFOVEnv",
    "SARSim-MiniGrid-v0": "src.gym_env:SARSimMiniGridEnv",
}

for environment_id, entry_point in _ENVIRONMENTS.items():
    if environment_id not in registry:
        register(id=environment_id, entry_point=entry_point)
