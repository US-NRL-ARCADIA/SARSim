from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pygame

from src.utils.generator import generate_scenario
from src.utils.serializer import build_engine_from_scenario_definition

WINDOW_WIDTH = 1960
WINDOW_HEIGHT = 920
GRID_MARGIN = 24
TOOLS_PANEL_WIDTH = 260
CONTROLS_PANEL_WIDTH = 320
DETAILS_PANEL_WIDTH = 420
CELL_SIZE = 48
BACKGROUND = (24, 28, 36)
GRID_COLOR = (70, 78, 92)
TEXT_COLOR = (230, 235, 245)
PANEL_COLOR = (34, 40, 52)
SELECTED_COLOR = (255, 215, 0)
SMOKE_COLOR = (120, 120, 120)
DEBRIS_COLOR = (160, 120, 70)
WALL_COLOR = (90, 90, 110)
AGENT_COLOR = (80, 180, 255)
CASUALTY_COLOR = (220, 90, 90)
ZONE_COLOR = (80, 200, 120)
BUILDING_COLOR = (180, 120, 220)


class ScenarioEditor:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("SARSim Scenario Editor")
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Menlo", 18)
        self.small_font = pygame.font.SysFont("Menlo", 14)

        self.scenario: dict[str, Any] = generate_scenario(
            grid_size=10,
            z_depth=3,
            building_density=0.08,
            hazard_density=0.04,
            casualty_density=0.06,
            debris_density=0.05,
            seed=42,
            agent_count=3,
        )
        self.current_z = 0
        self.selected_tool = "wall"
        self.selected_zone_type = "EXTRACTION"
        self.active_zone_id: str | None = None
        self.selected_cell: tuple[int, int] | None = None
        self.sidebar_scroll_offset = 0
        self.running = True
        self.status_message = "Ready"
        self.selected_agent_id: str | None = None
        self.selected_casualty_id: str | None = None
        self.selected_building_id: str | None = None
        self._ensure_scenario_defaults()
        self._ensure_active_zone()

    def run(self) -> None:
        while self.running:
            self._handle_events()
            self._draw()
            pygame.display.flip()
            self.clock.tick(30)
        pygame.quit()

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self._handle_keydown(event)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_click(event.pos)
            elif event.type == pygame.MOUSEWHEEL:
                if self._mouse_in_details_panel():
                    self._scroll_sidebar(-event.y * 40)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 4:
                self._scroll_sidebar(-40)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 5:
                self._scroll_sidebar(40)

    def _handle_keydown(self, event: pygame.event.Event) -> None:
        if event.key == pygame.K_ESCAPE:
            self.running = False
        elif event.key == pygame.K_8:
            self.selected_tool = "select"
            self.status_message = "Selection tool active"
        elif event.key == pygame.K_0:
            self.selected_tool = "clear"
        elif event.key == pygame.K_1:
            self.selected_tool = "wall"
        elif event.key == pygame.K_2:
            self.selected_tool = "debris"
        elif event.key == pygame.K_3:
            self.selected_tool = "smoke"
        elif event.key == pygame.K_4:
            self.selected_tool = "casualty"
        elif event.key == pygame.K_5:
            self.selected_tool = "agent"
        elif event.key == pygame.K_6:
            self.selected_tool = "zone"
        elif event.key == pygame.K_7:
            self.selected_tool = "building"
        elif event.key == pygame.K_LEFTBRACKET:
            self.current_z = max(0, self.current_z - 1)
            self.status_message = f"Viewing z={self.current_z}"
        elif event.key == pygame.K_RIGHTBRACKET:
            self.current_z = min(self.scenario["grid"]["Z"] - 1, self.current_z + 1)
            self.status_message = f"Viewing z={self.current_z}"
        elif event.key == pygame.K_s:
            self._save_scenario()
        elif event.key == pygame.K_l:
            self._load_scenario()
        elif event.key == pygame.K_g:
            self._regenerate_scenario()
        elif event.key == pygame.K_v:
            self._validate_scenario()
        elif event.key == pygame.K_o:
            self._cycle_agent_orientation()
        elif event.key == pygame.K_c:
            self._toggle_selected_agent_class()
        elif event.key == pygame.K_h:
            self._adjust_selected_casualty_health(-10.0)
        elif event.key == pygame.K_j:
            self._adjust_selected_casualty_health(10.0)
        elif event.key == pygame.K_d:
            self._adjust_selected_casualty_decay(0.5)
        elif event.key == pygame.K_f:
            self._toggle_selected_casualty_cover()
        elif event.key == pygame.K_i:
            self._adjust_selected_building_integrity(0.1)
        elif event.key == pygame.K_k:
            self._adjust_selected_building_integrity(-0.1)
        elif event.key == pygame.K_x:
            self._toggle_selected_building_collapsed()
        elif event.key == pygame.K_m:
            self._cycle_metadata_difficulty()
        elif event.key == pygame.K_t:
            self._cycle_constraint_deadline()
        elif event.key == pygame.K_y:
            self._cycle_rescue_target()
        elif event.key == pygame.K_b:
            self._toggle_temporal_constraint()
        elif event.key == pygame.K_e:
            self._add_scheduled_event_for_selected_cell()
        elif event.key == pygame.K_r:
            self._remove_last_scheduled_event()
        elif event.key == pygame.K_z:
            self._cycle_active_zone_type()
        elif event.key == pygame.K_n:
            self._create_new_zone()
        elif event.key == pygame.K_p:
            self._cycle_active_zone()
        elif event.key == pygame.K_UP:
            self._scroll_sidebar(-40)
        elif event.key == pygame.K_DOWN:
            self._scroll_sidebar(40)
        elif event.key == pygame.K_PAGEUP:
            self._scroll_sidebar(-200)
        elif event.key == pygame.K_PAGEDOWN:
            self._scroll_sidebar(200)

    def _handle_click(self, pos: tuple[int, int]) -> None:
        grid_x, grid_y = self._screen_to_grid(pos)
        if grid_x is None or grid_y is None:
            return
        self.selected_cell = (grid_x, grid_y)
        self._update_selection(grid_x, grid_y, self.current_z)
        if self.selected_tool != "select":
            self._apply_tool(grid_x, grid_y, self.current_z)
            self._update_selection(grid_x, grid_y, self.current_z)

    def _apply_tool(self, x: int, y: int, z: int) -> None:
        coord = {"x": x, "y": y, "z": z}
        ground_coord = {"x": x, "y": y, "z": 0}

        if self.selected_tool == "clear":
            self._remove_cell_status(coord)
            self._remove_smoke(coord)
            self._remove_agent(coord)
            self._remove_casualty(coord)
            self._remove_zone_cell(coord)
            self.status_message = f"Cleared cell ({x}, {y}, {z})"
            return

        if self.selected_tool == "wall":
            self._set_cell_status(coord, "IMPASSABLE")
            self.status_message = f"Placed wall at ({x}, {y}, {z})"
            return

        if self.selected_tool == "debris":
            self._set_cell_status(ground_coord, "PASSABLE")
            self._sync_casualty_cover(x, y, 0, True)
            self.status_message = f"Placed debris at ({x}, {y}, 0)"
            return

        if self.selected_tool == "smoke":
            self._set_smoke(coord, 0.7)
            self.status_message = f"Placed smoke at ({x}, {y}, {z})"
            return

        if self.selected_tool == "casualty":
            self._upsert_casualty(ground_coord)
            self.status_message = f"Placed casualty at ({x}, {y}, 0)"
            return

        if self.selected_tool == "agent":
            self._upsert_agent(coord)
            self.status_message = f"Placed agent at ({x}, {y}, {z})"
            return

        if self.selected_tool == "zone":
            self._toggle_zone_cell(ground_coord)
            self.status_message = f"Toggled zone cell at ({x}, {y}, 0)"
            return

        if self.selected_tool == "building":
            self._upsert_building(ground_coord)
            self.status_message = f"Placed building cell at ({x}, {y}, 0)"

    def _draw(self) -> None:
        self.screen.fill(BACKGROUND)
        self._draw_grid()
        self._draw_tools_panel()
        self._draw_controls_panel()
        self._draw_details_panel()

    def _draw_grid(self) -> None:
        grid_size = self.scenario["grid"]["N"]
        for x in range(grid_size):
            for y in range(grid_size):
                rect = pygame.Rect(
                    GRID_MARGIN + x * CELL_SIZE,
                    GRID_MARGIN + y * CELL_SIZE,
                    CELL_SIZE,
                    CELL_SIZE,
                )
                color = self._cell_color(x, y, self.current_z)
                pygame.draw.rect(self.screen, color, rect)
                pygame.draw.rect(self.screen, GRID_COLOR, rect, 1)

                if self.selected_cell == (x, y):
                    pygame.draw.rect(self.screen, SELECTED_COLOR, rect, 3)

                self._draw_cell_overlays(x, y, rect)

    def _draw_cell_overlays(self, x: int, y: int, rect: pygame.Rect) -> None:
        if self._has_zone_cell(x, y, 0):
            pygame.draw.circle(self.screen, ZONE_COLOR, rect.center, 6)

        building = self._get_building_at(x, y, 0)
        if building is not None:
            pygame.draw.rect(self.screen, BUILDING_COLOR, rect.inflate(-18, -18), 2)

        if self._has_casualty(x, y, 0):
            pygame.draw.circle(self.screen, CASUALTY_COLOR, rect.center, 10)

        agent = self._get_agent_at(x, y, self.current_z)
        if agent is not None:
            pygame.draw.circle(self.screen, AGENT_COLOR, rect.center, 12, 3)
            label = self.small_font.render(agent["id"], True, TEXT_COLOR)
            self.screen.blit(label, (rect.x + 4, rect.y + 4))

    def _draw_tools_panel(self) -> None:
        panel_x = GRID_MARGIN + self.scenario["grid"]["N"] * CELL_SIZE + 24
        panel = pygame.Rect(panel_x, 0, TOOLS_PANEL_WIDTH, WINDOW_HEIGHT)
        pygame.draw.rect(self.screen, PANEL_COLOR, panel)

        lines = [
            "Tools",
            "",
            f"Current z-level: {self.current_z}",
            f"Selected tool: {self.selected_tool}",
            "",
            "0 clear",
            "1 wall",
            "2 debris",
            "3 smoke",
            "4 casualty",
            "5 agent",
            "6 zone",
            "7 building",
            "8 select",
        ]

        y_offset = 20
        for line in lines:
            surface = self.font.render(line, True, TEXT_COLOR)
            self.screen.blit(surface, (panel_x + 16, y_offset))
            y_offset += 24

    def _draw_controls_panel(self) -> None:
        panel_x = GRID_MARGIN + self.scenario["grid"]["N"] * CELL_SIZE + 24 + TOOLS_PANEL_WIDTH
        panel = pygame.Rect(panel_x, 0, CONTROLS_PANEL_WIDTH, WINDOW_HEIGHT)
        pygame.draw.rect(self.screen, PANEL_COLOR, panel)

        lines = [
            "Controls",
            "",
            "Zone controls:",
            "Z cycle active zone type",
            "N create new zone",
            "P cycle active zone",
            "",
            "General controls:",
            "[ / ] change z-level",
            "S save scenario",
            "L load scenario",
            "G regenerate scenario",
            "V validate scenario",
            "O cycle selected agent orientation",
            "C toggle selected agent class",
            "H/J casualty health -/+",
            "D increase casualty decay",
            "F toggle casualty cover",
            "I/K building integrity +/-",
            "X toggle building collapsed",
            "M cycle scenario difficulty",
            "B toggle rescue constraint",
            "T cycle rescue deadline",
            "Y cycle rescue target",
            "E add scheduled event at selected cell",
            "R remove last scheduled event",
            "Esc quit",
        ]

        y_offset = 20
        for line in lines:
            surface = self.font.render(line, True, TEXT_COLOR)
            self.screen.blit(surface, (panel_x + 16, y_offset))
            y_offset += 24

    def _draw_details_panel(self) -> None:
        panel_x = GRID_MARGIN + self.scenario["grid"]["N"] * CELL_SIZE + 24 + TOOLS_PANEL_WIDTH + CONTROLS_PANEL_WIDTH
        panel = pygame.Rect(panel_x, 0, DETAILS_PANEL_WIDTH, WINDOW_HEIGHT)
        pygame.draw.rect(self.screen, PANEL_COLOR, panel)

        lines = [
            "Status & Details",
            "",
            f"Status: {self.status_message}",
            "",
            f"Active zone: {self.active_zone_id or 'none'}",
            f"Active zone type: {self.selected_zone_type}",
            "",
            f"Scenario id: {self.scenario['metadata'].get('scenario_id', '')}",
            f"Difficulty: {self.scenario['evaluation'].get('expected_difficulty', '')}",
            self._temporal_constraint_summary(),
            f"Scheduled events: {len(self.scenario['scheduled_events'])}",
        ]

        if self.scenario["scheduled_events"]:
            last_event = self.scenario["scheduled_events"][-1]
            lines.extend([
                "",
                "Last scheduled event:",
                f"  id: {last_event.get('event_id', '')}",
                f"  tick: {last_event.get('tick', '')}",
                f"  type: {last_event.get('event_type', '')}",
            ])

        if self.selected_cell is not None:
            x, y = self.selected_cell
            zone_summaries = self._zones_at(x, y, 0)
            agent_at_cell = self._get_agent_at(x, y, self.current_z)
            casualty_at_cell = self._get_casualty_at(x, y, 0)
            building_at_cell = self._get_building_at(x, y, 0)
            lines.extend([
                "",
                "Selected Cell Details:",
                f"  coord: ({x}, {y}, {self.current_z})",
                f"  status: {self._cell_status_name(x, y, self.current_z)}",
                f"  smoke: {self._smoke_density(x, y, self.current_z):.2f}",
                f"  has casualty: {'yes' if casualty_at_cell else 'no'}",
                f"  has agent: {'yes' if agent_at_cell else 'no'}",
                f"  has building: {'yes' if building_at_cell else 'no'}",
                f"  has zone: {'yes' if zone_summaries else 'no'}",
            ])
            if agent_at_cell is not None:
                lines.extend([
                    "",
                    "Agent at cell:",
                    f"  id: {agent_at_cell['id']}",
                    f"  class: {agent_at_cell['agent_class']}",
                    f"  orientation: {agent_at_cell['orientation']}",
                    f"  payload: {agent_at_cell.get('payload_casualty_id')}",
                ])
            if casualty_at_cell is not None:
                lines.extend([
                    "",
                    "Casualty at cell:",
                    f"  id: {casualty_at_cell['id']}",
                    f"  health: {casualty_at_cell['health']}",
                    f"  decay: {casualty_at_cell['decay_rate']}",
                    f"  covered: {casualty_at_cell['is_covered']}",
                    f"  living: {casualty_at_cell['living_state']}",
                    f"  transport: {casualty_at_cell['transport_status']}",
                ])
            if building_at_cell is not None:
                building_cell = next(
                    cell for cell in building_at_cell['cells']
                    if cell['coord'] == {'x': x, 'y': y, 'z': 0}
                )
                lines.extend([
                    "",
                    "Building at cell:",
                    f"  id: {building_at_cell['id']}",
                    f"  integrity: {building_cell['integrity']}",
                    f"  collapsed: {building_cell['collapsed']}",
                ])
            if zone_summaries:
                lines.extend(["", "Zones at cell:"])
                for zone in zone_summaries:
                    lines.append(
                        f"  {zone['id']} | type={zone['zone_type']} | labels={','.join(zone['labels'])}"
                    )

        y_offset = 20 - self.sidebar_scroll_offset
        content_height = self._sidebar_content_height()
        for line in lines:
            if -30 <= y_offset <= WINDOW_HEIGHT:
                surface = self.font.render(line, True, TEXT_COLOR)
                self.screen.blit(surface, (panel_x + 16, y_offset))
            y_offset += 24

        if content_height > WINDOW_HEIGHT:
            track_x = WINDOW_WIDTH - 12
            track_y = 8
            track_h = WINDOW_HEIGHT - 16
            pygame.draw.rect(self.screen, (70, 78, 92), (track_x, track_y, 6, track_h))
            thumb_h = max(40, int(track_h * (WINDOW_HEIGHT / content_height)))
            max_scroll = max(1, content_height - WINDOW_HEIGHT)
            thumb_y = track_y + int((track_h - thumb_h) * (self.sidebar_scroll_offset / max_scroll))
            pygame.draw.rect(self.screen, (180, 190, 205), (track_x, thumb_y, 6, thumb_h))

    def _mouse_in_details_panel(self) -> bool:
        mouse_x, _mouse_y = pygame.mouse.get_pos()
        return mouse_x >= WINDOW_WIDTH - DETAILS_PANEL_WIDTH

    def _screen_to_grid(self, pos: tuple[int, int]) -> tuple[int | None, int | None]:
        px, py = pos
        grid_size = self.scenario["grid"]["N"]
        grid_width = grid_size * CELL_SIZE
        grid_height = grid_size * CELL_SIZE
        if not (GRID_MARGIN <= px < GRID_MARGIN + grid_width and GRID_MARGIN <= py < GRID_MARGIN + grid_height):
            return None, None
        x = (px - GRID_MARGIN) // CELL_SIZE
        y = (py - GRID_MARGIN) // CELL_SIZE
        return int(x), int(y)

    def _cell_color(self, x: int, y: int, z: int) -> tuple[int, int, int]:
        status = self._cell_status_name(x, y, z)
        smoke = self._smoke_density(x, y, z)
        if status == "IMPASSABLE":
            return WALL_COLOR
        if status == "PASSABLE":
            return DEBRIS_COLOR
        if smoke > 0.0:
            intensity = min(255, int(80 + smoke * 120))
            return (intensity, intensity, intensity)
        return (50, 58, 72)

    def _cell_status_name(self, x: int, y: int, z: int) -> str:
        for cell in self.scenario["grid"]["cells"]:
            coord = cell["coord"]
            if coord["x"] == x and coord["y"] == y and coord["z"] == z:
                return cell["status"]
        return "UNOCCUPIED"

    def _smoke_density(self, x: int, y: int, z: int) -> float:
        for smoke in self.scenario["grid"]["smoke"]:
            coord = smoke["coord"]
            if coord["x"] == x and coord["y"] == y and coord["z"] == z:
                return float(smoke["density"])
        return 0.0

    def _set_cell_status(self, coord: dict[str, int], status: str) -> None:
        cells = self.scenario["grid"]["cells"]
        for cell in cells:
            if cell["coord"] == coord:
                cell["status"] = status
                return
        cells.append({"coord": coord, "status": status})

    def _remove_cell_status(self, coord: dict[str, int]) -> None:
        self.scenario["grid"]["cells"] = [
            cell for cell in self.scenario["grid"]["cells"] if cell["coord"] != coord
        ]

    def _set_smoke(self, coord: dict[str, int], density: float) -> None:
        smoke_entries = self.scenario["grid"]["smoke"]
        for smoke in smoke_entries:
            if smoke["coord"] == coord:
                smoke["density"] = density
                return
        smoke_entries.append({"coord": coord, "density": density})

    def _remove_smoke(self, coord: dict[str, int]) -> None:
        self.scenario["grid"]["smoke"] = [
            smoke for smoke in self.scenario["grid"]["smoke"] if smoke["coord"] != coord
        ]

    def _upsert_casualty(self, coord: dict[str, int]) -> None:
        for casualty in self.scenario["casualties"]:
            if casualty["coord"] == coord:
                return
        casualty_id = f"C{len(self.scenario['casualties']) + 1}"
        self.scenario["casualties"].append(
            {
                "id": casualty_id,
                "coord": coord,
                "health": 50.0,
                "decay_rate": 1.0,
                "is_covered": self._cell_status_name(coord["x"], coord["y"], 0) == "PASSABLE",
                "triage_state": "UNKNOWN",
                "transport_status": "ON_GROUND",
                "living_state": "ALIVE",
            }
        )

    def _remove_casualty(self, coord: dict[str, int]) -> None:
        self.scenario["casualties"] = [
            casualty for casualty in self.scenario["casualties"] if casualty["coord"] != coord
        ]

    def _has_casualty(self, x: int, y: int, z: int) -> bool:
        return any(
            casualty["coord"] == {"x": x, "y": y, "z": z}
            for casualty in self.scenario["casualties"]
        )

    def _upsert_agent(self, coord: dict[str, int]) -> None:
        for agent in self.scenario["agents"]:
            if agent["coord"] == coord:
                return
        agent_id = f"A{len(self.scenario['agents']) + 1}"
        agent_class = "UAV" if coord["z"] >= 1 else "UGV"
        self.scenario["agents"].append(
            {
                "id": agent_id,
                "coord": coord,
                "orientation": "NORTH",
                "agent_class": agent_class,
                "busy_ticks_remaining": 0,
                "damage_status": None,
                "payload_casualty_id": None,
            }
        )

    def _remove_agent(self, coord: dict[str, int]) -> None:
        self.scenario["agents"] = [
            agent for agent in self.scenario["agents"] if agent["coord"] != coord
        ]

    def _get_agent_at(self, x: int, y: int, z: int) -> dict[str, Any] | None:
        for agent in self.scenario["agents"]:
            coord = agent["coord"]
            if coord["x"] == x and coord["y"] == y and coord["z"] == z:
                return agent
        return None

    def _ensure_scenario_defaults(self) -> None:
        self.scenario.setdefault("metadata", {})
        self.scenario.setdefault("objectives", {})
        self.scenario.setdefault("evaluation", {})
        self.scenario.setdefault("scheduled_events", [])
        self.scenario.setdefault("zones", [])
        self.scenario["metadata"].setdefault("scenario_id", "editor-scenario")
        self.scenario["metadata"].setdefault("name", "Editor Scenario")
        self.scenario["evaluation"].setdefault("expected_difficulty", "medium")
        self.scenario["objectives"].setdefault("primary_goals", ["stabilize casualties"])
        self.scenario["objectives"].pop("time_budget_ticks", None)

    def _update_selection(self, x: int, y: int, z: int) -> None:
        agent = self._get_agent_at(x, y, z)
        casualty = self._get_casualty_at(x, y, 0)
        building = self._get_building_at(x, y, 0)
        self.selected_agent_id = agent["id"] if agent is not None else None
        self.selected_casualty_id = casualty["id"] if casualty is not None else None
        self.selected_building_id = building["id"] if building is not None else None

    def _selected_agent(self) -> dict[str, Any] | None:
        if self.selected_agent_id is None:
            return None
        for agent in self.scenario["agents"]:
            if agent["id"] == self.selected_agent_id:
                return agent
        return None

    def _selected_casualty(self) -> dict[str, Any] | None:
        if self.selected_casualty_id is None:
            return None
        for casualty in self.scenario["casualties"]:
            if casualty["id"] == self.selected_casualty_id:
                return casualty
        return None

    def _selected_building(self) -> dict[str, Any] | None:
        if self.selected_building_id is None:
            return None
        for building in self.scenario["buildings"]:
            if building["id"] == self.selected_building_id:
                return building
        return None

    def _get_casualty_at(self, x: int, y: int, z: int) -> dict[str, Any] | None:
        for casualty in self.scenario["casualties"]:
            coord = casualty["coord"]
            if coord["x"] == x and coord["y"] == y and coord["z"] == z:
                return casualty
        return None

    def _upsert_building(self, coord: dict[str, int]) -> None:
        existing = self._get_building_at(coord["x"], coord["y"], coord["z"])
        if existing is not None:
            return
        building_id = f"B{len(self.scenario['buildings']) + 1}"
        self.scenario["buildings"].append(
            {
                "id": building_id,
                "cells": [
                    {
                        "coord": coord,
                        "integrity": 0.8,
                        "collapsed": False,
                    }
                ],
            }
        )
        self._set_cell_status(coord, "IMPASSABLE")
        self.selected_building_id = building_id

    def _get_building_at(self, x: int, y: int, z: int) -> dict[str, Any] | None:
        for building in self.scenario["buildings"]:
            for cell in building.get("cells", []):
                coord = cell["coord"]
                if coord["x"] == x and coord["y"] == y and coord["z"] == z:
                    return building
        return None

    def _cycle_agent_orientation(self) -> None:
        agent = self._selected_agent()
        if agent is None:
            self.status_message = "No agent selected"
            return
        orientations = ["NORTH", "EAST", "SOUTH", "WEST"]
        current_index = orientations.index(agent["orientation"])
        agent["orientation"] = orientations[(current_index + 1) % len(orientations)]
        self.status_message = f"Agent {agent['id']} orientation -> {agent['orientation']}"

    def _toggle_selected_agent_class(self) -> None:
        agent = self._selected_agent()
        if agent is None:
            self.status_message = "No agent selected"
            return
        if agent["agent_class"] == "UGV":
            agent["agent_class"] = "UAV"
            agent["coord"]["z"] = max(1, agent["coord"]["z"])
        else:
            agent["agent_class"] = "UGV"
            agent["coord"]["z"] = 0
        self.status_message = f"Agent {agent['id']} class -> {agent['agent_class']}"

    def _adjust_selected_casualty_health(self, delta: float) -> None:
        casualty = self._selected_casualty()
        if casualty is None:
            self.status_message = "No casualty selected"
            return
        casualty["health"] = max(0.0, min(100.0, float(casualty["health"]) + delta))
        self.status_message = f"Casualty {casualty['id']} health -> {casualty['health']}"

    def _adjust_selected_casualty_decay(self, delta: float) -> None:
        casualty = self._selected_casualty()
        if casualty is None:
            self.status_message = "No casualty selected"
            return
        casualty["decay_rate"] = max(0.0, float(casualty["decay_rate"]) + delta)
        self.status_message = f"Casualty {casualty['id']} decay -> {casualty['decay_rate']}"

    def _toggle_selected_casualty_cover(self) -> None:
        casualty = self._selected_casualty()
        if casualty is None:
            self.status_message = "No casualty selected"
            return
        casualty["is_covered"] = not bool(casualty["is_covered"])
        self.status_message = f"Casualty {casualty['id']} covered -> {casualty['is_covered']}"

    def _adjust_selected_building_integrity(self, delta: float) -> None:
        building = self._selected_building()
        if building is None:
            self.status_message = "No building selected"
            return
        cell = building["cells"][0]
        cell["integrity"] = max(0.0, min(1.0, float(cell["integrity"]) + delta))
        self.status_message = f"Building {building['id']} integrity -> {cell['integrity']:.2f}"

    def _toggle_selected_building_collapsed(self) -> None:
        building = self._selected_building()
        if building is None:
            self.status_message = "No building selected"
            return
        cell = building["cells"][0]
        cell["collapsed"] = not bool(cell["collapsed"])
        coord = cell["coord"]
        self._set_cell_status(coord, "PASSABLE" if cell["collapsed"] else "IMPASSABLE")
        self.status_message = f"Building {building['id']} collapsed -> {cell['collapsed']}"

    def _cycle_metadata_difficulty(self) -> None:
        levels = ["easy", "medium", "hard"]
        current = self.scenario["evaluation"].get("expected_difficulty", "medium")
        index = levels.index(current) if current in levels else 1
        next_value = levels[(index + 1) % len(levels)]
        self.scenario["evaluation"]["expected_difficulty"] = next_value
        self.status_message = f"Difficulty -> {next_value}"

    def _temporal_constraint_summary(self) -> str:
        constraint = self.scenario["objectives"].get("temporal_constraint")
        if not constraint:
            return "Rescue constraint: none"
        return (
            f"Rescue target: {constraint['target_count']} casualties in "
            f"{constraint['deadline_cycles']} cycles"
        )

    def _toggle_temporal_constraint(self) -> None:
        objectives = self.scenario["objectives"]
        if objectives.get("temporal_constraint"):
            objectives.pop("temporal_constraint")
            self.status_message = "Rescue constraint disabled"
            return
        objectives["temporal_constraint"] = {
            "type": "rescue_count",
            "target_count": 1,
            "deadline_cycles": 20,
        }
        self.status_message = "Rescue constraint enabled: 1 casualty in 20 cycles"

    def _cycle_constraint_deadline(self) -> None:
        constraint = self.scenario["objectives"].get("temporal_constraint")
        if not constraint:
            self.status_message = "Enable the rescue constraint first (B)"
            return
        deadlines = [20, 50, 100, 200, 500]
        current = int(constraint.get("deadline_cycles", 20))
        index = deadlines.index(current) if current in deadlines else 0
        next_value = deadlines[(index + 1) % len(deadlines)]
        constraint["deadline_cycles"] = next_value
        self.status_message = f"Rescue deadline -> {next_value} cycles"

    def _cycle_rescue_target(self) -> None:
        constraint = self.scenario["objectives"].get("temporal_constraint")
        if not constraint:
            self.status_message = "Enable the rescue constraint first (B)"
            return
        max_target = max(1, len(self.scenario["casualties"]))
        current = int(constraint.get("target_count", 1))
        constraint["target_count"] = 1 if current >= max_target else current + 1
        self.status_message = f"Rescue target -> {constraint['target_count']} casualties"

    def _add_scheduled_event_for_selected_cell(self) -> None:
        if self.selected_cell is None:
            self.status_message = "No cell selected"
            return
        x, y = self.selected_cell
        event_id = f"evt-{len(self.scenario['scheduled_events']) + 1}"
        event = {
            "event_id": event_id,
            "tick": 10 + len(self.scenario["scheduled_events"]) * 5,
            "event_type": "SMOKE_INCREASE",
            "payload": {
                "coord": {"x": x, "y": y, "z": self.current_z},
                "density": 0.8,
            },
        }
        self.scenario["scheduled_events"].append(event)
        self.status_message = f"Added scheduled event {event_id}"

    def _remove_last_scheduled_event(self) -> None:
        if not self.scenario["scheduled_events"]:
            self.status_message = "No scheduled events to remove"
            return
        removed = self.scenario["scheduled_events"].pop()
        self.status_message = f"Removed scheduled event {removed['event_id']}"

    def _toggle_zone_cell(self, coord: dict[str, int]) -> None:
        zone = self._active_zone()
        if zone is None:
            zone = self._create_new_zone()
        if coord in zone["cells"]:
            zone["cells"].remove(coord)
        else:
            zone["cells"].append(coord)

    def _remove_zone_cell(self, coord: dict[str, int]) -> None:
        for zone in self.scenario["zones"]:
            zone["cells"] = [cell for cell in zone.get("cells", []) if cell != coord]

    def _has_zone_cell(self, x: int, y: int, z: int) -> bool:
        coord = {"x": x, "y": y, "z": z}
        return any(coord in zone.get("cells", []) for zone in self.scenario["zones"])

    def _zones_at(self, x: int, y: int, z: int) -> list[dict[str, Any]]:
        coord = {"x": x, "y": y, "z": z}
        return [
            zone for zone in self.scenario["zones"]
            if coord in zone.get("cells", [])
        ]

    def _sync_casualty_cover(self, x: int, y: int, z: int, is_covered: bool) -> None:
        coord = {"x": x, "y": y, "z": z}
        for casualty in self.scenario["casualties"]:
            if casualty["coord"] == coord:
                casualty["is_covered"] = is_covered

    def _save_scenario(self) -> None:
        path = Path("editor/last_scenario.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.scenario, indent=2), encoding="utf-8")
        self.status_message = f"Saved to {path}"

    def _load_scenario(self) -> None:
        path = Path("editor/last_scenario.json")
        if not path.exists():
            self.status_message = "No saved scenario found"
            return
        self.scenario = json.loads(path.read_text(encoding="utf-8"))
        self._ensure_scenario_defaults()
        self._ensure_active_zone()
        self.current_z = min(self.current_z, self.scenario["grid"]["Z"] - 1)
        self.status_message = f"Loaded from {path}"

    def _regenerate_scenario(self) -> None:
        self.scenario = generate_scenario(
            grid_size=self.scenario["grid"]["N"],
            z_depth=self.scenario["grid"]["Z"],
            building_density=0.08,
            hazard_density=0.04,
            casualty_density=0.06,
            debris_density=0.05,
            seed=42,
            agent_count=max(2, len(self.scenario["agents"])),
        )
        self._ensure_scenario_defaults()
        self._ensure_active_zone()
        self.current_z = 0
        self.selected_cell = None
        self.status_message = "Regenerated scenario"

    def _validate_scenario(self) -> None:
        try:
            build_engine_from_scenario_definition(self.scenario)
        except (IndexError, KeyError, TypeError, ValueError) as exc:
            self.status_message = f"Validation failed: {exc}"
            return
        self.status_message = "Scenario validated successfully"

    def _zone_type_options(self) -> list[str]:
        return ["EXTRACTION", "FIELD_HOSPITAL"]

    def _sidebar_content_height(self) -> int:
        base_lines = 11
        extra_lines = 0
        if self.scenario["scheduled_events"]:
            extra_lines += 5
        if self.selected_cell is not None:
            x, y = self.selected_cell
            zone_summaries = self._zones_at(x, y, 0)
            agent_at_cell = self._get_agent_at(x, y, self.current_z)
            casualty_at_cell = self._get_casualty_at(x, y, 0)
            building_at_cell = self._get_building_at(x, y, 0)
            extra_lines += 8
            if agent_at_cell is not None:
                extra_lines += 6
            if casualty_at_cell is not None:
                extra_lines += 8
            if building_at_cell is not None:
                extra_lines += 5
            if zone_summaries:
                extra_lines += 2 + len(zone_summaries)
        return (base_lines + extra_lines) * 24 + 20

    def _scroll_sidebar(self, delta: int) -> None:
        content_height = self._sidebar_content_height()
        max_scroll = max(0, content_height - WINDOW_HEIGHT + 20)
        self.sidebar_scroll_offset = max(0, min(max_scroll, self.sidebar_scroll_offset + delta))

    def _default_labels_for_zone_type(self, zone_type: str) -> list[str]:
        if zone_type == "FIELD_HOSPITAL":
            return ["medical-dropoff", "field-hospital"]
        if zone_type == "EXTRACTION":
            return ["editor", "extraction"]
        return ["editor"]

    def _ensure_active_zone(self) -> None:
        if self.active_zone_id and any(zone.get("id") == self.active_zone_id for zone in self.scenario["zones"]):
            active = self._active_zone()
            if active is not None:
                self.selected_zone_type = str(active.get("zone_type", self.selected_zone_type))
            return
        if self.scenario["zones"]:
            self.active_zone_id = str(self.scenario["zones"][0].get("id", "zone-1"))
            active = self._active_zone()
            if active is not None:
                self.selected_zone_type = str(active.get("zone_type", self.selected_zone_type))
            return
        zone = self._create_new_zone()
        self.active_zone_id = str(zone["id"])
        self.selected_zone_type = str(zone["zone_type"])

    def _active_zone(self) -> dict[str, Any] | None:
        if self.active_zone_id is None:
            return None
        for zone in self.scenario["zones"]:
            if str(zone.get("id")) == self.active_zone_id:
                return zone
        return None

    def _create_new_zone(self) -> dict[str, Any]:
        zone_type = self.selected_zone_type
        prefix = "field-hospital" if zone_type == "FIELD_HOSPITAL" else zone_type.lower().replace("_", "-")
        next_index = 1
        existing_ids = {str(zone.get("id", "")) for zone in self.scenario["zones"]}
        while f"{prefix}-{next_index}" in existing_ids:
            next_index += 1
        zone = {
            "id": f"{prefix}-{next_index}",
            "zone_type": zone_type,
            "cells": [],
            "labels": self._default_labels_for_zone_type(zone_type),
        }
        self.scenario["zones"].append(zone)
        self.active_zone_id = str(zone["id"])
        self.selected_zone_type = zone_type
        self.status_message = f"Created zone {zone['id']} ({zone_type})"
        return zone

    def _cycle_active_zone_type(self) -> None:
        options = self._zone_type_options()
        current_index = options.index(self.selected_zone_type) if self.selected_zone_type in options else 0
        self.selected_zone_type = options[(current_index + 1) % len(options)]
        active = self._active_zone()
        if active is not None:
            active["zone_type"] = self.selected_zone_type
            active["labels"] = self._default_labels_for_zone_type(self.selected_zone_type)
            self.status_message = f"Zone {active['id']} type -> {self.selected_zone_type}"
        else:
            self.status_message = f"Selected zone type -> {self.selected_zone_type}"

    def _cycle_active_zone(self) -> None:
        zones = self.scenario["zones"]
        if not zones:
            self._create_new_zone()
            return
        zone_ids = [str(zone.get("id", "")) for zone in zones]
        if self.active_zone_id not in zone_ids:
            self.active_zone_id = zone_ids[0]
        else:
            current_index = zone_ids.index(self.active_zone_id)
            self.active_zone_id = zone_ids[(current_index + 1) % len(zone_ids)]
        active = self._active_zone()
        if active is not None:
            self.selected_zone_type = str(active.get("zone_type", self.selected_zone_type))
            self.status_message = f"Active zone -> {self.active_zone_id} ({self.selected_zone_type})"


def main() -> None:
    ScenarioEditor().run()


if __name__ == "__main__":
    main()
