from __future__ import annotations

import json

import pytest

from src.rl.dqn import ACTION_NAMES, AGENTS_DIR, list_checkpoints, observation_size
from src.rl.training import TrainingConfig


def test_bundled_checkpoint_metadata_matches_network_contract() -> None:
    checkpoints = {item["name"]: item for item in list_checkpoints()}

    for name, grid_size in (
        ("utilitarian_rescue_dqn_8x8", 8),
        ("utilitarian_rescue_dqn_10x10", 10),
    ):
        summary = checkpoints[name]
        metadata = json.loads((AGENTS_DIR / f"{name}.json").read_text())

        assert summary["ready"] is True
        assert metadata["input_size"] == observation_size(grid_size)
        assert tuple(metadata["action_names"]) == ACTION_NAMES
        assert metadata["episodes_trained"] == 500
        assert metadata["held_out_living_rescue_rate"] == 1.0
        assert metadata["held_out_success_rate"] == 1.0


@pytest.mark.parametrize("name", ["", "../escape", "has spaces", "slash/name"])
def test_training_config_rejects_unsafe_checkpoint_names(name: str) -> None:
    with pytest.raises(ValueError, match="name may contain only"):
        TrainingConfig(name=name).validate()


def test_training_defaults_target_the_default_simulator_size() -> None:
    config = TrainingConfig()

    assert config.grid_size == 10
    assert config.max_steps == 240
    config.validate()
