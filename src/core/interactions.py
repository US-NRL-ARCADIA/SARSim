from __future__ import annotations

from .agents import Agent
from .buildings import BuildingCell
from .casualties import Casualty, LivingState, TriageState
from .geometry import are_adjacent
from .grid import Coordinate, SpatialGrid
from .types import CellStatus, TransportStatus


def triage(agent: Agent, casualty: Casualty, stable_decay_rate: float) -> tuple[bool, str]:
    """Perform triage on a casualty."""
    if casualty.living_state is not LivingState.ALIVE:
        return False, "CASUALTY_NOT_ALIVE"
    if casualty.is_covered:
        return False, "CASUALTY_COVERED_BLOCKS_TRIAGE"
    if agent.coord == casualty.coord:
        return False, "COLOCATED_NOT_ALLOWED"
    if not are_adjacent(agent.coord, casualty.coord):
        return False, "NOT_ADJACENT"

    casualty.decay_rate = stable_decay_rate
    casualty.triage_state = TriageState.MINOR
    return True, "OK"


def clear_debris(
    agent: Agent,
    grid: SpatialGrid,
    coord: Coordinate,
    casualties: dict[str, Casualty],
) -> tuple[bool, str]:
    """Clear debris at the given ground-level coordinate."""
    if agent.coord == coord:
        return False, "COLOCATED_NOT_ALLOWED"
    if not are_adjacent(agent.coord, coord):
        return False, "NOT_ADJACENT"

    ground_coord = Coordinate(x=coord.x, y=coord.y, z=0)
    if grid.get_cell_status(ground_coord) != CellStatus.PASSABLE:
        return False, "NO_DEBRIS"

    grid.set_cell_status(ground_coord, CellStatus.UNOCCUPIED)
    for casualty in casualties.values():
        if casualty.coord == coord:
            casualty.is_covered = False
    return True, "OK"


def retrieve_body(agent: Agent, casualty: Casualty) -> tuple[bool, str]:
    """Retrieve a deceased casualty into the agent's payload."""
    if casualty.living_state is not LivingState.DECEASED:
        return False, "CASUALTY_NOT_DECEASED"
    if casualty.is_covered:
        return False, "CASUALTY_COVERED_BLOCKS_RETRIEVE"
    if agent.coord == casualty.coord:
        return False, "COLOCATED_NOT_ALLOWED"
    if not are_adjacent(agent.coord, casualty.coord):
        return False, "NOT_ADJACENT"
    if agent.payload is not None:
        return False, "PAYLOAD_FULL"

    agent.payload = casualty
    casualty.transport_status = TransportStatus.LOADED
    casualty.coord = agent.coord
    return True, "OK"


def load_casualty(
    agent: Agent,
    casualty: Casualty,
    hospital_casualty_ids_by_zone: dict[str, list[str]] | None = None,
) -> tuple[bool, str]:
    """Load a living casualty into the agent payload for transport."""
    if casualty.living_state is not LivingState.ALIVE:
        return False, "CASUALTY_NOT_ALIVE"
    if casualty.is_covered:
        return False, "CASUALTY_COVERED_BLOCKS_LOAD"
    if agent.coord == casualty.coord:
        return False, "COLOCATED_NOT_ALLOWED"
    if not are_adjacent(agent.coord, casualty.coord):
        return False, "NOT_ADJACENT"
    if agent.payload is not None:
        return False, "PAYLOAD_FULL"

    agent.payload = casualty
    casualty.transport_status = TransportStatus.LOADED
    casualty.coord = agent.coord

    if hospital_casualty_ids_by_zone is not None:
        for roster in hospital_casualty_ids_by_zone.values():
            if casualty.id in roster:
                roster.remove(casualty.id)

    return True, "OK"


def unload_casualty(agent: Agent) -> tuple[bool, str]:
    """Unload the currently carried casualty at the agent location."""
    if agent.payload is None:
        return False, "NO_PAYLOAD"

    casualty = agent.payload
    casualty.transport_status = TransportStatus.UNLOADED
    casualty.coord = agent.coord
    agent.payload = None
    return True, "OK"


def transfer_casualty_to_hospital(
    agent: Agent,
    zones: list[dict[str, object]],
    hospital_casualty_ids_by_zone: dict[str, list[str]],
) -> tuple[bool, str, str | None]:
    """Transfer the currently carried casualty into adjacent field-hospital care."""
    if agent.payload is None:
        return False, "NO_PAYLOAD", None

    for zone in zones:
        if str(zone.get("zone_type", "")) != "FIELD_HOSPITAL":
            continue
        zone_id = str(zone.get("id", ""))
        for cell in zone.get("cells", []):
            coord = Coordinate(x=int(cell["x"]), y=int(cell["y"]), z=int(cell["z"]))
            if are_adjacent(agent.coord, coord) or agent.coord == coord:
                casualty = agent.payload
                casualty.transport_status = TransportStatus.UNLOADED
                casualty.coord = coord
                agent.payload = None
                roster = hospital_casualty_ids_by_zone.setdefault(zone_id, [])
                if casualty.id not in roster:
                    roster.append(casualty.id)
                return True, "OK", zone_id

    return False, "NOT_ADJACENT_TO_FIELD_HOSPITAL", None


def breach_entryway(
    agent: Agent,
    grid: SpatialGrid,
    building_cell: BuildingCell,
) -> tuple[bool, str]:
    """Breach a building cell to create/clear an entryway."""
    cell_coord = building_cell.coord
    if building_cell.collapsed:
        return False, "CELL_ALREADY_COLLAPSED"
    if agent.coord == cell_coord:
        return False, "COLOCATED_NOT_ALLOWED"
    if not are_adjacent(agent.coord, cell_coord):
        return False, "NOT_ADJACENT"

    building_cell.integrity = max(building_cell.integrity, 0.5)
    ground_coord = Coordinate(x=cell_coord.x, y=cell_coord.y, z=0)
    grid.set_cell_status(ground_coord, CellStatus.UNOCCUPIED)
    return True, "OK"
