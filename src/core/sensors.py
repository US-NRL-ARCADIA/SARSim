from __future__ import annotations

from dataclasses import dataclass, field
from math import atan2, degrees, hypot

from .entities import Agent, AgentClass, Casualty, Orientation
from .grid import Coordinate, SpatialGrid
from .types import CellStatus


@dataclass
class RaySample:
    """Single sample along a ray through the grid."""

    coord: Coordinate
    cell_status: CellStatus
    smoke_density: float
    has_casualty: bool
    is_visible: bool = True
    obscured_by_smoke: bool = False


@dataclass
class ObservationSample:
    """Observed state for a cell in an agent-centric view."""

    coord: Coordinate
    is_visible: bool
    cell_status: CellStatus | None
    smoke_density: float | None
    has_casualty: bool | None
    obscured_by_smoke: bool = False


@dataclass
class AgentBeliefCell:
    """Agent-local belief about a single cell."""

    coord: Coordinate
    last_update_tick: int
    last_seen_tick: int | None
    ever_observed: bool
    currently_visible: bool
    last_known_cell_status: CellStatus | None
    last_known_smoke_density: float | None
    last_known_has_casualty: bool | None
    obscured_by_smoke: bool = False


@dataclass
class AgentBeliefState:
    """Accumulated per-agent belief map over time."""

    agent_id: str
    cells: dict[tuple[int, int, int], AgentBeliefCell] = field(default_factory=dict)


def _has_casualty_at(coord: Coordinate, casualties: dict[str, Casualty]) -> bool:
    return any(
        c.coord.x == coord.x and c.coord.y == coord.y and c.coord.z == coord.z
        for c in casualties.values()
    )


def _orientation_direction(orientation: Orientation) -> tuple[int, int, int]:
    if orientation is Orientation.NORTH:
        return (0, -1, 0)
    if orientation is Orientation.SOUTH:
        return (0, 1, 0)
    if orientation is Orientation.EAST:
        return (1, 0, 0)
    if orientation is Orientation.WEST:
        return (-1, 0, 0)
    return (0, 0, 0)


def _bearing_degrees(dx: int, dy: int) -> float:
    return degrees(atan2(dy, dx))


def _normalize_angle_degrees(angle: float) -> float:
    while angle <= -180.0:
        angle += 360.0
    while angle > 180.0:
        angle -= 360.0
    return angle


def _orientation_bearing_degrees(orientation: Orientation) -> float:
    dx, dy, _ = _orientation_direction(orientation)
    return _bearing_degrees(dx, dy)


def _line_points(origin: Coordinate, target: Coordinate) -> list[Coordinate]:
    dx = target.x - origin.x
    dy = target.y - origin.y
    dz = target.z - origin.z
    steps = max(abs(dx), abs(dy), abs(dz))
    if steps == 0:
        return []

    points: list[Coordinate] = []
    x, y, z = origin.x, origin.y, origin.z
    x_inc = 1 if dx > 0 else -1 if dx < 0 else 0
    y_inc = 1 if dy > 0 else -1 if dy < 0 else 0
    z_inc = 1 if dz > 0 else -1 if dz < 0 else 0
    x_length = abs(dx)
    m = abs(dy)
    n = abs(dz)
    dx2 = x_length * 2
    dy2 = m * 2
    dz2 = n * 2

    if x_length >= m and x_length >= n:
        err_y = dy2 - x_length
        err_z = dz2 - x_length
        for _ in range(x_length):
            x += x_inc
            if err_y > 0:
                y += y_inc
                err_y -= dx2
            if err_z > 0:
                z += z_inc
                err_z -= dx2
            err_y += dy2
            err_z += dz2
            points.append(Coordinate(x=x, y=y, z=z))
    elif m >= x_length and m >= n:
        err_x = dx2 - m
        err_z = dz2 - m
        for _ in range(m):
            y += y_inc
            if err_x > 0:
                x += x_inc
                err_x -= dy2
            if err_z > 0:
                z += z_inc
                err_z -= dy2
            err_x += dx2
            err_z += dz2
            points.append(Coordinate(x=x, y=y, z=z))
    else:
        err_x = dx2 - n
        err_y = dy2 - n
        for _ in range(n):
            z += z_inc
            if err_x > 0:
                x += x_inc
                err_x -= dz2
            if err_y > 0:
                y += y_inc
                err_y -= dz2
            err_x += dx2
            err_y += dy2
            points.append(Coordinate(x=x, y=y, z=z))

    return points


