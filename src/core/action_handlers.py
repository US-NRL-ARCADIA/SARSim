from __future__ import annotations

from typing import Optional

from .actions import EngineAction, EngineActionType
from .agents import ascend, move_forward, turn_left, turn_right, descend
from .buildings import BuildingCell
from .interactions import breach_entryway, clear_debris, load_casualty, retrieve_body, transfer_casualty_to_hospital, triage, unload_casualty


def apply_action(engine: object, action: EngineAction) -> None:
    actor = engine.agents.get(action.actor_id)
    if actor is None:
        _fail_action(engine, action, "ACTOR_NOT_FOUND", f"Actor {action.actor_id} not found for action {action.action_id}")
        return

    if actor.busy_ticks_remaining > 0:
        _fail_action(engine, action, "ACTOR_BUSY", f"Actor {actor.id} is busy for action {action.action_id}", actor_id=actor.id)
        return

    if action.duration > 0:
        actor.busy_ticks_remaining = action.duration

    if action.action_type is EngineActionType.MOVE_FORWARD:
        success, reason = move_forward(actor, engine.grid)
        if success:
            _complete_action(engine, action, actor.id, f"Agent {actor.id} moved forward.")
        else:
            _fail_action(engine, action, reason, f"Agent {actor.id} failed to move: {reason}", actor_id=actor.id)
        return

    if action.action_type is EngineActionType.TRIAGE:
        casualty = _require_casualty(engine, action)
        if casualty is None:
            return
        success, reason = triage(actor, casualty, stable_decay_rate=0.5)
        if success:
            _complete_action(
                engine,
                action,
                actor.id,
                f"Agent {actor.id} triaged casualty {casualty.id}.",
                {"casualty_id": casualty.id},
            )
        else:
            _fail_action(engine, action, reason, f"Agent {actor.id} failed triage: {reason}", actor_id=actor.id, payload={"casualty_id": casualty.id})
        return

    if action.action_type is EngineActionType.CLEAR_DEBRIS:
        coord = _require_coord(engine, action)
        if coord is None:
            return
        success, reason = clear_debris(actor, engine.grid, coord=coord, casualties=engine.casualties)
        if success:
            _complete_action(engine, action, actor.id, f"Agent {actor.id} cleared debris at {coord}.", {"coord": coord.__dict__})
        else:
            _fail_action(engine, action, reason, f"Agent {actor.id} failed clear_debris: {reason}", actor_id=actor.id, payload={"coord": coord.__dict__})
        return

    if action.action_type is EngineActionType.RETRIEVE_BODY:
        casualty = _require_casualty(engine, action)
        if casualty is None:
            return
        success, reason = retrieve_body(actor, casualty)
        if success:
            _complete_action(
                engine,
                action,
                actor.id,
                f"Agent {actor.id} retrieved casualty {casualty.id}.",
                {"casualty_id": casualty.id},
            )
        else:
            _fail_action(engine, action, reason, f"Agent {actor.id} failed retrieve: {reason}", actor_id=actor.id, payload={"casualty_id": casualty.id})
        return

    if action.action_type is EngineActionType.LOAD_CASUALTY:
        casualty = _require_casualty(engine, action)
        if casualty is None:
            return
        success, reason = load_casualty(
            actor,
            casualty,
            engine.hospital_casualty_ids_by_zone,
        )
        if success:
            _complete_action(
                engine,
                action,
                actor.id,
                f"Agent {actor.id} loaded casualty {casualty.id}.",
                {"casualty_id": casualty.id},
            )
        else:
            _fail_action(engine, action, reason, f"Agent {actor.id} failed load_casualty: {reason}", actor_id=actor.id, payload={"casualty_id": casualty.id})
        return

    if action.action_type is EngineActionType.UNLOAD_CASUALTY:
        success, reason = unload_casualty(actor)
        if success:
            _complete_action(
                engine,
                action,
                actor.id,
                f"Agent {actor.id} unloaded casualty.",
            )
        else:
            _fail_action(engine, action, reason, f"Agent {actor.id} failed unload_casualty: {reason}", actor_id=actor.id)
        return

    if action.action_type is EngineActionType.TRANSFER_CASUALTY:
        casualty_id = actor.payload.id if actor.payload is not None else None
        success, reason, zone_id = transfer_casualty_to_hospital(
            actor,
            engine.zones,
            engine.hospital_casualty_ids_by_zone,
        )
        if success:
            if casualty_id is not None:
                engine.rescued_casualty_ids.add(casualty_id)
            _complete_action(
                engine,
                action,
                actor.id,
                f"Agent {actor.id} transferred casualty to field hospital {zone_id}.",
                {"zone_id": zone_id},
            )
        else:
            _fail_action(engine, action, reason, f"Agent {actor.id} failed transfer_casualty: {reason}", actor_id=actor.id)
        return

    if action.action_type is EngineActionType.BREACH_ENTRYWAY:
        coord = _require_coord(engine, action)
        if coord is None:
            return
        building_cell = _find_building_cell(engine, coord)
        if building_cell is None:
            _fail_action(engine, action, "BUILDING_CELL_NOT_FOUND", f"Building cell not found at {coord}", actor_id=actor.id)
            return
        success, reason = breach_entryway(actor, engine.grid, building_cell)
        if success:
            _complete_action(engine, action, actor.id, f"Agent {actor.id} breached entryway at {coord}.", {"coord": coord.__dict__})
        else:
            _fail_action(engine, action, reason, f"Agent {actor.id} failed breach: {reason}", actor_id=actor.id, payload={"coord": coord.__dict__})
        return

    if action.action_type is EngineActionType.ASCEND:
        success, reason = ascend(actor, engine.grid)
        if success:
            _complete_action(engine, action, actor.id, f"Agent {actor.id} ascended.")
        else:
            _fail_action(engine, action, reason, f"Agent {actor.id} failed ascend: {reason}", actor_id=actor.id)
        return

    if action.action_type is EngineActionType.DESCEND:
        success, reason = descend(actor, engine.grid)
        if success:
            _complete_action(engine, action, actor.id, f"Agent {actor.id} descended.")
        else:
            _fail_action(engine, action, reason, f"Agent {actor.id} failed descend: {reason}", actor_id=actor.id)
        return

    if action.action_type is EngineActionType.TURN_LEFT:
        turn_left(actor)
        _complete_action(engine, action, actor.id, f"Agent {actor.id} turned left.")
        return

    if action.action_type is EngineActionType.TURN_RIGHT:
        turn_right(actor)
        _complete_action(engine, action, actor.id, f"Agent {actor.id} turned right.")
        return

    _fail_action(engine, action, "UNKNOWN_ACTION_TYPE", f"Unknown action type for {action.action_id}", actor_id=actor.id)


