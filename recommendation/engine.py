from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable

import os

from .types import BehaviorScores, Reservation, Room, ScoredRoom, SemanticExplanation, UserRequirements
from .utils import clamp01, jaccard, normalize_list, normalize_text, parse_iso_dt, to_time_slot, tokenize_text


@dataclass
class RecommendInput:
    user_query: str
    requirements: UserRequirements
    rooms: list[Room]
    reservations: list[Reservation]


SEMANTIC_HINTS: dict[str, list[str]] = {
    "monitor": ["screen", "display"],
    "screen": ["monitor", "display"],
    "display": ["screen", "monitor"],
    "interview": ["private", "quiet", "booth", "meeting"],
    "zoom": ["online", "meeting", "booth", "screen"],
    "online": ["meeting", "booth", "screen"],
    "video": ["multimedia", "booth", "recording", "screen"],
    "recording": ["video", "multimedia", "booth"],
    "brainstorm": ["whiteboard", "collaboration", "discussion"],
    "presentation": ["screen", "display", "general purpose room"],
    "practice": ["booth", "multimedia", "private"],
    "quiet": ["study room", "private"],
    "private": ["booth", "study room", "quiet"],
    "meeting": ["discussion", "general purpose room", "screen"],
}


RESERVATION_TEXT_KEYS = ("description", "room_type")
RAW_DESCRIPTION_KEYS = ("room_type", "description", "space_type")


