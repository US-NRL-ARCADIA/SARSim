from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.server import UI_DIR, app
from src.api.state import reset_engine

client = TestClient(app)


def setup_function() -> None:
    reset_engine()


def test_root_serves_integrated_application() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "SARSim Studio" in response.text
    assert "/ui/app.js" in response.text


def test_health_endpoint() -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_static_ui_assets_are_served() -> None:
    assert UI_DIR.parent.name == "src"
    assert UI_DIR.name == "ui"

    response = client.get("/ui/app.js")

    assert response.status_code == 200
    assert "GoldenLayout" in response.text

    styles_response = client.get("/ui/styles.css")
    assert styles_response.status_code == 200
    assert "--bg: #e9eef4" in styles_response.text
    assert ".cell.passable" in styles_response.text
    assert ".legend-group" in styles_response.text

    logo_response = client.get("/ui/nrl-official.jpg")
    assert logo_response.status_code == 200
    assert logo_response.headers["content-type"] == "image/jpeg"

    scene_response = client.get("/ui/scene3d.js")
    assert scene_response.status_code == 200
    assert "THREE.WebGLRenderer" in scene_response.text
    assert "Drag to orbit" in scene_response.text
    assert "hospitalCasualtyStackLevels" in scene_response.text
    assert "hospitalStackLevel * casualtyStackHeight" in scene_response.text
    assert "buildVisibilityFootprint" in scene_response.text
    assert "options.visibleCells" in scene_response.text
    assert "applyVisibilityGhosting" in scene_response.text
    assert "visibleCellKeys" in scene_response.text
    assert "subject.ghosted = true" in scene_response.text
    assert ".filter(canSee)" not in scene_response.text

    three_response = client.get("/ui/vendor/three.module.js")
    assert three_response.status_code == 200
    assert "from './three.core.js'" in three_response.text

    three_core_response = client.get("/ui/vendor/three.core.js")
    assert three_core_response.status_code == 200
    assert "const REVISION = '187';" in three_core_response.text

    three_license_response = client.get("/ui/vendor/THREE_LICENSE.txt")
    assert three_license_response.status_code == 200
    assert "Copyright © 2010-2026 three.js authors" in three_license_response.text


def test_ui_exposes_keyboard_controls_scenario_picker_and_map_legend() -> None:
    app_js = client.get("/ui/app.js").text
    index_html = client.get("/").text

    assert "U.S. Naval Research Laboratory" in index_html
    assert 'src="/ui/nrl-official.jpg"' in index_html
    assert 'document.addEventListener("keydown"' in app_js
    assert 'KeyW:"NORTH"' in app_js
    assert 'c:"KeyC"' in app_js
    assert 'code==="KeyC"' in app_js
    assert "cycleControlledAgent" in app_js
    assert 'code==="Space"' in app_js
    assert 'event.stopPropagation()' in app_js
    assert 'data-control="scenario"' in app_js
    assert 'aria-label="Map legend"' in app_js
    assert "UNOCCUPIED" in app_js
    assert "PASSABLE" in app_js
    assert "IMPASSABLE" in app_js
    assert "Field hospital" in app_js
    assert 'if(app.runtime?.ended)' in app_js
    assert 'data-editor-field="casualty-health"' in app_js
    assert 'data-editor-field="casualty-decay"' in app_js
    assert 'data-editor-field="building-integrity"' in app_js
    assert 'data-editor-field="constraint-enabled"' in app_js
    assert 'data-editor-action="add-event"' in app_js
    assert 'data-editor-action="new-zone"' in app_js
    assert "Stack building cells on any level" in app_js
    assert "Placed building level" in app_js
    assert 'data-editor-field="sensor-regime"' in app_js
    assert 'data-editor-field="sensor-range"' in app_js
    assert "MINIGRID_3" in app_js
    assert 'scene3d.js?v=5' in app_js
    assert "runtimeVisibility" in app_js
    assert 'class="sensor-banner"' in app_js
    assert "visibleCells:runtimeVisibility()" in app_js
    styles = client.get("/ui/styles.css").text
    assert ".cell.unseen" in styles
    assert "filter: grayscale(1)" in styles
    assert "isVisible?cellBadge" not in app_js
    assert "isVisible?(a?" not in app_js
    assert 'transport_status!=="LOADED"&&sees(c)' not in app_js
    assert 'data-workspace-mode="simulation"' in index_html
    assert 'data-workspace-mode="editing"' in index_html
    assert 'simulation:["simulator","scene3d","controls","inspector","events"]' in app_js
    assert "Gymnasium API" not in app_js
    assert "Gymnasium API" not in index_html
    assert "Load demo" not in app_js
    assert 'data-command="init"' not in app_js
    assert "loadedScenario" not in app_js
    assert 'post("/scenario/reset")' in app_js
    assert 'post("/reset")' not in app_js
    assert "Scenario reset to its initial state" in app_js
    assert (
        'editing:["editor","editor3d","editorTools","editorProperties",'
        '"editorScenario","json"]'
        in app_js
    )


