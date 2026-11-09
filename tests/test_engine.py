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
    Building,
    BuildingCell,
    Casualty,
    Coordinate,
    LivingState,
    Orientation,
    TriageState,
)
from src.core.grid import SpatialGrid, CellStatus


def _make_engine() -> SimulationEngine:
    # Z=3 so UAV can ascend from z=1 to z=2.
    grid = SpatialGrid(N=4, Z=3)
    return SimulationEngine(grid=grid)


def test_tick_advances_casualty_health() -> None:
    """Engine.tick should advance casualty health according to update rules."""
    engine = _make_engine()

    casualty = Casualty(
        id="C1",
        coord=Coordinate(x=0, y=0, z=0),
        health=10.0,
        decay_rate=3.0,
        is_covered=False,
        triage_state=TriageState.UNKNOWN,
        transport_status="ON_GROUND",
        living_state=LivingState.ALIVE,
    )
    engine.add_casualty(casualty)

    assert engine.current_tick == 0

    engine.tick()  # tick 1
    assert engine.current_tick == 1
    assert casualty.health == 7.0

    engine.tick()  # tick 2
    assert engine.current_tick == 2
    assert casualty.health == 4.0

    engine.tick()  # tick 3
    assert engine.current_tick == 3
    assert casualty.health == 1.0
    assert casualty.living_state is LivingState.ALIVE

    engine.tick()  # tick 4
    assert engine.current_tick == 4
    assert casualty.health == 0.0
    assert casualty.living_state is LivingState.DECEASED


def test_rescue_constraint_counts_hospital_transfer_and_ends_at_deadline() -> None:
    engine = _make_engine()
    casualty = Casualty(
        id="C1", coord=Coordinate(x=1, y=1, z=0), health=50.0, decay_rate=0.0,
        is_covered=False, triage_state=TriageState.UNKNOWN,
        transport_status="LOADED", living_state=LivingState.ALIVE,
    )
    agent = Agent(
        id="A1", coord=Coordinate(x=1, y=1, z=0),
        orientation=Orientation.NORTH, agent_class=AgentClass.UGV, payload=casualty,
    )
    engine.add_casualty(casualty)
    engine.add_agent(agent)
    engine.zones = [{"id": "H1", "zone_type": "FIELD_HOSPITAL", "cells": [{"x": 2, "y": 1, "z": 0}]}]
    engine.temporal_constraint = {"type": "rescue_count", "target_count": 1, "deadline_cycles": 1}
    engine.queue_action(EngineAction(
        action_id="TRANSFER", actor_id="A1",
        action_type=EngineActionType.TRANSFER_CASUALTY, start_tick=0,
    ))

    engine.tick()

    assert engine.current_tick == 1
    assert engine.rescued_count == 1
    assert engine.ended is True
    assert engine.success is True
    assert engine.events[-1].event_type is EventType.SCENARIO_ENDED
    engine.hospital_casualty_ids_by_zone["H1"].remove("C1")
    assert engine.rescued_count == 1
    engine.tick()
    assert engine.current_tick == 1


def test_rescue_constraint_ends_unsuccessfully_at_deadline() -> None:
    engine = _make_engine()
    engine.temporal_constraint = {"type": "rescue_count", "target_count": 1, "deadline_cycles": 2}

    engine.tick()
    assert engine.ended is False
    engine.tick()

    assert engine.current_tick == 2
    assert engine.ended is True
    assert engine.success is False
    engine.tick()
    assert engine.current_tick == 2


def test_scenario_without_temporal_constraint_keeps_advancing() -> None:
    engine = _make_engine()
    engine.tick()
    engine.tick()

    assert engine.current_tick == 2
    assert engine.ended is False
    assert engine.success is None


