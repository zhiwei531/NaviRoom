from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Optional

import os

from .types import BehaviorScores, Reservation, Room, ScoredRoom, SemanticExplanation, UserRequirements
from .utils import clamp01, jaccard, normalize_list, parse_iso_dt, to_time_slot


@dataclass
class RecommendInput:
    user_query: str
    requirements: UserRequirements
    rooms: list[Room]
    reservations: list[Reservation]


def _extract_room_text(room: Room) -> list[str]:
    tokens: list[str] = []
    for key in ("room_type",):
        v = room.get(key)
        if isinstance(v, str) and v.strip():
            tokens.append(v.strip().lower())

    for key in ("layout", "equipment", "use_cases", "accessibility"):
        vals = room.get(key)
        if isinstance(vals, list):
            tokens.extend([str(x).strip().lower() for x in vals if str(x).strip()])

    desc = room.get("description")
    if isinstance(desc, str) and desc.strip():
        tokens.append(desc.strip().lower())

    raw = room.get("raw_description")
    if isinstance(raw, dict):
        # include string-ish values only
        for v in raw.values():
            if isinstance(v, str) and v.strip():
                tokens.append(v.strip().lower())

    # de-dup while preserving order
    seen: set[str] = set()
    uniq: list[str] = []
    for t in tokens:
        if t not in seen:
            uniq.append(t)
            seen.add(t)
    return uniq


# ----------------------------
# STEP 1: FILTER (HARD CONSTRAINTS)
# ----------------------------

def filter_rooms(rooms: Iterable[Room], requirements: UserRequirements) -> list[Room]:
    required_capacity = requirements.get("capacity")
    required_room_type = requirements.get("room_type")
    required_equipment = normalize_list(requirements.get("equipment"))

    candidates: list[Room] = []
    for r in rooms:
        cap = r.get("capacity")
        if required_capacity is not None and isinstance(cap, int):
            if cap < required_capacity:
                continue
        elif required_capacity is not None:
            # missing/invalid capacity => can't satisfy hard constraint
            continue

        if required_room_type:
            rt = r.get("room_type")
            if not isinstance(rt, str) or rt.strip().lower() != str(required_room_type).strip().lower():
                continue

        if required_equipment:
            eq = set(normalize_list(r.get("equipment")))
            if not set(required_equipment).issubset(eq):
                continue

        candidates.append(r)

    return candidates


# ----------------------------
# STEP 2: SEMANTIC RECALL (MATCHING)
# ----------------------------

def semantic_match(user_query: str, requirements: UserRequirements, room: Room) -> SemanticExplanation:
    # Semantic scorer is pluggable.
    # Default: lexical token overlap.
    # Optional: LLM scoring (DeepSeek) enabled via RECO_SEMANTIC_MODE=llm.
    mode = os.getenv("RECO_SEMANTIC_MODE", "lexical").strip().lower()
    if mode == "llm":
        try:
            from .llm import llm_score_relevance

            score, llm_reasons = llm_score_relevance(
                user_query=user_query,
                room_features=room,
            )
            rr = llm_reasons if llm_reasons else ["llm semantic score"]
            return SemanticExplanation(score=clamp01(float(score)), reasons=rr)
        except Exception:
            # Fall back to lexical if LLM is unavailable.
            pass

    # No external embeddings: use token overlap between query+preferences and room features.
    # Score = jaccard(query_tokens, room_tokens)
    query_tokens = set(normalize_list(user_query.split()))

    # include explicit preferences as tokens
    prefs = normalize_list(requirements.get("preferences"))
    query_tokens |= set(prefs)

    # include explicit desired room_type/equipment as tokens, if present
    if requirements.get("room_type"):
        query_tokens.add(str(requirements["room_type"]).strip().lower())
    query_tokens |= set(normalize_list(requirements.get("equipment")))

    room_tokens = set(_extract_room_text(room))

    score = clamp01(jaccard(query_tokens, room_tokens))

    reasons: list[str] = []
    # brief, data-backed reasons only
    overlap = sorted(list(query_tokens & room_tokens))
    if overlap:
        reasons.append(f"semantic overlap: {', '.join(overlap[:6])}" + ("" if len(overlap) <= 6 else " ..."))
    else:
        reasons.append("no strong semantic overlap")

    return SemanticExplanation(score=score, reasons=reasons)


# ----------------------------
# STEP 3: BEHAVIOR-BASED RANKING
# ----------------------------

