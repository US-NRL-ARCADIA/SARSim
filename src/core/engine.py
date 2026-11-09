from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .action_handlers import apply_action
from .actions import EngineAction, EngineActionType
from .agents import Agent, AgentClass, Orientation
from .buildings import Building
from .casualties import Casualty
from .events import Event, EventType
from .grid import Coordinate, SpatialGrid
from .sensors import AgentBeliefState, AgentView, get_agent_view, update_belief_state
from .types import TransportStatus


@dataclass
class SimulationEngine:
    """Minimal simulation engine for SARSim.

    Responsibilities:
    - Own the world state: grid, agents, casualties, buildings.
    - Advance time with tick().
    - Apply queued actions when they become ready.
    - Update per-tick processes (e.g., casualty health decay).
    """

    grid: SpatialGrid
    agents: dict[str, Agent] = field(default_factory=dict)
    casualties: dict[str, Casualty] = field(default_factory=dict)
    buildings: dict[str, Building] = field(default_factory=dict)
    zones: list[dict[str, Any]] = field(default_factory=list)
    hospital_casualty_ids_by_zone: dict[str, list[str]] = field(default_factory=dict)
    rescued_casualty_ids: set[str] = field(default_factory=set)
    temporal_constraint: dict[str, Any] | None = None
    ended: bool = False
    success: bool | None = None

    current_tick: int = 0
    pending_actions: list[EngineAction] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    scheduled_events: list[dict[str, Any]] = field(default_factory=list)
    agent_beliefs: dict[str, AgentBeliefState] = field(default_factory=dict)
    latest_agent_views: dict[str, AgentView] = field(default_factory=dict)
    telemetry_log: list[dict[str, Any]] = field(default_factory=list)
    event_type_enum = EventType

    def add_agent(self, agent: Agent) -> None:
        self.agents[agent.id] = agent
        self.grid.add_entity(agent.coord, agent)
        self.agent_beliefs[agent.id] = AgentBeliefState(agent_id=agent.id)

    def add_casualty(self, casualty: Casualty) -> None:
        self.casualties[casualty.id] = casualty
        # Casualties aren't registered in entity_locations for now; only agents are.

    def add_building(self, building: Building) -> None:
        self.buildings[building.id] = building

    def log_event(
        self,
        event_type: EventType,
        message: str,
        actor_id: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> None:
        self.events.append(
            Event(
                tick=self.current_tick,
                event_type=event_type,
                message=message,
                actor_id=actor_id,
                payload=payload,
            )
        )

    def queue_action(self, action: EngineAction) -> None:
        """Queue an action to be applied when its start_tick + duration is reached."""
        self.pending_actions.append(action)

    def tick(self) -> None:
        """Advance the simulation by one tick.

        - Increment current_tick.
        - Decrement busy timers for agents.
        - Update casualty health.
        - Apply any actions that are ready at this tick.
        """
        if self.ended:
            return

        self.current_tick += 1

        # 1) Decrement busy timers.
        self._update_agent_busy_timers()

        # 2) Per-tick casualty health updates.
        self._update_casualties_health()

        # 3) Per-tick building collapse checks.
        self._update_building_collapses()

        # 4) Apply scheduled exogenous events.
        self._apply_scheduled_events()

        # 5) Apply any actions that are ready.
        self._apply_ready_actions()

        # 6) Refresh per-agent observations/beliefs.
        self._update_agent_observations()

        constraint = self.temporal_constraint
        if constraint is not None and self.current_tick >= int(constraint["deadline_cycles"]):
            self.ended = True
            self.success = self.rescued_count >= int(constraint["target_count"])
            outcome = "met" if self.success else "not met"
            self.log_event(
                EventType.SCENARIO_ENDED,
                f"Scenario ended at cycle {self.current_tick}; rescue target {outcome}.",
                payload={
                    "rescued_count": self.rescued_count,
                    "target_count": int(constraint["target_count"]),
                    "deadline_cycles": int(constraint["deadline_cycles"]),
                    "success": self.success,
                },
            )

    @property
    def rescued_count(self) -> int:
        """Number of unique casualties ever transferred into hospital care."""
        return len(self.rescued_casualty_ids)

    def _update_agent_busy_timers(self) -> None:
        for agent in self.agents.values():
            if agent.busy_ticks_remaining > 0:
                agent.busy_ticks_remaining -= 1
                agent.busy_ticks_remaining = max(agent.busy_ticks_remaining, 0)

    def _update_casualties_health(self) -> None:
        for casualty in self.casualties.values():
            if casualty.transport_status != TransportStatus.ON_GROUND:
                continue
            smoke_density = 0.0
            try:
                # Use grid smoke at casualty.coord if available.
                smoke_density = self.grid.get_smoke_density(casualty.coord)
            except IndexError:
                smoke_density = 0.0
            before = casualty.health
            casualty.update_health(smoke_density=smoke_density)
            if casualty.health != before:
                self.log_event(
                    event_type=EventType.CASUALTY_HEALTH_UPDATED,
                    message=(
                        f"Casualty {casualty.id} health changed "
                        f"from {before} to {casualty.health}"
                    ),
                    actor_id=None,
                    payload={
                        "casualty_id": casualty.id,
                        "before": before,
                        "after": casualty.health,
                    },
                )

    def _update_building_collapses(self) -> None:
        for building in self.buildings.values():
            for cell in building.cells.values():
                if cell.collapsed or cell.integrity >= 0.2:
                    continue

                building.collapse_cell(self.grid, cell.coord, self.casualties)
                self.log_event(
                    event_type=EventType.BUILDING_COLLAPSED,
                    message=(
                        f"Building {building.id} cell at {cell.coord} collapsed."
                    ),
                    payload={
                        "building_id": building.id,
                        "coord": cell.coord.__dict__,
                    },
                )

    def _apply_scheduled_events(self) -> None:
        remaining_events: list[dict[str, Any]] = []
        for scheduled_event in self.scheduled_events:
            tick = int(scheduled_event.get("tick", -1))
            if tick != self.current_tick:
                remaining_events.append(scheduled_event)
                continue

            event_type = str(scheduled_event.get("event_type", ""))
            payload = scheduled_event.get("payload")
            self._apply_scheduled_event_effect(event_type, payload)
            self.log_event(
                event_type=EventType.SCHEDULED_EVENT_TRIGGERED,
                message=f"Scheduled event triggered: {event_type}",
                payload={
                    "event_id": scheduled_event.get("event_id"),
                    "event_type": event_type,
                    "payload": payload,
                },
            )

        self.scheduled_events = remaining_events

    def _apply_scheduled_event_effect(self, event_type: str, payload: object) -> None:
        if not isinstance(payload, dict):
            return

        if event_type == "SMOKE_INCREASE":
            coord_data = payload.get("coord")
            density = float(payload.get("density", 0.0))
            if isinstance(coord_data, dict):
                coord = self.grid_coord_from_dict(coord_data)
                self.grid.set_smoke_density(coord, density)
            return

        if event_type == "SET_CELL_STATUS":
            coord_data = payload.get("coord")
            status_name = payload.get("status")
            if isinstance(coord_data, dict) and isinstance(status_name, str):
                coord = self.grid_coord_from_dict(coord_data)
                from .types import CellStatus
                self.grid.set_cell_status(coord, CellStatus[status_name])
            return

    def grid_coord_from_dict(self, data: dict[str, Any]) -> Coordinate:
        return Coordinate(x=int(data["x"]), y=int(data["y"]), z=int(data["z"]))

    def _apply_ready_actions(self) -> None:
        ready_actions = [
            action for action in self.pending_actions if action.ready_to_apply(self.current_tick)
        ]

        blocked_action_ids = self._resolve_concurrent_move_conflicts(ready_actions)
        for action in ready_actions:
            if action.action_id in blocked_action_ids:
                actor = self.agents.get(action.actor_id)
                actor_id = actor.id if actor is not None else action.actor_id
                action.failed = True
                action.failure_reason = "MOVEMENT_BLOCKED"
                self.log_event(
                    event_type=EventType.ACTION_FAILED,
                    message=f"Agent {actor_id} movement blocked by concurrent conflict.",
                    actor_id=actor_id,
                    payload={"action_id": action.action_id, "reason": "MOVEMENT_BLOCKED"},
                )
                continue
            apply_action(self, action)

        self.pending_actions = [
            a for a in self.pending_actions if not (a.completed or a.failed)
        ]

    def _resolve_concurrent_move_conflicts(self, ready_actions: list[EngineAction]) -> set[str]:
        move_actions = [
            action
            for action in ready_actions
            if action.action_type is EngineActionType.MOVE_FORWARD
        ]
        target_to_actions: dict[tuple[int, int, int], list[EngineAction]] = {}

        for action in move_actions:
            actor = self.agents.get(action.actor_id)
            if actor is None:
                continue
            target = self._target_for_move_forward(actor)
            if target is None:
                continue
            key = (target.x, target.y, target.z)
            target_to_actions.setdefault(key, []).append(action)

        blocked_action_ids: set[str] = set()
        for actions in target_to_actions.values():
            if len(actions) <= 1:
                continue
            winner = min(actions, key=self._movement_priority_key)
            for action in actions:
                if action is not winner:
                    blocked_action_ids.add(action.action_id)
        return blocked_action_ids

    def _movement_priority_key(self, action: EngineAction) -> tuple[int, str]:
        actor = self.agents[action.actor_id]
        class_priority = 0 if actor.agent_class is AgentClass.UAV else 1
        return (class_priority, actor.id)

    def _target_for_move_forward(self, actor: Agent) -> Coordinate:
        dx, dy = 0, 0
        if actor.orientation is Orientation.NORTH:
            dy = -1
        elif actor.orientation is Orientation.SOUTH:
            dy = 1
        elif actor.orientation is Orientation.EAST:
            dx = 1
        elif actor.orientation is Orientation.WEST:
            dx = -1
        return actor.coord.__class__(
            x=actor.coord.x + dx,
            y=actor.coord.y + dy,
            z=actor.coord.z,
        )

    def _update_agent_observations(self) -> None:
        for agent in self.agents.values():
            view = get_agent_view(
                grid=self.grid,
                casualties=self.casualties,
                agent=agent,
                max_range=4,
            )
            self.latest_agent_views[agent.id] = view
            belief = self.agent_beliefs.setdefault(
                agent.id,
                AgentBeliefState(agent_id=agent.id),
            )
            update_belief_state(
                belief_state=belief,
                observations=view.cone_samples,
                tick=self.current_tick,
            )
            self.telemetry_log.append(
                {
                    "tick": self.current_tick,
                    "agent_id": agent.id,
                    "observation": {
                        "cone_samples": [
                            {
                                "coord": {
                                    "x": sample.coord.x,
                                    "y": sample.coord.y,
                                    "z": sample.coord.z,
                                },
                                "is_visible": sample.is_visible,
                                "cell_status": (
                                    sample.cell_status.name
                                    if sample.cell_status is not None
                                    else None
                                ),
                                "smoke_density": sample.smoke_density,
                                "has_casualty": sample.has_casualty,
                                "obscured_by_smoke": sample.obscured_by_smoke,
                            }
                            for sample in view.cone_samples
                        ],
                        "radial_samples": [
                            {
                                "coord": {
                                    "x": sample.coord.x,
                                    "y": sample.coord.y,
                                    "z": sample.coord.z,
                                },
                                "is_visible": sample.is_visible,
                                "cell_status": (
                                    sample.cell_status.name
                                    if sample.cell_status is not None
                                    else None
                                ),
                                "smoke_density": sample.smoke_density,
                                "has_casualty": sample.has_casualty,
                                "obscured_by_smoke": sample.obscured_by_smoke,
                            }
                            for sample in view.radial_samples
                        ],
                    },
                    "belief": {
                        "cells": [
                            {
                                "coord": {
                                    "x": cell.coord.x,
                                    "y": cell.coord.y,
                                    "z": cell.coord.z,
                                },
                                "last_update_tick": cell.last_update_tick,
                                "last_seen_tick": cell.last_seen_tick,
                                "ever_observed": cell.ever_observed,
                                "currently_visible": cell.currently_visible,
                                "last_known_cell_status": (
                                    cell.last_known_cell_status.name
                                    if cell.last_known_cell_status is not None
                                    else None
                                ),
                                "last_known_smoke_density": cell.last_known_smoke_density,
                                "last_known_has_casualty": cell.last_known_has_casualty,
                                "obscured_by_smoke": cell.obscured_by_smoke,
                            }
                            for cell in belief.cells.values()
                        ]
                    },
                }
            )

    
