from __future__ import annotations

from dataclasses import dataclass

from .agents import Agent
from .casualties import Casualty, LivingState
from .grid import Coordinate, SpatialGrid
from .types import CellStatus, DamageStatus


@dataclass
class BuildingCell:
    """Single cell of a building with integrity and collapse state."""

    coord: Coordinate
    integrity: float
    collapsed: bool = False


@dataclass
class Building:
    """Collection of building cells."""

    id: str
    cells: dict[tuple[int, int, int], BuildingCell]

    def collapse_cell(
        self,
        grid: SpatialGrid,
        cell_coord: Coordinate,
        casualties: dict[str, Casualty],
    ) -> None:
        """Apply collapse rule to the specified cell if integrity < 0.2."""
        key = (cell_coord.x, cell_coord.y, cell_coord.z)
        building_cell = self.cells.get(key)
        if building_cell is None or building_cell.collapsed or building_cell.integrity >= 0.2:
            return

        building_cell.collapsed = True
        ground_coord = Coordinate(x=cell_coord.x, y=cell_coord.y, z=0)
        grid.set_cell_status(ground_coord, CellStatus.PASSABLE)

        for casualty in casualties.values():
            if casualty.coord == cell_coord:
                casualty.health = max(0.0, casualty.health - 50.0)
                if casualty.health <= 0.0:
                    casualty.living_state = LivingState.DECEASED

        agents_at_cell = [e for e in grid.get_entities(cell_coord) if isinstance(e, Agent)]
        for agent in agents_at_cell:
            candidates = [
                Coordinate(cell_coord.x + 1, cell_coord.y, cell_coord.z),
                Coordinate(cell_coord.x - 1, cell_coord.y, cell_coord.z),
                Coordinate(cell_coord.x, cell_coord.y + 1, cell_coord.z),
                Coordinate(cell_coord.x, cell_coord.y - 1, cell_coord.z),
            ]
            for target in candidates:
                if not grid.is_in_bounds(target):
                    continue
                if any(isinstance(e, Agent) for e in grid.get_entities(target)):
                    continue
                grid.remove_entity(agent.coord, agent)
                agent.coord = target
                grid.add_entity(agent.coord, agent)
                break
            agent.damage_status = DamageStatus.DAMAGED