def test_queue_and_execute_triage_action() -> None:
    """Queued triage action should apply on the correct tick and update decay_rate."""
    engine = _make_engine()

    agent = Agent(
        id="A1",
        coord=Coordinate(x=1, y=2, z=0),
        orientation=Orientation.NORTH,
        agent_class=AgentClass.UGV,
    )
    engine.add_agent(agent)

    casualty = Casualty(
        id="C_TRIAGE",
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
        action_id="ACT_TRIAGE_1",
        actor_id=agent.id,
        action_type=EngineActionType.TRIAGE,
        target_casualty_id=casualty.id,
        start_tick=0,
        duration=2,  # becomes ready at tick >= 2
    )
    engine.queue_action(action)

    # Tick 1: action not yet ready.
    engine.tick()
    assert casualty.decay_rate == 2.0
    assert not action.completed
    assert not action.failed

    # Tick 2: action becomes ready and is applied.
    engine.tick()
    assert action.completed
    assert casualty.decay_rate == 0.5

    # Action should be removed from pending_actions after application.
    assert action not in engine.pending_actions


def test_clear_debris_then_triage_sequence() -> None:
    """Sequence: clear debris first, then triage, coordinated by engine ticks."""
    engine = _make_engine()

    # Debris-covered casualty at (1,1,0).
    casualty_coord = Coordinate(x=1, y=1, z=0)
    ground_coord = casualty_coord

    engine.grid.set_cell_status(ground_coord, CellStatus.PASSABLE)

    casualty = Casualty(
        id="C_SEQ",
        coord=casualty_coord,
        health=50.0,
        decay_rate=2.0,
        is_covered=True,
        triage_state=TriageState.UNKNOWN,
        transport_status="ON_GROUND",
        living_state=LivingState.ALIVE,
    )
    engine.add_casualty(casualty)

    # Agent adjacent at (1,2,0).
    agent = Agent(
        id="A_SEQ",
        coord=Coordinate(x=1, y=2, z=0),
        orientation=Orientation.NORTH,
        agent_class=AgentClass.UGV,
    )
    engine.add_agent(agent)

    # Queue clear_debris to complete at tick 1.
    clear_action = EngineAction(
        action_id="ACT_CLEAR",
        actor_id=agent.id,
        action_type=EngineActionType.CLEAR_DEBRIS,
        target_coord=casualty_coord,
        start_tick=0,
        duration=1,
    )
    engine.queue_action(clear_action)

    # Queue triage to complete at tick 2.
    triage_action = EngineAction(
        action_id="ACT_TRIAGE_SEQ",
        actor_id=agent.id,
        action_type=EngineActionType.TRIAGE,
        target_casualty_id=casualty.id,
        start_tick=0,
        duration=2,
    )
    engine.queue_action(triage_action)

    # Tick 1: clear_debris is applied.
    engine.tick()
    assert clear_action.completed
    assert engine.grid.get_cell_status(ground_coord) == CellStatus.UNOCCUPIED
    assert casualty.is_covered is False
    assert casualty.decay_rate == 2.0

    # Tick 2: triage becomes ready and should succeed now that debris is gone.
    engine.tick()
    assert triage_action.completed
    assert casualty.decay_rate == 0.5


def test_breach_entryway_action() -> None:
    """Engine should execute BREACH_ENTRYWAY and update building cell + grid."""
    engine = _make_engine()

    cell_coord = Coordinate(x=1, y=1, z=0)
    building_cell = BuildingCell(coord=cell_coord, integrity=0.3, collapsed=False)
    building = Building(
        id="B_BREACH",
        cells={(cell_coord.x, cell_coord.y, cell_coord.z): building_cell},
    )
    engine.add_building(building)

    # Debris at that coord to be cleared by breach.
    engine.grid.set_cell_status(cell_coord, CellStatus.PASSABLE)

    agent = Agent(
        id="A_BREACH",
        coord=Coordinate(x=1, y=2, z=0),  # adjacent SOUTH
        orientation=Orientation.NORTH,
        agent_class=AgentClass.UGV,
    )
    engine.add_agent(agent)

    action = EngineAction(
        action_id="ACT_BREACH",
        actor_id=agent.id,
        action_type=EngineActionType.BREACH_ENTRYWAY,
        target_coord=cell_coord,
        start_tick=0,
        duration=0,
    )
    engine.queue_action(action)

    engine.tick()  # apply action

    assert action.completed
    assert building_cell.integrity >= 0.5
    assert engine.grid.get_cell_status(cell_coord) == CellStatus.UNOCCUPIED


