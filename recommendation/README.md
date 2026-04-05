# Recommendation module

This folder implements a **3-step room recommendation pipeline**:

1. **Hard constraints filter** (capacity / room_type / equipment)
2. **Semantic recall** (lexical by default, optional DeepSeek LLM scoring)
3. **Behavior-based ranking** (popularity + time-slot usage + duration similarity)

It returns **top 5 rooms** in the strict JSON format required by your prompt.

## Data schema (current)

The code is aligned with your dataset JSON shape:

- Dataset object:
  - `rooms`: array of room objects
  - `reservations`: array of reservation objects

Example path in this repo:
- `data_processing/output/dku_dataset.json`

## API usage (Python)

### 1) Recommend from a dataset JSON

```python
import json
from recommendation.api import recommend_from_dataset_json

with open("data_processing/output/dku_dataset.json", "r", encoding="utf-8") as f:
    dataset = json.load(f)

results = recommend_from_dataset_json(
    user_query="Need a study room with a screen in the afternoon",
    requirements={
        "capacity": 4,
        "time_slot": "afternoon",
        "duration": 60,
        "room_type": "study room",
        "equipment": ["screen"],
        "preferences": ["quiet"],
    },
    dataset=dataset,
)

print(results)  # already JSON-serializable
```

### 2) Recommend from an API-style payload

```python
from recommendation.api import recommend_rooms_payload

payload = {
  "user_query": "study room with screen",
  "requirements": {"capacity": 4, "time_slot": "afternoon", "duration": 60},
  "rooms": [...],
  "reservations": [...],
}

results = recommend_rooms_payload(payload)
```

## Enabling DeepSeek LLM scoring (optional)

This repo already includes a DeepSeek-compatible client in `recommendation/llm.py` (uses the `openai` SDK).

### Environment variables

- `LLM_API_KEY` (required)
- `RECO_SEMANTIC_MODE=llm` enables LLM semantic scoring (Step 2)
- `RECO_REQUIREMENTS_MODE=llm` enables LLM extraction of requirements **only when you pass an empty requirements dict**

Example:

```bash
export LLM_API_KEY='***'
export RECO_SEMANTIC_MODE=llm
# optional
export RECO_REQUIREMENTS_MODE=llm
```

Notes:
- The LLM is asked to return **ONLY JSON**.
- Reasons are constrained to reference only values present in the provided room object and/or the query.
- If the LLM call fails, the system **falls back to lexical scoring**.

## CLI usage

```bash
python -m recommendation.cli \
  --dataset data_processing/output/dku_dataset.json \
  --query "study room with screen" \
  --capacity 4 \
  --time-slot afternoon \
  --duration 60 \
  --room-type "study room" \
  --equipment screen
```

## Output format

The recommender returns a list with up to 5 items:

```json
[
  {
    "room_id": "R1124",
    "final_score": 0.8432,
    "semantic_score": 0.8123,
    "behavior_score": 0.9055,
    "reasons": [
      "matches capacity",
      "has required equipment",
      "frequently used in afternoon",
      "similar duration usage",
      "semantic overlap: screen, study room"
    ]
  }
]
```
