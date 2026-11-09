from __future__ import annotations

from .grid import Coordinate


def are_adjacent(a: Coordinate, b: Coordinate) -> bool:
    """Return True if two coordinates are adjacent on the same z level."""
    if a.z != b.z:
        return False

    dx = abs(a.x - b.x)
    dy = abs(a.y - b.y)
    return dx + dy == 1
