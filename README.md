# NaviRoom

NaviRoom is an intelligent room reservation prototype focused on three problems:

1. heterogeneous room data ingestion;
2. zero-shot room recommendation under cold-start conditions;
3. a clean integration surface for future frontend and backend services.

## Current repository structure

- `data_processing/`: data cleaning, schema normalization, and dataset generation.
- `recommendation/`: room recommendation engine and Python-facing API wrappers.
- `frontend/`: current UI prototype.
- `deploy/`: deployment-related configuration.

## Dataset

Current local datasets:

- `data_processing/output/dku_dataset.json`
- `data_processing/output/kaggle_dataset.json`

Expected dataset shape:

```json
{
  "rooms": [...],
  "reservations": [...]
}
```

## Recommendation status

The recommendation module now supports a hybrid zero-shot path:

1. hard constraint filtering on capacity, room type, and equipment;
2. room-profile enrichment from raw room metadata and reservation-side text;
3. hybrid semantic scoring with local semantic hints plus optional DeepSeek LLM scoring;
4. behavior scoring from historical usage when available;
5. cold-start-friendly final weighting so recommendation quality does not collapse when history is sparse.

This is designed to satisfy the proposal requirement that recommendation should still work for newly uploaded datasets without depending entirely on prior booking behavior.

## Backend integration contract

The repository does not yet include a full production backend service, but the recommendation layer now exposes a stable Python integration surface through `recommendation/api.py`.

Primary entry points:

- `recommend_from_dataset_json(user_query, requirements, dataset)`
- `recommend_rooms_payload(payload)`

Recommended backend request shape:

```json
{
  "user_query": "Need a multimedia booth for video practice",
  "requirements": {
    "capacity": 2,
    "duration": 30,
    "time_slot": "afternoon",
    "room_type": "multi-media booth",
    "equipment": ["screen"],
    "preferences": ["quiet"]
  },
  "rooms": [...],
  "reservations": [...]
}
```

Response shape:

```json
[
  {
    "room_id": "M03",
    "final_score": 0.6479,
    "semantic_score": 0.8075,
    "behavior_score": 0.0458,
    "reasons": [
      "matches capacity",
      "matches requested room type",
      "duration differs from typical usage"
    ]
  }
]
```

Suggested backend route contract for later implementation:

- `POST /api/recommendations`
- request body: same as `recommend_rooms_payload(...)`
- response body: same list returned by the recommendation module

## Frontend integration contract

The current `frontend/` directory is still a prototype UI and is not yet wired to the recommendation engine. To integrate cleanly later, the frontend should treat the backend as the single source of truth and submit a payload compatible with `POST /api/recommendations`.

Suggested frontend flow:

1. collect user free-text intent;
2. collect optional structured constraints such as capacity, duration, equipment, and preferred time slot;
3. submit one JSON request to the backend recommendation endpoint;
4. render the ranked room list and explanation reasons returned by the backend.

Suggested frontend request payload:

```ts
interface RecommendationRequest {
  user_query: string;
  requirements?: {
    capacity?: number;
    time_slot?: 'morning' | 'afternoon' | 'evening' | 'night';
    duration?: number;
    room_type?: string;
    equipment?: string[];
    preferences?: string[];
  };
}
```

Suggested frontend response payload:

```ts
interface RecommendationResult {
  room_id: string;
  final_score: number;
  semantic_score: number;
  behavior_score: number;
  reasons: string[];
}
```

## Environment variables

Optional LLM-backed recommendation features use:

- `LLM_API_KEY`
- `RECO_SEMANTIC_MODE`
- `RECO_REQUIREMENTS_MODE`

Recommended modes:

- `RECO_SEMANTIC_MODE=hybrid`: local semantic scoring plus LLM re-scoring when useful.
- `RECO_REQUIREMENTS_MODE=merge`: preserve provided constraints and let the LLM fill only missing fields.

## Validation

Because `pytest` is not installed in the current server virtual environment, validation was done with manual regression checks plus `python -m py_compile recommendation/*.py`.
