from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

from .agents import Agent
from .grid import Coordinate
from .sensors import observe_targets, raycast_cone

if TYPE_CHECKING:
    from .engine import SimulationEngine


class SensorRegime(StrEnum):
    """Scenario-selectable sensor regimes."""

    FULL = "FULL"
    FOV_CONE = "FOV_CONE"
    MINIGRID_3 = "MINIGRID_3"


@dataclass(frozen=True, slots=True)
class SensorConfig:
    """Serializable sensor configuration attached to a simulation engine."""

    regime: SensorRegime = SensorRegime.FULL
    max_range: int = 4
    cone_angle_degrees: float = 90.0


class PerceptionFilter(Protocol):
    """Contract for converting complete engine state into visible coordinates."""

    def visible_cells(self, engine: SimulationEngine, observer: Agent) -> set[Coordinate]:
        """Return cells currently visible to ``observer``."""
        ...


@dataclass(frozen=True, slots=True)
class FullObservationFilter:
    """Unrestricted observation of every grid cell."""

    def visible_cells(
        self,
        engine: SimulationEngine,
        observer: Agent,
    ) -> set[Coordinate]:
        del observer
        return {
            Coordinate(x=x, y=y, z=z)
            for x in range(engine.grid.N)
            for y in range(engine.grid.N)
            for z in range(engine.grid.Z)
        }


@dataclass(frozen=True, slots=True)
class FieldOfViewConeFilter:
    """Forward cone blocked by smoke, walls, and intact building cells.

    The observer's cell and an opaque cell are visible. Cells beyond an opaque
    cell are not. Any positive smoke density is opaque by default.
    """

    max_range: int = 4
    angle_degrees: float = 90.0
    smoke_obscures_at: float = 0.0

    def __post_init__(self) -> None:
        if self.max_range <= 0:
            raise ValueError("max_range must be positive")
        if not 0.0 < self.angle_degrees <= 360.0:
            raise ValueError("angle_degrees must be in (0, 360]")
        if not 0.0 <= self.smoke_obscures_at <= 1.0:
            raise ValueError("smoke_obscures_at must be in [0, 1]")

    def visible_cells(
        self,
        engine: SimulationEngine,
        observer: Agent,
    ) -> set[Coordinate]:
        origin_smoke = engine.grid.get_smoke_density(observer.coord)
        if _smoke_is_opaque(origin_smoke, self.smoke_obscures_at):
            return {observer.coord}

        observations = raycast_cone(
            grid=engine.grid,
            casualties={},
            origin=observer.coord,
            orientation=observer.orientation,
            max_range=self.max_range,
            agent_class=observer.agent_class,
            angle_degrees=self.angle_degrees,
            smoke_obscures_at=self.smoke_obscures_at,
            opaque_coords=_opaque_building_cells(engine),
        )
        return {observer.coord, *(sample.coord for sample in observations if sample.is_visible)}


@dataclass(frozen=True, slots=True)
class MiniGridThreeWideFilter:
    """Agent-relative corridor three cells wide and ``max_range`` cells deep."""

    max_range: int = 4
    smoke_obscures_at: float = 0.0

    def __post_init__(self) -> None:
        if self.max_range <= 0:
            raise ValueError("max_range must be positive")
        if not 0.0 <= self.smoke_obscures_at <= 1.0:
            raise ValueError("smoke_obscures_at must be in [0, 1]")

    def visible_cells(
        self,
        engine: SimulationEngine,
        observer: Agent,
    ) -> set[Coordinate]:
        if _smoke_is_opaque(
            engine.grid.get_smoke_density(observer.coord),
            self.smoke_obscures_at,
        ):
            return {observer.coord}

        forward = {
            "NORTH": (0, -1),
            "EAST": (1, 0),
            "SOUTH": (0, 1),
            "WEST": (-1, 0),
        }[observer.orientation.name]
        right = (-forward[1], forward[0])
        targets = {
            Coordinate(
                x=observer.coord.x + forward[0] * depth + right[0] * lateral,
                y=observer.coord.y + forward[1] * depth + right[1] * lateral,
                z=observer.coord.z,
            )
            for depth in range(self.max_range)
            for lateral in range(-1, 2)
        }
        observations = observe_targets(
            grid=engine.grid,
            casualties={},
            origin=observer.coord,
            targets=targets,
            agent_class=observer.agent_class,
            smoke_obscures_at=self.smoke_obscures_at,
            opaque_coords=_opaque_building_cells(engine),
        )
        return {observer.coord, *(sample.coord for sample in observations if sample.is_visible)}


def perception_filter_for(config: SensorConfig) -> PerceptionFilter:
    """Create the filter selected by a scenario sensor configuration."""
    if config.regime is SensorRegime.FULL:
        return FullObservationFilter()
    if config.regime is SensorRegime.MINIGRID_3:
        return MiniGridThreeWideFilter(max_range=config.max_range)
    return FieldOfViewConeFilter(
        max_range=config.max_range,
        angle_degrees=config.cone_angle_degrees,
    )


def _opaque_building_cells(engine: SimulationEngine) -> set[Coordinate]:
    return {
        cell.coord
        for building in engine.buildings.values()
        for cell in building.cells.values()
        if not cell.collapsed
    }


def _smoke_is_opaque(density: float, threshold: float) -> bool:
    return density > 0.0 if threshold <= 0.0 else density >= threshold
