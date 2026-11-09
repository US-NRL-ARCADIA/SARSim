from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .types import CellStatus


@dataclass(frozen=True)
class Coordinate:
    """3D integer coordinate within the spatial grid."""
    x: int
    y: int
    z: int


class SpatialGrid:
    """Core spatial grid model for SARSim.

    Represents:
    - status_grid: int32 (N, N, Z) with CellStatus codes.
    - smoke_grid: float32 (N, N, Z) with D ∈ [0.0, 1.0].
    - entity_locations: mapping from (x, y, z) to list of entities.
    """

    def __init__(self, N: int, Z: int) -> None:
        if N <= 0 or Z <= 0:
            raise ValueError("Grid dimensions N and Z must be positive integers.")

        self.N: int = N
        self.Z: int = Z

        self.status_grid: np.ndarray = np.zeros((N, N, Z), dtype=np.int32)
        self.smoke_grid: np.ndarray = np.zeros((N, N, Z), dtype=np.float64)
        self.entity_locations: dict[tuple[int, int, int], list[object]] = {}

    def is_in_bounds(self, coord: Coordinate) -> bool:
        """Return True if coord is inside [0, N-1] x [0, N-1] x [0, Z-1]."""
        return (
            0 <= coord.x < self.N
            and 0 <= coord.y < self.N
            and 0 <= coord.z < self.Z
        )

    def set_cell_status(self, coord: Coordinate, status: int) -> None:
        """Set the status of a given cell."""
        if not self.is_in_bounds(coord):
            raise IndexError("Coordinate out of bounds.")
        self.status_grid[coord.x, coord.y, coord.z] = status

    def get_cell_status(self, coord: Coordinate) -> CellStatus:
        """Return the status code of a given cell."""
        if not self.is_in_bounds(coord):
            raise IndexError("Coordinate out of bounds.")
        return CellStatus(int(self.status_grid[coord.x, coord.y, coord.z]))

    def set_smoke_density(self, coord: Coordinate, density: float) -> None:
        """Set smoke density for a cell, clamped to [0.0, 1.0]."""
        if not self.is_in_bounds(coord):
            raise IndexError("Coordinate out of bounds.")
        clamped = max(0.0, min(1.0, density))
        self.smoke_grid[coord.x, coord.y, coord.z] = clamped

    def get_smoke_density(self, coord: Coordinate) -> float:
        """Get smoke density for a cell."""
        if not self.is_in_bounds(coord):
            raise IndexError("Coordinate out of bounds.")
        return float(self.smoke_grid[coord.x, coord.y, coord.z])

    def add_entity(self, coord: Coordinate, entity: object) -> None:
        """Add an entity to the given coordinate."""
        if not self.is_in_bounds(coord):
            raise IndexError("Coordinate out of bounds.")
        key = (coord.x, coord.y, coord.z)
        self.entity_locations.setdefault(key, []).append(entity)

    def remove_entity(self, coord: Coordinate, entity: object) -> None:
        """Remove an entity from the given coordinate, if present."""
        if not self.is_in_bounds(coord):
            raise IndexError("Coordinate out of bounds.")
        key = (coord.x, coord.y, coord.z)
        if key not in self.entity_locations:
            return
        entities = self.entity_locations[key]
        if entity in entities:
            entities.remove(entity)
        if not entities:
            del self.entity_locations[key]

    def get_entities(self, coord: Coordinate) -> list[object]:
        """Return list of entities at the given coordinate."""
        if not self.is_in_bounds(coord):
            raise IndexError("Coordinate out of bounds.")
        return list(self.entity_locations.get((coord.x, coord.y, coord.z), []))

    def evaluate_cell_status(self, coord: Coordinate, agent_class: object) -> CellStatus:
        """Evaluate effective cell status for an agent class.

        This is a placeholder; Phase 1 will refine this based on:
        - UGV / UAV differences.
        - Ground-level vs agent-level z rules.
        - Co-occupancy rules (agents in same cell).
        """
        if not self.is_in_bounds(coord):
            return CellStatus.IMPASSABLE
        return self.get_cell_status(coord)