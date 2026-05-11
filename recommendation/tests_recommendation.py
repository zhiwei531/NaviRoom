from __future__ import annotations

import json
from pathlib import Path

from recommendation.api import recommend_from_dataset_json


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
