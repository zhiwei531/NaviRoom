# Recommendation module

This folder implements a cold-start-friendly room recommendation pipeline for NaviRoom.

## Pipeline overview

1. hard constraints filter on `capacity`, `room_type`, and `equipment`;
2. room profile enrichment from `raw_description` and reservation-side metadata;
3. hybrid zero-shot semantic scoring;
4. behavior-based scoring from usage history when available;
5. final weighted ranking with reduced dependence on history under sparse-data conditions.

## What changed

The previous implementation relied too heavily on lexical overlap and historical behavior. That was not sufficient for the proposal target of zero-shot recommendation.

The current implementation adds:

- semantic alias handling such as `monitor -> screen`;
- room-type recovery from `raw_description`, e.g. `Multi-Media Booth` even when canonical `room_type` is generic;
- derived room use cases such as `video practice`, `online meeting`, and `online interview`;
- optional LLM requirement completion that can merge with partially provided structured constraints;
- a hybrid semantic path where local matching remains available even if the LLM is unavailable.

## Data schema

Expected dataset object:

```json
{
  "rooms": [...],
  "reservations": [...]
}
```

The current repo includes:

- `data_processing/output/dku_dataset.json`
- `data_processing/output/kaggle_dataset.json`

## Python API

### 1. Recommend from a dataset object

```python
import json
from recommendation.api import recommend_from_dataset_json

with open("data_processing/output/dku_dataset.json", "r", encoding="utf-8") as f:
    dataset = json.load(f)

results = recommend_from_dataset_json(
    user_query="Need a multimedia booth for video practice",
    requirements={
        "capacity": 2,
        "duration": 30,
        "room_type": "multi-media booth",
    },
    dataset=dataset,
)
```

### 2. Recommend from a backend-style payload

```python
from recommendation.api import recommend_rooms_payload

payload = {
    "user_query": "Need a place for an online interview with a monitor",
    "requirements": {
        "capacity": 1,
        "duration": 60,
        "equipment": ["screen"]
    },
    "rooms": [...],
    "reservations": [...],
}

results = recommend_rooms_payload(payload)
```

## Integration surface for backend services

If you later add Flask/FastAPI/Django routes, the intended wrapper is:

```python
from recommendation.api import recommend_rooms_payload

# pseudo-code
@app.post('/api/recommendations')
def recommend_route(payload: dict):
    return recommend_rooms_payload(payload)
```

Backend responsibilities should be limited to:

- authentication and authorization;
- tenant-specific dataset loading;
- request validation;
- calling `recommend_rooms_payload(...)`;
- returning the JSON result to frontend clients.

## Integration surface for frontend clients

Frontend clients should not reproduce recommendation logic locally. They should only submit:

- user free-text query;
- optional structured constraints;
- then render the ranked response list.

Suggested request body:

```json
{
  "user_query": "Need a quiet room for a team brainstorm with whiteboard",
  "requirements": {
    "capacity": 4,
    "time_slot": "evening",
    "duration": 90,
    "equipment": ["whiteboard"]
  }
}
```

## Environment variables

- `LLM_API_KEY`: required for DeepSeek-backed semantic scoring or requirement extraction.
- `RECO_SEMANTIC_MODE`: `lexical`, `llm`, `hybrid`, or `zero_shot`.
- `RECO_REQUIREMENTS_MODE`: `manual`, `llm`, or `merge`.

Recommended defaults:

```bash
export RECO_SEMANTIC_MODE=hybrid
export RECO_REQUIREMENTS_MODE=merge
```

## Validation notes

Current server validation used:

- `python -m py_compile recommendation/*.py`
- manual regression checks for:
  - `Need a multimedia booth for video practice`
  - `Need a place for an online interview with a monitor`
  - `need a study room with screen and whiteboard in the afternoon`
