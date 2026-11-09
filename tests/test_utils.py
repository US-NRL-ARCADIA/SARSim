from __future__ import annotations

from src.api.scenarios import seed_dev_scenario
from src.core.actions import EngineAction, EngineActionType
from src.core.agents import Agent, AgentClass, Orientation
from src.core.buildings import Building, BuildingCell
from src.core.casualties import Casualty, LivingState, TriageState
from src.core.engine import SimulationEngine
from src.core.events import Event, EventType
from src.core.grid import Coordinate, SpatialGrid
from src.core.types import CellStatus, DamageStatus, TransportStatus
from src.utils.generator import generate_scenario
from src.utils.serializer import (
    build_engine_from_scenario_definition,
    deserialize_engine_state,
    deserialize_scenario_definition,
    serialize_engine_state,
    serialize_scenario_definition,
)


def test_round_trip_serialization() -> None:
    grid = SpatialGrid(N=4, Z=3)
    grid.set_cell_status(Coordinate(x=1, y=1, z=0), CellStatus.PASSABLE)
    grid.set_smoke_density(Coordinate(x=2, y=2, z=1), 0.6)

    engine = SimulationEngine(grid=grid)
    casualty = Casualty(
        id="C1",
        coord=Coordinate(x=1, y=2, z=0),
        health=42.0,
        decay_rate=1.5,
        is_covered=False,
        triage_state=TriageState.DELAYED,
        transport_status=TransportStatus.ON_GROUND,
        living_state=LivingState.ALIVE,
    )
    engine.add_casualty(casualty)

    agent = Agent(
        id="A1",
        coord=Coordinate(x=1, y=1, z=0),
        orientation=Orientation.NORTH,
        agent_class=AgentClass.UGV,
        busy_ticks_remaining=2,
        last_error=None,
        damage_status=DamageStatus.DAMAGED,
        payload=casualty,
    )
    engine.add_agent(agent)

    building_coord = Coordinate(x=3, y=3, z=0)
    building = Building(
        id="B1",
        cells={
            (3, 3, 0): BuildingCell(
                coord=building_coord,
                integrity=0.4,
                collapsed=False,
            )
        },
    )
    engine.add_building(building)

    engine.current_tick = 7
    engine.events.append(
        Event(
            tick=7,
            event_type=EventType.ACTION_COMPLETED,
            message="Serialized event",
            actor_id="A1",
            payload={"action_id": "ACT1"},
        )
    )
    engine.queue_action(
        EngineAction(
            action_id="PENDING1",
            actor_id="A1",
            action_type=EngineActionType.TURN_LEFT,
            start_tick=8,
            duration=1,
        )
    )

    serialized = serialize_engine_state(engine)
    restored = deserialize_engine_state(serialized)

    assert restored.current_tick == 7
    assert restored.grid.N == 4
    assert restored.grid.Z == 3
    assert restored.grid.get_cell_status(Coordinate(x=1, y=1, z=0)) == CellStatus.PASSABLE
    assert restored.grid.get_smoke_density(Coordinate(x=2, y=2, z=1)) == 0.6

    restored_agent = restored.agents["A1"]
    restored_casualty = restored.casualties["C1"]
    restored_building = restored.buildings["B1"]

    assert restored_agent.coord == Coordinate(x=1, y=1, z=0)
    assert restored_agent.orientation is Orientation.NORTH
    assert restored_agent.agent_class is AgentClass.UGV
    assert restored_agent.busy_ticks_remaining == 2
    assert restored_agent.damage_status is DamageStatus.DAMAGED
    assert restored_agent.payload is restored_casualty

    assert restored_casualty.health == 42.0
    assert restored_casualty.decay_rate == 1.5
    assert restored_casualty.triage_state is TriageState.DELAYED
    assert restored_casualty.transport_status is TransportStatus.ON_GROUND

    restored_cell = restored_building.cells[(3, 3, 0)]
    assert restored_cell.coord == building_coord
    assert restored_cell.integrity == 0.4
    assert restored_cell.collapsed is False

    assert len(restored.events) == 1
    assert restored.events[0].event_type is EventType.ACTION_COMPLETED
    assert restored.events[0].payload == {"action_id": "ACT1"}
    assert restored.pending_actions == []


def test_dev_scenario_serializes_and_restores() -> None:
    engine = SimulationEngine(grid=SpatialGrid(N=10, Z=3))
    seed_dev_scenario(engine)

    serialized = serialize_engine_state(engine)
    restored = deserialize_engine_state(serialized)

    assert set(restored.agents.keys()) == {"A1"}
    assert set(restored.casualties.keys()) == {"C1"}
    assert restored.agents["A1"].coord == Coordinate(x=1, y=1, z=0)
    assert restored.casualties["C1"].coord == Coordinate(x=1, y=2, z=0)


