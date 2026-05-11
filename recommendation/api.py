from __future__ import annotations

from typing import Any

import os

from .engine import RecommendInput, recommend_top5
from .types import UserRequirements


def _merge_requirements(user_query: str, requirements: dict[str, Any]) -> dict[str, Any]:
    merged = dict(requirements)
    mode = os.getenv("RECO_REQUIREMENTS_MODE", "manual").strip().lower()
    should_extract = bool(user_query) and mode in {"llm", "merge"}
    if (not merged and mode == "llm") or (should_extract and mode == "merge"):
        try:
            from .llm import llm_extract_requirements

            extracted = llm_extract_requirements(user_query=user_query)
            if isinstance(extracted, dict):
                for key, value in extracted.items():
                    if key not in merged or merged.get(key) in (None, "", [], {}):
                        merged[key] = value
        except Exception:
            pass
    return merged


def recommend_rooms_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    user_query = str(payload.get("user_query", ""))
    requirements = payload.get("requirements") or {}
    rooms = payload.get("rooms") or []
    reservations = payload.get("reservations") or []

    if not isinstance(requirements, dict):
        requirements = {}

    requirements = _merge_requirements(user_query, requirements)

    inp = RecommendInput(
        user_query=user_query,
        requirements=requirements,  # type: ignore[assignment]
        rooms=rooms,  # type: ignore[assignment]
        reservations=reservations,  # type: ignore[assignment]
    )
    return recommend_top5(inp)


def recommend_from_dataset_json(*, user_query: str, requirements: UserRequirements, dataset: dict[str, Any]) -> list[dict[str, Any]]:
    rooms = dataset.get("rooms") or []
    reservations = dataset.get("reservations") or []

    if not isinstance(rooms, list) or not isinstance(reservations, list):
        raise ValueError("dataset must contain 'rooms' and 'reservations' arrays")

    merged_requirements = _merge_requirements(user_query, dict(requirements))

    inp = RecommendInput(
        user_query=user_query,
        requirements=merged_requirements,  # type: ignore[arg-type]
        rooms=rooms,  # type: ignore[arg-type]
        reservations=reservations,  # type: ignore[arg-type]
    )
    return recommend_top5(inp)
