from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional


def parse_iso_dt(value: str) -> datetime:
    # Dataset uses e.g. 2025-04-29T14:50:00
    return datetime.fromisoformat(value)


def to_time_slot(dt: datetime) -> str:
    h = dt.hour
    if 6 <= h < 12:
        return "morning"
    if 12 <= h < 17:
        return "afternoon"
    if 17 <= h < 22:
        return "evening"
    return "night"


def normalize_list(values: Optional[Iterable[str]]) -> list[str]:
    if not values:
        return []
    return [str(v).strip().lower() for v in values if str(v).strip()]


def clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)
