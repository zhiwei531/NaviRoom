"""
room_parser.py  –  v2
=====================
Unified room feature extractor with robust irregular-language support.

Key improvements over v1
------------------------
1. Key=value token extraction from plain text  (has_screen=Y, cap=30, …)
2. Phrase-level accessibility matching         (no more "wheelchair" + "accessible" duplicates)
3. Abbreviation / synonym normalisation        (WB→whiteboard, proj→projector, pax→people, …)
4. Slash/ampersand list expansion              (projector/whiteboard → two items)
5. Richer capacity patterns                    (pax, max N, up to N, N-person, …)
6. Richer floor patterns                       (B1/basement, G/ground, L2, 2F, …)
7. Longest-match-first for multi-word keywords (prevents partial matches)
8. Input-type detection unchanged, public API unchanged

Usage
-----
    from room_parser import RoomParser
    parser = RoomParser()
    rooms  = parser.parse(<str | dict | pd.DataFrame | file_path>)
    parser.save(rooms, "out.json")
"""

import json
import os
import re
from io import StringIO
from pathlib import Path
from typing import Union

import pandas as pd
import spacy

# ── Load spaCy once ──────────────────────────────────────────────────────────
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    import subprocess, sys
    subprocess.run([sys.executable, "-m", "spacy", "download", "en_core_web_sm"], check=True)
    nlp = spacy.load("en_core_web_sm")


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 1 – VOCABULARY
# ═══════════════════════════════════════════════════════════════════════════

EQUIPMENT_VOCAB: list[tuple[str, list[str]]] = [
    ("recording equipment",  ["recording equipment", "recorder", "recording"]),
    ("video conferencing",   ["video conferencing", "videoconference", "vc system", "vc"]),
    ("smart board",          ["smart board", "smartboard", "smart-board"]),
    ("interactive display",  ["interactive display", "interactive screen"]),
    ("document camera",      ["document camera", "doc cam", "visualizer"]),
    ("audio system",         ["audio system", "sound system", "speaker system", "speakers"]),
    ("microphone",           ["microphone", "mic", "mics"]),
    ("computer",             ["computer", "pc", "desktop", "workstation"]),
    ("monitor",              ["monitor", "display"]),
    ("projector",            ["projector", "proj", "beamer"]),
    ("whiteboard",           ["whiteboard", "white board", "wb", "white-board", "marker board"]),
    ("screen",               ["screen", "projection screen", "pull-down screen"]),
    ("tv",                   ["tv", "television", "flat screen tv", "flat-screen"]),
    ("printer",              ["printer", "photocopier", "copier"]),
    ("air conditioning",     ["air conditioning", "air con", "a/c", "hvac"]),
]

LAYOUT_VOCAB: list[tuple[str, list[str]]] = [
    ("lecture hall",         ["lecture hall", "auditorium", "theatre style", "theater style"]),
    ("conference room",      ["conference room", "boardroom", "board room", "meeting room", "conf rm", "conf room"]),
    ("seminar room",         ["seminar room", "seminar space", "seminar"]),
    ("laboratory",           ["laboratory", "lab", "computer lab", "science lab"]),
    ("study room",           ["study room", "study space", "group study", "quiet study"]),
    ("classroom",            ["classroom", "class room"]),
    ("office",               ["office"]),
    ("workshop",             ["workshop space", "workshop room"]),
]

USE_CASE_VOCAB: list[tuple[str, list[str]]] = [
    ("lecture",              ["lecture", "lecturing"]),
    ("presentation",         ["presentation", "presenting"]),
    ("workshop",             ["workshop"]),
    ("examination",          ["examination", "exam", "test"]),
    ("meeting",              ["meeting"]),
    ("discussion",           ["discussion", "tutorial", "tute"]),
    ("research",             ["research"]),
    ("training",             ["training"]),
    ("study",                ["self-study", "independent study", "quiet study"]),
    ("recording",            ["recording session", "podcast", "streaming"]),
]

