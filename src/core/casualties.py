from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from .grid import Coordinate, SpatialGrid
from .types import CellStatus, TransportStatus


class TriageState(Enum):
    """Triage classification for casualties."""

    UNKNOWN = auto()
    MINOR = auto()
    DELAYED = auto()
    IMMEDIATE = auto()
    EXPECTANT = auto()


class LivingState(Enum):
    """Life state of a casualty."""

    ALIVE = auto()
    DECEASED = auto()


@dataclass
class Casualty:
    """Casualty model with simple health decay."""

    id: str
    coord: Coordinate
    health: float
    decay_rate: float
    is_covered: bool
    triage_state: TriageState
    transport_status: TransportStatus | str
    living_state: LivingState

    def update_health(self, smoke_density: float) -> None:
        """Advance casualty health by one time step."""
        if self.living_state is LivingState.DECEASED:
            return

        effective_decay = self.decay_rate
        if self.is_covered or smoke_density >= 0.5:
            effective_decay *= 2.0

        self.health = max(0.0, min(100.0, self.health - effective_decay))
        if self.health <= 0.0:
            self.living_state = LivingState.DECEASED


def update_casualty_cover_from_grid(grid: SpatialGrid, casualty: Casualty) -> None:
    """Update casualty.is_covered based on debris at its coordinate."""
    ground_coord = Coordinate(x=casualty.coord.x, y=casualty.coord.y, z=0)
    casualty.is_covered = grid.get_cell_status(ground_coord) == CellStatus.PASSABLE
