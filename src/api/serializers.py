from __future__ import annotations

from typing import Dict

from src.api.models import (
    AgentBeliefModel,
    AgentObservationModel,
    AgentStateModel,
    BeliefCellModel,
    BuildingCellStateModel,
    BuildingStateModel,
    CasualtyStateModel,
    EventModel,
    GridCellStateModel,
    ObservationSampleModel,
    TelemetryFrameModel,
    TemporalConstraintStateModel,
    ZoneCellModel,
    ZoneStateModel,
)
from src.core.engine import SimulationEngine
from src.core.events import Event
from src.core.sensors import get_agent_view
from src.core.types import CellStatus


def _observation_sample_to_model(sample: object) -> ObservationSampleModel:
    return ObservationSampleModel(
        x=sample.coord.x,
        y=sample.coord.y,
        z=sample.coord.z,
        is_visible=sample.is_visible,
        cell_status=sample.cell_status.name if sample.cell_status is not None else None,
        smoke_density=sample.smoke_density,
        has_casualty=sample.has_casualty,
        obscured_by_smoke=sample.obscured_by_smoke,
    )


def _belief_model_from_engine(engine: SimulationEngine, agent_id: str) -> AgentBeliefModel:
    belief_state = engine.agent_beliefs.get(agent_id)
    belief_cells = []
    if belief_state is not None:
        belief_cells = [
            BeliefCellModel(
                x=cell.coord.x,
                y=cell.coord.y,
                z=cell.coord.z,
                last_update_tick=cell.last_update_tick,
                last_seen_tick=cell.last_seen_tick,
                ever_observed=cell.ever_observed,
                currently_visible=cell.currently_visible,
                last_known_cell_status=(
                    cell.last_known_cell_status.name
                    if cell.last_known_cell_status is not None
                    else None
                ),
                last_known_smoke_density=cell.last_known_smoke_density,
                last_known_has_casualty=cell.last_known_has_casualty,
                obscured_by_smoke=cell.obscured_by_smoke,
            )
            for cell in belief_state.cells.values()
        ]
        belief_cells.sort(key=lambda cell: (cell.y, cell.x, cell.z))
    return AgentBeliefModel(cells=belief_cells)


def telemetry_frame_from_engine(engine: SimulationEngine, agent_id: str) -> TelemetryFrameModel:
    agent = engine.agents[agent_id]
    view = get_agent_view(
        grid=engine.grid,
        casualties=engine.casualties,
        agent=agent,
        max_range=4,
    )
    return TelemetryFrameModel(
        tick=engine.current_tick,
        agent_id=agent_id,
        observation=AgentObservationModel(
            cone_samples=[_observation_sample_to_model(sample) for sample in view.cone_samples],
            radial_samples=[_observation_sample_to_model(sample) for sample in view.radial_samples],
        ),
        belief=_belief_model_from_engine(engine, agent_id),
    )


def agent_state_from_engine(engine: SimulationEngine) -> Dict[str, AgentStateModel]:
    result: Dict[str, AgentStateModel] = {}
    for aid, agent in engine.agents.items():
        frame = telemetry_frame_from_engine(engine, aid)
        result[aid] = AgentStateModel(
            id=agent.id,
            x=agent.coord.x,
            y=agent.coord.y,
            z=agent.coord.z,
            orientation=agent.orientation.name,
            agent_class=agent.agent_class.name,
            busy_ticks_remaining=agent.busy_ticks_remaining,
            damage_status=agent.damage_status.value if agent.damage_status is not None else None,
            payload_casualty_id=agent.payload.id if agent.payload is not None else None,
            observation=frame.observation,
            belief=frame.belief,
        )
    return result


def casualty_state_from_engine(engine: SimulationEngine) -> Dict[str, CasualtyStateModel]:
    result: Dict[str, CasualtyStateModel] = {}
    for cid, casualty in engine.casualties.items():
        transport_status = (
            casualty.transport_status.value
            if hasattr(casualty.transport_status, "value")
            else casualty.transport_status
        )
        result[cid] = CasualtyStateModel(
            id=casualty.id,
            x=casualty.coord.x,
            y=casualty.coord.y,
            z=casualty.coord.z,
            health=casualty.health,
            decay_rate=casualty.decay_rate,
            is_covered=casualty.is_covered,
            triage_state=casualty.triage_state.name,
            living_state=casualty.living_state.name,
            transport_status=transport_status,
        )
    return result


def building_state_from_engine(engine: SimulationEngine) -> Dict[str, BuildingStateModel]:
    result: Dict[str, BuildingStateModel] = {}
    for bid, building in engine.buildings.items():
        cells = [
            BuildingCellStateModel(
                x=cell.coord.x,
                y=cell.coord.y,
                z=cell.coord.z,
                integrity=cell.integrity,
                collapsed=cell.collapsed,
            )
            for cell in building.cells.values()
        ]
        result[bid] = BuildingStateModel(id=bid, cells=cells)
    return result


def zones_from_engine(engine: SimulationEngine) -> list[ZoneStateModel]:
    zones = getattr(engine, "zones", [])
    hospital_casualty_ids_by_zone = getattr(engine, "hospital_casualty_ids_by_zone", {})
    result: list[ZoneStateModel] = []
    for zone in zones:
        zone_id = str(zone.get("id", ""))
        casualty_ids_under_care = list(hospital_casualty_ids_by_zone.get(zone_id, []))
        result.append(
            ZoneStateModel(
                id=zone_id,
                zone_type=str(zone.get("zone_type", "")),
                cells=[
                    ZoneCellModel(x=int(cell["x"]), y=int(cell["y"]), z=int(cell["z"]))
                    for cell in zone.get("cells", [])
                ],
                labels=[str(label) for label in zone.get("labels", [])],
                casualty_count_under_care=len(casualty_ids_under_care),
                casualty_ids_under_care=casualty_ids_under_care,
            )
        )
    return result


def temporal_constraint_from_engine(engine: SimulationEngine) -> TemporalConstraintStateModel | None:
    constraint = engine.temporal_constraint
    if constraint is None:
        return None
    deadline = int(constraint["deadline_cycles"])
    return TemporalConstraintStateModel(
        type=str(constraint["type"]),
        target_count=int(constraint["target_count"]),
        deadline_cycles=deadline,
        rescued_count=engine.rescued_count,
        cycles_remaining=max(0, deadline - engine.current_tick),
    )


def grid_cells_from_engine(engine: SimulationEngine) -> list[GridCellStateModel]:
    cells: list[GridCellStateModel] = []
    for x in range(engine.grid.N):
        for y in range(engine.grid.N):
            for z in range(engine.grid.Z):
                status = CellStatus(int(engine.grid.status_grid[x, y, z])).name
                smoke_density = float(engine.grid.smoke_grid[x, y, z])
                if status == CellStatus.UNOCCUPIED.name and smoke_density == 0.0:
                    continue
                cells.append(
                    GridCellStateModel(
                        x=x,
                        y=y,
                        z=z,
                        status=status,
                        smoke_density=smoke_density,
                    )
                )
    return cells


def event_to_model(event: Event) -> EventModel:
    return EventModel(
        tick=event.tick,
        event_type=event.event_type.name,
        message=event.message,
        actor_id=event.actor_id,
        payload=event.payload,
    )
