from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class EventType(Enum):
    CASUALTY_HEALTH_UPDATED = auto()
    ACTION_COMPLETED = auto()
    ACTION_FAILED = auto()
    BUILDING_COLLAPSED = auto()
    SCHEDULED_EVENT_TRIGGERED = auto()
    SCENARIO_ENDED = auto()


@dataclass
class Event:
    """Simple event record for engine activity."""

    tick: int
    event_type: EventType
    message: str
    actor_id: str | None = None
    payload: dict[str, object] | None = None