# Phrase-level — longest match wins, prevents sub-phrase duplicates
ACCESSIBILITY_VOCAB: list[tuple[str, list[str]]] = [
    ("wheelchair accessible", ["wheelchair accessible", "wheelchair access", "wheelchair-accessible"]),
    ("hearing loop",          ["hearing loop", "hearing induction loop", "induction loop"]),
    ("braille signage",       ["braille signage", "braille"]),
    ("disabled access",       ["disabled access", "disability access"]),
    ("elevator access",       ["elevator access", "lift access"]),
    ("accessible bathroom",   ["accessible bathroom", "accessible toilet", "accessible restroom"]),
    ("step-free access",      ["step-free", "step free", "no steps"]),
]

ROOM_TYPE_RULES: list[tuple[str, list[str]]] = [
    ("laboratory",      ["lab", "laboratory", "computer lab"]),
    ("lecture hall",    ["lecture hall", "auditorium", "lec hall"]),
    ("conference room", ["conference", "boardroom", "board room", "conf rm"]),
    ("seminar room",    ["seminar"]),
    ("study room",      ["study room", "quiet study"]),
    ("classroom",       ["classroom"]),
    ("office",          ["office"]),
]

COL_ALIASES: dict[str, str] = {
    "room_number": "room_id", "room_no": "room_id", "roomnumber": "room_id",
    "roomno": "room_id", "room": "room_id",
    "floor_number": "floor", "storey": "floor", "level": "floor",
    "seats": "capacity", "size": "capacity", "max_capacity": "capacity", "pax": "capacity",
}

BOOL_EQUIPMENT_MAP: dict[str, str] = {
    "has_projector":       "projector",
    "has_whiteboard":      "whiteboard",
    "has_screen":          "screen",
    "has_tv":              "tv",
    "has_microphone":      "microphone",
    "has_computer":        "computer",
    "has_smartboard":      "smart board",
    "has_videoconference": "video conferencing",
    "has_vc":              "video conferencing",
    "has_recording":       "recording equipment",
    "has_audio":           "audio system",
    "has_ac":              "air conditioning",
    "has_printer":         "printer",
    "has_display":         "interactive display",
    "accessible":          "_access:wheelchair accessible",
    "wheelchair":          "_access:wheelchair accessible",
}

_TRUTHY = {"y", "yes", "true", "1", "t", "x", "on"}


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 2 – TEXT PRE-PROCESSING
# ═══════════════════════════════════════════════════════════════════════════

def _expand_slashes(text: str) -> str:
    """'projector/whiteboard' → 'projector whiteboard'  (skip URLs/fractions)."""
    return re.sub(r"(?<=[a-zA-Z0-9])\/(?=[a-zA-Z])", " ", text)

def _expand_ampersands(text: str) -> str:
    return re.sub(r"\s*&\s*", " and ", text)

def _extract_inline_kv(text: str) -> tuple[str, dict]:
    """
    Pull 'key=value' and 'key:value' tokens from text.
    Returns (cleaned_text, {key: value}).
    """
    kv: dict[str, str] = {}
    pattern = re.compile(
        r"\b([a-zA-Z_][a-zA-Z0-9_]*)[\s]*[=:][\s]*([A-Za-z0-9_\-\.]+)"
    )
    cleaned = text
    for m in pattern.finditer(text):
        raw_key = m.group(1).strip()
        # Skip "floor 1" style (spaced) — only grab = or : separated
        kv[raw_key.lower()] = m.group(2).strip()
        cleaned = cleaned.replace(m.group(0), " ")
    return cleaned.strip(), kv

def _resolve_kv_dict(kv: dict) -> dict:
    """Map arbitrary kv tokens to canonical room fields."""
    result: dict = {}

    for cap_key in ("cap", "capacity", "seats", "pax", "size", "max_capacity", "max"):
        if cap_key in kv:
            try:
                result["capacity"] = int(kv[cap_key])
            except ValueError:
                pass
            break

    for fl_key in ("floor", "fl", "level", "storey", "f", "lvl"):
        if fl_key in kv:
            result["floor"] = _parse_floor_token(kv[fl_key])
            break

    for id_key in ("room", "room_id", "room_number", "id", "room_no"):
        if id_key in kv:
            result["room_id"] = kv[id_key].upper()
            break

    equipment: list[str] = []
    accessibility: list[str] = []
    for raw_key, raw_val in kv.items():
        if raw_val.lower() not in _TRUTHY:
            continue
        mapped = BOOL_EQUIPMENT_MAP.get(raw_key.lower())
        if mapped:
            if mapped.startswith("_access:"):
                accessibility.append(mapped[len("_access:"):])
            else:
                equipment.append(mapped)

    if equipment:
        result["_kv_equipment"] = equipment
    if accessibility:
        result["_kv_accessibility"] = accessibility

    return result


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 3 – VOCABULARY MATCHERS  (longest-alias-first, span-aware)
# ═══════════════════════════════════════════════════════════════════════════

