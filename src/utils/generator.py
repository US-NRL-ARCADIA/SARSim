from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass
from typing import Any

from src.core.agents import Agent, AgentClass, Orientation
from src.core.buildings import Building, BuildingCell
from src.core.casualties import Casualty, LivingState, TriageState
from src.core.engine import SimulationEngine
from src.core.grid import Coordinate, SpatialGrid
from src.core.types import CellStatus, TransportStatus
from src.utils.serializer import ScenarioDefinition, serialize_scenario_definition


@dataclass(frozen=True)
class SolvabilityReport:
    """Result of the static rescue-reachability check used by the generator."""

    solvable: bool
    reachable_casualty_ids: tuple[str, ...]
    unreachable_casualty_ids: tuple[str, ...]
    reason: str | None = None


@dataclass(frozen=True)
class _Layout:
    hospital: Coordinate
    casualties: list[Coordinate]
    ground_agents: list[Coordinate]
    air_agents: list[Coordinate]


class ScenarioGenerator:
    """Fast, seeded generator for solvable research scenarios.

    Ground routes joining responders, casualties, and a field hospital are
    constructed before obstacles are sampled. This avoids expensive
    generate-and-reject loops and makes rescue reachability an invariant rather
    than a likely outcome.
    """

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
        self._validate_inputs(
            grid_size=grid_size,
            z_depth=z_depth,
            building_density=building_density,
            hazard_density=hazard_density,
            casualty_density=casualty_density,
            debris_density=debris_density,
            agent_count=agent_count,
        )

        engine = SimulationEngine(grid=SpatialGrid(N=grid_size, Z=z_depth))
        layout = self._create_layout(
            grid_size=grid_size,
            z_depth=z_depth,
            casualty_density=casualty_density,
            agent_count=agent_count,
        )
        protected = self._protected_rescue_network(
            layout.hospital,
            layout.casualties,
            layout.ground_agents,
        )

        self._place_agents(engine, layout.ground_agents, layout.air_agents)
        covered_ids = self._place_casualties(
            engine,
            layout.casualties,
            debris_density=debris_density,
        )
        building_count = self._place_buildings(
            engine,
            building_density,
            protected=protected,
            reserved_columns={
                (coord.x, coord.y)
                for coord in layout.air_agents
            },
        )
        debris_count = self._place_debris(
            engine,
            debris_density,
            protected=protected,
            covered_casualty_ids=covered_ids,
        )
        smoke_count, route_smoke_count = self._place_hazards(
            engine,
            hazard_density,
            protected=protected,
            reserved=set(layout.casualties)
            | set(layout.ground_agents)
            | set(layout.air_agents)
            | {layout.hospital},
        )

        zones = self._default_zones(layout.hospital)
        metadata = {
            "scenario_id": self._scenario_id(),
            "name": "Generated Solvable Research Scenario",
            "seed": self.seed,
            "scenario_family": "procedural",
            "generation_method": "constructive_rescue_network",
        }
        objectives = {
            "primary_goals": ["rescue casualties", "navigate hazards"],
        }
        evaluation: dict[str, Any] = {
            "expected_difficulty": self._difficulty_label(
                building_density=building_density,
                hazard_density=hazard_density,
                casualty_density=casualty_density,
            ),
            "tradeoffs": {
                "covered_casualties": len(covered_ids),
                "smoke_on_guaranteed_routes": route_smoke_count,
                "buildings": building_count,
                "debris_cells": debris_count,
                "smoke_cells": smoke_count,
                "casualty_urgency_levels": min(3, len(layout.casualties)),
            },
        }

        scenario = serialize_scenario_definition(
            engine,
            metadata=metadata,
            zones=zones,
            scheduled_events=[],
            objectives=objectives,
            evaluation=evaluation,
        )
        report = analyze_solvability(scenario)
        if not report.solvable:  # Defensive assertion against future generator changes.
            raise RuntimeError(f"generated scenario is not solvable: {report.reason}")
        evaluation["solvability"] = {
            "verified": True,
            "method": "ground_component_reachability",
            "reachable_casualties": len(report.reachable_casualty_ids),
            "guaranteed_route_cells": len(protected),
        }
        return scenario

    def _create_layout(
        self,
        *,
        grid_size: int,
        z_depth: int,
        casualty_density: float,
        agent_count: int,
    ) -> _Layout:
        ground_capacity = grid_size * grid_size
        air_capacity = ground_capacity * (z_depth - 1)
        minimum_ground_agents = max(1, agent_count - air_capacity)
        preferred_ground_agents = agent_count if z_depth == 1 else (agent_count + 1) // 2
        ground_agent_count = min(
            ground_capacity - 2,
            max(minimum_ground_agents, preferred_ground_agents),
        )
        if ground_agent_count + 2 > ground_capacity:
            raise ValueError(
                "agent_count leaves no distinct ground cells for a casualty and hospital"
            )

        requested_casualties = max(1, int(ground_capacity * casualty_density))
        casualty_count = min(
            requested_casualties,
            ground_capacity - ground_agent_count - 1,
        )
        ground_coords = [
            Coordinate(x=x, y=y, z=0)
            for x in range(grid_size)
            for y in range(grid_size)
        ]
        chosen_ground = self.rng.sample(
            ground_coords,
            1 + casualty_count + ground_agent_count,
        )
        hospital = chosen_ground[0]
        casualties = chosen_ground[1 : 1 + casualty_count]
        ground_agents = chosen_ground[1 + casualty_count :]

        air_agent_count = agent_count - ground_agent_count
        air_coords = [
            Coordinate(x=x, y=y, z=z)
            for z in range(1, z_depth)
            for x in range(grid_size)
            for y in range(grid_size)
        ]
        air_agents = self.rng.sample(air_coords, air_agent_count)
        return _Layout(
            hospital=hospital,
            casualties=casualties,
            ground_agents=ground_agents,
            air_agents=air_agents,
        )

    def _protected_rescue_network(
        self,
        hospital: Coordinate,
        casualties: list[Coordinate],
        ground_agents: list[Coordinate],
    ) -> set[Coordinate]:
        protected = {hospital}
        for endpoint in casualties + ground_agents:
            protected.update(self._randomized_manhattan_path(endpoint, hospital))
        return protected

    def _randomized_manhattan_path(
        self,
        start: Coordinate,
        goal: Coordinate,
    ) -> list[Coordinate]:
        current = start
        path = [current]
        while current != goal:
            candidates: list[Coordinate] = []
            if current.x != goal.x:
                candidates.append(Coordinate(
                    x=current.x + (1 if goal.x > current.x else -1),
                    y=current.y,
                    z=0,
                ))
            if current.y != goal.y:
                candidates.append(Coordinate(
                    x=current.x,
                    y=current.y + (1 if goal.y > current.y else -1),
                    z=0,
                ))
            current = self.rng.choice(candidates)
            path.append(current)
        return path

    def _place_buildings(
        self,
        engine: SimulationEngine,
        density: float,
        *,
        protected: set[Coordinate],
        reserved_columns: set[tuple[int, int]],
    ) -> int:
        target_count = int(engine.grid.N * engine.grid.N * density)
        candidates = [
            Coordinate(x=x, y=y, z=0)
            for x in range(engine.grid.N)
            for y in range(engine.grid.N)
            if Coordinate(x=x, y=y, z=0) not in protected
            and (x, y) not in reserved_columns
        ]
        selected = self.rng.sample(candidates, min(target_count, len(candidates)))
        for index, coord in enumerate(selected, start=1):
            height = self.rng.randint(1, engine.grid.Z)
            cells: dict[tuple[int, int, int], BuildingCell] = {}
            for z in range(height):
                level_coord = Coordinate(x=coord.x, y=coord.y, z=z)
                cells[(coord.x, coord.y, z)] = BuildingCell(
                    coord=level_coord,
                    integrity=round(self.rng.uniform(0.25, 1.0), 3),
                    collapsed=False,
                )
                engine.grid.set_cell_status(level_coord, CellStatus.IMPASSABLE)
            engine.add_building(Building(id=f"B{index}", cells=cells))
        return len(selected)

    def _place_hazards(
        self,
        engine: SimulationEngine,
        density: float,
        *,
        protected: set[Coordinate],
        reserved: set[Coordinate],
    ) -> tuple[int, int]:
        target_count = int(engine.grid.N * engine.grid.N * engine.grid.Z * density)
        candidates = [
            Coordinate(x=x, y=y, z=z)
            for x in range(engine.grid.N)
            for y in range(engine.grid.N)
            for z in range(engine.grid.Z)
            if Coordinate(x=x, y=y, z=z) not in reserved
        ]
        route_candidates = sorted(
            protected - reserved,
            key=lambda coord: (coord.z, coord.x, coord.y),
        )
        route_count = min(len(route_candidates), target_count // 3)
        if target_count > 0 and route_candidates:
            route_count = max(1, route_count)
        selected = self.rng.sample(route_candidates, route_count)
        selected_set = set(selected)
        remaining = [coord for coord in candidates if coord not in selected_set]
        selected.extend(self.rng.sample(
            remaining,
            min(target_count - route_count, len(remaining)),
        ))
        for coord in selected:
            engine.grid.set_smoke_density(coord, round(self.rng.uniform(0.2, 1.0), 3))
        return len(selected), route_count

    def _place_debris(
        self,
        engine: SimulationEngine,
        density: float,
        *,
        protected: set[Coordinate],
        covered_casualty_ids: set[str],
    ) -> int:
        target_count = int(engine.grid.N * engine.grid.N * density)
        already_placed = 0
        for casualty_id in covered_casualty_ids:
            coord = engine.casualties[casualty_id].coord
            engine.grid.set_cell_status(coord, CellStatus.PASSABLE)
            already_placed += 1

        occupied = {agent.coord for agent in engine.agents.values()}
        casualty_coords = {casualty.coord for casualty in engine.casualties.values()}
        candidates = [
            Coordinate(x=x, y=y, z=0)
            for x in range(engine.grid.N)
            for y in range(engine.grid.N)
            if Coordinate(x=x, y=y, z=0) not in protected
            and Coordinate(x=x, y=y, z=0) not in occupied
            and Coordinate(x=x, y=y, z=0) not in casualty_coords
            and engine.grid.get_cell_status(Coordinate(x=x, y=y, z=0))
            is CellStatus.UNOCCUPIED
        ]
        selected = self.rng.sample(
            candidates,
            min(max(0, target_count - already_placed), len(candidates)),
        )
        for coord in selected:
            engine.grid.set_cell_status(coord, CellStatus.PASSABLE)
        return already_placed + len(selected)

    def _place_casualties(
        self,
        engine: SimulationEngine,
        coords: list[Coordinate],
        *,
        debris_density: float,
    ) -> set[str]:
        debris_budget = int(engine.grid.N * engine.grid.N * debris_density)
        covered_count = min(len(coords) // 2, debris_budget)
        if len(coords) > 1 and debris_budget > 0:
            covered_count = max(1, covered_count)
        covered_indexes = set(self.rng.sample(range(len(coords)), covered_count))
        covered_ids: set[str] = set()
        urgency_profiles = (
            ((65.0, 80.0), (0.20, 0.35)),
            ((78.0, 92.0), (0.10, 0.20)),
            ((90.0, 100.0), (0.03, 0.10)),
        )
        for index, coord in enumerate(coords):
            health_range, decay_range = urgency_profiles[index % len(urgency_profiles)]
            casualty_id = f"C{index + 1}"
            is_covered = index in covered_indexes
            casualty = Casualty(
                id=casualty_id,
                coord=coord,
                health=round(self.rng.uniform(*health_range), 2),
                decay_rate=round(self.rng.uniform(*decay_range), 2),
                is_covered=is_covered,
                triage_state=TriageState.UNKNOWN,
                transport_status=TransportStatus.ON_GROUND,
                living_state=LivingState.ALIVE,
            )
            engine.add_casualty(casualty)
            if is_covered:
                covered_ids.add(casualty_id)
        return covered_ids

    def _place_agents(
        self,
        engine: SimulationEngine,
        ground_coords: list[Coordinate],
        air_coords: list[Coordinate],
    ) -> None:
        for index, coord in enumerate(ground_coords + air_coords, start=1):
            agent_class = AgentClass.UGV if coord.z == 0 else AgentClass.UAV
            engine.add_agent(Agent(
                id=f"A{index}",
                coord=coord,
                orientation=self.rng.choice(list(Orientation)),
                agent_class=agent_class,
            ))

    @staticmethod
    def _default_zones(hospital: Coordinate) -> list[dict[str, Any]]:
        cell = {"x": hospital.x, "y": hospital.y, "z": hospital.z}
        return [
            {
                "id": "zone-extraction-1",
                "zone_type": "EXTRACTION",
                "cells": [dict(cell)],
                "labels": ["default", "evacuation"],
            },
            {
                "id": "zone-field-hospital-1",
                "zone_type": "FIELD_HOSPITAL",
                "cells": [dict(cell)],
                "labels": ["default", "medical-dropoff"],
            },
        ]

    def _scenario_id(self) -> str:
        seed_part = "none" if self.seed is None else str(self.seed)
        return f"generated-{seed_part}"

    @staticmethod
    def _difficulty_label(
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

    @staticmethod
    def _validate_inputs(
        *,
        grid_size: int,
        z_depth: int,
        building_density: float,
        hazard_density: float,
        casualty_density: float,
        debris_density: float,
        agent_count: int,
    ) -> None:
        if not isinstance(grid_size, int) or isinstance(grid_size, bool) or grid_size < 2:
            raise ValueError("grid_size must be an integer of at least 2")
        if not isinstance(z_depth, int) or isinstance(z_depth, bool) or z_depth < 1:
            raise ValueError("z_depth must be a positive integer")
        if not isinstance(agent_count, int) or isinstance(agent_count, bool) or agent_count < 1:
            raise ValueError("agent_count must be at least 1 for a solvable scenario")
        if agent_count > grid_size * grid_size * z_depth - 2:
            raise ValueError("agent_count is too large for distinct rescue-critical cells")
        densities = {
            "building_density": building_density,
            "hazard_density": hazard_density,
            "casualty_density": casualty_density,
            "debris_density": debris_density,
        }
        for name, value in densities.items():
            if isinstance(value, bool) or not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be a finite number in [0, 1]")


def analyze_solvability(scenario: ScenarioDefinition) -> SolvabilityReport:
    """Check that every casualty can be loaded and taken to a field hospital.

    The analysis mirrors current engine interaction rules: UGVs traverse open
    ground, load from an adjacent ground cell, and transfer from a hospital cell
    or an adjacent cell. Generated debris on a casualty does not invalidate the
    route because it can be cleared from that same interaction cell.
    """

    grid = scenario.get("grid", {})
    size = int(grid.get("N", 0))
    if size < 1:
        return SolvabilityReport(False, (), (), "scenario has no valid grid")

    blocked: set[tuple[int, int]] = set()
    for cell in grid.get("cells", []):
        coord = cell["coord"]
        if int(coord["z"]) != 0:
            continue
        key = (int(coord["x"]), int(coord["y"]))
        if cell["status"] == CellStatus.IMPASSABLE.name:
            blocked.add(key)

    # PASSABLE cells are debris, not permanent walls. A responder can clear a
    # debris cell from its reachable frontier and then continue, so connectivity
    # is evaluated after any required sequence of clear actions.
    traversable_cells = {
        (x, y)
        for x in range(size)
        for y in range(size)
        if (x, y) not in blocked
    }
    components = _ground_components(traversable_cells)
    responder_components = {
        components[(int(agent["coord"]["x"]), int(agent["coord"]["y"]))]
        for agent in scenario.get("agents", [])
        if agent.get("agent_class") == AgentClass.UGV.name
        and int(agent["coord"]["z"]) == 0
        and (int(agent["coord"]["x"]), int(agent["coord"]["y"])) in components
    }
    if not responder_components:
        casualties = tuple(sorted(str(item["id"]) for item in scenario.get("casualties", [])))
        return SolvabilityReport(False, (), casualties, "no UGV starts on traversable ground")

    hospital_components: set[int] = set()
    for zone in scenario.get("zones", []):
        if zone.get("zone_type") != "FIELD_HOSPITAL":
            continue
        for cell in zone.get("cells", []):
            if int(cell["z"]) != 0:
                continue
            hospital_components.update(
                _interaction_components(
                    (int(cell["x"]), int(cell["y"])),
                    components,
                    include_center=True,
                )
            )
    usable_components = responder_components & hospital_components
    if not usable_components:
        casualties = tuple(sorted(str(item["id"]) for item in scenario.get("casualties", [])))
        return SolvabilityReport(
            False,
            (),
            casualties,
            "no field hospital is connected to a ground responder",
        )

    reachable: list[str] = []
    unreachable: list[str] = []
    for casualty in scenario.get("casualties", []):
        casualty_id = str(casualty["id"])
        coord = casualty["coord"]
        if int(coord["z"]) != 0:
            unreachable.append(casualty_id)
            continue
        interaction_components = _interaction_components(
            (int(coord["x"]), int(coord["y"])),
            components,
            include_center=False,
        )
        if interaction_components & usable_components:
            reachable.append(casualty_id)
        else:
            unreachable.append(casualty_id)

    return SolvabilityReport(
        not unreachable,
        tuple(sorted(reachable)),
        tuple(sorted(unreachable)),
        None if not unreachable else "one or more casualties lack a complete rescue route",
    )


def _ground_components(open_cells: set[tuple[int, int]]) -> dict[tuple[int, int], int]:
    components: dict[tuple[int, int], int] = {}
    component_id = 0
    for start in sorted(open_cells):
        if start in components:
            continue
        component_id += 1
        components[start] = component_id
        frontier = deque([start])
        while frontier:
            x, y = frontier.popleft()
            for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if neighbor in open_cells and neighbor not in components:
                    components[neighbor] = component_id
                    frontier.append(neighbor)
    return components


def _interaction_components(
    coord: tuple[int, int],
    components: dict[tuple[int, int], int],
    *,
    include_center: bool,
) -> set[int]:
    x, y = coord
    candidates = [(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)]
    if include_center:
        candidates.append(coord)
    return {components[candidate] for candidate in candidates if candidate in components}


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
    """Generate a seeded scenario with verified rescue reachability."""
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
