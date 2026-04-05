from __future__ import annotations

import json
import os
from typing import Any

from .engine import RecommendInput, recommend_top5
from .types import Reservation, Room, UserRequirements


def recommend_rooms_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """API-friendly wrapper.

    Expected payload keys:
      - user_query: str
      - requirements: dict
      - rooms: list[dict]
      - reservations: list[dict]

    Returns: top-5 list in the strict JSON shape required by the prompt.
    """

    user_query = str(payload.get("user_query", ""))
    requirements = payload.get("requirements") or {}
    rooms = payload.get("rooms") or []
    reservations = payload.get("reservations") or []

    if not isinstance(requirements, dict):
        requirements = {}

    # Optional: let LLM extract structured requirements if caller didn't provide them.
    # This never invents room fields; it only parses the user query.
    if not requirements and os.getenv("RECO_REQUIREMENTS_MODE", "manual").strip().lower() == "llm":
        try:
            from .llm import llm_extract_requirements

            extracted = llm_extract_requirements(user_query=user_query)
            if isinstance(extracted, dict):
                requirements = extracted
        except Exception:
            pass

    inp = RecommendInput(
        user_query=user_query,
        requirements=requirements,  # type: ignore[assignment]
        rooms=rooms,  # type: ignore[assignment]
        reservations=reservations,  # type: ignore[assignment]
    )

    return recommend_top5(inp)


def recommend_from_dataset_json(
    *,
    user_query: str,
    requirements: UserRequirements,
    dataset: dict[str, Any],
) -> list[dict[str, Any]]:
    rooms = dataset.get("rooms") or []
    reservations = dataset.get("reservations") or []

    if not isinstance(rooms, list) or not isinstance(reservations, list):
        raise ValueError("dataset must contain 'rooms' and 'reservations' arrays")

    inp = RecommendInput(
        user_query=user_query,
        requirements=requirements,
        rooms=rooms,  # type: ignore[arg-type]
        reservations=reservations,  # type: ignore[arg-type]
    )
    return recommend_top5(inp)
