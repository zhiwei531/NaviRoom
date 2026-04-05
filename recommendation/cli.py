from __future__ import annotations

import argparse
import json
from pathlib import Path

from .api import recommend_from_dataset_json


def main() -> int:
    p = argparse.ArgumentParser(description="Recommend rooms from a dataset JSON")
    p.add_argument("--dataset", required=True, help="Path to dataset json (e.g. data_processing/output/dku_dataset.json)")
    p.add_argument("--query", required=True, help="Free-text user query")
    p.add_argument("--capacity", type=int, default=None)
    p.add_argument("--time-slot", dest="time_slot", default=None, choices=["morning", "afternoon", "evening", "night"])
    p.add_argument("--duration", type=int, default=None, help="Duration in minutes")
    p.add_argument("--room-type", dest="room_type", default=None)
    p.add_argument("--equipment", nargs="*", default=None)
    p.add_argument("--preferences", nargs="*", default=None)
    p.epilog = (
        "Env toggles (optional): "
        "RECO_SEMANTIC_MODE=llm enables DeepSeek-based semantic scoring; "
        "RECO_REQUIREMENTS_MODE=llm lets LLM parse requirements when none are provided."
    )
    args = p.parse_args()

    dataset = json.loads(Path(args.dataset).read_text(encoding="utf-8"))

    requirements = {}
    if args.capacity is not None:
        requirements["capacity"] = args.capacity
    if args.time_slot is not None:
        requirements["time_slot"] = args.time_slot
    if args.duration is not None:
        requirements["duration"] = args.duration
    if args.room_type is not None:
        requirements["room_type"] = args.room_type
    if args.equipment is not None:
        requirements["equipment"] = args.equipment
    if args.preferences is not None:
        requirements["preferences"] = args.preferences

    out = recommend_from_dataset_json(user_query=args.query, requirements=requirements, dataset=dataset)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