def test_scenario_definition_round_trip_and_engine_build() -> None:
    engine = SimulationEngine(grid=SpatialGrid(N=6, Z=3))
    seed_dev_scenario(engine)
    engine.grid.set_cell_status(Coordinate(x=2, y=2, z=0), CellStatus.IMPASSABLE)
    engine.grid.set_smoke_density(Coordinate(x=3, y=3, z=1), 0.4)

    scenario = serialize_scenario_definition(
        engine,
        metadata={
            "scenario_id": "scenario-001",
            "name": "Research Scenario",
            "seed": 123,
        },
        zones=[
            {
                "id": "zone-1",
                "zone_type": "EXTRACTION",
                "cells": [{"x": 5, "y": 5, "z": 0}],
            }
        ],
        scheduled_events=[
            {
                "event_id": "evt-1",
                "tick": 10,
                "event_type": "SMOKE_INCREASE",
                "payload": {"coord": {"x": 3, "y": 3, "z": 1}, "density": 0.8},
            }
        ],
        objectives={
            "primary_goals": ["stabilize casualty C1"],
            "temporal_constraint": {
                "type": "rescue_count",
                "target_count": 2,
                "deadline_cycles": 50,
            },
        },
        evaluation={
            "expected_difficulty": "medium",
        },
    )

    normalized = deserialize_scenario_definition(scenario)
    rebuilt = build_engine_from_scenario_definition(normalized)

    assert normalized["schema_version"] == "1.0"
    assert normalized["metadata"]["scenario_id"] == "scenario-001"
    assert normalized["zones"][0]["zone_type"] == "EXTRACTION"
    assert normalized["scheduled_events"][0]["event_type"] == "SMOKE_INCREASE"
    assert normalized["objectives"]["temporal_constraint"]["target_count"] == 2

    assert rebuilt.grid.N == 6
    assert rebuilt.grid.Z == 3
    assert rebuilt.grid.get_cell_status(Coordinate(x=2, y=2, z=0)) == CellStatus.IMPASSABLE
    assert rebuilt.grid.get_smoke_density(Coordinate(x=3, y=3, z=1)) == 0.4
    assert set(rebuilt.agents.keys()) == {"A1"}
    assert set(rebuilt.casualties.keys()) == {"C1"}


def test_invalid_rescue_constraint_is_rejected() -> None:
    scenario = {
        "grid": {"N": 4, "Z": 1},
        "objectives": {"temporal_constraint": {
            "type": "rescue_count", "target_count": 1, "deadline_cycles": 0,
        }},
    }

    try:
        deserialize_scenario_definition(scenario)
    except ValueError as exc:
        assert "must be positive" in str(exc)
    else:
        raise AssertionError("invalid rescue deadline should be rejected")


def test_engine_state_serialization_round_trips_beliefs_and_telemetry() -> None:
    engine = SimulationEngine(grid=SpatialGrid(N=10, Z=3))
    seed_dev_scenario(engine)
    engine.tick()

    serialized = serialize_engine_state(engine)
    restored = deserialize_engine_state(serialized)

    assert set(restored.agent_beliefs.keys()) == set(engine.agent_beliefs.keys())
    assert restored.telemetry_log == engine.telemetry_log


def test_engine_state_serialization_round_trips_temporal_constraint_and_terminal_state() -> None:
    engine = SimulationEngine(grid=SpatialGrid(N=4, Z=1))
    engine.temporal_constraint = {"type": "rescue_count", "target_count": 1, "deadline_cycles": 4}
    engine.zones = [{"id": "H1", "zone_type": "FIELD_HOSPITAL", "cells": [{"x": 0, "y": 0, "z": 0}]}]
    engine.hospital_casualty_ids_by_zone["H1"] = ["C1"]
    engine.rescued_casualty_ids = {"C1"}
    engine.ended = True
    engine.success = True

    restored = deserialize_engine_state(serialize_engine_state(engine))

    assert restored.temporal_constraint == engine.temporal_constraint
    assert restored.zones == engine.zones
    assert restored.hospital_casualty_ids_by_zone == engine.hospital_casualty_ids_by_zone
    assert restored.rescued_casualty_ids == engine.rescued_casualty_ids
    assert restored.ended is True
    assert restored.success is True



def test_generate_scenario_is_reproducible_for_same_seed() -> None:
    scenario_a = generate_scenario(
        grid_size=8,
        z_depth=3,
        building_density=0.1,
        hazard_density=0.05,
        casualty_density=0.08,
        debris_density=0.06,
        seed=123,
        agent_count=3,
    )
    scenario_b = generate_scenario(
        grid_size=8,
        z_depth=3,
        building_density=0.1,
        hazard_density=0.05,
        casualty_density=0.08,
        debris_density=0.06,
        seed=123,
        agent_count=3,
    )

    assert scenario_a == scenario_b


def test_generated_scenario_builds_valid_engine() -> None:
    scenario = generate_scenario(
        grid_size=8,
        z_depth=3,
        building_density=0.12,
        hazard_density=0.08,
        casualty_density=0.1,
        debris_density=0.05,
        seed=999,
        agent_count=4,
    )

    rebuilt = build_engine_from_scenario_definition(scenario)

    assert scenario["schema_version"] == "1.0"
    assert scenario["metadata"]["seed"] == 999
    assert scenario["metadata"]["scenario_family"] == "procedural"
    assert scenario["zones"]
    assert "temporal_constraint" not in scenario["objectives"]
    assert scenario["evaluation"]["expected_difficulty"] in {"easy", "medium", "hard"}

    assert rebuilt.grid.N == 8
    assert rebuilt.grid.Z == 3
    assert len(rebuilt.agents) == 4
    assert len(rebuilt.casualties) >= 1

    for agent in rebuilt.agents.values():
        if agent.agent_class is AgentClass.UGV:
            assert agent.coord.z == 0
        if agent.agent_class is AgentClass.UAV:
            assert agent.coord.z >= 1
