from __future__ import annotations

from src.core.engine import (
    EngineAction,
    EngineActionType,
    EventType,
    SimulationEngine,
)
from src.core.entities import (
    Agent,
    AgentClass,
    Casualty,
    Coordinate,
    LivingState,
    Orientation,
    TriageState,
)
from src.core.grid import SpatialGrid


def _make_engine() -> SimulationEngine:
    grid = SpatialGrid(N=4, Z=2)
    return SimulationEngine(grid=grid)


def test_triage_emits_action_completed_event() -> None:
    engine = _make_engine()

    agent = Agent(
        id="A_EVT",
        coord=Coordinate(x=1, y=2, z=0),
        orientation=Orientation.NORTH,
        agent_class=AgentClass.UGV,
    )
    engine.add_agent(agent)

    casualty = Casualty(
        id="C_EVT",
        coord=Coordinate(x=1, y=1, z=0),
        health=50.0,
        decay_rate=2.0,
        is_covered=False,
        triage_state=TriageState.UNKNOWN,
        transport_status="ON_GROUND",
        living_state=LivingState.ALIVE,
    )
    engine.add_casualty(casualty)

    action = EngineAction(
        action_id="ACT_EVT_TRIAGE",
        actor_id=agent.id,
        action_type=EngineActionType.TRIAGE,
        target_casualty_id=casualty.id,
        start_tick=0,
        duration=0,
    )
    engine.queue_action(action)

    engine.tick()

    # Find an ACTION_COMPLETED event for this action.
    evt = next(
        e
        for e in engine.events
        if e.event_type is EventType.ACTION_COMPLETED
        and e.payload is not None
        and e.payload.get("action_id") == "ACT_EVT_TRIAGE"
    )

    assert evt.actor_id == agent.id
    assert evt.payload is not None
    assert evt.payload.get("casualty_id") == casualty.id


def test_casualty_health_update_event() -> None:
    engine = _make_engine()

    casualty = Casualty(
        id="C_HEALTH",
        coord=Coordinate(x=0, y=0, z=0),
        health=10.0,
        decay_rate=3.0,
        is_covered=False,
        triage_state=TriageState.UNKNOWN,
        transport_status="ON_GROUND",
        living_state=LivingState.ALIVE,
    )
    engine.add_casualty(casualty)

    engine.tick()

    evt = next(
        e
        for e in engine.events
        if e.event_type is EventType.CASUALTY_HEALTH_UPDATED
        and e.payload is not None
        and e.payload.get("casualty_id") == "C_HEALTH"
    )

    assert evt.payload is not None
    assert evt.payload.get("before") == 10.0
    assert evt.payload.get("after") == 7.0