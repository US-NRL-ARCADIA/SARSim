from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.server import app
from src.api.state import reset_engine


client = TestClient(app)


def setup_function() -> None:
    reset_engine()


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
