from __future__ import annotations

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
    breach_entryway,
    clear_debris,
    load_casualty,
    retrieve_body,
    transfer_casualty_to_hospital,
    triage,
    unload_casualty,
)
from src.core.grid import CellStatus, SpatialGrid


def test_casualty_health_decay_and_death_transition() -> None:
    """Health decays each step and eventually leads to death."""
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

    # Step 1: 10 -> 7
    casualty.update_health(smoke_density=0.0)
    assert casualty.health == 7.0
    assert casualty.living_state is LivingState.ALIVE

    # Step 2: 7 -> 4
    casualty.update_health(smoke_density=0.0)
    assert casualty.health == 4.0
    assert casualty.living_state is LivingState.ALIVE

    # Step 3: 4 -> 1
    casualty.update_health(smoke_density=0.0)
    assert casualty.health == 1.0
    assert casualty.living_state is LivingState.ALIVE

    # Step 4: 1 -> 0 (clamped), transition to DECEASED
    casualty.update_health(smoke_density=0.0)
    assert casualty.health == 0.0
    assert casualty.living_state is LivingState.DECEASED

    # Further updates should not change state.
    casualty.update_health(smoke_density=1.0)
    assert casualty.health == 0.0
    assert casualty.living_state is LivingState.DECEASED


def test_casualty_cover_doubles_decay() -> None:
    """is_covered or high smoke doubles effective decay."""
    casualty = Casualty(
        id="C2",
        coord=Coordinate(x=0, y=0, z=0),
        health=20.0,
        decay_rate=2.0,
        is_covered=True,  # covered -> double decay
        triage_state=TriageState.UNKNOWN,
        transport_status="ON_GROUND",
        living_state=LivingState.ALIVE,
    )

    # With coverage and smoke < 0.5, decay should double.
    casualty.update_health(smoke_density=0.1)
    assert casualty.health == 16.0  # 20 - (2 * 2)

    # With high smoke, still double decay (coverage already true).
    casualty.update_health(smoke_density=0.8)
    assert casualty.health == 12.0  # 16 - (2 * 2)


def test_building_collapse_causes_health_penalty() -> None:
    """Building cell with low integrity should collapse and penalize casualty health."""
    grid = SpatialGrid(N=4, Z=2)

    collapse_coord = Coordinate(x=1, y=1, z=0)
    cell = BuildingCell(coord=collapse_coord, integrity=0.1, collapsed=False)
    building = Building(
        id="B1",
        cells={(collapse_coord.x, collapse_coord.y, collapse_coord.z): cell},
    )

    # Casualty located in the collapsing cell, with low enough health to die from penalty.
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
    casualties = {casualty.id: casualty}

    # Before collapse, ground cell should be UNOCCUPIED.
    assert grid.get_cell_status(collapse_coord) == CellStatus.UNOCCUPIED

    # Apply collapse rule.
    building.collapse_cell(grid, collapse_coord, casualties)

    # Ground-level cell should now be PASSABLE (debris).
    assert grid.get_cell_status(collapse_coord) == CellStatus.PASSABLE

    # Casualty health should be reduced by 50 and clamped at 0, with death.
    assert casualty.health == 0.0
    assert casualty.living_state is LivingState.DECEASED

    # If we collapse again (idempotent), health should not change further.
    building.collapse_cell(grid, collapse_coord, casualties)
    assert casualty.health == 0.0
    assert casualty.living_state is LivingState.DECEASED


def test_casualty_cover_blocks_triage() -> None:
    """Covered casualty should block triage."""
    grid = SpatialGrid(N=4, Z=2)

    casualty_coord = Coordinate(x=1, y=1, z=0)
    # Set debris at casualty coord -> PASSABLE at ground.
    grid.set_cell_status(casualty_coord, CellStatus.PASSABLE)

    casualty = Casualty(
        id="C_TRIAGE",
        coord=casualty_coord,
        health=50.0,
        decay_rate=2.0,
        is_covered=True,  # covered
        triage_state=TriageState.UNKNOWN,
        transport_status="ON_GROUND",
        living_state=LivingState.ALIVE,
    )

    agent_coord = Coordinate(x=1, y=2, z=0)  # adjacent SOUTH
    agent = Agent(
        id="A_TRIAGE",
        coord=agent_coord,
        orientation=Orientation.NORTH,
        agent_class=AgentClass.UGV,
    )

    success, reason = triage(agent, casualty, stable_decay_rate=0.5)
    assert success is False
    assert reason == "CASUALTY_COVERED_BLOCKS_TRIAGE"
    assert casualty.decay_rate == 2.0  # unchanged


