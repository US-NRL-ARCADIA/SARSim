from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, model_validator

from src.utils.serializer import ScenarioDefinition


class ApiEngineActionType(str, Enum):
    MOVE_FORWARD = "MOVE_FORWARD"
    TRIAGE = "TRIAGE"
    CLEAR_DEBRIS = "CLEAR_DEBRIS"
    RETRIEVE_BODY = "RETRIEVE_BODY"
    LOAD_CASUALTY = "LOAD_CASUALTY"
    UNLOAD_CASUALTY = "UNLOAD_CASUALTY"
    TRANSFER_CASUALTY = "TRANSFER_CASUALTY"
    BREACH_ENTRYWAY = "BREACH_ENTRYWAY"
    ASCEND = "ASCEND"
    DESCEND = "DESCEND"
    TURN_LEFT = "TURN_LEFT"
    TURN_RIGHT = "TURN_RIGHT"


class CoordinateModel(BaseModel):
    x: int
    y: int
    z: int


class QueueActionRequest(BaseModel):
    action_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    action_type: ApiEngineActionType
    start_tick: int = Field(default=0, ge=0)
    duration: int = Field(default=0, ge=0)
    target_casualty_id: Optional[str] = Field(default=None, min_length=1)
    target_coord: Optional[CoordinateModel] = None

    @model_validator(mode="after")
    def validate_targets(self) -> "QueueActionRequest":
        casualty_actions = {
            ApiEngineActionType.TRIAGE,
            ApiEngineActionType.RETRIEVE_BODY,
            ApiEngineActionType.LOAD_CASUALTY,
        }
        coord_actions = {
            ApiEngineActionType.CLEAR_DEBRIS,
            ApiEngineActionType.BREACH_ENTRYWAY,
        }

        if self.action_type in casualty_actions:
            if self.target_casualty_id is None:
                raise ValueError("target_casualty_id is required for this action type")
            if self.target_coord is not None:
                raise ValueError("target_coord must not be provided for this action type")

        if self.action_type in coord_actions:
            if self.target_coord is None:
                raise ValueError("target_coord is required for this action type")
            if self.target_casualty_id is not None:
                raise ValueError("target_casualty_id must not be provided for this action type")

        return self


class QueueActionsRequest(BaseModel):
    actions: List[QueueActionRequest] = Field(min_length=1)


class StepRequest(BaseModel):
    ticks: int = Field(default=1, ge=1)


class ObservationSampleModel(BaseModel):
    x: int
    y: int
    z: int
    is_visible: bool
    cell_status: Optional[str] = None
    smoke_density: Optional[float] = None
    has_casualty: Optional[bool] = None
    obscured_by_smoke: bool = False


class BeliefCellModel(BaseModel):
    x: int
    y: int
    z: int
    last_update_tick: int
    last_seen_tick: Optional[int] = None
    ever_observed: bool
    currently_visible: bool
    last_known_cell_status: Optional[str] = None
    last_known_smoke_density: Optional[float] = None
    last_known_has_casualty: Optional[bool] = None
    obscured_by_smoke: bool = False


class AgentObservationModel(BaseModel):
    cone_samples: List[ObservationSampleModel]
    radial_samples: List[ObservationSampleModel]


class AgentBeliefModel(BaseModel):
    cells: List[BeliefCellModel]


class AgentStateModel(BaseModel):
    id: str
    x: int
    y: int
    z: int
    orientation: str
    agent_class: str
    busy_ticks_remaining: int
    damage_status: Optional[str] = None
    payload_casualty_id: Optional[str] = None
    observation: Optional[AgentObservationModel] = None
    belief: Optional[AgentBeliefModel] = None


class CasualtyStateModel(BaseModel):
    id: str
    x: int
    y: int
    z: int
    health: float
    decay_rate: float
    is_covered: bool
    triage_state: str
    living_state: str
    transport_status: str


class BuildingCellStateModel(BaseModel):
    x: int
    y: int
    z: int
    integrity: float
    collapsed: bool


class BuildingStateModel(BaseModel):
    id: str
    cells: List[BuildingCellStateModel]


class GridCellStateModel(BaseModel):
    x: int
    y: int
    z: int
    status: str
    smoke_density: float


class TelemetryFrameModel(BaseModel):
    tick: int
    agent_id: str
    observation: AgentObservationModel
    belief: AgentBeliefModel


class ZoneCellModel(BaseModel):
    x: int
    y: int
    z: int


class ZoneStateModel(BaseModel):
    id: str
    zone_type: str
    cells: List[ZoneCellModel]
    labels: List[str] = Field(default_factory=list)
    casualty_count_under_care: int = 0
    casualty_ids_under_care: List[str] = Field(default_factory=list)


class StateSnapshotModel(BaseModel):
    tick: int
    temporal_constraint: Optional["TemporalConstraintStateModel"] = None
    ended: bool = False
    success: Optional[bool] = None
    grid_size: int
    z_levels: int
    agents: Dict[str, AgentStateModel]
    casualties: Dict[str, CasualtyStateModel]
    buildings: Dict[str, BuildingStateModel]
    zones: List[ZoneStateModel] = Field(default_factory=list)
    grid_cells: List[GridCellStateModel] = Field(default_factory=list)
    events: List["EventModel"] = Field(default_factory=list)


class TemporalConstraintStateModel(BaseModel):
    type: str
    target_count: int
    deadline_cycles: int
    rescued_count: int
    cycles_remaining: int


class EventModel(BaseModel):
    tick: int
    event_type: str
    message: str
    actor_id: Optional[str] = None
    payload: Optional[Dict[str, object]] = None


class LoadScenarioFromPathRequest(BaseModel):
    filepath: str = Field(min_length=1)


class LoadScenarioRequest(BaseModel):
    scenario: ScenarioDefinition
