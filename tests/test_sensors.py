from __future__ import annotations

from src.core.entities import (
    Agent,
    AgentClass,
    Casualty,
    Coordinate,
    LivingState,
    Orientation,
    TriageState,
)
from src.core.grid import CellStatus, SpatialGrid
from src.core.sensors import (
    AgentBeliefState,
    AgentView,
    ObservationSample,
    RaySample,
    get_agent_view,
    raycast,
    raycast_cone,
    raycast_radial,
    update_belief_state,
)


def _make_grid() -> SpatialGrid:
    # Small 2D grid with one z-level for simplicity here.
    return SpatialGrid(N=5, Z=1)


def test_raycast_stops_at_impassable_wall() -> None:
    grid = _make_grid()

    # Place an IMPASSABLE wall at x=2, y=2, z=0.
    wall_coord = Coordinate(x=2, y=2, z=0)
    grid.set_cell_status(wall_coord, CellStatus.IMPASSABLE)

    # No casualties.
    casualties: dict[str, Casualty] = {}

    origin = Coordinate(x=0, y=2, z=0)
    direction = (1, 0, 0)  # EAST
    samples = raycast(
        grid=grid,
        casualties=casualties,
        origin=origin,
        direction=direction,
        max_range=10,
        agent_class=AgentClass.UGV,
    )

    # We should see cells at x=1,y=2 and x=2,y=2; then stop due to IMPASSABLE.
    assert len(samples) == 2
    assert samples[0].coord == Coordinate(x=1, y=2, z=0)
    assert samples[0].cell_status == CellStatus.UNOCCUPIED
    assert samples[1].coord == wall_coord
    assert samples[1].cell_status == CellStatus.IMPASSABLE


def test_raycast_detects_casualty_and_smoke() -> None:
    grid = _make_grid()

    # Set some smoke along the ray.
    grid.set_smoke_density(Coordinate(x=1, y=2, z=0), 0.2)
    grid.set_smoke_density(Coordinate(x=2, y=2, z=0), 0.5)

    # Casualty at (2,2,0).
    casualty = Casualty(
        id="C1",
        coord=Coordinate(x=2, y=2, z=0),
        health=50.0,
        decay_rate=1.0,
        is_covered=False,
        triage_state=TriageState.UNKNOWN,
        transport_status="ON_GROUND",
        living_state=LivingState.ALIVE,
    )
    casualties = {casualty.id: casualty}

    origin = Coordinate(x=0, y=2, z=0)
    direction = (1, 0, 0)  # EAST

    samples = raycast(
        grid=grid,
        casualties=casualties,
        origin=origin,
        direction=direction,
        max_range=5,
        agent_class=AgentClass.UGV,
    )

    # We should hit coords (1,2,0), (2,2,0), (3,2,0), (4,2,0).
    assert [s.coord.x for s in samples] == [1, 2, 3, 4]

    s1 = samples[0]
    s2 = samples[1]

    assert s1.coord == Coordinate(x=1, y=2, z=0)
    assert abs(s1.smoke_density - 0.2) < 1e-6
    assert not s1.has_casualty

    assert s2.coord == Coordinate(x=2, y=2, z=0)
    assert abs(s2.smoke_density - 0.5) < 1e-6
    assert s2.has_casualty    


def test_get_agent_view_uses_agent_orientation() -> None:
    grid = _make_grid()

    # Put IMPASSABLE at NORTH of agent, PASSABLE at EAST, nothing else.
    north_block = Coordinate(x=2, y=1, z=0)
    east_block = Coordinate(x=3, y=2, z=0)
    grid.set_cell_status(north_block, CellStatus.IMPASSABLE)
    grid.set_cell_status(east_block, CellStatus.PASSABLE)

    casualties: dict[str, Casualty] = {}

    # Agent at (2,2,0), facing NORTH.
    agent = Agent(
        id="A_VIEW",
        coord=Coordinate(x=2, y=2, z=0),
        orientation=Orientation.NORTH,
        agent_class=AgentClass.UGV,
    )

    view = get_agent_view(grid, casualties, agent, max_range=5)
    assert isinstance(view, AgentView)
    assert view.agent_id == agent.id
    assert view.origin == agent.coord
    assert view.orientation == "NORTH"

    # Ray should go NORTH: (2,1,0), (2,0,0) but stop at IMPASSABLE at (2,1,0).
    assert len(view.ray_samples) == 1
    sample0 = view.ray_samples[0]
    assert isinstance(sample0, RaySample)
    assert sample0.coord == north_block
    assert sample0.cell_status is CellStatus.IMPASSABLE

    # Now face EAST and confirm ray goes east instead.
    agent.orientation = Orientation.EAST
    view_east = get_agent_view(grid, casualties, agent, max_range=5)

    # East from (2,2,0): (3,2,0), (4,2,0) - PASSABLE then UNOCCUPIED.
    assert [s.coord for s in view_east.ray_samples] == [
        Coordinate(x=3, y=2, z=0),
        Coordinate(x=4, y=2, z=0),
    ]
    assert view_east.ray_samples[0].cell_status is CellStatus.PASSABLE


def test_raycast_radial_marks_cells_behind_wall_as_not_visible() -> None:
    grid = _make_grid()
    wall = Coordinate(x=2, y=2, z=0)
    hidden = Coordinate(x=3, y=2, z=0)
    grid.set_cell_status(wall, CellStatus.IMPASSABLE)

    observations = raycast_radial(
        grid=grid,
        casualties={},
        origin=Coordinate(x=1, y=2, z=0),
        radius=3,
        agent_class=AgentClass.UGV,
    )

    by_coord = {sample.coord: sample for sample in observations}
    assert isinstance(by_coord[wall], ObservationSample)
    assert by_coord[wall].is_visible
    assert by_coord[wall].cell_status is CellStatus.IMPASSABLE
    assert not by_coord[hidden].is_visible
    assert by_coord[hidden].cell_status is None


