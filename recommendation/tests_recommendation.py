from __future__ import annotations

import json
from pathlib import Path

from recommendation.api import recommend_from_dataset_json


def test_recommendation_returns_top5_shape():
    dataset_path = Path("data_processing/output/dku_dataset.json")
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))

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
        for k in ("final_score", "semantic_score", "behavior_score"):
            assert isinstance(item[k], float)
            assert 0.0 <= item[k] <= 1.0
        assert isinstance(item["reasons"], list)
        assert all(isinstance(r, str) for r in item["reasons"])
