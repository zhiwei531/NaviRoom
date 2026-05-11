from __future__ import annotations

import json
from pathlib import Path

from recommendation.api import recommend_from_dataset_json, recommend_rooms_payload


def _load_dataset():
    dataset_path = Path("data_processing/output/dku_dataset.json")
    return json.loads(dataset_path.read_text(encoding="utf-8"))


def test_recommendation_returns_top5_shape():
    dataset = _load_dataset()

    out = recommend_from_dataset_json(
        user_query="need a study room with screen and whiteboard in the afternoon",
        requirements={
            "capacity": 4,
            "time_slot": "afternoon",
            "duration": 60,
            "room_type": "study room",
            "equipment": ["screen", "whiteboard"],
            "preferences": ["quiet"],
        },
        dataset=dataset,
    )

    assert isinstance(out, list)
    assert 1 <= len(out) <= 5

    for item in out:
        assert set(item.keys()) == {"room_id", "final_score", "semantic_score", "behavior_score", "reasons"}
        assert isinstance(item["room_id"], str) and item["room_id"]
        for key in ("final_score", "semantic_score", "behavior_score"):
            assert isinstance(item[key], float)
            assert 0.0 <= item[key] <= 1.0
        assert isinstance(item["reasons"], list)
        assert all(isinstance(reason, str) for reason in item["reasons"])


def test_zero_shot_query_recovers_multimedia_booth_without_exact_room_type_match():
    dataset = _load_dataset()

    out = recommend_from_dataset_json(
        user_query="Need a multimedia booth for video practice",
        requirements={"capacity": 2, "duration": 30, "room_type": "multi-media booth"},
        dataset=dataset,
    )

    top_ids = [item["room_id"] for item in out[:3]]
    assert "M01" in top_ids or "M02" in top_ids or "M03" in top_ids


def test_zero_shot_monitor_query_maps_to_screen_equipment():
    dataset = _load_dataset()

    out = recommend_from_dataset_json(
        user_query="Need a place for an online interview with a monitor",
        requirements={"capacity": 1, "duration": 60, "equipment": ["screen"]},
        dataset=dataset,
    )

    assert out
    assert out[0]["semantic_score"] >= 0.3
    assert any("screen" in reason or "booth" in reason or "monitor" in reason for reason in out[0]["reasons"])


def test_availability_filter_removes_overlapping_room():
    payload = {
        "user_query": "Need a study room for a 10am team meeting",
        "requirements": {
            "capacity": 4,
            "requested_start": "2026-05-12T10:00:00",
            "requested_end": "2026-05-12T11:00:00",
        },
        "rooms": [
            {"room_id": "A", "capacity": 4, "equipment": ["screen"], "room_type": "study room"},
            {"room_id": "B", "capacity": 4, "equipment": ["screen"], "room_type": "study room"},
        ],
        "reservations": [
            {
                "room_id": "A",
                "start_time": "2026-05-12T10:15:00",
                "end_time": "2026-05-12T10:45:00",
                "status": "confirmed",
                "duration_minutes": 30,
            },
            {
                "room_id": "B",
                "start_time": "2026-05-12T12:00:00",
                "end_time": "2026-05-12T13:00:00",
                "status": "confirmed",
                "duration_minutes": 60,
            },
        ],
    }

    out = recommend_rooms_payload(payload)
    assert out
    assert out[0]["room_id"] == "B"
    assert all(item["room_id"] != "A" for item in out)
    assert "available for the requested time window" in out[0]["reasons"]


def test_recent_usage_outweighs_old_usage_for_behavior_score():
    payload = {
        "user_query": "Need a morning study room",
        "requirements": {
            "capacity": 2,
            "time_slot": "morning",
            "requested_start": "2026-05-12T09:00:00",
            "requested_end": "2026-05-12T10:00:00",
        },
        "rooms": [
            {"room_id": "RECENT", "capacity": 2, "equipment": [], "room_type": "study room"},
            {"room_id": "OLD", "capacity": 2, "equipment": [], "room_type": "study room"},
        ],
        "reservations": [
            {
                "room_id": "RECENT",
                "start_time": "2026-05-10T09:00:00",
                "end_time": "2026-05-10T10:00:00",
                "status": "completed",
                "duration_minutes": 60,
            },
            {
                "room_id": "OLD",
                "start_time": "2025-01-10T09:00:00",
                "end_time": "2025-01-10T10:00:00",
                "status": "completed",
                "duration_minutes": 60,
            },
        ],
    }

    out = recommend_rooms_payload(payload)
    assert out[0]["room_id"] == "RECENT"
    assert out[0]["behavior_score"] > out[1]["behavior_score"]


def test_llm_rerank_is_limited_to_shortlist():
    import os
    from unittest.mock import patch

    payload = {
        "user_query": "Need a screen room",
        "requirements": {"capacity": 1},
        "rooms": [
            {"room_id": "R1", "capacity": 1, "equipment": ["screen"], "room_type": "study room"},
            {"room_id": "R2", "capacity": 1, "equipment": ["screen"], "room_type": "study room"},
            {"room_id": "R3", "capacity": 1, "equipment": ["screen"], "room_type": "study room"},
            {"room_id": "R4", "capacity": 1, "equipment": ["screen"], "room_type": "study room"},
        ],
        "reservations": [],
    }

    old_mode = os.environ.get("RECO_SEMANTIC_MODE")
    old_top_k = os.environ.get("RECO_LLM_TOP_K")
    os.environ["RECO_SEMANTIC_MODE"] = "hybrid"
    os.environ["RECO_LLM_TOP_K"] = "2"

    calls = []

    def fake_llm_score_relevance(*, user_query, room_features, cfg=None):
        calls.append(room_features["room_id"])
        return 0.8, [f"llm rerank for {room_features['room_id']}"]

    try:
        with patch("recommendation.llm.llm_score_relevance", side_effect=fake_llm_score_relevance):
            out = recommend_rooms_payload(payload)
        assert out
        assert len(calls) == 2, calls
    finally:
        if old_mode is None:
            os.environ.pop("RECO_SEMANTIC_MODE", None)
        else:
            os.environ["RECO_SEMANTIC_MODE"] = old_mode
        if old_top_k is None:
            os.environ.pop("RECO_LLM_TOP_K", None)
        else:
            os.environ["RECO_LLM_TOP_K"] = old_top_k
