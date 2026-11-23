from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from fastapi import HTTPException

from src.core.engine import SimulationEngine
from src.core.grid import SpatialGrid
from src.utils.serializer import ScenarioDefinition, build_engine_from_scenario_definition

grid = SpatialGrid(N=10, Z=3)
engine = SimulationEngine(grid=grid)
active_scenario_template: ScenarioDefinition | None = None


def get_engine() -> SimulationEngine:
    return engine


def set_engine(new_engine: SimulationEngine) -> SimulationEngine:
    global engine
    engine = new_engine
    return engine


def set_active_scenario(
    new_engine: SimulationEngine,
    scenario: ScenarioDefinition,
) -> SimulationEngine:
    """Activate an engine and retain an immutable definition for scenario reset."""
    global active_scenario_template
    active_scenario_template = deepcopy(scenario)
    return set_engine(new_engine)


def load_engine_from_scenario_definition(
    scenario: ScenarioDefinition,
) -> SimulationEngine:
    new_engine = build_engine_from_scenario_definition(scenario)
    return set_active_scenario(new_engine, scenario)


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
    global active_scenario_template, engine
    grid_size = engine.grid.N
    z_levels = engine.grid.Z
    engine = SimulationEngine(grid=SpatialGrid(N=grid_size, Z=z_levels))
    active_scenario_template = None
    return engine


def reset_active_scenario() -> SimulationEngine:
    """Rebuild the active scenario from its original loaded definition."""
    if active_scenario_template is None:
        raise ValueError("No active scenario is available to reset")
    return load_engine_from_scenario_definition(deepcopy(active_scenario_template))
