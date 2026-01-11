import spacy
import json
import re
from typing import Dict, List

nlp = spacy.load("en_core_web_sm")

# predefined vocabularies (can grow over time)
EQUIPMENT_KEYWORDS = [
    "projector", "whiteboard", "blackboard", "tv", "screen",
    "video conferencing", "microphone", "speaker", "computer"
]

LAYOUT_KEYWORDS = [
    "lecture", "seminar", "conference", "classroom", "round table", "study room", "multi-media room",
    "team room"
]

USE_CASE_KEYWORDS = [
    "meeting", "lecture", "discussion", "workshop",
    "presentation", "hybrid meeting", "training"
]

ACCESSIBILITY_KEYWORDS = [
    "wheelchair accessible", "accessible", "elevator"
]


def extract_capacity(text: str) -> int | None:
    match = re.search(r'(\d+)\s*(people|persons|seats)', text.lower())
    if match:
        return int(match.group(1))
    return None


def extract_keywords(text: str, keyword_list: List[str]) -> List[str]:
    text_lower = text.lower()
    return [kw for kw in keyword_list if kw in text_lower]


def infer_room_type(text: str) -> str:
    text_lower = text.lower()
    if "lab" in text_lower:
        return "laboratory"
    if "seminar" in text_lower:
        return "seminar room"
    if "conference" in text_lower:
        return "conference room"
    if "classroom" in text_lower:
        return "classroom"
    return "general purpose room"


def parse_room_description(description: str) -> Dict:
    doc = nlp(description)

    room_features = {
        "capacity": extract_capacity(description),
        "room_type": infer_room_type(description),
        "equipment": extract_keywords(description, EQUIPMENT_KEYWORDS),
        "layout": extract_keywords(description, LAYOUT_KEYWORDS),
        "use_cases": extract_keywords(description, USE_CASE_KEYWORDS),
        "accessibility": extract_keywords(description, ACCESSIBILITY_KEYWORDS),
        "raw_description": description
    }

    return room_features


def save_to_json(data: Dict, filename: str):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# ===== Example usage =====
if __name__ == "__main__":
    description = (
        "A medium-sized seminar room with capacity for around 25 people, "
        "equipped with a projector, whiteboard, and video conferencing system. "
        "Suitable for group discussions and hybrid meetings. Wheelchair accessible."
    )

    features = parse_room_description(description)
    save_to_json(features, "room_features.json")

    print(json.dumps(features, indent=4))