def test_bundled_scenarios_are_listed_and_loadable() -> None:
    response = client.get("/scenarios")

    assert response.status_code == 200
    scenarios = response.json()
    assert len(scenarios) >= 10
    assert [scenario["path"] for scenario in scenarios] == sorted(
        scenario["path"] for scenario in scenarios
    )
    field_hospital = next(
        scenario
        for scenario in scenarios
        if scenario["path"] == "editor/field_hospital_transport_scenario.json"
    )
    assert field_hospital["name"] == "Field Hospital Transport Demo Scenario"
    assert "designated field hospital" in field_hospital["description"]
    assert field_hospital["sensor_regime"] == "MINIGRID_3"
    regimes = {scenario["sensor_regime"] for scenario in scenarios}
    assert regimes == {"FULL", "FOV_CONE", "MINIGRID_3"}
    assert sum(scenario["sensor_regime"] != "FULL" for scenario in scenarios) >= 10

    showcase_expectations = {
        "editor/vertical_city_rescue.json": (8, 10),
        "editor/transit_hub_collapse.json": (8, 9),
        "editor/harbor_refinery_emergency.json": (10, 12),
    }
    showcase_sensor_regimes = {
        "editor/vertical_city_rescue.json": "FOV_CONE",
        "editor/transit_hub_collapse.json": "MINIGRID_3",
        "editor/harbor_refinery_emergency.json": "FULL",
    }
    available_paths = {scenario["path"] for scenario in scenarios}
    assert showcase_expectations.keys() <= available_paths
    for path, (agent_count, casualty_count) in showcase_expectations.items():
        showcase_response = client.post(
            "/scenario/load-from-path",
            json={"filepath": path},
        )
        assert showcase_response.status_code == 200
        showcase = client.get("/state").json()
        assert showcase["perception"]["regime"] == showcase_sensor_regimes[path]
        assert len(showcase["agents"]) == agent_count
        assert len(showcase["casualties"]) == casualty_count
        positions = {
            (agent["x"], agent["y"], agent["z"])
            for agent in showcase["agents"].values()
        }
        assert len(positions) == agent_count
        assert any(
            cell["z"] > 0
            for building in showcase["buildings"].values()
            for cell in building["cells"]
        )

    load_response = client.post(
        "/scenario/load-from-path",
        json={"filepath": field_hospital["path"]},
    )
    assert load_response.status_code == 200
    state = client.get("/state").json()
    assert state["agents"]["A1"]["orientation"] == "NORTH"
    assert state["zones"][0]["zone_type"] == "FIELD_HOSPITAL"


def test_editor_can_regenerate_the_former_desktop_editor_scenario() -> None:
    response = client.post(
        "/scenario/generate",
        json={"grid_size": 8, "z_depth": 2, "agent_count": 3, "seed": 42},
    )

    assert response.status_code == 200
    scenario = response.json()
    assert scenario["grid"]["N"] == 8
    assert scenario["grid"]["Z"] == 2
    assert len(scenario["agents"]) == 3
    assert scenario["metadata"]["seed"] == 42
    assert scenario["zones"][0]["zone_type"] == "EXTRACTION"
    assert client.post(
        "/scenario/validate",
        json={"scenario": scenario},
    ).status_code == 200
    assert any(
        any(cell["coord"]["z"] > 0 for cell in building["cells"])
        for building in scenario["buildings"]
    )


def test_scenario_rejects_agents_at_the_same_coordinate() -> None:
    scenario = {
        "grid": {"N": 4, "Z": 2},
        "agents": [
            {
                "id": "A1",
                "coord": {"x": 1, "y": 1, "z": 0},
                "orientation": "NORTH",
                "agent_class": "UGV",
            },
            {
                "id": "A2",
                "coord": {"x": 1, "y": 1, "z": 0},
                "orientation": "SOUTH",
                "agent_class": "UGV",
            },
        ],
    }

    response = client.post("/scenario/validate", json={"scenario": scenario})

    assert response.status_code == 422
    assert "cannot share coordinate (1, 1, 0)" in response.json()["detail"]


