from __future__ import annotations

from src.core.actions import EngineAction, EngineActionType
from src.core.agents import Agent, AgentClass, Orientation
from src.core.engine import SimulationEngine
from src.core.grid import Coordinate, SpatialGrid


def _make_engine() -> SimulationEngine:
    return SimulationEngine(grid=SpatialGrid(N=5, Z=2))


def test_simultaneous_movement_conflict_prefers_alphabetical_agent_id_for_same_class() -> None:
    engine = _make_engine()

    agent_a = Agent(
        id="A1",
        coord=Coordinate(x=1, y=2, z=0),
        orientation=Orientation.EAST,
        agent_class=AgentClass.UGV,
    )
    agent_b = Agent(
        id="B1",
        coord=Coordinate(x=3, y=2, z=0),
        orientation=Orientation.WEST,
        agent_class=AgentClass.UGV,
    )
    engine.add_agent(agent_a)
    engine.add_agent(agent_b)

    action_a = EngineAction(
        action_id="MOVE_A",
        actor_id="A1",
        action_type=EngineActionType.MOVE_FORWARD,
        start_tick=0,
        duration=0,
    )
    action_b = EngineAction(
        action_id="MOVE_B",
        actor_id="B1",
        action_type=EngineActionType.MOVE_FORWARD,
        start_tick=0,
        duration=0,
    )
    engine.queue_action(action_a)
    engine.queue_action(action_b)

    engine.tick()

    assert action_a.completed is True
    assert action_b.failed is True
    assert action_b.failure_reason == "MOVEMENT_BLOCKED"
    assert agent_a.coord == Coordinate(x=2, y=2, z=0)
    assert agent_b.coord == Coordinate(x=3, y=2, z=0)


def test_simultaneous_movement_conflict_prefers_uav_over_ugv() -> None:
    engine = _make_engine()

    ugv = Agent(
        id="UGV1",
        coord=Coordinate(x=1, y=1, z=1),
        orientation=Orientation.EAST,
        agent_class=AgentClass.UGV,
    )
    uav = Agent(
        id="UAV1",
        coord=Coordinate(x=3, y=1, z=1),
        orientation=Orientation.WEST,
        agent_class=AgentClass.UAV,
    )
    engine.add_agent(ugv)
    engine.add_agent(uav)

    ugv_action = EngineAction(
        action_id="MOVE_UGV",
        actor_id="UGV1",
        action_type=EngineActionType.MOVE_FORWARD,
        start_tick=0,
        duration=0,
    )
    uav_action = EngineAction(
        action_id="MOVE_UAV",
        actor_id="UAV1",
        action_type=EngineActionType.MOVE_FORWARD,
        start_tick=0,
        duration=0,
    )
    engine.queue_action(ugv_action)
    engine.queue_action(uav_action)

    engine.tick()

    assert uav_action.completed is True
    assert ugv_action.failed is True
    assert ugv_action.failure_reason == "MOVEMENT_BLOCKED"
    assert uav.coord == Coordinate(x=2, y=1, z=1)
    assert ugv.coord == Coordinate(x=1, y=1, z=1)