def test_clear_debris_enables_triage() -> None:
    """Clearing debris should remove cover and enable triage."""
    grid = SpatialGrid(N=4, Z=2)

    casualty_coord = Coordinate(x=1, y=1, z=0)
    ground_coord = Coordinate(x=1, y=1, z=0)

    # Debris at ground -> PASSABLE.
    grid.set_cell_status(ground_coord, CellStatus.PASSABLE)

    casualty = Casualty(
        id="C_CLEAR",
        coord=casualty_coord,
        health=50.0,
        decay_rate=2.0,
        is_covered=True,
        triage_state=TriageState.UNKNOWN,
        transport_status="ON_GROUND",
        living_state=LivingState.ALIVE,
    )
    casualties = {casualty.id: casualty}

    agent_coord = Coordinate(x=1, y=2, z=0)  # adjacent SOUTH
    agent = Agent(
        id="A_CLEAR",
        coord=agent_coord,
        orientation=Orientation.NORTH,
        agent_class=AgentClass.UGV,
    )

    # Clear debris.
    success_clear, reason_clear = clear_debris(agent, grid, casualty_coord, casualties)
    assert success_clear is True
    assert reason_clear == "OK"
    assert grid.get_cell_status(ground_coord) == CellStatus.UNOCCUPIED
    assert casualty.is_covered is False

    # Now triage should succeed and set a stable decay rate.
    success_triage, reason_triage = triage(agent, casualty, stable_decay_rate=0.5)
    assert success_triage is True
    assert reason_triage == "OK"
    assert casualty.decay_rate == 0.5


def test_agent_payload_capacity_one_entity() -> None:
    """Agent should only be able to carry one casualty payload at a time."""
    # Deceased casualty 1, directly NORTH of the agent.
    casualty1 = Casualty(
        id="C_BODY1",
        coord=Coordinate(x=1, y=1, z=0),
        health=0.0,
        decay_rate=0.0,
        is_covered=False,
        triage_state=TriageState.UNKNOWN,
        transport_status="ON_GROUND",
        living_state=LivingState.DECEASED,
    )

    # Deceased casualty 2, directly EAST of the agent.
    casualty2 = Casualty(
        id="C_BODY2",
        coord=Coordinate(x=2, y=2, z=0),
        health=0.0,
        decay_rate=0.0,
        is_covered=False,
        triage_state=TriageState.UNKNOWN,
        transport_status="ON_GROUND",
        living_state=LivingState.DECEASED,
    )

    # Agent at (1, 2, 0):
    # - Adjacent to casualty1 at (1, 1, 0): |dx|+|dy| = 1
    # - Adjacent to casualty2 at (2, 2, 0): |dx|+|dy| = 1
    agent = Agent(
        id="A_PAYLOAD",
        coord=Coordinate(x=1, y=2, z=0),
        orientation=Orientation.NORTH,
        agent_class=AgentClass.UGV,
    )

    # First retrieve should succeed.
    success1, reason1 = retrieve_body(agent, casualty1)
    assert success1 is True
    assert reason1 == "OK"
    assert agent.payload is casualty1

    # Second retrieve should fail due to payload full (adjacency satisfied).
    success2, reason2 = retrieve_body(agent, casualty2)
    assert success2 is False
    assert reason2 == "PAYLOAD_FULL"
    assert agent.payload is casualty1


def test_load_and_unload_living_casualty() -> None:
    """Living casualties should be loadable and unloadable for transport."""
    casualty = Casualty(
        id="C_LOAD",
        coord=Coordinate(x=1, y=1, z=0),
        health=40.0,
        decay_rate=1.0,
        is_covered=False,
        triage_state=TriageState.UNKNOWN,
        transport_status="ON_GROUND",
        living_state=LivingState.ALIVE,
    )

    agent = Agent(
        id="A_LOAD",
        coord=Coordinate(x=1, y=2, z=0),
        orientation=Orientation.NORTH,
        agent_class=AgentClass.UGV,
    )

    success_load, reason_load = load_casualty(agent, casualty)
    assert success_load is True
    assert reason_load == "OK"
    assert agent.payload is casualty
    assert casualty.transport_status == "LOADED"
    assert casualty.coord == agent.coord

    success_unload, reason_unload = unload_casualty(agent)
    assert success_unload is True
    assert reason_unload == "OK"
    assert agent.payload is None
    assert casualty.transport_status == "UNLOADED"
    assert casualty.coord == agent.coord


