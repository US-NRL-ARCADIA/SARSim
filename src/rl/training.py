from __future__ import annotations

import random
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass
from statistics import fmean
from typing import Any

import numpy as np

from src.core.casualties import LivingState
from src.core.engine import SimulationEngine
from src.utils.generator import generate_scenario
from src.utils.serializer import build_engine_from_scenario_definition

from .dqn import (
    ACTION_COUNT,
    ACTION_NAMES,
    CheckpointMetadata,
    DQNPolicy,
    ReplayBuffer,
    backend_status,
    encode_engine,
    heuristic_action,
    require_training_modules,
)


@dataclass(frozen=True)
class TrainingConfig:
    name: str = "sarsim_dqn"
    episodes: int = 250
    max_steps: int = 240
    grid_size: int = 10
    seed: int = 42
    hidden_size: int = 128
    batch_size: int = 64
    replay_capacity: int = 20_000
    learning_rate: float = 0.0005
    gamma: float = 0.98
    epsilon_start: float = 1.0
    epsilon_end: float = 0.05
    demonstration_start: float = 0.85
    demonstration_end: float = 0.35

    def validate(self) -> None:
        if not self.name or any(
            not (character.isalnum() or character in "-_") for character in self.name
        ):
            raise ValueError("name may contain only letters, numbers, '-' and '_'")
        if not 1 <= self.episodes <= 100_000:
            raise ValueError("episodes must be in [1, 100000]")
        if not 10 <= self.max_steps <= 10_000:
            raise ValueError("max_steps must be in [10, 10000]")
        if not 4 <= self.grid_size <= 20:
            raise ValueError("grid_size must be in [4, 20]")
        if not 16 <= self.hidden_size <= 1024:
            raise ValueError("hidden_size must be in [16, 1024]")
        if not 8 <= self.batch_size <= 1024:
            raise ValueError("batch_size must be in [8, 1024]")
        if not 0.0 < self.learning_rate <= 0.1:
            raise ValueError("learning_rate must be in (0, 0.1]")