def _build_matcher(vocab: list[tuple[str, list[str]]]) -> list[tuple[str, list[re.Pattern]]]:
    result = []
    for canonical, aliases in vocab:
        patterns = [
            re.compile(rf"\b{re.escape(a)}\b", re.IGNORECASE)
            for a in sorted(aliases, key=len, reverse=True)
        ]
        result.append((canonical, patterns))
    return result

_EQUIPMENT_MATCHER    = _build_matcher(EQUIPMENT_VOCAB)
_LAYOUT_MATCHER       = _build_matcher(LAYOUT_VOCAB)
_USE_CASE_MATCHER     = _build_matcher(USE_CASE_VOCAB)
_ACCESSIBILITY_MATCHER = _build_matcher(ACCESSIBILITY_VOCAB)

def _match_vocab(text: str, matcher: list[tuple[str, list[re.Pattern]]]) -> list[str]:
    """
    Match vocabulary against text using span tracking to prevent
    sub-phrase duplicates (e.g. 'wheelchair' inside 'wheelchair accessible').
    """
    found: list[str] = []
    used_spans: list[tuple[int, int]] = []

    for canonical, patterns in matcher:
        matched = False
        for pat in patterns:
            for m in pat.finditer(text):
                s, e = m.start(), m.end()
                if any(s < ue and e > us for us, ue in used_spans):
                    continue
                found.append(canonical)
                used_spans.append((s, e))
                matched = True
                break
            if matched:
                break

    seen: set[str] = set()
    return [x for x in found if not (x in seen or seen.add(x))]  # type: ignore


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 4 – FIELD EXTRACTORS
# ═══════════════════════════════════════════════════════════════════════════

def _parse_floor_token(token: str) -> int | None:
    t = str(token).strip().lower()
    if t in ("g", "ground", "gr", "gf"):    return 0
    if t in ("b", "basement", "b1", "-1"):  return -1
    m = re.fullmatch(r"b(\d+)", t)
    if m: return -int(m.group(1))
    m = re.fullmatch(r"(\d+)", t)
    if m: return int(m.group(1))
    return None