def raycast(
    grid: SpatialGrid,
    casualties: dict[str, Casualty],
    origin: Coordinate,
    direction: tuple[int, int, int],
    max_range: int,
    agent_class: AgentClass,
) -> list[RaySample]:
    """Cast a ray from `origin` in `direction`, returning samples up to `max_range`."""

    dx, dy, dz = direction
    samples: list[RaySample] = []

    current = origin
    for _ in range(max_range):
        current = Coordinate(current.x + dx, current.y + dy, current.z + dz)

        if not grid.is_in_bounds(current):
            break

        cell_status = grid.evaluate_cell_status(current, agent_class=agent_class.name)
        smoke = grid.get_smoke_density(current)
        has_casualty = _has_casualty_at(current, casualties)

        samples.append(
            RaySample(
                coord=current,
                cell_status=cell_status,
                smoke_density=smoke,
                has_casualty=has_casualty,
            )
        )

        if cell_status == CellStatus.IMPASSABLE:
            break

    return samples


def _observe_target(
    grid: SpatialGrid,
    casualties: dict[str, Casualty],
    origin: Coordinate,
    target: Coordinate,
    agent_class: AgentClass,
    smoke_obscures_at: float,
) -> ObservationSample:
    line = _line_points(origin, target)
    visible = True
    obscured_by_smoke = False

    for point in line:
        cell_status = grid.evaluate_cell_status(point, agent_class=agent_class.name)
        smoke = grid.get_smoke_density(point)

        if point == target:
            return ObservationSample(
                coord=target,
                is_visible=visible and not obscured_by_smoke,
                cell_status=cell_status if visible and not obscured_by_smoke else None,
                smoke_density=smoke if visible else None,
                has_casualty=(
                    _has_casualty_at(target, casualties)
                    if visible and not obscured_by_smoke
                    else None
                ),
                obscured_by_smoke=obscured_by_smoke,
            )

        if smoke >= smoke_obscures_at:
            return ObservationSample(
                coord=target,
                is_visible=False,
                cell_status=None,
                smoke_density=None,
                has_casualty=None,
                obscured_by_smoke=True,
            )

        if cell_status == CellStatus.IMPASSABLE:
            return ObservationSample(
                coord=target,
                is_visible=False,
                cell_status=None,
                smoke_density=None,
                has_casualty=None,
                obscured_by_smoke=False,
            )

    return ObservationSample(
        coord=target,
        is_visible=False,
        cell_status=None,
        smoke_density=None,
        has_casualty=None,
        obscured_by_smoke=False,
    )


def raycast_radial(
    grid: SpatialGrid,
    casualties: dict[str, Casualty],
    origin: Coordinate,
    radius: int,
    agent_class: AgentClass,
    smoke_obscures_at: float = 1.0,
) -> list[ObservationSample]:
    """Return visible/observed cells within a radius using LOS checks."""

    observations: list[ObservationSample] = []

    for x in range(origin.x - radius, origin.x + radius + 1):
        for y in range(origin.y - radius, origin.y + radius + 1):
            target = Coordinate(x=x, y=y, z=origin.z)
            if target == origin or not grid.is_in_bounds(target):
                continue
            if hypot(target.x - origin.x, target.y - origin.y) > radius:
                continue
            observations.append(
                _observe_target(
                    grid=grid,
                    casualties=casualties,
                    origin=origin,
                    target=target,
                    agent_class=agent_class,
                    smoke_obscures_at=smoke_obscures_at,
                )
            )

    observations.sort(
        key=lambda sample: (sample.coord.y, sample.coord.x, sample.coord.z)
    )
    return observations