def test_raycast_cone_limits_observations_to_facing_direction() -> None:
    grid = _make_grid()
    casualties: dict[str, Casualty] = {}

    observations = raycast_cone(
        grid=grid,
        casualties=casualties,
        origin=Coordinate(x=2, y=2, z=0),
        orientation=Orientation.EAST,
        max_range=2,
        agent_class=AgentClass.UGV,
        angle_degrees=90.0,
    )

    coords = {sample.coord for sample in observations}
    assert Coordinate(x=3, y=2, z=0) in coords
    assert Coordinate(x=4, y=2, z=0) in coords
    assert Coordinate(x=1, y=2, z=0) not in coords
    assert Coordinate(x=2, y=1, z=0) not in coords


def test_raycast_cone_marks_cells_behind_dense_smoke_unknown() -> None:
    grid = _make_grid()
    smoke_coord = Coordinate(x=2, y=2, z=0)
    hidden = Coordinate(x=3, y=2, z=0)
    grid.set_smoke_density(smoke_coord, 1.0)

    observations = raycast_cone(
        grid=grid,
        casualties={},
        origin=Coordinate(x=1, y=2, z=0),
        orientation=Orientation.EAST,
        max_range=3,
        agent_class=AgentClass.UGV,
        angle_degrees=60.0,
        smoke_obscures_at=1.0,
    )

    by_coord = {sample.coord: sample for sample in observations}
    assert by_coord[smoke_coord].is_visible
    assert by_coord[smoke_coord].smoke_density == 1.0
    assert not by_coord[hidden].is_visible
    assert by_coord[hidden].cell_status is None
    assert by_coord[hidden].obscured_by_smoke


def test_line_of_sight_diagonal_blocking_uses_consistent_grid_traversal() -> None:
    grid = _make_grid()
    blocker = Coordinate(x=2, y=2, z=0)
    hidden = Coordinate(x=3, y=3, z=0)
    grid.set_cell_status(blocker, CellStatus.IMPASSABLE)

    observations = raycast_radial(
        grid=grid,
        casualties={},
        origin=Coordinate(x=1, y=1, z=0),
        radius=4,
        agent_class=AgentClass.UGV,
    )

    by_coord = {sample.coord: sample for sample in observations}
    assert by_coord[blocker].is_visible
    assert by_coord[blocker].cell_status is CellStatus.IMPASSABLE
    assert not by_coord[hidden].is_visible


def test_get_agent_view_includes_cone_and_radial_samples() -> None:
    grid = _make_grid()
    agent = Agent(
        id="A_VIEW2",
        coord=Coordinate(x=2, y=2, z=0),
        orientation=Orientation.EAST,
        agent_class=AgentClass.UGV,
    )

    view = get_agent_view(grid, {}, agent, max_range=2)
    assert isinstance(view, AgentView)
    assert len(view.cone_samples) > 0
    assert len(view.radial_samples) > 0


def test_belief_state_accumulates_latest_observations() -> None:
    belief = AgentBeliefState(agent_id="A1")
    coord = Coordinate(x=2, y=2, z=0)

    update_belief_state(
        belief_state=belief,
        observations=[
            ObservationSample(
                coord=coord,
                is_visible=True,
                cell_status=CellStatus.UNOCCUPIED,
                smoke_density=0.2,
                has_casualty=False,
            )
        ],
        tick=3,
    )
    update_belief_state(
        belief_state=belief,
        observations=[
            ObservationSample(
                coord=coord,
                is_visible=False,
                cell_status=None,
                smoke_density=None,
                has_casualty=None,
                obscured_by_smoke=True,
            )
        ],
        tick=4,
    )

    stored = belief.cells[(2, 2, 0)]
    assert stored.last_update_tick == 4
    assert stored.last_seen_tick == 3
    assert stored.ever_observed
    assert not stored.currently_visible
    assert stored.last_known_cell_status is CellStatus.UNOCCUPIED
    assert stored.last_known_smoke_density == 0.2
    assert stored.last_known_has_casualty is False
    assert stored.obscured_by_smoke


def test_belief_state_marks_unobserved_cells_not_currently_visible() -> None:
    belief = AgentBeliefState(agent_id="A1")
    coord1 = Coordinate(x=2, y=2, z=0)
    coord2 = Coordinate(x=3, y=2, z=0)

    update_belief_state(
        belief_state=belief,
        observations=[
            ObservationSample(
                coord=coord1,
                is_visible=True,
                cell_status=CellStatus.UNOCCUPIED,
                smoke_density=0.0,
                has_casualty=False,
            ),
            ObservationSample(
                coord=coord2,
                is_visible=True,
                cell_status=CellStatus.PASSABLE,
                smoke_density=0.1,
                has_casualty=True,
            ),
        ],
        tick=1,
    )

    update_belief_state(
        belief_state=belief,
        observations=[
            ObservationSample(
                coord=coord1,
                is_visible=True,
                cell_status=CellStatus.UNOCCUPIED,
                smoke_density=0.0,
                has_casualty=False,
            )
        ],
        tick=2,
    )

    stored1 = belief.cells[(2, 2, 0)]
    stored2 = belief.cells[(3, 2, 0)]
    assert stored1.currently_visible
    assert stored1.last_seen_tick == 2
    assert not stored2.currently_visible
    assert stored2.last_update_tick == 1
    assert stored2.last_seen_tick == 1
    assert stored2.last_known_cell_status is CellStatus.PASSABLE
    assert stored2.last_known_has_casualty is True