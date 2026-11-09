from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from .grid import Coordinate


class EngineActionType(Enum):
    MOVE_FORWARD = auto()
    TRIAGE = auto()
    CLEAR_DEBRIS = auto()
    RETRIEVE_BODY = auto()
    LOAD_CASUALTY = auto()
    UNLOAD_CASUALTY = auto()
    TRANSFER_CASUALTY = auto()
    BREACH_ENTRYWAY = auto()
    ASCEND = auto()
    DESCEND = auto()
    TURN_LEFT = auto()
    TURN_RIGHT = auto()


@dataclass
class EngineAction:
    """A scheduled high-level action in the simulation engine."""

    action_id: str
    actor_id: str
    action_type: EngineActionType
    target_casualty_id: str | None = None
    target_coord: Coordinate | None = None
    start_tick: int = 0
    duration: int = 0
    completed: bool = False
    failed: bool = False
    failure_reason: str | None = None

    def ready_to_apply(self, current_tick: int) -> bool:
        return (
            not (self.completed or self.failed)
            and current_tick >= self.start_tick + self.duration
        )
