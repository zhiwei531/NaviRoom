from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, NotRequired, TypedDict


TimeSlot = Literal["morning", "afternoon", "evening", "night"]


class UserRequirements(TypedDict, total=False):
    capacity: int
    time_slot: TimeSlot
    duration: int  # minutes
    preferences: list[str]
    room_type: str
    equipment: list[str]


class Room(TypedDict, total=False):
    room_id: str
    floor: int
    capacity: int
    equipment: list[str]
    layout: list[str]
    use_cases: list[str]
    accessibility: list[str]
    room_type: str
    raw_description: dict[str, Any]
    description: str


class Reservation(TypedDict, total=False):
    room_id: str
    start_time: str
    end_time: str
    duration_minutes: int
    status: str
    request_date: str
    description: str
    room_type: str


class ScoredRoom(TypedDict):
    room_id: str
    final_score: float
    semantic_score: float
    behavior_score: float
    reasons: list[str]


@dataclass
class SemanticExplanation:
    score: float
    reasons: list[str] = field(default_factory=list)


@dataclass
class BehaviorScores:
    popularity: float
    time_match: float
    duration_match: float

    @property
    def behavior_score(self) -> float:
        # equal weights inside behavior
        return (self.popularity + self.time_match + self.duration_match) / 3.0