def test_turn_and_move_actions() -> None:
    """Engine should handle TURN_LEFT, TURN_RIGHT, and MOVE_FORWARD actions."""
    engine = _make_engine()

    agent = Agent(
        id="A_MOVE",
        coord=Coordinate(x=1, y=1, z=0),
        orientation=Orientation.NORTH,
        agent_class=AgentClass.UGV,
    )
    engine.add_agent(agent)

    # Turn right (NORTH -> EAST).
    act_turn_right = EngineAction(
        action_id="ACT_TURN_RIGHT",
        actor_id=agent.id,
        action_type=EngineActionType.TURN_RIGHT,
        start_tick=0,
        duration=0,
    )
    engine.queue_action(act_turn_right)

    engine.tick()
    assert act_turn_right.completed
    assert agent.orientation is Orientation.EAST

    # Move forward to (2,1,0).
    act_move = EngineAction(
        action_id="ACT_MOVE",
        actor_id=agent.id,
        action_type=EngineActionType.MOVE_FORWARD,
        start_tick=engine.current_tick,
        duration=0,
    )
    engine.queue_action(act_move)

    engine.tick()
    assert act_move.completed
    assert agent.coord == Coordinate(x=2, y=1, z=0)

    # Turn left (EAST -> NORTH).
    act_turn_left = EngineAction(
        action_id="ACT_TURN_LEFT",
        actor_id=agent.id,
        action_type=EngineActionType.TURN_LEFT,
        start_tick=engine.current_tick,
        duration=0,
    )
    engine.queue_action(act_turn_left)

    engine.tick()
    assert act_turn_left.completed
    assert agent.orientation is Orientation.NORTH


def test_ascend_and_descend_actions() -> None:
    """Engine should handle ASCEND and DESCEND for UAV agents."""
    engine = _make_engine()

    # UAV starting at z=1 (valid UAV altitude).
    agent = Agent(
        id="A_UAV",
        coord=Coordinate(x=1, y=1, z=1),
        orientation=Orientation.NORTH,
        agent_class=AgentClass.UAV,
    )
    engine.add_agent(agent)

    # Ascend to z=2.
    act_ascend = EngineAction(
        action_id="ACT_ASCEND",
        actor_id=agent.id,
        action_type=EngineActionType.ASCEND,
        start_tick=0,
        duration=0,
    )
    engine.queue_action(act_ascend)

    engine.tick()
    assert act_ascend.completed
    assert agent.coord.z == 2

    # Descend back to z=1.
    act_descend = EngineAction(
        action_id="ACT_DESCEND",
        actor_id=agent.id,
        action_type=EngineActionType.DESCEND,
        start_tick=engine.current_tick,
        duration=0,
    )
    engine.queue_action(act_descend)

    engine.tick()
    assert act_descend.completed
    assert agent.coord.z == 1


def test_action_duration_sets_agent_busy_and_frees_after_ticks() -> None:
    """Agent should be busy for the duration of an action, then become free."""
    engine = _make_engine()

    agent = Agent(
        id="A_BUSY",
        coord=Coordinate(x=1, y=1, z=0),
        orientation=Orientation.NORTH,
        agent_class=AgentClass.UGV,
    )
    engine.add_agent(agent)

    # TURN_RIGHT with duration 2, starts at tick 0 → ready at tick 2.
    action = EngineAction(
        action_id="ACT_BUSY",
        actor_id=agent.id,
        action_type=EngineActionType.TURN_RIGHT,
        start_tick=0,
        duration=2,
    )
    engine.queue_action(action)

    # Tick 1: not ready yet, no busy, no orientation change.
    engine.tick()
    assert not action.completed
    assert agent.busy_ticks_remaining == 0
    assert agent.orientation is Orientation.NORTH

    # Tick 2: action becomes ready, is applied, and sets busy=2.
    engine.tick()
    assert action.completed
    assert agent.orientation is Orientation.EAST
    assert agent.busy_ticks_remaining == 2

    # Tick 3: busy decremented to 1.
    engine.tick()
    assert agent.busy_ticks_remaining == 1

    # Tick 4: busy decremented to 0 (free).
    engine.tick()
    assert agent.busy_ticks_remaining == 0


