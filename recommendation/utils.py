from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable, Optional


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def parse_iso_dt(value: str) -> datetime:
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


def normalize_text(value: object) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("_", " ").replace("-", " ").replace("/", " ")
    return " ".join(text.split())


def tokenize_text(value: object) -> list[str]:
    text = normalize_text(value)
    if not text:
        return []
    return _TOKEN_RE.findall(text)


def normalize_list(values: Optional[Iterable[str]]) -> list[str]:
    if not values:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for v in values:
        text = normalize_text(v)
        if text and text not in seen:
            out.append(text)
            seen.add(text)
    return out


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


def overlaps(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    return start_a < end_b and start_b < end_a


def minutes_between(start: datetime, end: datetime) -> int:
    return int((end - start).total_seconds() // 60)
