from __future__ import annotations

from src.core.engine import SimulationEngine
from src.core.events import EventType
from src.core.grid import Coordinate, SpatialGrid
from src.core.types import CellStatus
from src.utils.serializer import build_engine_from_scenario_definition


def test_scheduled_smoke_increase_event_applies_on_tick() -> None:
    scenario = {
        "schema_version": "1.0",
        "metadata": {"scenario_id": "sched-1"},
        "grid": {"N": 4, "Z": 2, "cells": [], "smoke": []},
        "agents": [],
        "casualties": [],
        "buildings": [],
        "zones": [],
        "scheduled_events": [
            {
                "event_id": "evt-1",
                "tick": 1,
                "event_type": "SMOKE_INCREASE",
                "payload": {
                    "coord": {"x": 1, "y": 1, "z": 0},
                    "density": 0.8,
                },
            }
        ],
        "objectives": {},
        "evaluation": {},
    }

    engine = build_engine_from_scenario_definition(scenario)
    engine.tick()

    assert engine.grid.get_smoke_density(Coordinate(x=1, y=1, z=0)) == 0.8
    evt = next(e for e in engine.events if e.event_type is EventType.SCHEDULED_EVENT_TRIGGERED)
    assert evt.payload is not None
    assert evt.payload["event_id"] == "evt-1"


def test_scheduled_set_cell_status_event_applies_on_tick() -> None:
    scenario = {
        "schema_version": "1.0",
        "metadata": {"scenario_id": "sched-2"},
        "grid": {"N": 4, "Z": 2, "cells": [], "smoke": []},
        "agents": [],
        "casualties": [],
        "buildings": [],
        "zones": [],
        "scheduled_events": [
            {
                "event_id": "evt-2",
                "tick": 1,
                "event_type": "SET_CELL_STATUS",
                "payload": {
                    "coord": {"x": 2, "y": 2, "z": 0},
                    "status": "IMPASSABLE",
                },
            }
        ],
        "objectives": {},
        "evaluation": {},
    }

    engine = build_engine_from_scenario_definition(scenario)
    engine.tick()

    assert engine.grid.get_cell_status(Coordinate(x=2, y=2, z=0)) is CellStatus.IMPASSABLE


def test_scheduled_events_are_removed_after_triggering() -> None:
    engine = SimulationEngine(grid=SpatialGrid(N=3, Z=1))
    engine.scheduled_events = [
        {
            "event_id": "evt-3",
            "tick": 1,
            "event_type": "SMOKE_INCREASE",
            "payload": {
                "coord": {"x": 0, "y": 0, "z": 0},
                "density": 0.5,
            },
        }
    ]

    engine.tick()

    assert engine.scheduled_events == []