def raycast_cone(
    grid: SpatialGrid,
    casualties: dict[str, Casualty],
    origin: Coordinate,
    orientation: Orientation,
    max_range: int,
    agent_class: AgentClass,
    angle_degrees: float = 90.0,
    smoke_obscures_at: float = 1.0,
) -> list[ObservationSample]:
    """Return visible/observed cells within a forward-facing cone."""

    facing = _orientation_bearing_degrees(orientation)
    observations: list[ObservationSample] = []

    for x in range(origin.x - max_range, origin.x + max_range + 1):
        for y in range(origin.y - max_range, origin.y + max_range + 1):
            target = Coordinate(x=x, y=y, z=origin.z)
            if target == origin or not grid.is_in_bounds(target):
                continue

            dx = target.x - origin.x
            dy = target.y - origin.y
            distance = hypot(dx, dy)
            if distance > max_range or distance == 0:
                continue

            bearing = _bearing_degrees(dx, dy)
            delta = abs(_normalize_angle_degrees(bearing - facing))
            if delta > angle_degrees / 2.0:
                continue

            observations.append(
                _observe_target(
                    grid=grid,
                    casualties=casualties,
                    origin=origin,
                    target=target,
                    agent_class=agent_class,
                    smoke_obscures_at=smoke_obscures_at,
                )
            )

    observations.sort(
        key=lambda sample: (sample.coord.y, sample.coord.x, sample.coord.z)
    )
    return observations


@dataclass
class AgentView:
    """Per-agent perception summary."""

    agent_id: str
    origin: Coordinate
    orientation: str
    ray_samples: list[RaySample]
    cone_samples: list[ObservationSample] = field(default_factory=list)
    radial_samples: list[ObservationSample] = field(default_factory=list)


def get_agent_view(
    grid: SpatialGrid,
    casualties: dict[str, Casualty],
    agent: Agent,
    max_range: int,
    cone_angle_degrees: float = 90.0,
    radial_range: int | None = None,
    smoke_obscures_at: float = 1.0,
) -> AgentView:
    """Return a perception summary for the agent."""

    direction = _orientation_direction(agent.orientation)

    samples = raycast(
        grid=grid,
        casualties=casualties,
        origin=agent.coord,
        direction=direction,
        max_range=max_range,
        agent_class=agent.agent_class,
    )
    cone_samples = raycast_cone(
        grid=grid,
        casualties=casualties,
        origin=agent.coord,
        orientation=agent.orientation,
        max_range=max_range,
        agent_class=agent.agent_class,
        angle_degrees=cone_angle_degrees,
        smoke_obscures_at=smoke_obscures_at,
    )
    radial_samples = raycast_radial(
        grid=grid,
        casualties=casualties,
        origin=agent.coord,
        radius=radial_range if radial_range is not None else max_range,
        agent_class=agent.agent_class,
        smoke_obscures_at=smoke_obscures_at,
    )

    return AgentView(
        agent_id=agent.id,
        origin=agent.coord,
        orientation=agent.orientation.name,
        ray_samples=samples,
        cone_samples=cone_samples,
        radial_samples=radial_samples,
    )


def update_belief_state(
    belief_state: AgentBeliefState,
    observations: list[ObservationSample],
    tick: int,
) -> AgentBeliefState:
    """Merge new observations into an agent-local belief map."""

    observed_keys = {
        (observation.coord.x, observation.coord.y, observation.coord.z)
        for observation in observations
    }

    for key, cell in belief_state.cells.items():
        if key not in observed_keys:
            cell.currently_visible = False
            cell.obscured_by_smoke = False

    for observation in observations:
        key = (observation.coord.x, observation.coord.y, observation.coord.z)
        existing = belief_state.cells.get(key)

        if observation.is_visible:
            belief_state.cells[key] = AgentBeliefCell(
                coord=observation.coord,
                last_update_tick=tick,
                last_seen_tick=tick,
                ever_observed=True,
                currently_visible=True,
                last_known_cell_status=observation.cell_status,
                last_known_smoke_density=observation.smoke_density,
                last_known_has_casualty=observation.has_casualty,
                obscured_by_smoke=observation.obscured_by_smoke,
            )
            continue

        belief_state.cells[key] = AgentBeliefCell(
            coord=observation.coord,
            last_update_tick=tick,
            last_seen_tick=(
                existing.last_seen_tick if existing is not None else None
            ),
            ever_observed=True,
            currently_visible=False,
            last_known_cell_status=(
                existing.last_known_cell_status if existing is not None else None
            ),
            last_known_smoke_density=(
                existing.last_known_smoke_density if existing is not None else None
            ),
            last_known_has_casualty=(
                existing.last_known_has_casualty if existing is not None else None
            ),
            obscured_by_smoke=observation.obscured_by_smoke,
        )
    return belief_state
