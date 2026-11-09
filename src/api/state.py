from __future__ import annotations

import json
from pathlib import Path

from fastapi import HTTPException

from src.core.engine import SimulationEngine
from src.core.grid import SpatialGrid
from src.utils.serializer import ScenarioDefinition, build_engine_from_scenario_definition

grid = SpatialGrid(N=10, Z=3)
engine = SimulationEngine(grid=grid)


def get_engine() -> SimulationEngine:
    return engine


def set_engine(new_engine: SimulationEngine) -> SimulationEngine:
    global engine
    engine = new_engine
    return engine


def load_engine_from_scenario_definition(
    scenario: ScenarioDefinition,
) -> SimulationEngine:
    return set_engine(build_engine_from_scenario_definition(scenario))


def load_engine_from_scenario_file(filepath: str) -> SimulationEngine:
    path = Path(filepath)
    if not path.is_absolute() and not path.exists():
        project_relative_path = Path(__file__).resolve().parents[2] / path
        if project_relative_path.exists():
            path = project_relative_path
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Scenario file not found: {filepath}")
    try:
        scenario = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid scenario JSON in {filepath}: {exc}") from exc
    return load_engine_from_scenario_definition(scenario)


def reset_engine() -> SimulationEngine:
    global engine
    grid_size = engine.grid.N
    z_levels = engine.grid.Z
    engine = SimulationEngine(grid=SpatialGrid(N=grid_size, Z=z_levels))
    return engine