class TrainingManager:
    """Own one background MLX training job and its browser-facing metrics."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._active_policy: DQNPolicy | None = None
        self._active_name: str | None = None
        self._status: dict[str, Any] = {
            "state": "idle",
            "episode": 0,
            "total_episodes": 0,
            "backend": backend_status(),
            "history": [],
            "checkpoint": None,
            "message": "Ready to train",
        }

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                **self._status,
                "history": list(self._status["history"]),
                "active_agent": self._active_name,
            }

    def start(self, config: TrainingConfig) -> dict[str, Any]:
        config.validate()
        if not bool(backend_status()["available"]):
            raise RuntimeError(str(backend_status()["device"]))
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("a training run is already active")
            self._stop_event.clear()
            self._status = {
                "state": "starting",
                "episode": 0,
                "total_episodes": config.episodes,
                "backend": backend_status(),
                "history": [],
                "checkpoint": None,
                "message": "Initializing replay buffer on MLX",
                "config": asdict(config),
            }
            self._thread = threading.Thread(
                target=self._run,
                args=(config,),
                name="sarsim-mlx-training",
                daemon=True,
            )
            self._thread.start()
        return self.status()

    def stop(self) -> dict[str, Any]:
        self._stop_event.set()
        with self._lock:
            if self._status["state"] in {"running", "starting"}:
                self._status["message"] = "Stopping after the current simulator step"
        return self.status()

    def activate(self, name: str) -> dict[str, Any]:
        policy = DQNPolicy.load(name)
        with self._lock:
            self._active_policy = policy
            self._active_name = name
        return {"status": "ok", "active_agent": name, "grid_size": policy.grid_size}

    def step_active(self, engine: SimulationEngine) -> dict[str, object]:
        with self._lock:
            policy = self._active_policy
            name = self._active_name
        if policy is None:
            raise RuntimeError("activate a trained agent before running it")
        result = policy.step_engine(engine)
        result["agent"] = name
        return result

    def _run(self, config: TrainingConfig) -> None:
        try:
            checkpoint = train_dqn(config, self._record_metric, self._stop_event)
            with self._lock:
                stopped = self._stop_event.is_set()
                self._status["state"] = "stopped" if stopped else "completed"
                self._status["checkpoint"] = checkpoint
                self._status["message"] = (
                    "Training stopped; latest policy saved"
                    if stopped
                    else "Training complete; checkpoint ready"
                )
        except Exception as exc:  # noqa: BLE001 - preserve failures from a daemon thread.
            with self._lock:
                self._status["state"] = "failed"
                self._status["message"] = f"{type(exc).__name__}: {exc}"

    def _record_metric(self, metric: dict[str, object]) -> None:
        with self._lock:
            history = self._status["history"]
            history.append(metric)
            if len(history) > 500:
                del history[:-500]
            self._status["state"] = "running"
            self._status["episode"] = metric["episode"]
            self._status["message"] = "Training DQN on generated solvable levels"


def train_dqn(
    config: TrainingConfig,
    metric_callback: Callable[[dict[str, object]], None],
    stop_event: threading.Event,
) -> dict[str, object]:
    """Train DQN with replay, a target network, and decaying demonstrations."""
    mlx, neural, optimizers = require_training_modules()
    rng = random.Random(config.seed)
    np.random.seed(config.seed)
    policy = DQNPolicy(config.grid_size, config.hidden_size, config.seed)
    target = type(policy.model)(policy.input_size, config.hidden_size, ACTION_COUNT)
    target.update(policy.model.parameters())
    mlx.eval(target.parameters())
    optimizer = optimizers.Adam(learning_rate=config.learning_rate)
    replay = ReplayBuffer(config.replay_capacity, config.seed)

    def loss_fn(
        model: Any,
        states: Any,
        actions: Any,
        targets: Any,
        demonstrations: Any,
    ) -> Any:
        values = model(states)
        selected = mlx.take_along_axis(values, actions[:, None], axis=1).squeeze(1)
        temporal_difference = neural.losses.huber_loss(
            selected,
            targets,
            reduction="mean",
        )
        imitation_per_item = neural.losses.cross_entropy(
            values,
            actions,
            reduction="none",
        )
        imitation = mlx.sum(imitation_per_item * demonstrations) / mlx.maximum(
            mlx.sum(demonstrations),
            1.0,
        )
        return temporal_difference + imitation

    loss_and_grad = neural.value_and_grad(policy.model, loss_fn)
    recent_rewards: list[float] = []
    recent_rescues: list[float] = []
    completed_episodes = 0
    total_updates = 0

    for episode in range(1, config.episodes + 1):
        if stop_event.is_set():
            break
        engine = _training_engine(config, episode)
        state = encode_engine(engine)
        episode_reward = 0.0
        episode_losses: list[float] = []
        epsilon = _linear_schedule(
            config.epsilon_start,
            config.epsilon_end,
            episode - 1,
            config.episodes,
        )
        demonstration = _linear_schedule(
            config.demonstration_start,
            config.demonstration_end,
            episode - 1,
            config.episodes,
        )

        for step in range(1, config.max_steps + 1):
            if stop_event.is_set():
                break
            used_demonstration = rng.random() < demonstration
            if used_demonstration:
                action_index = heuristic_action(engine)
            elif rng.random() < epsilon:
                action_index = rng.randrange(ACTION_COUNT)
            else:
                action_index = policy.select_engine_action(engine)

            reward, done = _apply_training_step(policy, engine, action_index)
            next_state = encode_engine(engine)
            replay.append(
                state,
                action_index,
                reward / 100.0,
                next_state,
                done,
                used_demonstration,
            )
            state = next_state
            episode_reward += reward

            if len(replay) >= config.batch_size:
                batch = replay.sample(config.batch_size)
                states, actions, rewards, next_states, dones, demonstrations = batch
                next_values = target(mlx.array(next_states))
                targets = mlx.array(rewards) + config.gamma * (
                    1.0 - mlx.array(dones)
                ) * mlx.max(next_values, axis=1)
                loss, gradients = loss_and_grad(
                    policy.model,
                    mlx.array(states),
                    mlx.array(actions),
                    mlx.stop_gradient(targets),
                    mlx.array(demonstrations),
                )
                optimizer.update(policy.model, gradients)
                mlx.eval(policy.model.parameters(), optimizer.state)
                episode_losses.append(float(loss.item()))
                total_updates += 1
                if total_updates % 200 == 0:
                    target.update(policy.model.parameters())
                    mlx.eval(target.parameters())
            if done:
                break

        completed_episodes = episode
        recent_rewards.append(episode_reward)
        recent_rescues.append(float(engine.rescued_count))
        recent_rewards = recent_rewards[-20:]
        recent_rescues = recent_rescues[-20:]
        metric_callback({
            "episode": episode,
            "steps": step,
            "loss": fmean(episode_losses) if episode_losses else 0.0,
            "reward": round(episode_reward, 3),
            "rescued": engine.rescued_count,
            "casualties": len(engine.casualties),
            "epsilon": round(epsilon, 4),
            "demonstration": round(demonstration, 4),
        })

    held_out_episodes = 0 if stop_event.is_set() else 50
    held_out = (
        _evaluate_policy(policy, config, episodes=held_out_episodes)
        if held_out_episodes
        else {"living_rescue_rate": 0.0, "success_rate": 0.0}
    )
    metadata = CheckpointMetadata(
        name=config.name,
        algorithm="DQN",
        backend="mlx-metal",
        grid_size=config.grid_size,
        input_size=policy.input_size,
        hidden_size=config.hidden_size,
        action_names=ACTION_NAMES,
        episodes_trained=completed_episodes,
        mean_rescued_last_20=fmean(recent_rescues) if recent_rescues else 0.0,
        mean_reward_last_20=fmean(recent_rewards) if recent_rewards else 0.0,
        held_out_episodes=held_out_episodes,
        held_out_living_rescue_rate=held_out["living_rescue_rate"],
        held_out_success_rate=held_out["success_rate"],
        description=(
            "Planner-guided utilitarian DQN: +100 living rescue, -100 casualty "
            "death, small time/health penalties. Trained on solvable levels."
        ),
    )
    return policy.save(metadata)


def _training_engine(config: TrainingConfig, episode: int) -> SimulationEngine:
    scenario = generate_scenario(
        grid_size=config.grid_size,
        z_depth=1,
        building_density=0.08,
        hazard_density=0.04,
        casualty_density=0.035,
        debris_density=0.05,
        seed=config.seed + episode,
        agent_count=1,
    )
    engine = build_engine_from_scenario_definition(scenario)
    engine.perception_enabled = False
    return engine


def _apply_training_step(
    policy: DQNPolicy,
    engine: SimulationEngine,
    action_index: int,
) -> tuple[float, bool]:
    rescued_before = set(engine.rescued_casualty_ids)
    deceased_before = {
        casualty.id
        for casualty in engine.casualties.values()
        if casualty.living_state is LivingState.DECEASED
    }
    health_before = sum(
        casualty.health
        for casualty in engine.casualties.values()
        if casualty.living_state is LivingState.ALIVE
    )
    event_count = len(engine.events)
    action = policy.engine_action(engine, action_index)
    if action is not None:
        engine.queue_action(action)
    engine.tick()

    newly_rescued = engine.rescued_casualty_ids - rescued_before
    newly_deceased = {
        casualty.id
        for casualty in engine.casualties.values()
        if casualty.living_state is LivingState.DECEASED
    } - deceased_before
    living_rescued = sum(
        engine.casualties[casualty_id].living_state is LivingState.ALIVE
        for casualty_id in newly_rescued
    )
    body_recoveries = len(newly_rescued) - living_rescued
    health_after = sum(
        casualty.health
        for casualty in engine.casualties.values()
        if casualty.living_state is LivingState.ALIVE
    )
    invalid = any(
        event.event_type.name == "ACTION_FAILED"
        for event in engine.events[event_count:]
    )
    reward = (
        -0.05
        + 100.0 * living_rescued
        + 2.0 * body_recoveries
        - 100.0 * len(newly_deceased)
        - 0.01 * max(0.0, health_before - health_after)
        - (0.25 if invalid else 0.0)
    )
    done = engine.rescued_count == len(engine.casualties)
    if done and not newly_deceased and not deceased_before:
        reward += 25.0
    return reward, done


def _linear_schedule(start: float, end: float, index: int, total: int) -> float:
    progress = min(1.0, index / max(1, total - 1))
    return start + (end - start) * progress


def _evaluate_policy(
    policy: DQNPolicy,
    config: TrainingConfig,
    *,
    episodes: int,
) -> dict[str, float]:
    living_rescued = 0
    casualty_count = 0
    successes = 0
    evaluation_config = TrainingConfig(**{
        **asdict(config),
        "seed": config.seed + 1_000_000,
    })
    for episode in range(1, episodes + 1):
        engine = _training_engine(evaluation_config, episode)
        casualty_count += len(engine.casualties)
        for _ in range(config.max_steps):
            action_index = policy.select_engine_action(engine)
            _, done = _apply_training_step(policy, engine, action_index)
            if done:
                break
        successes += int(engine.rescued_count == len(engine.casualties))
        living_rescued += sum(
            casualty.id in engine.rescued_casualty_ids
            and casualty.living_state is LivingState.ALIVE
            for casualty in engine.casualties.values()
        )
    return {
        "living_rescue_rate": living_rescued / max(1, casualty_count),
        "success_rate": successes / episodes,
    }
