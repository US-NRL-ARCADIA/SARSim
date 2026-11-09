from __future__ import annotations

from typing import Any

from src.core.agents import Agent, AgentClass, Orientation
from src.core.buildings import Building, BuildingCell
from src.core.casualties import Casualty, LivingState, TriageState
from src.core.engine import SimulationEngine
from src.core.events import Event, EventType
from src.core.grid import Coordinate, SpatialGrid
from src.core.sensors import AgentBeliefCell, AgentBeliefState
from src.core.types import CellStatus, DamageStatus, TransportStatus


SerializedState = dict[str, Any]
ScenarioDefinition = dict[str, Any]


def serialize_engine_state(engine: SimulationEngine) -> SerializedState:
    """Serialize the current engine state into a JSON-friendly dictionary."""
    return {
        "grid": {
            "N": engine.grid.N,
            "Z": engine.grid.Z,
            "cells": [
                {
                    "x": x,
                    "y": y,
                    "z": z,
                    "status": int(engine.grid.status_grid[x, y, z]),
                    "smoke_density": float(engine.grid.smoke_grid[x, y, z]),
                }
                for x in range(engine.grid.N)
                for y in range(engine.grid.N)
                for z in range(engine.grid.Z)
                if int(engine.grid.status_grid[x, y, z]) != int(CellStatus.UNOCCUPIED)
                or float(engine.grid.smoke_grid[x, y, z]) != 0.0
            ],
        },
        "tick": engine.current_tick,
        "agents": [
            {
                "id": agent.id,
                "coord": _serialize_coordinate(agent.coord),
                "orientation": agent.orientation.name,
                "agent_class": agent.agent_class.name,
                "busy_ticks_remaining": agent.busy_ticks_remaining,
                "last_error": agent.last_error,
                "damage_status": agent.damage_status.value if agent.damage_status is not None else None,
                "payload_casualty_id": agent.payload.id if agent.payload is not None else None,
            }
            for agent in engine.agents.values()
        ],
        "casualties": [
            {
                "id": casualty.id,
                "coord": _serialize_coordinate(casualty.coord),
                "health": casualty.health,
                "decay_rate": casualty.decay_rate,
                "is_covered": casualty.is_covered,
                "triage_state": casualty.triage_state.name,
                "transport_status": _enum_or_value(casualty.transport_status),
                "living_state": casualty.living_state.name,
            }
            for casualty in engine.casualties.values()
        ],
        "buildings": [
            {
                "id": building.id,
                "cells": [
                    {
                        "coord": _serialize_coordinate(cell.coord),
                        "integrity": cell.integrity,
                        "collapsed": cell.collapsed,
                    }
                    for cell in building.cells.values()
                ],
            }
            for building in engine.buildings.values()
        ],
        "events": [
            {
                "tick": event.tick,
                "event_type": event.event_type.name,
                "message": event.message,
                "actor_id": event.actor_id,
                "payload": event.payload,
            }
            for event in engine.events
        ],
        "scheduled_events": list(engine.scheduled_events),
        "zones": list(engine.zones),
        "hospital_casualty_ids_by_zone": dict(engine.hospital_casualty_ids_by_zone),
        "rescued_casualty_ids": sorted(engine.rescued_casualty_ids),
        "temporal_constraint": engine.temporal_constraint,
        "ended": engine.ended,
        "success": engine.success,
        "agent_beliefs": {
            agent_id: {
                "cells": [
                    {
                        "coord": _serialize_coordinate(cell.coord),
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
            }
            for agent_id, belief in engine.agent_beliefs.items()
        },
        "telemetry_log": list(engine.telemetry_log),
    }


def deserialize_engine_state(data: SerializedState) -> SimulationEngine:
    """Deserialize a JSON-friendly dictionary into a SimulationEngine."""
    grid_data = data["grid"]
    grid = SpatialGrid(N=grid_data["N"], Z=grid_data["Z"])

    for cell in grid_data.get("cells", []):
        coord = _deserialize_coordinate(cell["x"], cell["y"], cell["z"])
        grid.set_cell_status(coord, CellStatus(cell["status"]))
        grid.set_smoke_density(coord, float(cell["smoke_density"]))

    engine = SimulationEngine(grid=grid)
    engine.current_tick = int(data.get("tick", 0))

    casualties_by_id: dict[str, Casualty] = {}
    for casualty_data in data.get("casualties", []):
        casualty = Casualty(
            id=casualty_data["id"],
            coord=_deserialize_coordinate_from_dict(casualty_data["coord"]),
            health=float(casualty_data["health"]),
            decay_rate=float(casualty_data["decay_rate"]),
            is_covered=bool(casualty_data["is_covered"]),
            triage_state=TriageState[casualty_data["triage_state"]],
            transport_status=TransportStatus(casualty_data["transport_status"]),
            living_state=LivingState[casualty_data["living_state"]],
        )
        engine.add_casualty(casualty)
        casualties_by_id[casualty.id] = casualty

    for agent_data in data.get("agents", []):
        payload_casualty_id = agent_data.get("payload_casualty_id")
        payload = casualties_by_id.get(payload_casualty_id) if payload_casualty_id is not None else None
        damage_status = agent_data.get("damage_status")
        agent = Agent(
            id=agent_data["id"],
            coord=_deserialize_coordinate_from_dict(agent_data["coord"]),
            orientation=Orientation[agent_data["orientation"]],
            agent_class=AgentClass[agent_data["agent_class"]],
            busy_ticks_remaining=int(agent_data.get("busy_ticks_remaining", 0)),
            last_error=agent_data.get("last_error"),
            damage_status=DamageStatus(damage_status) if damage_status is not None else None,
            payload=payload,
        )
        engine.add_agent(agent)

    for building_data in data.get("buildings", []):
        cells: dict[tuple[int, int, int], BuildingCell] = {}
        for cell_data in building_data.get("cells", []):
            coord = _deserialize_coordinate_from_dict(cell_data["coord"])
            cell = BuildingCell(
                coord=coord,
                integrity=float(cell_data["integrity"]),
                collapsed=bool(cell_data["collapsed"]),
            )
            cells[(coord.x, coord.y, coord.z)] = cell
        engine.add_building(Building(id=building_data["id"], cells=cells))

    engine.events = [
        Event(
            tick=int(event_data["tick"]),
            event_type=EventType[event_data["event_type"]],
            message=event_data["message"],
            actor_id=event_data.get("actor_id"),
            payload=event_data.get("payload"),
        )
        for event_data in data.get("events", [])
    ]
    engine.scheduled_events = list(data.get("scheduled_events", []))
    engine.zones = list(data.get("zones", []))
    engine.hospital_casualty_ids_by_zone = {
        str(zone_id): [str(casualty_id) for casualty_id in casualty_ids]
        for zone_id, casualty_ids in data.get("hospital_casualty_ids_by_zone", {}).items()
    }
    engine.rescued_casualty_ids = set(
        str(casualty_id)
        for casualty_id in data.get(
            "rescued_casualty_ids",
            [casualty_id for roster in engine.hospital_casualty_ids_by_zone.values() for casualty_id in roster],
        )
    )
    engine.temporal_constraint = data.get("temporal_constraint")
    engine.ended = bool(data.get("ended", False))
    engine.success = data.get("success")

    for agent_id, belief_data in data.get("agent_beliefs", {}).items():
        belief_state = AgentBeliefState(agent_id=agent_id)
        for cell_data in belief_data.get("cells", []):
            coord = _deserialize_coordinate_from_dict(cell_data["coord"])
            belief_state.cells[(coord.x, coord.y, coord.z)] = AgentBeliefCell(
                coord=coord,
                last_update_tick=int(cell_data["last_update_tick"]),
                last_seen_tick=(
                    int(cell_data["last_seen_tick"])
                    if cell_data.get("last_seen_tick") is not None
                    else None
                ),
                ever_observed=bool(cell_data["ever_observed"]),
                currently_visible=bool(cell_data["currently_visible"]),
                last_known_cell_status=(
                    CellStatus[cell_data["last_known_cell_status"]]
                    if cell_data.get("last_known_cell_status") is not None
                    else None
                ),
                last_known_smoke_density=cell_data.get("last_known_smoke_density"),
                last_known_has_casualty=cell_data.get("last_known_has_casualty"),
                obscured_by_smoke=bool(cell_data.get("obscured_by_smoke", False)),
            )
        engine.agent_beliefs[agent_id] = belief_state

    engine.telemetry_log = list(data.get("telemetry_log", []))

    return engine


def serialize_scenario_definition(
    engine: SimulationEngine,
    *,
    metadata: dict[str, Any] | None = None,
    zones: list[dict[str, Any]] | None = None,
    scheduled_events: list[dict[str, Any]] | None = None,
    objectives: dict[str, Any] | None = None,
    evaluation: dict[str, Any] | None = None,
) -> ScenarioDefinition:
    """Serialize an engine into a research-grade scenario definition."""
    return {
        "schema_version": "1.0",
        "metadata": metadata or {},
        "grid": {
            "N": engine.grid.N,
            "Z": engine.grid.Z,
            "cells": [
                {
                    "coord": _serialize_coordinate(Coordinate(x=x, y=y, z=z)),
                    "status": CellStatus(int(engine.grid.status_grid[x, y, z])).name,
                }
                for x in range(engine.grid.N)
                for y in range(engine.grid.N)
                for z in range(engine.grid.Z)
                if int(engine.grid.status_grid[x, y, z]) != int(CellStatus.UNOCCUPIED)
            ],
            "smoke": [
                {
                    "coord": _serialize_coordinate(Coordinate(x=x, y=y, z=z)),
                    "density": float(engine.grid.smoke_grid[x, y, z]),
                }
                for x in range(engine.grid.N)
                for y in range(engine.grid.N)
                for z in range(engine.grid.Z)
                if float(engine.grid.smoke_grid[x, y, z]) != 0.0
            ],
        },
        "agents": [
            {
                "id": agent.id,
                "coord": _serialize_coordinate(agent.coord),
                "orientation": agent.orientation.name,
                "agent_class": agent.agent_class.name,
                "busy_ticks_remaining": agent.busy_ticks_remaining,
                "damage_status": agent.damage_status.value if agent.damage_status is not None else None,
                "payload_casualty_id": agent.payload.id if agent.payload is not None else None,
            }
            for agent in engine.agents.values()
        ],
        "casualties": [
            {
                "id": casualty.id,
                "coord": _serialize_coordinate(casualty.coord),
                "health": casualty.health,
                "decay_rate": casualty.decay_rate,
                "is_covered": casualty.is_covered,
                "triage_state": casualty.triage_state.name,
                "transport_status": _enum_or_value(casualty.transport_status),
                "living_state": casualty.living_state.name,
            }
            for casualty in engine.casualties.values()
        ],
        "buildings": [
            {
                "id": building.id,
                "cells": [
                    {
                        "coord": _serialize_coordinate(cell.coord),
                        "integrity": cell.integrity,
                        "collapsed": cell.collapsed,
                    }
                    for cell in building.cells.values()
                ],
            }
            for building in engine.buildings.values()
        ],
        "zones": zones or [],
        "scheduled_events": scheduled_events or [],
        "objectives": objectives or {},
        "evaluation": evaluation or {},
    }


def deserialize_scenario_definition(data: ScenarioDefinition) -> dict[str, Any]:
    """Normalize a scenario definition into a validated in-memory dictionary."""
    objectives = dict(data.get("objectives", {}))
    constraint = objectives.get("temporal_constraint")
    if constraint is not None:
        if not isinstance(constraint, dict) or constraint.get("type") != "rescue_count":
            raise ValueError("objectives.temporal_constraint must have type 'rescue_count'")
        target_count = constraint.get("target_count")
        deadline_cycles = constraint.get("deadline_cycles")
        if (
            isinstance(target_count, bool)
            or not isinstance(target_count, int)
            or isinstance(deadline_cycles, bool)
            or not isinstance(deadline_cycles, int)
        ):
            raise ValueError("rescue_count constraint requires integer target_count and deadline_cycles")
        if target_count < 1 or deadline_cycles < 1:
            raise ValueError("target_count and deadline_cycles must be positive integers")
        objectives["temporal_constraint"] = {
            "type": "rescue_count",
            "target_count": target_count,
            "deadline_cycles": deadline_cycles,
        }

    return {
        "schema_version": data.get("schema_version", "1.0"),
        "metadata": dict(data.get("metadata", {})),
        "grid": {
            "N": int(data["grid"]["N"]),
            "Z": int(data["grid"]["Z"]),
            "cells": list(data["grid"].get("cells", [])),
            "smoke": list(data["grid"].get("smoke", [])),
        },
        "agents": list(data.get("agents", [])),
        "casualties": list(data.get("casualties", [])),
        "buildings": list(data.get("buildings", [])),
        "zones": list(data.get("zones", [])),
        "scheduled_events": list(data.get("scheduled_events", [])),
        "objectives": objectives,
        "evaluation": dict(data.get("evaluation", {})),
    }


def build_engine_from_scenario_definition(data: ScenarioDefinition) -> SimulationEngine:
    """Build a SimulationEngine from a scenario definition."""
    scenario = deserialize_scenario_definition(data)
    grid_data = scenario["grid"]
    grid = SpatialGrid(N=grid_data["N"], Z=grid_data["Z"])

    for cell in grid_data["cells"]:
        coord = _deserialize_coordinate_from_dict(cell["coord"])
        grid.set_cell_status(coord, CellStatus[cell["status"]])

    for smoke in grid_data["smoke"]:
        coord = _deserialize_coordinate_from_dict(smoke["coord"])
        grid.set_smoke_density(coord, float(smoke["density"]))

    engine = SimulationEngine(grid=grid)

    casualties_by_id: dict[str, Casualty] = {}
    for casualty_data in scenario["casualties"]:
        casualty = Casualty(
            id=casualty_data["id"],
            coord=_deserialize_coordinate_from_dict(casualty_data["coord"]),
            health=float(casualty_data["health"]),
            decay_rate=float(casualty_data["decay_rate"]),
            is_covered=bool(casualty_data["is_covered"]),
            triage_state=TriageState[casualty_data["triage_state"]],
            transport_status=TransportStatus(casualty_data["transport_status"]),
            living_state=LivingState[casualty_data["living_state"]],
        )
        engine.add_casualty(casualty)
        casualties_by_id[casualty.id] = casualty

    for agent_data in scenario["agents"]:
        payload_casualty_id = agent_data.get("payload_casualty_id")
        payload = casualties_by_id.get(payload_casualty_id) if payload_casualty_id is not None else None
        damage_status = agent_data.get("damage_status")
        agent = Agent(
            id=agent_data["id"],
            coord=_deserialize_coordinate_from_dict(agent_data["coord"]),
            orientation=Orientation[agent_data["orientation"]],
            agent_class=AgentClass[agent_data["agent_class"]],
            busy_ticks_remaining=int(agent_data.get("busy_ticks_remaining", 0)),
            damage_status=DamageStatus(damage_status) if damage_status is not None else None,
            payload=payload,
        )
        engine.add_agent(agent)

    for building_data in scenario["buildings"]:
        cells: dict[tuple[int, int, int], BuildingCell] = {}
        for cell_data in building_data.get("cells", []):
            coord = _deserialize_coordinate_from_dict(cell_data["coord"])
            cell = BuildingCell(
                coord=coord,
                integrity=float(cell_data["integrity"]),
                collapsed=bool(cell_data["collapsed"]),
            )
            cells[(coord.x, coord.y, coord.z)] = cell
        engine.add_building(Building(id=building_data["id"], cells=cells))

    engine.scheduled_events = list(scenario["scheduled_events"])
    engine.zones = list(scenario.get("zones", []))
    engine.temporal_constraint = scenario["objectives"].get("temporal_constraint")
    return engine


def _serialize_coordinate(coord: Coordinate) -> dict[str, int]:
    return {"x": coord.x, "y": coord.y, "z": coord.z}


def _deserialize_coordinate(x: int, y: int, z: int) -> Coordinate:
    return Coordinate(x=int(x), y=int(y), z=int(z))


def _deserialize_coordinate_from_dict(data: dict[str, int]) -> Coordinate:
    return _deserialize_coordinate(data["x"], data["y"], data["z"])


def _enum_or_value(value: object) -> object:
    return value.value if hasattr(value, "value") else value