def _behavior_model(reservations: list[Reservation]):
    # Precompute per-room stats.
    by_room: dict[str, list[Reservation]] = defaultdict(list)
    for r in reservations:
        rid = r.get("room_id")
        if isinstance(rid, str) and rid.strip():
            by_room[rid].append(r)

    room_booking_counts = {rid: len(items) for rid, items in by_room.items()}
    max_count = max(room_booking_counts.values(), default=0)

    room_time_slot_counts: dict[str, Counter[str]] = {}
    room_durations: dict[str, list[int]] = {}

    for rid, items in by_room.items():
        c: Counter[str] = Counter()
        durations: list[int] = []
        for it in items:
            st = it.get("start_time")
            if isinstance(st, str):
                try:
                    slot = to_time_slot(parse_iso_dt(st))
                    c[slot] += 1
                except Exception:
                    pass

            d = it.get("duration_minutes")
            if isinstance(d, int) and d > 0:
                durations.append(d)

        room_time_slot_counts[rid] = c
        room_durations[rid] = durations

    return room_booking_counts, max_count, room_time_slot_counts, room_durations


def behavior_scores(
    room_id: str,
    requirements: UserRequirements,
    model,
) -> BehaviorScores:
    room_booking_counts, max_count, room_time_slot_counts, room_durations = model

    # popularity
    popularity = 0.0
    if max_count > 0:
        popularity = room_booking_counts.get(room_id, 0) / max_count

    # time match
    requested_slot = requirements.get("time_slot")
    time_match = 0.0
    if requested_slot:
        c = room_time_slot_counts.get(room_id, Counter())
        total = sum(c.values())
        if total > 0:
            time_match = c.get(requested_slot, 0) / total

    # duration match
    requested_duration = requirements.get("duration")
    duration_match = 0.0
    if isinstance(requested_duration, int) and requested_duration > 0:
        durations = room_durations.get(room_id, [])
        if durations:
            avg = sum(durations) / len(durations)
            # convert to similarity: 1 when exact; decays with relative error
            rel_err = abs(avg - requested_duration) / max(requested_duration, 1)
            duration_match = clamp01(1.0 - rel_err)

    return BehaviorScores(popularity=clamp01(popularity), time_match=clamp01(time_match), duration_match=clamp01(duration_match))


# ----------------------------
# FINAL SCORING
# ----------------------------

def rule_score(room: Room, requirements: UserRequirements) -> tuple[float, list[str]]:
    # "how well constraints are satisfied" without hallucinating.
    # Capacity: prefer tight fit (less wasted seats) but must be >=.
    reasons: list[str] = []

    required_capacity = requirements.get("capacity")
    cap = room.get("capacity")

    score = 0.5  # neutral baseline for rule satisfaction

    if isinstance(required_capacity, int) and isinstance(cap, int) and cap >= required_capacity:
        reasons.append("matches capacity")
        # tight fit: 1.0 when exact, trending to 0.0 as it gets much larger
        # cap_fit = required/cap
        cap_fit = required_capacity / cap if cap > 0 else 0.0
        score = 0.5 + 0.5 * clamp01(cap_fit)
    elif required_capacity is not None:
        # should have been filtered, but keep safe
        score = 0.0

    req_eq = normalize_list(requirements.get("equipment"))
    if req_eq:
        eq = set(normalize_list(room.get("equipment")))
        if set(req_eq).issubset(eq):
            reasons.append("has required equipment")
            score = clamp01(score + 0.1)

    req_rt = requirements.get("room_type")
    if req_rt:
        rt = room.get("room_type")
        if isinstance(rt, str) and rt.strip().lower() == str(req_rt).strip().lower():
            reasons.append("matches required room type")
            score = clamp01(score + 0.1)

    return clamp01(score), reasons


def recommend_top5(inp: RecommendInput) -> list[ScoredRoom]:
    # Step 1
    candidates = filter_rooms(inp.rooms, inp.requirements)

    # Step 3 model precompute
    model = _behavior_model(inp.reservations)

    scored: list[tuple[float, ScoredRoom]] = []

    for room in candidates:
        rid = room.get("room_id")
        if not isinstance(rid, str) or not rid:
            continue

        # Step 2
        sem = semantic_match(inp.user_query, inp.requirements, room)

        # Step 3
        beh = behavior_scores(rid, inp.requirements, model)
        behavior_score = beh.behavior_score

        # Rule score
        r_score, r_reasons = rule_score(room, inp.requirements)

        final = clamp01(0.4 * sem.score + 0.4 * behavior_score + 0.2 * r_score)

        reasons: list[str] = []
        reasons.extend(r_reasons)
        # behavior reasons must reflect data (only when requirement present)
        if inp.requirements.get("time_slot"):
            reasons.append(f"frequently used in {inp.requirements['time_slot']}" if beh.time_match >= 0.5 else f"used in {inp.requirements['time_slot']} sometimes")
        if isinstance(inp.requirements.get("duration"), int):
            reasons.append("similar duration usage" if beh.duration_match >= 0.7 else "duration differs from historical average")
        # semantic reason
        reasons.extend(sem.reasons[:1])

        scored_room: ScoredRoom = {
            "room_id": rid,
            "final_score": round(final, 4),
            "semantic_score": round(clamp01(sem.score), 4),
            "behavior_score": round(clamp01(behavior_score), 4),
            "reasons": reasons[:6],
        }
        scored.append((final, scored_room))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [sr for _, sr in scored[:5]]