def _dedupe(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = normalize_text(value)
        if text and text not in seen:
            out.append(text)
            seen.add(text)
    return out


def _reservation_index(reservations: list[Reservation]) -> dict[str, list[Reservation]]:
    by_room: dict[str, list[Reservation]] = defaultdict(list)
    for reservation in reservations:
        rid = reservation.get("room_id")
        if isinstance(rid, str) and rid.strip():
            by_room[rid].append(reservation)
    return by_room


def _collect_room_aliases(room: Room, room_reservations: list[Reservation]) -> list[str]:
    aliases: list[str] = []
    room_type = room.get("room_type")
    if isinstance(room_type, str):
        aliases.append(room_type)

    raw = room.get("raw_description")
    if isinstance(raw, dict):
        for key in RAW_DESCRIPTION_KEYS:
            value = raw.get(key)
            if isinstance(value, str):
                aliases.append(value)

    for reservation in room_reservations:
        for key in RESERVATION_TEXT_KEYS:
            value = reservation.get(key)
            if isinstance(value, str):
                aliases.append(value)

    raw_tokens = []
    for alias in aliases:
        tokens = tokenize_text(alias)
        raw_tokens.extend(tokens)
        if "multi" in tokens and "media" in tokens:
            raw_tokens.extend(["multimedia", "booth"])
        if "study" in tokens and "room" in tokens:
            raw_tokens.append("quiet")
        if "booth" in tokens:
            raw_tokens.extend(["private", "video", "online"])

    return _dedupe(aliases + raw_tokens)


def _derive_use_cases(room: Room, room_reservations: list[Reservation], aliases: list[str]) -> list[str]:
    use_cases = list(normalize_list(room.get("use_cases")))
    text_blob = " ".join(aliases)
    if "booth" in text_blob:
        use_cases.extend(["online meeting", "video practice", "private call"])
    if "study room" in text_blob:
        use_cases.extend(["quiet study", "individual work"])
    if "whiteboard" in text_blob:
        use_cases.append("brainstorming")
    if "screen" in text_blob:
        use_cases.extend(["presentation", "online interview"])
    for reservation in room_reservations[:20]:
        desc = reservation.get("description")
        if isinstance(desc, str):
            lowered = normalize_text(desc)
            if "people" in lowered:
                use_cases.append(lowered)
    return _dedupe(use_cases)


def _enrich_room(room: Room, room_reservations: list[Reservation]) -> Room:
    enriched: Room = dict(room)
    aliases = _collect_room_aliases(room, room_reservations)
    use_cases = _derive_use_cases(room, room_reservations, aliases)
    enriched["layout"] = _dedupe([*normalize_list(room.get("layout")), *aliases])
    enriched["use_cases"] = use_cases
    description_bits = [
        room.get("description", ""),
        room.get("room_type", ""),
        *aliases,
        *use_cases,
        *normalize_list(room.get("equipment")),
    ]
    enriched["description"] = "; ".join(_dedupe([str(x) for x in description_bits if str(x).strip()]))
    return enriched


def _extract_room_text(room: Room) -> list[str]:
    tokens: list[str] = []
    for key in ("room_type", "description"):
        value = room.get(key)
        if isinstance(value, str):
            tokens.extend(tokenize_text(value))
            tokens.append(normalize_text(value))

    for key in ("layout", "equipment", "use_cases", "accessibility"):
        values = room.get(key)
        if isinstance(values, list):
            for value in values:
                tokens.append(normalize_text(value))
                tokens.extend(tokenize_text(value))

    raw = room.get("raw_description")
    if isinstance(raw, dict):
        for value in raw.values():
            if isinstance(value, str):
                tokens.append(normalize_text(value))
                tokens.extend(tokenize_text(value))

    return _dedupe(tokens)


def _expand_query_terms(user_query: str, requirements: UserRequirements) -> set[str]:
    tokens = set(tokenize_text(user_query))
    phrases = set(normalize_list([user_query]))
    phrases |= set(normalize_list(requirements.get("preferences")))
    room_type = requirements.get("room_type")
    if room_type:
        phrases.add(normalize_text(room_type))
        tokens |= set(tokenize_text(room_type))
    equipment = normalize_list(requirements.get("equipment"))
    phrases |= set(equipment)
    for item in list(tokens) + list(phrases):
        for hint in SEMANTIC_HINTS.get(item, []):
            phrases.add(normalize_text(hint))
            tokens |= set(tokenize_text(hint))
    return {term for term in (tokens | phrases) if term}


def _room_type_candidates(room: Room) -> set[str]:
    candidates: set[str] = set()
    for value in _extract_room_text(room):
        candidates.add(normalize_text(value))
    return {value for value in candidates if value}


# ----------------------------
# STEP 1: FILTER (HARD CONSTRAINTS)
# ----------------------------

def filter_rooms(rooms: Iterable[Room], requirements: UserRequirements) -> list[Room]:
    required_capacity = requirements.get("capacity")
    required_room_type = normalize_text(requirements.get("room_type")) if requirements.get("room_type") else ""
    required_equipment = normalize_list(requirements.get("equipment"))

    candidates: list[Room] = []
    for room in rooms:
        cap = room.get("capacity")
        if required_capacity is not None and isinstance(cap, int):
            if cap < required_capacity:
                continue
        elif required_capacity is not None:
            continue

        if required_room_type:
            room_type_candidates = _room_type_candidates(room)
            if required_room_type not in room_type_candidates:
                required_tokens = set(tokenize_text(required_room_type))
                if not required_tokens or not required_tokens.issubset(set().union(*(set(tokenize_text(v)) for v in room_type_candidates))):
                    continue

        if required_equipment:
            equipment = set(normalize_list(room.get("equipment")))
            if not set(required_equipment).issubset(equipment):
                continue

        candidates.append(room)

    return candidates


# ----------------------------
# STEP 2: SEMANTIC RECALL (MATCHING)
# ----------------------------

def _local_semantic_match(user_query: str, requirements: UserRequirements, room: Room) -> SemanticExplanation:
    query_terms = _expand_query_terms(user_query, requirements)
    room_terms = set(_extract_room_text(room))
    score = clamp01(jaccard(query_terms, room_terms))

    overlap = [term for term in sorted(query_terms & room_terms) if len(term) > 2]
    reasons: list[str] = []
    if overlap:
        reasons.append(f"semantic match: {', '.join(overlap[:6])}")
    else:
        reasons.append("semantic match is weak")

    if any("booth" in term for term in room_terms) and any(term in query_terms for term in {"video", "interview", "online", "practice"}):
        score = max(score, 0.45)
        reasons.insert(0, "room profile suggests private booth-style usage")

    if "screen" in room_terms and any(term in query_terms for term in {"monitor", "display", "presentation", "online"}):
        score = max(score, 0.35)
        reasons.insert(0, "screen feature matches monitor/display intent")

    return SemanticExplanation(score=score, reasons=_dedupe(reasons))


def semantic_match(user_query: str, requirements: UserRequirements, room: Room) -> SemanticExplanation:
    mode = os.getenv("RECO_SEMANTIC_MODE", "hybrid").strip().lower()
    local = _local_semantic_match(user_query, requirements, room)

    should_call_llm = mode == "llm" or local.score >= 0.08 or any(term in set(_extract_room_text(room)) for term in {"booth", "screen", "whiteboard", "study room"})

    if mode in {"llm", "hybrid", "zero_shot"} and should_call_llm:
        try:
            from .llm import llm_score_relevance

            score, llm_reasons = llm_score_relevance(user_query=user_query, room_features=room)
            llm_score = clamp01(float(score))
            if mode == "llm":
                return SemanticExplanation(score=llm_score, reasons=llm_reasons or local.reasons)
            combined = clamp01(0.35 * local.score + 0.65 * llm_score)
            reasons = _dedupe([*(llm_reasons or []), *local.reasons])
            return SemanticExplanation(score=combined, reasons=reasons[:4])
        except Exception:
            pass

    return local


# ----------------------------
# STEP 3: BEHAVIOR-BASED RANKING
# ----------------------------

def _behavior_model(reservations: list[Reservation]):
    by_room = _reservation_index(reservations)
    room_booking_counts = {rid: len(items) for rid, items in by_room.items()}
    max_count = max(room_booking_counts.values(), default=0)

    room_time_slot_counts: dict[str, Counter[str]] = {}
    room_durations: dict[str, list[int]] = {}

    for rid, items in by_room.items():
        counter: Counter[str] = Counter()
        durations: list[int] = []
        for item in items:
            start_time = item.get("start_time")
            if isinstance(start_time, str):
                try:
                    counter[to_time_slot(parse_iso_dt(start_time))] += 1
                except Exception:
                    pass

            duration = item.get("duration_minutes")
            if isinstance(duration, int) and duration > 0:
                durations.append(duration)

        room_time_slot_counts[rid] = counter
        room_durations[rid] = durations

    return by_room, room_booking_counts, max_count, room_time_slot_counts, room_durations


def behavior_scores(room_id: str, requirements: UserRequirements, model) -> BehaviorScores:
    by_room, room_booking_counts, max_count, room_time_slot_counts, room_durations = model

    popularity = room_booking_counts.get(room_id, 0) / max_count if max_count > 0 else 0.0

    requested_slot = requirements.get("time_slot")
    time_match = 0.0
    if requested_slot:
        counter = room_time_slot_counts.get(room_id, Counter())
        total = sum(counter.values())
        if total > 0:
            time_match = counter.get(requested_slot, 0) / total

    requested_duration = requirements.get("duration")
    duration_match = 0.0
    if isinstance(requested_duration, int) and requested_duration > 0:
        durations = room_durations.get(room_id, [])
        if durations:
            avg = sum(durations) / len(durations)
            rel_err = abs(avg - requested_duration) / max(requested_duration, 1)
            duration_match = clamp01(1.0 - rel_err)

    return BehaviorScores(
        popularity=clamp01(popularity),
        time_match=clamp01(time_match),
        duration_match=clamp01(duration_match),
    )


# ----------------------------
# FINAL SCORING
# ----------------------------

def rule_score(room: Room, requirements: UserRequirements) -> tuple[float, list[str]]:
    reasons: list[str] = []
    required_capacity = requirements.get("capacity")
    cap = room.get("capacity")

    score = 0.45
    if isinstance(required_capacity, int) and isinstance(cap, int) and cap >= required_capacity:
        reasons.append("matches capacity")
        cap_fit = required_capacity / cap if cap > 0 else 0.0
        score = 0.45 + 0.35 * clamp01(cap_fit)
    elif required_capacity is not None:
        score = 0.0

    req_eq = normalize_list(requirements.get("equipment"))
    if req_eq:
        eq = set(normalize_list(room.get("equipment")))
        if set(req_eq).issubset(eq):
            reasons.append("has required equipment")
            score = clamp01(score + 0.15)

    req_rt = requirements.get("room_type")
    if req_rt and normalize_text(req_rt) in _room_type_candidates(room):
        reasons.append("matches requested room type")
        score = clamp01(score + 0.1)

    return clamp01(score), reasons


def _score_weights(requirements: UserRequirements, history_count: int) -> tuple[float, float, float]:
    behavior_requested = bool(requirements.get("time_slot")) or isinstance(requirements.get("duration"), int)
    if history_count <= 0:
        return 0.55, 0.35, 0.10
    if behavior_requested:
        return 0.5, 0.3, 0.2
    return 0.55, 0.35, 0.10


def recommend_top5(inp: RecommendInput) -> list[ScoredRoom]:
    model = _behavior_model(inp.reservations)
    by_room = model[0]
    enriched_rooms = [_enrich_room(room, by_room.get(str(room.get("room_id")), [])) for room in inp.rooms]
    candidates = filter_rooms(enriched_rooms, inp.requirements)

    scored: list[tuple[float, ScoredRoom]] = []
    for room in candidates:
        rid = room.get("room_id")
        if not isinstance(rid, str) or not rid:
            continue

        sem = semantic_match(inp.user_query, inp.requirements, room)
        beh = behavior_scores(rid, inp.requirements, model)
        rule, rule_reasons = rule_score(room, inp.requirements)

        sem_w, rule_w, beh_w = _score_weights(inp.requirements, len(by_room.get(rid, [])))
        final = clamp01(sem_w * sem.score + rule_w * rule + beh_w * beh.behavior_score)

        reasons: list[str] = []
        reasons.extend(rule_reasons)
        if inp.requirements.get("time_slot"):
            reasons.append(
                f"historically used in {inp.requirements['time_slot']}" if beh.time_match >= 0.5 else f"some {inp.requirements['time_slot']} usage history"
            )
        if isinstance(inp.requirements.get("duration"), int):
            reasons.append("duration aligns with past usage" if beh.duration_match >= 0.7 else "duration differs from typical usage")
        reasons.extend(sem.reasons[:2])

        scored_room: ScoredRoom = {
            "room_id": rid,
            "final_score": round(final, 4),
            "semantic_score": round(clamp01(sem.score), 4),
            "behavior_score": round(clamp01(beh.behavior_score), 4),
            "reasons": _dedupe(reasons)[:6],
        }
        scored.append((final, scored_room))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [room for _, room in scored[:5]]
