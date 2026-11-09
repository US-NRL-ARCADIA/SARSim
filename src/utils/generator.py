from __future__ import annotations

import random
from typing import Any

from src.core.agents import Agent, AgentClass, Orientation
from src.core.buildings import Building, BuildingCell
from src.core.casualties import Casualty, LivingState, TriageState
from src.core.engine import SimulationEngine
from src.core.grid import Coordinate, SpatialGrid
from src.core.types import CellStatus, TransportStatus
from src.utils.serializer import ScenarioDefinition, serialize_scenario_definition


class ScenarioGenerator:
    """Seeded procedural generator for research scenarios."""

    def __init__(self, seed: int | None = None) -> None:
        self.seed = seed
        self.rng = random.Random(seed)

    def generate(
        self,
        *,
        grid_size: int,
        z_depth: int,
        building_density: float,
        hazard_density: float,
        casualty_density: float,
        debris_density: float,
        agent_count: int = 2,
    ) -> ScenarioDefinition:
        engine = SimulationEngine(grid=SpatialGrid(N=grid_size, Z=z_depth))

        self._place_buildings(engine, building_density)
        self._place_hazards(engine, hazard_density)
        self._place_debris(engine, debris_density)
        self._place_casualties(engine, casualty_density)
        self._place_agents(engine, agent_count)

        metadata = {
            "scenario_id": self._scenario_id(),
            "name": "Generated Research Scenario",
            "seed": self.seed,
            "scenario_family": "procedural",
        }
        objectives = {
            "primary_goals": ["stabilize casualties", "navigate hazards"],
        }
        evaluation = {
            "expected_difficulty": self._difficulty_label(
                building_density=building_density,
                hazard_density=hazard_density,
                casualty_density=casualty_density,
            )
        }
        zones = self._default_zones(grid_size)

        return serialize_scenario_definition(
            engine,
            metadata=metadata,
            zones=zones,
            scheduled_events=[],
            objectives=objectives,
            evaluation=evaluation,
        )

    def _place_buildings(self, engine: SimulationEngine, density: float) -> None:
        target_count = max(0, int(engine.grid.N * engine.grid.N * density))
        placed = 0
        attempts = 0
        while placed < target_count and attempts < target_count * 10 + 10:
            attempts += 1
            coord = Coordinate(
                x=self.rng.randrange(engine.grid.N),
                y=self.rng.randrange(engine.grid.N),
                z=0,
            )
            key = (coord.x, coord.y, coord.z)
            if any(key in building.cells for building in engine.buildings.values()):
                continue
            integrity = round(self.rng.uniform(0.2, 1.0), 3)
            building = Building(
                id=f"B{placed + 1}",
                cells={key: BuildingCell(coord=coord, integrity=integrity, collapsed=False)},
            )
            engine.add_building(building)
            engine.grid.set_cell_status(coord, CellStatus.IMPASSABLE)
            placed += 1

    def _place_hazards(self, engine: SimulationEngine, density: float) -> None:
        target_count = max(0, int(engine.grid.N * engine.grid.N * engine.grid.Z * density))
        for _ in range(target_count):
            coord = Coordinate(
                x=self.rng.randrange(engine.grid.N),
                y=self.rng.randrange(engine.grid.N),
                z=self.rng.randrange(engine.grid.Z),
            )
            density_value = round(self.rng.uniform(0.2, 1.0), 3)
            engine.grid.set_smoke_density(coord, density_value)

    def _place_debris(self, engine: SimulationEngine, density: float) -> None:
        target_count = max(0, int(engine.grid.N * engine.grid.N * density))
        placed = 0
        attempts = 0
        while placed < target_count and attempts < target_count * 10 + 10:
            attempts += 1
            coord = Coordinate(
                x=self.rng.randrange(engine.grid.N),
                y=self.rng.randrange(engine.grid.N),
                z=0,
            )
            if engine.grid.get_cell_status(coord) != CellStatus.UNOCCUPIED:
                continue
            engine.grid.set_cell_status(coord, CellStatus.PASSABLE)
            placed += 1

    def _place_casualties(self, engine: SimulationEngine, density: float) -> None:
        target_count = max(1, int(engine.grid.N * engine.grid.N * density))
        placed = 0
        attempts = 0
        while placed < target_count and attempts < target_count * 20 + 20:
            attempts += 1
            coord = Coordinate(
                x=self.rng.randrange(engine.grid.N),
                y=self.rng.randrange(engine.grid.N),
                z=0,
            )
            if any(c.coord == coord for c in engine.casualties.values()):
                continue
            health = round(self.rng.uniform(20.0, 100.0), 2)
            decay_rate = round(self.rng.uniform(0.5, 3.0), 2)
            is_covered = engine.grid.get_cell_status(coord) == CellStatus.PASSABLE
            casualty = Casualty(
                id=f"C{placed + 1}",
                coord=coord,
                health=health,
                decay_rate=decay_rate,
                is_covered=is_covered,
                triage_state=TriageState.UNKNOWN,
                transport_status=TransportStatus.ON_GROUND,
                living_state=LivingState.ALIVE,
            )
            engine.add_casualty(casualty)
            placed += 1

    def _place_agents(self, engine: SimulationEngine, agent_count: int) -> None:
        placed = 0
        attempts = 0
        while placed < agent_count and attempts < agent_count * 20 + 20:
            attempts += 1
            agent_class = AgentClass.UAV if placed % 2 == 1 and engine.grid.Z > 1 else AgentClass.UGV
            z = 1 if agent_class is AgentClass.UAV else 0
            coord = Coordinate(
                x=self.rng.randrange(engine.grid.N),
                y=self.rng.randrange(engine.grid.N),
                z=z,
            )
            if any(agent.coord == coord for agent in engine.agents.values()):
                continue
            if agent_class is AgentClass.UGV and engine.grid.get_cell_status(Coordinate(coord.x, coord.y, 0)) == CellStatus.IMPASSABLE:
                continue
            agent = Agent(
                id=f"A{placed + 1}",
                coord=coord,
                orientation=self.rng.choice(list(Orientation)),
                agent_class=agent_class,
            )
            engine.add_agent(agent)
            placed += 1

    def _default_zones(self, grid_size: int) -> list[dict[str, Any]]:
        return [
            {
                "id": "zone-extraction-1",
                "zone_type": "EXTRACTION",
                "cells": [{"x": grid_size - 1, "y": grid_size - 1, "z": 0}],
                "labels": ["default"],
            }
        ]

    def _scenario_id(self) -> str:
        seed_part = "none" if self.seed is None else str(self.seed)
        return f"generated-{seed_part}"

    def _difficulty_label(
        self,
        *,
        building_density: float,
        hazard_density: float,
        casualty_density: float,
    ) -> str:
        score = building_density + hazard_density + casualty_density
        if score < 0.4:
            return "easy"
        if score < 0.9:
            return "medium"
        return "hard"


def generate_scenario(
    *,
    grid_size: int,
    z_depth: int,
    building_density: float,
    hazard_density: float,
    casualty_density: float,
    debris_density: float,
    seed: int | None = None,
    agent_count: int = 2,
) -> ScenarioDefinition:
    """Convenience wrapper for seeded scenario generation."""
    generator = ScenarioGenerator(seed=seed)
    return generator.generate(
        grid_size=grid_size,
        z_depth=z_depth,
        building_density=building_density,
        hazard_density=hazard_density,
        casualty_density=casualty_density,
        debris_density=debris_density,
        agent_count=agent_count,
    )
