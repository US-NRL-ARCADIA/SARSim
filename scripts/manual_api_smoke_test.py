from __future__ import annotations

import json

import httpx


BASE_URL = "http://localhost:8000"


def pretty(obj: object) -> str:
    return json.dumps(obj, indent=2, sort_keys=True)


def init_dev() -> None:
    resp = httpx.post(f"{BASE_URL}/init/dev")
    print("INIT /init/dev:", resp.status_code, resp.text)


def get_state() -> None:
    resp = httpx.get(f"{BASE_URL}/state")
    print("GET /state:", resp.status_code)
    print(pretty(resp.json()))


def step(ticks: int = 1) -> None:
    resp = httpx.post(f"{BASE_URL}/step", json={"ticks": ticks})
    print(f"POST /step ticks={ticks}:", resp.status_code)
    print(pretty(resp.json()))


def queue_move_forward(actor_id: str, action_id: str = "move1") -> None:
    payload = {
        "actions": [
            {
                "action_id": action_id,
                "actor_id": actor_id,
                "action_type": "MOVE_FORWARD",
                "start_tick": 0,
                "duration": 0,
            }
        ]
    }
    resp = httpx.post(f"{BASE_URL}/actions", json=payload)
    print("POST /actions (MOVE_FORWARD):", resp.status_code, resp.text)


def queue_triage(actor_id: str, casualty_id: str, action_id: str = "triage1") -> None:
    payload = {
        "actions": [
            {
                "action_id": action_id,
                "actor_id": actor_id,
                "action_type": "TRIAGE",
                "target_casualty_id": casualty_id,
                "start_tick": 0,
                "duration": 0,
            }
        ]
    }
    resp = httpx.post(f"{BASE_URL}/actions", json=payload)
    print("POST /actions (TRIAGE):", resp.status_code, resp.text)


def main() -> None:
    print("Initializing dev scenario...")
    init_dev()

    print("\nInitial state:")
    get_state()

    print("\nQueue MOVE_FORWARD for A1...")
    queue_move_forward(actor_id="A1")

    print("\nStep 1 tick...")
    step(ticks=1)

    print("\nQueue TRIAGE A1 -> C1...")
    queue_triage(actor_id="A1", casualty_id="C1")

    print("\nStep 1 tick...")
    step(ticks=1)

    print("\nFinal state:")
    get_state()


if __name__ == "__main__":
    main()