def test_busy_agent_rejects_overlapping_actions() -> None:
    """Engine should reject actions scheduled while an agent is busy."""
    engine = _make_engine()

    agent = Agent(
        id="A_BUSY2",
        coord=Coordinate(x=1, y=1, z=0),
        orientation=Orientation.NORTH,
        agent_class=AgentClass.UGV,
    )
    engine.add_agent(agent)

    # First action: TURN_RIGHT with duration 2, ready at tick 2.
    action1 = EngineAction(
        action_id="ACT1",
        actor_id=agent.id,
        action_type=EngineActionType.TURN_RIGHT,
        start_tick=0,
        duration=2,
    )
    engine.queue_action(action1)

    # Second action: TURN_LEFT, also ready at tick 2.
    action2 = EngineAction(
        action_id="ACT2",
        actor_id=agent.id,
        action_type=EngineActionType.TURN_LEFT,
        start_tick=0,
        duration=2,
    )
    engine.queue_action(action2)

    # Tick 1: neither action ready.
    engine.tick()
    assert not action1.completed
    assert not action2.completed
    assert agent.busy_ticks_remaining == 0

    # Tick 2:
    # - _update_agent_busy_timers: still 0.
    # - _apply_ready_actions: both actions are ready.
    #   We expect action1 applied first, marking busy, then action2 rejected.
    engine.tick()

    assert action1.completed
    assert action2.failed
    assert action2.failure_reason == "ACTOR_BUSY"
    assert agent.busy_ticks_remaining == 2


def test_load_and_unload_casualty_actions() -> None:
    """Engine should support loading and unloading living casualties."""
    engine = _make_engine()

    agent = Agent(
        id="A_LOAD_ENGINE",
        coord=Coordinate(x=1, y=2, z=0),
        orientation=Orientation.NORTH,
        agent_class=AgentClass.UGV,
    )
    engine.add_agent(agent)

    casualty = Casualty(
        id="C_LOAD_ENGINE",
        coord=Coordinate(x=1, y=1, z=0),
        health=50.0,
        decay_rate=1.0,
        is_covered=False,
        triage_state=TriageState.UNKNOWN,
        transport_status="ON_GROUND",
        living_state=LivingState.ALIVE,
    )
    engine.add_casualty(casualty)

    load_action = EngineAction(
        action_id="ACT_LOAD",
        actor_id=agent.id,
        action_type=EngineActionType.LOAD_CASUALTY,
        target_casualty_id=casualty.id,
        start_tick=0,
        duration=0,
    )
    engine.queue_action(load_action)
    engine.tick()

    assert load_action.completed
    assert agent.payload is casualty
    assert casualty.transport_status == "LOADED"

    unload_action = EngineAction(
        action_id="ACT_UNLOAD",
        actor_id=agent.id,
        action_type=EngineActionType.UNLOAD_CASUALTY,
        start_tick=engine.current_tick,
        duration=0,
    )
    engine.queue_action(unload_action)
    engine.tick()

    assert unload_action.completed
    assert agent.payload is None
    assert casualty.transport_status == "UNLOADED"


