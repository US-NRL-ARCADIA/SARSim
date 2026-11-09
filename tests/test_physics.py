from __future__ import annotations

from src.core.grid import Coordinate, SpatialGrid, CellStatus
from src.core.entities import (
    Agent,
    AgentClass,
    Orientation,
    move_forward,
)


def _make_grid() -> SpatialGrid:
    # Small grid for unit tests: N=4, Z=2
    return SpatialGrid(N=4, Z=2)


def test_agent_forward_movement_out_of_bounds() -> None:
    """Agent attempting to move beyond grid should be blocked with OUT_OF_BOUNDS."""
    grid = _make_grid()

    # Place agent at the northern edge facing NORTH.
    start = Coordinate(x=1, y=0, z=0)
    agent = Agent(
        id="A_OUT",
        coord=start,
        orientation=Orientation.NORTH,
        agent_class=AgentClass.UGV,
    )
    grid.add_entity(agent.coord, agent)

    success, reason = move_forward(agent, grid)

    assert success is False
    assert reason == "OUT_OF_BOUNDS"
    # Position should remain unchanged.
    assert agent.coord == start


def test_ugv_blocked_by_passable_debris() -> None:
    """UGV cannot enter PASSABLE debris at z=0."""
    grid = _make_grid()

    start = Coordinate(x=0, y=0, z=0)
    target = Coordinate(x=1, y=0, z=0)  # EAST of start at ground level

    # Set target cell to PASSABLE debris.
    grid.set_cell_status(target, CellStatus.PASSABLE)

    agent = Agent(
        id="UGV1",
        coord=start,
        orientation=Orientation.EAST,
        agent_class=AgentClass.UGV,
    )
    grid.add_entity(agent.coord, agent)

    success, reason = move_forward(agent, grid)

    assert success is False
    assert reason == "PASSABLE_BLOCKED"
    # Agent should not move.
    assert agent.coord == start


def test_uav_can_fly_over_ground_debris() -> None:
    """UAV at z=1 should be able to move over ground-level PASSABLE debris."""
    grid = _make_grid()

    # Ground cell has PASSABLE debris.
    ground_target = Coordinate(x=1, y=0, z=0)
    grid.set_cell_status(ground_target, CellStatus.PASSABLE)

    # Air cell above is UNOCCUPIED.
    air_start = Coordinate(x=0, y=0, z=1)
    air_target = Coordinate(x=1, y=0, z=1)
    grid.set_cell_status(air_target, CellStatus.UNOCCUPIED)

    agent = Agent(
        id="UAV1",
        coord=air_start,
        orientation=Orientation.EAST,
        agent_class=AgentClass.UAV,
    )
    grid.add_entity(agent.coord, agent)

    success, reason = move_forward(agent, grid)

    assert success is True
    assert reason == "OK"
    # UAV should move horizontally at its own z level.
    assert agent.coord == air_target


def test_no_two_agents_same_cell() -> None:
    """Movement into a cell occupied by another agent should be blocked."""
    grid = _make_grid()

    # Agent 1 starts at (1, 1, 0)
    cell = Coordinate(x=1, y=1, z=0)
    agent1 = Agent(
        id="A1",
        coord=cell,
        orientation=Orientation.NORTH,
        agent_class=AgentClass.UGV,
    )
    grid.add_entity(agent1.coord, agent1)

    # Agent 2 starts adjacent and tries to move into agent1's cell.
    start2 = Coordinate(x=1, y=2, z=0)  # SOUTH of cell
    agent2 = Agent(
        id="A2",
        coord=start2,
        orientation=Orientation.NORTH,  # moving from (1,2,0) to (1,1,0)
        agent_class=AgentClass.UGV,
    )
    grid.add_entity(agent2.coord, agent2)

    success, reason = move_forward(agent2, grid)

    assert success is False
    assert reason == "COLLISION_OCCURRED"
    # Agent 2 should remain in its original cell.
    assert agent2.coord == start2
    # Agent 1 remains in its original cell.
    assert agent1.coord == cell