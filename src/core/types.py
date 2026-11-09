from __future__ import annotations

from enum import IntEnum, StrEnum


class CellStatus(IntEnum):
    """Cell occupancy / traversability categories."""

    UNOCCUPIED = 0
    PASSABLE = 1
    IMPASSABLE = 2


class TransportStatus(StrEnum):
    """Transport state for a casualty."""

    ON_GROUND = "ON_GROUND"
    LOADED = "LOADED"
    UNLOADED = "UNLOADED"


class DamageStatus(StrEnum):
    """Damage state for an agent."""

    DAMAGED = "DAMAGED"