def test_ui_loads_populated_workspace_after_render_helpers_are_initialized() -> None:
    app_js = client.get("/ui/app.js").text

    assert app_js.index("const esc=") < app_js.rindex("start();")
    assert "LayoutConfig.fromResolved" in app_js
    assert 'componentType:"controls"' in app_js
    assert 'componentType:"simulator"' in app_js
    assert 'componentType:"scene3d"' in app_js
    assert 'componentType:"editor"' in app_js
    assert 'componentType:"editor3d"' in app_js
    assert 'componentType:"editorTools"' in app_js
    assert 'componentType:"editorProperties"' in app_js
    assert 'componentType:"editorScenario"' in app_js
    assert 'componentType:"events"' in app_js
    assert 'componentType:"gym"' not in app_js
    assert "layoutKeys[app.mode]" in app_js


def test_get_state_initially_empty() -> None:
    response = client.get("/state")
    assert response.status_code == 200

    payload = response.json()
    assert payload["tick"] == 0
    assert payload["agents"] == {}
    assert payload["casualties"] == {}
    assert payload["buildings"] == {}
    assert payload["temporal_constraint"] is None
    assert payload["ended"] is False
    assert payload["success"] is None


def test_scenario_deadline_is_reported_and_step_stops_at_it() -> None:
    response = client.post("/scenario/load", json={"scenario": {
        "grid": {"N": 4, "Z": 1},
        "agents": [],
        "casualties": [],
        "objectives": {"temporal_constraint": {
            "type": "rescue_count", "target_count": 1, "deadline_cycles": 2,
        }},
    }})
    assert response.status_code == 200

    payload = client.post("/step", json={"ticks": 5}).json()
    assert payload["tick"] == 2
    assert payload["temporal_constraint"] == {
        "type": "rescue_count", "target_count": 1, "deadline_cycles": 2,
        "rescued_count": 0, "cycles_remaining": 0,
    }
    assert payload["ended"] is True
    assert payload["success"] is False

    client.post("/step", json={"ticks": 1})
    assert client.get("/state").json()["tick"] == 2
    assert client.post("/actions", json={"actions": [{
        "action_id": "after-end", "actor_id": "A1", "action_type": "TURN_LEFT",
    }]}).status_code == 409


def test_unconstrained_scenario_has_no_implicit_deadline() -> None:
    client.post("/scenario/load", json={"scenario": {"grid": {"N": 4, "Z": 1}}})
    payload = client.post("/step", json={"ticks": 150}).json()

    assert payload["tick"] == 150
    assert payload["temporal_constraint"] is None
    assert payload["ended"] is False


def test_init_dev_populates_state() -> None:
    init_response = client.post("/init/dev")
    assert init_response.status_code == 200
    assert init_response.json() == {"status": "ok"}

    state_response = client.get("/state")
    assert state_response.status_code == 200
    payload = state_response.json()

    assert "A1" in payload["agents"]
    assert "C1" in payload["casualties"]
    assert payload["agents"]["A1"]["x"] == 1
    assert payload["agents"]["A1"]["y"] == 1
    assert payload["casualties"]["C1"]["x"] == 1
    assert payload["casualties"]["C1"]["y"] == 2
    assert payload["temporal_constraint"]["target_count"] == 1
    assert payload["temporal_constraint"]["deadline_cycles"] == 20
    assert payload["temporal_constraint"]["rescued_count"] == 0
    assert payload["ended"] is False
    assert "observation" in payload["agents"]["A1"]
    assert "belief" in payload["agents"]["A1"]


def test_init_dev_restarts_an_ended_mission_from_clean_state() -> None:
    client.post("/init/dev")
    client.post("/actions", json={"actions": [{
        "action_id": "move-before-restart",
        "actor_id": "A1",
        "action_type": "MOVE_FORWARD",
    }]})
    client.post("/step", json={"ticks": 20})
    assert client.get("/state").json()["ended"] is True

    response = client.post("/init/dev")
    state = client.get("/state").json()

    assert response.status_code == 200
    assert state["tick"] == 0
    assert state["ended"] is False
    assert (state["agents"]["A1"]["x"], state["agents"]["A1"]["y"]) == (1, 1)
    assert client.post("/actions", json={"actions": [{
        "action_id": "move-after-restart",
        "actor_id": "A1",
        "action_type": "MOVE_FORWARD",
    }]}).status_code == 200


