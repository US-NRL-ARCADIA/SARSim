from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

from .grid import Coordinate, SpatialGrid
from .types import CellStatus, DamageStatus

if TYPE_CHECKING:
    from .casualties import Casualty


class Orientation(Enum):
    """Cardinal orientation for agents in the grid."""

    NORTH = auto()
    EAST = auto()
    SOUTH = auto()
    WEST = auto()


class AgentClass(Enum):
    """High-level agent classes."""

    UGV = auto()
    UAV = auto()


@dataclass
class Agent:
    """Core agent representation for SARSim."""

    id: str
    coord: Coordinate
    orientation: Orientation
    agent_class: AgentClass
    busy_ticks_remaining: int = 0
    last_error: str | None = None
    damage_status: DamageStatus | None = None
    payload: Casualty | None = None


def _orientation_delta(orientation: Orientation) -> tuple[int, int]:
    if orientation is Orientation.NORTH:
        return 0, -1
    if orientation is Orientation.SOUTH:
        return 0, 1
    if orientation is Orientation.EAST:
        return 1, 0
    return -1, 0


def move_forward(agent: Agent, grid: SpatialGrid) -> tuple[bool, str]:
    """Move the agent one cell forward if allowed."""
    dx, dy = _orientation_delta(agent.orientation)
    target = Coordinate(x=agent.coord.x + dx, y=agent.coord.y + dy, z=agent.coord.z)

    if not grid.is_in_bounds(target):
        agent.last_error = "OUT_OF_BOUNDS"
        return False, "OUT_OF_BOUNDS"

    status = grid.evaluate_cell_status(target, agent.agent_class)
    if status == CellStatus.IMPASSABLE:
        agent.last_error = "IMPASSABLE"
        return False, "IMPASSABLE"

    if agent.agent_class == AgentClass.UGV and target.z == 0 and status == CellStatus.PASSABLE:
        agent.last_error = "PASSABLE_BLOCKED"
        return False, "PASSABLE_BLOCKED"

    entities = grid.get_entities(target)
    if any(isinstance(e, Agent) for e in entities):
        agent.last_error = "COLLISION_OCCURRED"
        return False, "COLLISION_OCCURRED"

    grid.remove_entity(agent.coord, agent)
    agent.coord = target
    grid.add_entity(agent.coord, agent)
    agent.last_error = None
    return True, "OK"


def turn_left(agent: Agent) -> None:
    """Rotate agent orientation 90° counter-clockwise."""
    if agent.orientation == Orientation.NORTH:
        agent.orientation = Orientation.WEST
    elif agent.orientation == Orientation.WEST:
        agent.orientation = Orientation.SOUTH
    elif agent.orientation == Orientation.SOUTH:
        agent.orientation = Orientation.EAST
    elif agent.orientation == Orientation.EAST:
        agent.orientation = Orientation.NORTH


def turn_right(agent: Agent) -> None:
    """Rotate agent orientation 90° clockwise."""
    if agent.orientation == Orientation.NORTH:
        agent.orientation = Orientation.EAST
    elif agent.orientation == Orientation.EAST:
        agent.orientation = Orientation.SOUTH
    elif agent.orientation == Orientation.SOUTH:
        agent.orientation = Orientation.WEST
    elif agent.orientation == Orientation.WEST:
        agent.orientation = Orientation.NORTH


def ascend(agent: Agent, grid: SpatialGrid) -> tuple[bool, str]:
    """Ascend one z-level for UAV agents."""
    if agent.agent_class != AgentClass.UAV:
        agent.last_error = "ASCEND_NOT_ALLOWED_FOR_UGV"
        return False, "ASCEND_NOT_ALLOWED_FOR_UGV"

    target = Coordinate(x=agent.coord.x, y=agent.coord.y, z=agent.coord.z + 1)
    if not grid.is_in_bounds(target):
        agent.last_error = "OUT_OF_BOUNDS"
        return False, "OUT_OF_BOUNDS"

    status = grid.evaluate_cell_status(target, agent.agent_class)
    if status == CellStatus.IMPASSABLE:
        agent.last_error = "IMPASSABLE"
        return False, "IMPASSABLE"

    entities = grid.get_entities(target)
    if any(isinstance(e, Agent) for e in entities):
        agent.last_error = "COLLISION_OCCURRED"
        return False, "COLLISION_OCCURRED"

    grid.remove_entity(agent.coord, agent)
    agent.coord = target
    grid.add_entity(agent.coord, agent)
    agent.last_error = None
    return True, "OK"


def descend(agent: Agent, grid: SpatialGrid) -> tuple[bool, str]:
    """Descend one z-level for UAV agents."""
    if agent.agent_class != AgentClass.UAV:
        agent.last_error = "DESCEND_NOT_ALLOWED_FOR_UGV"
        return False, "DESCEND_NOT_ALLOWED_FOR_UGV"

    target = Coordinate(x=agent.coord.x, y=agent.coord.y, z=agent.coord.z - 1)
    if target.z < 1 or not grid.is_in_bounds(target):
        agent.last_error = "OUT_OF_BOUNDS"
        return False, "OUT_OF_BOUNDS"

    status = grid.evaluate_cell_status(target, agent.agent_class)
    if status == CellStatus.IMPASSABLE:
        agent.last_error = "IMPASSABLE"
        return False, "IMPASSABLE"

    entities = grid.get_entities(target)
    if any(isinstance(e, Agent) for e in entities):
        agent.last_error = "COLLISION_OCCURRED"
        return False, "COLLISION_OCCURRED"

    grid.remove_entity(agent.coord, agent)
    agent.coord = target
    grid.add_entity(agent.coord, agent)
    agent.last_error = None
    return True, "OK"