def _extract_floor(text: str) -> int | None:
    patterns = [
        r"floor[\s:\.]*(\w+)",
        r"(\w+)(?:st|nd|rd|th)?\s+floor",
        r"\b(?:level|lvl|lv)[\s:\.]*(\w+)",
        r"\b(\w+)[Ff]\b",
        r"\b[Ll](\d+)\b",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            v = _parse_floor_token(m.group(1))
            if v is not None:
                return v
    return None

def _extract_capacity(text: str) -> int | None:
    patterns = [
        r"(\d+)\s*(?:seats?|persons?|people|pax|students?|participants?|attendees?|users?)",
        r"(?:capacity|cap|seats?|pax|size)[\s:=\.]*(\d+)",
        r"(?:for|holds?|accommodates?|up\s+to|max\.?|maximum)\s+(\d+)",
        r"(\d+)\s*[-–]\s*(?:person|people|seat)",
        r"(?:room\s+(?:for|of)|size)\s+(\d+)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return int(m.group(1))
    doc = nlp(text)
    for ent in doc.ents:
        if ent.label_ == "CARDINAL":
            try:
                n = int(ent.text.replace(",", ""))
                if 2 <= n <= 999:
                    return n
            except ValueError:
                pass
    return None

def _extract_room_id(text: str) -> str | None:
    m = re.search(r"\b([A-Z]{1,3}\d{1,5})\b", text)
    return m.group(1) if m else None

def _infer_room_type(text: str) -> str:
    text_l = text.lower()
    for room_type, triggers in ROOM_TYPE_RULES:
        if any(t in text_l for t in triggers):
            return room_type
    return "general purpose room"


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 5 – CORE PARSERS
# ═══════════════════════════════════════════════════════════════════════════

def parse_text(description: str) -> dict:
    """
    Parse free-text (including mixed key=value) room descriptions.
    Pipeline: expand → extract kv → regex fields → vocab match → merge.
    """
    text_norm  = _expand_slashes(_expand_ampersands(description))
    text_clean, kv = _extract_inline_kv(text_norm)
    kv_fields  = _resolve_kv_dict(kv)

    room_id  = kv_fields.get("room_id")  or _extract_room_id(text_clean)  or _extract_room_id(description)
    floor    = kv_fields.get("floor")    or _extract_floor(text_clean)    or _extract_floor(description)
    capacity = kv_fields.get("capacity") or _extract_capacity(text_clean) or _extract_capacity(description)

    equipment     = _match_vocab(text_norm, _EQUIPMENT_MATCHER)
    layout        = _match_vocab(text_norm, _LAYOUT_MATCHER)
    use_cases     = _match_vocab(text_norm, _USE_CASE_MATCHER)
    accessibility = _match_vocab(text_norm, _ACCESSIBILITY_MATCHER)

    equipment     = _dedupe(equipment + kv_fields.get("_kv_equipment", []))
    accessibility = _dedupe(accessibility + kv_fields.get("_kv_accessibility", []))

    if floor is None and room_id:
        m = re.match(r"[A-Z]+(\d)", room_id)
        if m:
            floor = int(m.group(1))

    return {
        "room_id":         room_id,
        "floor":           floor,
        "capacity":        capacity,
        "equipment":       sorted(equipment),
        "layout":          layout,
        "use_cases":       use_cases,
        "accessibility":   accessibility,
        "room_type":       _infer_room_type(description),
        "raw_description": description,
    }


def parse_structured_row(row: dict) -> dict:
    """Parse one structured row (CSV/Excel or plain dict)."""
    row_lower = {k.lower().strip(): v for k, v in row.items()}

    def _get(*keys):
        for k in keys:
            v = row_lower.get(k)
            if v is not None and str(v).strip() not in ("", "nan", "None"):
                return v
        return None

    room_id  = str(_get("room_id", "room_number", "room_no", "room") or "").strip().upper() or None
    capacity = _safe_int(_get("capacity", "seats", "pax", "size", "max_capacity"))
    floor    = _safe_int_floor(_get("floor", "floor_number", "storey", "level", "lvl"))

    bool_equipment:   list[str] = []
    bool_access:      list[str] = []
    for col_raw, equip_name in BOOL_EQUIPMENT_MAP.items():
        val = str(row_lower.get(col_raw, "")).strip().lower()
        if val in _TRUTHY:
            if equip_name.startswith("_access:"):
                bool_access.append(equip_name[len("_access:"):])
            elif "accessible" in equip_name or "wheelchair" in equip_name:
                bool_access.append(equip_name)
            else:
                bool_equipment.append(equip_name)

    text_cols = {"description", "notes", "details", "comments", "info", "remarks"}
    text_fragments = [
        str(v).strip() for k, v in row_lower.items()
        if k in text_cols and str(v).strip() not in ("", "nan", "None")
    ]
    for k, v in row_lower.items():
        v_s = str(v).strip()
        if k not in text_cols and len(v_s) > 10 and not re.fullmatch(r"[\d\.\-]+", v_s):
            text_fragments.append(v_s)

    text_blob = " ".join(text_fragments)

    nlp_equipment     = _match_vocab(text_blob, _EQUIPMENT_MATCHER)   if text_blob else []
    nlp_layout        = _match_vocab(text_blob, _LAYOUT_MATCHER)       if text_blob else []
    nlp_use_cases     = _match_vocab(text_blob, _USE_CASE_MATCHER)     if text_blob else []
    nlp_access        = _match_vocab(text_blob, _ACCESSIBILITY_MATCHER) if text_blob else []

    equipment     = _dedupe(bool_equipment + nlp_equipment)
    accessibility = _dedupe(bool_access + nlp_access)

    if floor is None and room_id:
        m = re.match(r"[A-Z]+(\d)", room_id)
        if m:
            floor = int(m.group(1))

    return {
        "room_id":         room_id,
        "floor":           floor,
        "capacity":        capacity,
        "equipment":       sorted(equipment),
        "layout":          nlp_layout,
        "use_cases":       nlp_use_cases,
        "accessibility":   accessibility,
        "room_type":       _infer_room_type(text_blob) if text_blob else "general purpose room",
        "raw_description": row,
    }


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 6 – UTILITIES
# ═══════════════════════════════════════════════════════════════════════════

def _dedupe(lst: list[str]) -> list[str]:
    seen: set[str] = set()
    return [x for x in lst if not (x in seen or seen.add(x))]  # type: ignore

def _safe_int(value) -> int | None:
    try:
        return int(value) if pd.notna(value) else None
    except (ValueError, TypeError):
        return None

def _safe_int_floor(value) -> int | None:
    if value is None:
        return None
    return _parse_floor_token(str(value))

def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename = {}
    for col in df.columns:
        key = col.strip().lower().replace(" ", "_")
        if key in COL_ALIASES:
            rename[col] = COL_ALIASES[key]
    return df.rename(columns=rename)


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 7 – INPUT TYPE DETECTION
# ═══════════════════════════════════════════════════════════════════════════

def _detect_input_type(data) -> str:
    if isinstance(data, pd.DataFrame): return "dataframe"
    if isinstance(data, dict):         return "dict"
    if isinstance(data, str):
        stripped = data.strip()
        if os.path.isfile(stripped):
            ext = Path(stripped).suffix.lower()
            if ext == ".csv":                      return "csv_path"
            if ext in (".xlsx", ".xls", ".xlsm"): return "excel_path"
        if "\n" in stripped and "," in stripped:   return "csv_inline"
        return "text"
    raise TypeError(f"Unsupported input type: {type(data)}")


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 8 – PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════

class RoomParser:
    def parse(self, data: Union[str, dict, pd.DataFrame]) -> list[dict]:
        t = _detect_input_type(data)
        if t == "text":       return [parse_text(data)]
        if t == "dict":       return [parse_structured_row(data)]
        if t == "csv_inline":
            df = _normalise_columns(pd.read_csv(StringIO(data)))
            return [parse_structured_row(r.to_dict()) for _, r in df.iterrows()]
        if t in ("csv_path", "excel_path"):
            df = (pd.read_csv if t == "csv_path" else pd.read_excel)(data)
            df = _normalise_columns(df)
            return [parse_structured_row(r.to_dict()) for _, r in df.iterrows()]
        if t == "dataframe":
            df = _normalise_columns(data)
            return [parse_structured_row(r.to_dict()) for _, r in df.iterrows()]
        raise ValueError(f"Cannot handle input type: {t}")

    @staticmethod
    def save(rooms: list[dict], path: str = "rooms_features.json") -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rooms, f, indent=2, ensure_ascii=False, default=str)
        print(f"✓ Saved {len(rooms)} room(s) → {path}")


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 9 – CLI DEMO
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = RoomParser()

    tests = [
        # ── Original 4 ──────────────────────────────────────────────────
        "A seminar room on floor 2 with 25 seats, projector and whiteboard, wheelchair accessible",
        "R1124, floor 1, capacity 4, has_screen=Y, has_whiteboard=Y",
        "Large lecture hall, floor 3, 100 seats, projector, microphone, recording equipment",
        {"Room_Number": "R2201", "Floor": 2, "Capacity": 30,
         "has_projector": "Y", "has_whiteboard": "Y", "Description": "seminar room"},
        # ── Irregular / abbreviated ──────────────────────────────────────
        "Conf rm B203, 2F, max 12 pax, proj/wb/vc, wheelchair access",
        "LT5 - Lec Hall - Floor G - 150 seats - mic, recording equip, hearing loop",
        "R301 study room up to 8 people has_screen=y has_ac=1",
        "Seminar space, lvl 3, seats: 20, WB & beamer, step-free entry",
        {"room_no": "AB104", "storey": "B1", "pax": 6,
         "has_smartboard": "YES", "accessible": "Y", "notes": "quiet study room"},
    ]

    for t in tests:
        label = "dict" if isinstance(t, dict) else "text"
        print(f"\n{'─'*60}")
        print(f"[{label}] {str(t)[:90]}")
        result = parser.parse(t)
        print(json.dumps(result, indent=2, default=str))