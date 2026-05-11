from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Optional

from dotenv import load_dotenv
from openai import OpenAI


@dataclass(frozen=True)
class LLMConfig:
    api_key_env: str = "LLM_API_KEY"
    base_url: str = "https://api.deepseek.com/v1"
    chat_model: str = "deepseek-chat"
    timeout_s: float = 15.0


def _client(cfg: LLMConfig) -> OpenAI:
    load_dotenv()
    api_key = os.getenv(cfg.api_key_env)
    if not api_key:
        raise RuntimeError(f"Missing env var {cfg.api_key_env} for LLM API key")
    return OpenAI(api_key=api_key, base_url=cfg.base_url)


def _extract_json_payload(content: str) -> dict[str, Any]:
    content = (content or "").strip()
    if not content:
        return {}

    candidates = [content]
    if "```json" in content:
        for part in content.split("```json"):
            if "```" in part:
                candidates.append(part.split("```", 1)[0].strip())
    if "```" in content:
        for part in content.split("```"):
            stripped = part.strip()
            if stripped.startswith("{") and stripped.endswith("}"):
                candidates.append(stripped)

    start = content.find("{")
    end = content.rfind("}")
    if 0 <= start < end:
        candidates.append(content[start : end + 1])

    for candidate in candidates:
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except Exception:
            continue
    return {}


def clamp_score(score: float) -> float:
    if score < 0.0:
        score = 0.0
    if score > 1.0:
        score = 1.0
    return score


def llm_score_relevance(*, user_query: str, room_features: dict[str, Any], cfg: Optional[LLMConfig] = None) -> tuple[float, list[str]]:
    cfg = cfg or LLMConfig()

    allowed = {
        "room_id": room_features.get("room_id"),
        "room_type": room_features.get("room_type"),
        "capacity": room_features.get("capacity"),
        "equipment": room_features.get("equipment"),
        "layout": room_features.get("layout"),
        "use_cases": room_features.get("use_cases"),
        "accessibility": room_features.get("accessibility"),
        "raw_description": room_features.get("raw_description"),
        "description": room_features.get("description"),
    }

    prompt = (
        "You are scoring semantic relevance between a user query and a room.\n"
        "Return ONLY valid JSON with keys: score (number 0-1), reasons (array of short strings).\n"
        "Rules:\n"
        "- score must be between 0 and 1\n"
        "- reasons must ONLY cite facts present in the provided room object or the user query\n"
        "- do NOT invent equipment or properties not in the room object\n\n"
        f"User query: {user_query}\n"
        f"Room object (JSON): {json.dumps(allowed, ensure_ascii=False)}\n"
    )

    client = _client(cfg)
    resp = client.chat.completions.create(
        model=cfg.chat_model,
        messages=[{"role": "user", "content": prompt}],
    )
    content = resp.choices[0].message.content or ""

    data = _extract_json_payload(content)
    if not data:
        return 0.0, ["llm score parse failed"]

    score = clamp_score(float(data.get("score", 0.0)))
    reasons = data.get("reasons", [])
    if not isinstance(reasons, list):
        reasons = []
    reasons = [str(x) for x in reasons][:4]
    return score, reasons


def llm_extract_requirements(*, user_query: str, cfg: Optional[LLMConfig] = None) -> dict[str, Any]:
    cfg = cfg or LLMConfig()
    client = _client(cfg)

    prompt = (
        "Extract room booking requirements from the user query.\n"
        "Return ONLY valid JSON. Allowed keys: capacity (int), time_slot (morning/afternoon/evening/night), "
        "duration (int minutes), preferences (array strings), room_type (string), equipment (array strings).\n"
        "If a value is not explicitly mentioned or strongly implied, omit the key.\n\n"
        f"User query: {user_query}\n"
    )

    resp = client.chat.completions.create(
        model=cfg.chat_model,
        messages=[{"role": "user", "content": prompt}],
    )

    content = resp.choices[0].message.content or "{}"
    data = _extract_json_payload(content)
    return data if isinstance(data, dict) else {}