def _complete_action(
    engine: object,
    action: EngineAction,
    actor_id: str,
    message: str,
    payload: Optional[dict[str, object]] = None,
) -> None:
    action.completed = True
    event_payload = {"action_id": action.action_id}
    if payload is not None:
        event_payload.update(payload)
    engine.log_event(engine.event_type_enum.ACTION_COMPLETED, message, actor_id=actor_id, payload=event_payload)


def _fail_action(
    engine: object,
    action: EngineAction,
    reason: str,
    message: str,
    actor_id: Optional[str] = None,
    payload: Optional[dict[str, object]] = None,
) -> None:
    action.failed = True
    action.failure_reason = reason
    event_payload = {"action_id": action.action_id, "reason": reason}
    if payload is not None:
        event_payload.update(payload)
    engine.log_event(engine.event_type_enum.ACTION_FAILED, message, actor_id=actor_id, payload=event_payload)


def _require_casualty(engine: object, action: EngineAction) -> object | None:
    if action.target_casualty_id is None:
        action.failed = True
        action.failure_reason = "MISSING_TARGET_CASUALTY"
        return None
    casualty = engine.casualties.get(action.target_casualty_id)
    if casualty is None:
        action.failed = True
        action.failure_reason = "CASUALTY_NOT_FOUND"
        return None
    return casualty


def _require_coord(engine: object, action: EngineAction) -> object | None:
    if action.target_coord is None:
        action.failed = True
        action.failure_reason = "MISSING_TARGET_COORD"
        return None
    return action.target_coord


def _find_building_cell(engine: object, coord: object) -> Optional[BuildingCell]:
    key = (coord.x, coord.y, coord.z)
    for building in engine.buildings.values():
        if key in building.cells:
            return building.cells[key]
    return None
