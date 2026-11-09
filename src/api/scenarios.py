from __future__ import annotations

from src.core.agents import Agent, AgentClass, Orientation
from src.core.casualties import Casualty, LivingState, TriageState
from src.core.engine import SimulationEngine
from src.core.grid import Coordinate
from src.core.types import TransportStatus


def seed_dev_scenario(engine: SimulationEngine) -> None:
    """Seed a simple scenario for manual testing."""
    engine.current_tick = 0
    engine.pending_actions.clear()
    engine.events.clear()
    engine.hospital_casualty_ids_by_zone.clear()
    engine.rescued_casualty_ids.clear()
    engine.temporal_constraint = {
        "type": "rescue_count",
        "target_count": 1,
        "deadline_cycles": 20,
    }
    engine.ended = False
    engine.success = None

    if "A1" not in engine.agents:
        engine.add_agent(
            Agent(
                id="A1",
                coord=Coordinate(x=1, y=1, z=0),
                orientation=Orientation.NORTH,
                agent_class=AgentClass.UGV,
            )
        )

    if "C1" not in engine.casualties:
        engine.add_casualty(
            Casualty(
                id="C1",
                coord=Coordinate(x=1, y=2, z=0),
                health=50.0,
                decay_rate=1.0,
                is_covered=False,
                triage_state=TriageState.UNKNOWN,
                transport_status=TransportStatus.ON_GROUND,
                living_state=LivingState.ALIVE,
            )
        )

    if not any(str(zone.get("id")) == "DEV_FIELD_HOSPITAL" for zone in engine.zones):
        engine.zones.append({
            "id": "DEV_FIELD_HOSPITAL",
            "zone_type": "FIELD_HOSPITAL",
            "cells": [{"x": 4, "y": 4, "z": 0}],
            "labels": ["dev-scenario", "medical-dropoff"],
        })