def test_current_scenario_can_be_validated_without_replacing_state() -> None:
    client.post("/init/dev")
    scenario_response = client.get("/scenario/current")
    assert scenario_response.status_code == 200
    scenario = scenario_response.json()
    assert scenario["grid"]["N"] == client.get("/state").json()["grid_size"]
    assert scenario["agents"][0]["id"] == "A1"

    validation_response = client.post("/scenario/validate", json={"scenario": scenario})
    assert validation_response.status_code == 200
    assert validation_response.json() == {
        "status": "ok",
        "agents": 1,
        "casualties": 1,
        "buildings": 0,
        "zones": 1,
    }
    assert client.get("/state").json()["agents"]["A1"]["x"] == 1


def test_invalid_authored_scenario_returns_422_and_preserves_state() -> None:
    client.post("/init/dev")
    invalid = {
        "grid": {
            "N": 4,
            "Z": 1,
            "cells": [
                {"coord": {"x": 0, "y": 0, "z": 0}, "status": "NOT_A_STATUS"}
            ],
        }
    }

    validation_response = client.post("/scenario/validate", json={"scenario": invalid})
    load_response = client.post("/scenario/load", json={"scenario": invalid})

    assert validation_response.status_code == 422
    assert "Invalid scenario" in validation_response.json()["detail"]
    assert load_response.status_code == 422
    assert "A1" in client.get("/state").json()["agents"]


def test_agent_state_includes_observation_and_belief_after_step() -> None:
    client.post("/init/dev")

    response = client.post("/step", json={"ticks": 1})
    assert response.status_code == 200
    payload = response.json()

    agent = payload["agents"]["A1"]
    assert agent["observation"] is not None
    assert isinstance(agent["observation"]["cone_samples"], list)
    assert isinstance(agent["observation"]["radial_samples"], list)
    assert agent["belief"] is not None
    assert isinstance(agent["belief"]["cells"], list)
    if agent["belief"]["cells"]:
        cell = agent["belief"]["cells"][0]
        assert "last_update_tick" in cell
        assert "last_seen_tick" in cell
        assert "ever_observed" in cell
        assert "currently_visible" in cell
        assert "last_known_cell_status" in cell


def test_queue_action_and_step_updates_state() -> None:
    client.post("/init/dev")

    queue_response = client.post(
        "/actions",
        json={
            "actions": [
                {
                    "action_id": "move1",
                    "actor_id": "A1",
                    "action_type": "MOVE_FORWARD",
                    "start_tick": 0,
                    "duration": 0,
                }
            ]
        },
    )
    assert queue_response.status_code == 200
    assert queue_response.json() == {"status": "ok"}

    step_response = client.post("/step", json={"ticks": 1})
    assert step_response.status_code == 200
    payload = step_response.json()

    assert payload["tick"] == 1
    assert payload["agents"]["A1"]["x"] == 1
    assert payload["agents"]["A1"]["y"] == 0
    assert payload["agents"]["A1"]["z"] == 0


def test_step_advances_tick_and_casualty_health() -> None:
    client.post("/init/dev")

    response = client.post("/step", json={"ticks": 2})
    assert response.status_code == 200
    payload = response.json()

    assert payload["tick"] == 2
    assert payload["casualties"]["C1"]["health"] == 48.0


def test_telemetry_endpoint_returns_agent_frames() -> None:
    client.post("/init/dev")
    client.post("/step", json={"ticks": 1})

    response = client.get("/telemetry")
    assert response.status_code == 200
    payload = response.json()

    assert isinstance(payload, list)
    assert len(payload) >= 1
    frame = payload[0]
    assert "tick" in frame
    assert "agent_id" in frame
    assert "observation" in frame
    assert "belief" in frame


def test_reset_clears_state() -> None:
    client.post("/init/dev")
    reset_response = client.post("/reset")
    assert reset_response.status_code == 200
    assert reset_response.json() == {"status": "ok"}

    state_response = client.get("/state")
    payload = state_response.json()
    assert payload["tick"] == 0
    assert payload["agents"] == {}
    assert payload["casualties"] == {}
    assert payload["buildings"] == {}


