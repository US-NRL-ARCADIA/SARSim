from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.api.scenarios import seed_dev_scenario
from src.api.serializers import (
    agent_state_from_engine,
    building_state_from_engine,
    casualty_state_from_engine,
    event_to_model,
    grid_cells_from_engine,
    sensor_state_from_engine,
    telemetry_frame_from_engine,
    temporal_constraint_from_engine,
    zones_from_engine,
)
from src.api.state import (
    get_engine,
    load_engine_from_scenario_file,
    reset_active_scenario,
    reset_engine,
    set_active_scenario,
)
from src.core.actions import EngineAction, EngineActionType
from src.core.engine import SimulationEngine
from src.core.grid import Coordinate, SpatialGrid
from src.utils.generator import generate_scenario
from src.utils.serializer import (
    ScenarioDefinition,
    build_engine_from_scenario_definition,
    serialize_scenario_definition,
)

from .models import (
    ApiEngineActionType,
    GenerateScenarioRequest,
    LoadScenarioFromPathRequest,
    LoadScenarioRequest,
    QueueActionsRequest,
    StateSnapshotModel,
    StepRequest,
    TelemetryFrameModel,
)

app = FastAPI(title="SARSim API")
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_ROOT.parent
UI_DIR = PACKAGE_ROOT / "ui"
SCENARIO_DIR = PROJECT_ROOT / "editor"


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


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}


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
        perception=sensor_state_from_engine(engine),
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
def queue_actions(req: QueueActionsRequest) -> dict[str, str]:
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
def init_dev() -> dict[str, str]:
    engine = SimulationEngine(grid=SpatialGrid(N=10, Z=3))
    seed_dev_scenario(engine)
    scenario = serialize_scenario_definition(
        engine,
        metadata={"scenario_id": "dev", "name": "Development scenario"},
        zones=engine.zones,
        scheduled_events=engine.scheduled_events,
        objectives={"temporal_constraint": dict(engine.temporal_constraint or {})},
    )
    set_active_scenario(engine, scenario)
    return {"status": "ok"}


@app.get("/scenarios")
def list_scenarios() -> list[dict[str, str]]:
    """List bundled scenario definitions available to the browser workspace."""
    scenarios: list[dict[str, str]] = []
    for path in sorted(SCENARIO_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict) or not isinstance(payload.get("grid"), dict):
            continue
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        raw_name = metadata.get("name")
        raw_description = metadata.get("description")
        scenarios.append(
            {
                "name": str(raw_name) if raw_name else path.stem.replace("_", " ").title(),
                "path": f"editor/{path.name}",
                "description": str(raw_description) if raw_description else "",
            }
        )
    return scenarios


@app.post("/scenario/generate")
def generate_authored_scenario(req: GenerateScenarioRequest) -> ScenarioDefinition:
    """Generate the same deterministic research scenario used by the former editor."""
    return generate_scenario(
        grid_size=req.grid_size,
        z_depth=req.z_depth,
        building_density=0.08,
        hazard_density=0.04,
        casualty_density=0.06,
        debris_density=0.05,
        seed=req.seed,
        agent_count=req.agent_count,
    )


@app.post("/scenario/load")
def load_scenario(req: LoadScenarioRequest) -> dict[str, str]:
    candidate = _build_scenario(req.scenario)
    set_active_scenario(candidate, req.scenario)
    return {"status": "ok"}


@app.post("/scenario/validate")
def validate_scenario(req: LoadScenarioRequest) -> dict[str, int | str]:
    """Validate an authored scenario without changing the active simulation."""
    candidate = _build_scenario(req.scenario)
    return {
        "status": "ok",
        "agents": len(candidate.agents),
        "casualties": len(candidate.casualties),
        "buildings": len(candidate.buildings),
        "zones": len(candidate.zones),
    }


@app.get("/scenario/current")
def current_scenario() -> dict[str, object]:
    """Export the active simulation as an editable scenario definition."""
    engine = get_engine()
    objectives: dict[str, object] = {}
    if engine.temporal_constraint is not None:
        objectives["temporal_constraint"] = dict(engine.temporal_constraint)
    return serialize_scenario_definition(
        engine,
        metadata={"name": "Active SARSim scenario"},
        zones=engine.zones,
        scheduled_events=engine.scheduled_events,
        objectives=objectives,
    )


@app.post("/scenario/load-from-path")
def load_scenario_from_path(req: LoadScenarioFromPathRequest) -> dict[str, str]:
    try:
        load_engine_from_scenario_file(req.filepath)
    except (IndexError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid scenario: {exc}") from exc
    return {"status": "ok"}


@app.post("/scenario/reset")
def reset_scenario() -> dict[str, str]:
    """Restore the active scenario to the exact state in which it was loaded."""
    try:
        reset_active_scenario()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "ok"}


def _build_scenario(scenario: ScenarioDefinition) -> SimulationEngine:
    try:
        return build_engine_from_scenario_definition(scenario)
    except (IndexError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid scenario: {exc}") from exc


@app.get("/telemetry", response_model=list[TelemetryFrameModel])
def get_telemetry() -> list[TelemetryFrameModel]:
    engine = get_engine()
    return [
        telemetry_frame_from_engine(engine, agent_id)
        for agent_id in engine.agents
    ]


@app.post("/reset")
def reset() -> dict[str, str]:
    """Reset the simulation and clear all state and events."""
    reset_engine()
    return {"status": "ok"}


@app.get("/", response_class=FileResponse, include_in_schema=False)
def root() -> FileResponse:
    """Serve the dependency-free browser workspace from the API process."""
    return FileResponse(UI_DIR / "index.html")


app.mount("/ui", StaticFiles(directory=UI_DIR), name="ui")
