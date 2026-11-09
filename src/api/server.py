from __future__ import annotations

from typing import Dict

import asyncio
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from src.api.scenarios import seed_dev_scenario
from src.api.serializers import (
    agent_state_from_engine,
    building_state_from_engine,
    casualty_state_from_engine,
    event_to_model,
    grid_cells_from_engine,
    telemetry_frame_from_engine,
    zones_from_engine,
    temporal_constraint_from_engine,
)
from src.api.state import (
    get_engine,
    load_engine_from_scenario_definition,
    load_engine_from_scenario_file,
    reset_engine,
)
from src.core.actions import EngineAction, EngineActionType
from src.core.grid import Coordinate
from .models import (
    ApiEngineActionType,
    BuildingCellStateModel,
    BuildingStateModel,
    CasualtyStateModel,
    EventModel,
    QueueActionsRequest,
    StateSnapshotModel,
    StepRequest,
    AgentStateModel,
    TelemetryFrameModel,
    LoadScenarioFromPathRequest,
    LoadScenarioRequest,
)


app = FastAPI(title="SARSim API")

# Optional: CORS for a web UI.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


_API_TO_ENGINE_ACTION_TYPE = {
    ApiEngineActionType.MOVE_FORWARD: EngineActionType.MOVE_FORWARD,
    ApiEngineActionType.TRIAGE: EngineActionType.TRIAGE,
    ApiEngineActionType.CLEAR_DEBRIS: EngineActionType.CLEAR_DEBRIS,
    ApiEngineActionType.RETRIEVE_BODY: EngineActionType.RETRIEVE_BODY,
    ApiEngineActionType.LOAD_CASUALTY: EngineActionType.LOAD_CASUALTY,
    ApiEngineActionType.UNLOAD_CASUALTY: EngineActionType.UNLOAD_CASUALTY,
    ApiEngineActionType.TRANSFER_CASUALTY: EngineActionType.TRANSFER_CASUALTY,
    ApiEngineActionType.BREACH_ENTRYWAY: EngineActionType.BREACH_ENTRYWAY,
    ApiEngineActionType.ASCEND: EngineActionType.ASCEND,
    ApiEngineActionType.DESCEND: EngineActionType.DESCEND,
    ApiEngineActionType.TURN_LEFT: EngineActionType.TURN_LEFT,
    ApiEngineActionType.TURN_RIGHT: EngineActionType.TURN_RIGHT,
}

@app.get("/state", response_model=StateSnapshotModel)
def get_state() -> StateSnapshotModel:
    engine = get_engine()
    return StateSnapshotModel(
        tick=engine.current_tick,
        temporal_constraint=temporal_constraint_from_engine(engine),
        ended=engine.ended,
        success=engine.success,
        grid_size=engine.grid.N,
        z_levels=engine.grid.Z,
        agents=agent_state_from_engine(engine),
        casualties=casualty_state_from_engine(engine),
        buildings=building_state_from_engine(engine),
        zones=zones_from_engine(engine),
        grid_cells=grid_cells_from_engine(engine),
        events=[event_to_model(event) for event in engine.events[-200:]],
    )

@app.post("/step", response_model=StateSnapshotModel)
def step(req: StepRequest) -> StateSnapshotModel:
    engine = get_engine()
    for _ in range(req.ticks):
        if engine.ended:
            break
        engine.tick()
    return get_state()

@app.post("/actions")
def queue_actions(req: QueueActionsRequest) -> Dict[str, str]:
    engine = get_engine()
    if engine.ended:
        raise HTTPException(status_code=409, detail="Scenario has ended")
    for a in req.actions:
        engine_action = EngineAction(
            action_id=a.action_id,
            actor_id=a.actor_id,
            action_type=_API_TO_ENGINE_ACTION_TYPE[a.action_type],
            start_tick=a.start_tick,
            duration=a.duration,
            target_casualty_id=a.target_casualty_id,
            target_coord=Coordinate(
                x=a.target_coord.x,
                y=a.target_coord.y,
                z=a.target_coord.z,
            )
            if a.target_coord is not None
            else None,
        )
        engine.queue_action(engine_action)

    return {"status": "ok"}

@app.websocket("/events/stream")
async def events_stream(ws: WebSocket) -> None:
    engine = get_engine()
    await ws.accept()
    last_index = len(engine.events)
    try:
        while True:
            # Send any new events
            if len(engine.events) > last_index:
                new_events = engine.events[last_index:]
                for e in new_events:
                    await ws.send_json(event_to_model(e).model_dump())
                last_index = len(engine.events)
            # Small sleep to avoid busy-loop; for real-time you might sync with ticks.
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        return
    
@app.post("/init/dev")
def init_dev() -> Dict[str, str]:
    seed_dev_scenario(get_engine())
    return {"status": "ok"}


@app.post("/scenario/load")
def load_scenario(req: LoadScenarioRequest) -> Dict[str, str]:
    load_engine_from_scenario_definition(req.scenario)
    return {"status": "ok"}


@app.post("/scenario/load-from-path")
def load_scenario_from_path(req: LoadScenarioFromPathRequest) -> Dict[str, str]:
    load_engine_from_scenario_file(req.filepath)
    return {"status": "ok"}

@app.get("/telemetry", response_model=list[TelemetryFrameModel])
def get_telemetry() -> list[TelemetryFrameModel]:
    engine = get_engine()
    return [
        telemetry_frame_from_engine(engine, agent_id)
        for agent_id in engine.agents.keys()
    ]


@app.post("/reset")
def reset() -> Dict[str, str]:
    """Reset the simulation and clear all state and events."""
    reset_engine()
    return {"status": "ok"}