def test_load_casualty_removes_hospital_care_membership() -> None:
    """Loading a casualty from hospital pickup should remove it from hospital care roster."""
    casualty = Casualty(
        id="C_HOSP_LOAD",
        coord=Coordinate(x=5, y=5, z=0),
        health=40.0,
        decay_rate=1.0,
        is_covered=False,
        triage_state=TriageState.UNKNOWN,
        transport_status="UNLOADED",
        living_state=LivingState.ALIVE,
    )

    agent = Agent(
        id="A_HOSP_LOAD",
        coord=Coordinate(x=5, y=4, z=0),
        orientation=Orientation.NORTH,
        agent_class=AgentClass.UGV,
    )

    hospital_casualty_ids_by_zone = {"FH1": ["C_HOSP_LOAD"]}

    success_load, reason_load = load_casualty(
        agent,
        casualty,
        hospital_casualty_ids_by_zone,
    )
    assert success_load is True
    assert reason_load == "OK"
    assert agent.payload is casualty
    assert casualty.transport_status == "LOADED"
    assert hospital_casualty_ids_by_zone == {"FH1": []}


def test_transfer_casualty_to_hospital() -> None:
    """Transferred casualties should move from payload into hospital care location."""
    casualty = Casualty(
        id="C_TRANSFER",
        coord=Coordinate(x=1, y=2, z=0),
        health=40.0,
        decay_rate=1.0,
        is_covered=False,
        triage_state=TriageState.UNKNOWN,
        transport_status="LOADED",
        living_state=LivingState.ALIVE,
    )

    agent = Agent(
        id="A_TRANSFER",
        coord=Coordinate(x=4, y=5, z=0),
        orientation=Orientation.EAST,
        agent_class=AgentClass.UGV,
        payload=casualty,
    )

    zones = [
        {
            "id": "FH1",
            "zone_type": "FIELD_HOSPITAL",
            "cells": [{"x": 5, "y": 5, "z": 0}],
            "labels": ["medical-dropoff"],
        }
    ]

    hospital_casualty_ids_by_zone: dict[str, list[str]] = {}

    success, reason, zone_id = transfer_casualty_to_hospital(
        agent,
        zones,
        hospital_casualty_ids_by_zone,
    )
    assert success is True
    assert reason == "OK"
    assert zone_id == "FH1"
    assert agent.payload is None
    assert casualty.transport_status == "UNLOADED"
    assert casualty.coord == Coordinate(x=5, y=5, z=0)
    assert hospital_casualty_ids_by_zone == {"FH1": ["C_TRANSFER"]}


def test_building_collapse_moves_and_damages_agent() -> None:
    """Agent in collapsing cell should be damaged and moved to adjacent free cell if possible."""
    grid = SpatialGrid(N=4, Z=2)

    collapse_coord = Coordinate(x=1, y=1, z=0)
    cell = BuildingCell(coord=collapse_coord, integrity=0.1, collapsed=False)
    building = Building(
        id="B2",
        cells={(collapse_coord.x, collapse_coord.y, collapse_coord.z): cell},
    )

    # Agent in the collapsing cell.
    agent = Agent(
        id="A_COLLAPSE",
        coord=collapse_coord,
        orientation=Orientation.NORTH,
        agent_class=AgentClass.UGV,
    )
    grid.add_entity(agent.coord, agent)

    casualties: dict[str, Casualty] = {}

    building.collapse_cell(grid, collapse_coord, casualties)

    # Agent should be marked damaged.
    assert agent.damage_status == "DAMAGED"

    # Agent should no longer be at collapse_coord.
    entities_after = grid.get_entities(collapse_coord)
    assert agent not in entities_after

    # Agent should now be in some adjacent cell.
    possible_targets = {
        (collapse_coord.x + 1, collapse_coord.y, collapse_coord.z),
        (collapse_coord.x - 1, collapse_coord.y, collapse_coord.z),
        (collapse_coord.x, collapse_coord.y + 1, collapse_coord.z),
        (collapse_coord.x, collapse_coord.y - 1, collapse_coord.z),
    }
    assert (agent.coord.x, agent.coord.y, agent.coord.z) in possible_targets

def test_breach_entryway_raises_integrity_and_clears_debris() -> None:
    """Breach entryway should raise cell integrity and clear debris at that coord."""
    grid = SpatialGrid(N=4, Z=2)

    cell_coord = Coordinate(x=1, y=1, z=0)
    # Start with a fragile, non-collapsed building cell.
    building_cell = BuildingCell(coord=cell_coord, integrity=0.1, collapsed=False)

    # Put debris at the ground-level coord.
    grid.set_cell_status(cell_coord, CellStatus.PASSABLE)

    # Agent adjacent to the building cell.
    agent = Agent(
        id="A_BREACH",
        coord=Coordinate(x=1, y=2, z=0),  # directly SOUTH
        orientation=Orientation.NORTH,
        agent_class=AgentClass.UGV,
    )

    success, reason = breach_entryway(agent, grid, building_cell)
    assert success is True
    assert reason == "OK"

    # Integrity should be raised to at least 0.5.
    assert building_cell.integrity >= 0.5

    # Debris should be cleared at ground level.
    assert grid.get_cell_status(cell_coord) == CellStatus.UNOCCUPIED