def test_transfer_casualty_action_to_field_hospital() -> None:
    """Engine should support transferring a carried casualty into field hospital care."""
    engine = _make_engine()
    engine.zones = [
        {
            "id": "FH1",
            "zone_type": "FIELD_HOSPITAL",
            "cells": [{"x": 2, "y": 2, "z": 0}],
            "labels": ["medical-dropoff"],
        }
    ]

    casualty = Casualty(
        id="C_TRANSFER_ENGINE",
        coord=Coordinate(x=1, y=1, z=0),
        health=50.0,
        decay_rate=1.0,
        is_covered=False,
        triage_state=TriageState.UNKNOWN,
        transport_status="LOADED",
        living_state=LivingState.ALIVE,
    )
    engine.add_casualty(casualty)

    agent = Agent(
        id="A_TRANSFER_ENGINE",
        coord=Coordinate(x=2, y=1, z=0),
        orientation=Orientation.NORTH,
        agent_class=AgentClass.UGV,
        payload=casualty,
    )
    engine.add_agent(agent)

    action = EngineAction(
        action_id="ACT_TRANSFER",
        actor_id=agent.id,
        action_type=EngineActionType.TRANSFER_CASUALTY,
        start_tick=0,
        duration=0,
    )
    engine.queue_action(action)
    engine.tick()

    assert action.completed
    assert agent.payload is None
    assert casualty.transport_status == "UNLOADED"
    assert casualty.coord == Coordinate(x=2, y=2, z=0)
    assert engine.hospital_casualty_ids_by_zone == {"FH1": ["C_TRANSFER_ENGINE"]}


def test_load_casualty_action_removes_hospital_roster_membership() -> None:
    """Loading a casualty from a hospital cell should remove it from hospital care roster."""
    engine = _make_engine()
    engine.zones = [
        {
            "id": "FH1",
            "zone_type": "FIELD_HOSPITAL",
            "cells": [{"x": 2, "y": 2, "z": 0}],
            "labels": ["medical-dropoff"],
        }
    ]
    engine.hospital_casualty_ids_by_zone = {"FH1": ["C_HOSP_ENGINE"]}

    casualty = Casualty(
        id="C_HOSP_ENGINE",
        coord=Coordinate(x=2, y=2, z=0),
        health=50.0,
        decay_rate=1.0,
        is_covered=False,
        triage_state=TriageState.UNKNOWN,
        transport_status="UNLOADED",
        living_state=LivingState.ALIVE,
    )
    engine.add_casualty(casualty)

    agent = Agent(
        id="A_HOSP_ENGINE",
        coord=Coordinate(x=2, y=1, z=0),
        orientation=Orientation.NORTH,
        agent_class=AgentClass.UGV,
    )
    engine.add_agent(agent)

    action = EngineAction(
        action_id="ACT_HOSP_LOAD",
        actor_id=agent.id,
        action_type=EngineActionType.LOAD_CASUALTY,
        target_casualty_id=casualty.id,
        start_tick=0,
        duration=0,
    )
    engine.queue_action(action)
    engine.tick()

    assert action.completed
    assert agent.payload is casualty
    assert casualty.transport_status == "LOADED"
    assert engine.hospital_casualty_ids_by_zone == {"FH1": []}


def test_tick_collapses_fragile_building_and_emits_event() -> None:
    """Engine tick should collapse fragile building cells and emit an event."""
    engine = _make_engine()

    collapse_coord = Coordinate(x=1, y=1, z=0)
    building_cell = BuildingCell(coord=collapse_coord, integrity=0.1, collapsed=False)
    building = Building(
        id="B_COLLAPSE",
        cells={(collapse_coord.x, collapse_coord.y, collapse_coord.z): building_cell},
    )
    engine.add_building(building)

    casualty = Casualty(
        id="C_COLLAPSE",
        coord=collapse_coord,
        health=40.0,
        decay_rate=1.0,
        is_covered=False,
        triage_state=TriageState.UNKNOWN,
        transport_status="ON_GROUND",
        living_state=LivingState.ALIVE,
    )
    engine.add_casualty(casualty)

    engine.tick()

    assert building_cell.collapsed is True
    assert engine.grid.get_cell_status(collapse_coord) == CellStatus.PASSABLE
    assert casualty.health == 0.0
    assert casualty.living_state is LivingState.DECEASED

    collapse_events = [
        e for e in engine.events if e.event_type is EventType.BUILDING_COLLAPSED
    ]
    assert len(collapse_events) == 1
    assert collapse_events[0].payload == {
        "building_id": "B_COLLAPSE",
        "coord": {"x": 1, "y": 1, "z": 0},
    }