def test_scenario_reset_restores_the_original_loaded_state() -> None:
    scenario = {
        "grid": {"N": 4, "Z": 1, "cells": [], "smoke": []},
        "agents": [{
            "id": "A1",
            "coord": {"x": 1, "y": 1, "z": 0},
            "orientation": "EAST",
            "agent_class": "UGV",
        }],
        "casualties": [{
            "id": "C1",
            "coord": {"x": 2, "y": 2, "z": 0},
            "health": 80.0,
            "decay_rate": 2.0,
            "is_covered": False,
            "triage_state": "UNKNOWN",
            "transport_status": "ON_GROUND",
            "living_state": "ALIVE",
        }],
    }
    assert client.post("/scenario/load", json={"scenario": scenario}).status_code == 200
    assert client.post("/step", json={"ticks": 3}).status_code == 200
    changed = client.get("/state").json()
    assert changed["tick"] == 3
    assert changed["casualties"]["C1"]["health"] == 74.0

    reset_response = client.post("/scenario/reset")

    assert reset_response.status_code == 200
    restored = client.get("/state").json()
    assert restored["tick"] == 0
    assert restored["agents"]["A1"]["x"] == 1
    assert restored["agents"]["A1"]["orientation"] == "EAST"
    assert restored["casualties"]["C1"]["health"] == 80.0
    assert restored["events"] == []

    client.post("/step", json={"ticks": 1})
    assert client.post("/scenario/reset").status_code == 200
    assert client.get("/state").json()["tick"] == 0


def test_scenario_reset_requires_an_active_scenario() -> None:
    response = client.post("/scenario/reset")

    assert response.status_code == 409
    assert response.json()["detail"] == "No active scenario is available to reset"


def test_scenario_sensor_regime_is_validated_and_exposed_with_visibility() -> None:
    scenario = {
        "grid": {"N": 6, "Z": 1, "cells": [], "smoke": []},
        "agents": [{
            "id": "A1",
            "coord": {"x": 2, "y": 4, "z": 0},
            "orientation": "NORTH",
            "agent_class": "UGV",
        }],
        "casualties": [],
        "perception": {
            "regime": "MINIGRID_3",
            "range": 3,
            "cone_angle_degrees": 90,
        },
    }

    response = client.post("/scenario/load", json={"scenario": scenario})
    state = client.get("/state").json()

    assert response.status_code == 200
    assert state["perception"]["regime"] == "MINIGRID_3"
    assert state["perception"]["range"] == 3
    visible = state["perception"]["visible_cells_by_agent"]["A1"]
    assert len(visible) == 9
    assert {cell["x"] for cell in visible} == {1, 2, 3}
    assert {cell["y"] for cell in visible} == {2, 3, 4}

    scenario["perception"]["regime"] = "THERMAL_XRAY"
    invalid = client.post("/scenario/validate", json={"scenario": scenario})
    assert invalid.status_code == 422
    assert "perception.regime" in invalid.json()["detail"]


def test_step_rejects_non_positive_ticks() -> None:
    response = client.post("/step", json={"ticks": 0})
    assert response.status_code == 422


def test_actions_reject_empty_batch() -> None:
    response = client.post("/actions", json={"actions": []})
    assert response.status_code == 422


def test_triage_action_requires_target_casualty_id() -> None:
    response = client.post(
        "/actions",
        json={
            "actions": [
                {
                    "action_id": "triage1",
                    "actor_id": "A1",
                    "action_type": "TRIAGE",
                    "start_tick": 0,
                    "duration": 0,
                }
            ]
        },
    )
    assert response.status_code == 422


def test_clear_debris_action_requires_target_coord() -> None:
    response = client.post(
        "/actions",
        json={
            "actions": [
                {
                    "action_id": "clear1",
                    "actor_id": "A1",
                    "action_type": "CLEAR_DEBRIS",
                    "start_tick": 0,
                    "duration": 0,
                }
            ]
        },
    )
    assert response.status_code == 422


def test_move_forward_rejects_irrelevant_target_fields() -> None:
    response = client.post(
        "/actions",
        json={
            "actions": [
                {
                    "action_id": "move1",
                    "actor_id": "A1",
                    "action_type": "MOVE_FORWARD",
                    "start_tick": 0,
                    "duration": 0,
                    "target_casualty_id": "C1",
                }
            ]
        },
    )
    assert response.status_code == 200
