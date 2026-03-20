import csv
import json
import re
from pathlib import Path
from typing import Dict, Optional, Any, List, Tuple


# --- patterns tuned for DKU descriptions ---
# Examples:
# "Study Room 4112 (4-6 People)"
# "Team Room 4109 (8-12 People)"
_ROOM_NUM_RE = re.compile(r"\b(?:study|team)\s*room\s*(\d{3,4})\b", re.IGNORECASE)

# Examples:
# "4F Multi-Media Booth No.1 (1-3 People)"
# "Multi-Media Booth No.6"
# allows: No.1 / No 1 / #1
_BOOTH_NO_RE = re.compile(
    r"\bmulti[-\s]*media\s*booth\b.*?\b(?:no\.?|#)\s*(\d{1,2})\b",
    re.IGNORECASE,
)


def load_rooms_csv(path: str) -> Dict[str, Dict[str, Any]]:
    """
    Load rooms.csv keyed by room_id (e.g., R4112, M01).
    """
    rooms: Dict[str, Dict[str, Any]] = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rid = (row.get("room_id") or "").strip()
            if not rid:
                continue
            rooms[rid.upper()] = row
    return rooms


def extract_room_id(description: Optional[str], rooms: Dict[str, Dict[str, Any]]) -> Optional[str]:
    """
    Parse description -> standardized room_id present in rooms.csv:
      - Study/Team Room 4112 -> R4112
      - Multi-Media Booth No.1 -> M01
    Returns None if cannot parse or not found in rooms.csv.
    """
    if not description:
        return None

    s = description.strip()

    # Study/Team rooms -> R####
    m = _ROOM_NUM_RE.search(s)
    if m:
        rid = f"R{int(m.group(1))}"
        return rid if rid.upper() in rooms else None

    # Multi-media booth -> M01..M06
    b = _BOOTH_NO_RE.search(s)
    if b:
        num = int(b.group(1))
        rid = f"M{num:02d}"
        return rid if rid.upper() in rooms else None

    return None


def normalize_booking_row(b: Dict[str, Any], rooms: Dict[str, Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], bool]:
    """
    Input booking json row keys (your xlsx_processing output):
      description, booking_start_time, booking_end_time, request_date
    Output (csv-processing-like):
      room_id, start_time, end_time, duration_minutes, status, request_date, description
    Returns (row_or_none, mapped_ok)
    """
    # Skip rows that are clearly incomplete (your current json has lots of request_date-only rows)
    if not isinstance(b, dict):
        return None, False

    description = b.get("description")
    start_time = b.get("booking_start_time")
    end_time = b.get("booking_end_time")
    request_date = b.get("request_date")

    if not description or not start_time or not end_time:
        return None, False

    room_id = extract_room_id(description, rooms)
    mapped_ok = room_id is not None

    duration_minutes = None
    try:
        # ISO like: 2025-10-22T13:30:00
        # compute minutes only if parseable
        from datetime import datetime
        st = datetime.fromisoformat(start_time)
        et = datetime.fromisoformat(end_time)
        duration_minutes = int((et - st).total_seconds() // 60)
    except Exception:
        duration_minutes = None

    out = {
        "room_id": room_id,                 # <-- mapped to rooms.csv
        "start_time": start_time,
        "end_time": end_time,
        "duration_minutes": duration_minutes,
        "status": b.get("status", "completed"),
        "request_date": request_date,       # <-- keep as-is (申请日期)
        "description": description,         # keep original
    }

    # Optional enrichment from rooms.csv if mapped
    if mapped_ok:
        meta = rooms[room_id.upper()]
        out.update(
            {
                "floor": int(meta["floor"]) if meta.get("floor") else None,
                "capacity": int(meta["capacity"]) if meta.get("capacity") else None,
                "has_screen": (meta.get("has_screen") or "").strip().upper(),
                "has_whiteboard": (meta.get("has_whiteboard") or "").strip().upper(),
                "room_type": meta.get("room_type"),
            }
        )

    return out, mapped_ok


def save_json(data: List[Dict[str, Any]], path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def main():
    rooms_csv_path = "data_processing/data/dku_room_data/rooms.csv"
    input_json_path = "data_processing/data/dku_room_data/dku_library_reservation.json"
    output_json_path = "data_processing/data/dku_room_data/dku_library_reservation_mapped.json"
    unmapped_json_path = "data_processing/data/dku_room_data/dku_library_reservation_unmapped.json"

    rooms = load_rooms_csv(rooms_csv_path)
    print(f"Loaded rooms: {len(rooms)}")

    with open(input_json_path, "r", encoding="utf-8") as f:
        bookings = json.load(f)

    if not isinstance(bookings, list):
        raise ValueError("Input JSON must be a list")

    mapped: List[Dict[str, Any]] = []
    unmapped: List[Dict[str, Any]] = []
    skipped_incomplete = 0
    skipped_room_id_null = 0

    for b in bookings:
        row, ok = normalize_booking_row(b, rooms)
        if row is None:
            skipped_incomplete += 1
            continue
        # Per requirement: do not keep any rows with room_id == None in the mapped output.
        if row.get("room_id") is None:
            skipped_room_id_null += 1
            unmapped.append(row)
            continue

        mapped.append(row)
        if not ok:
            # Keep a separate file for debugging even though mapped excludes these.
            unmapped.append(row)

    save_json(mapped, output_json_path)
    save_json(unmapped, unmapped_json_path)

    print(f"Total input rows: {len(bookings)}")
    print(f"Skipped incomplete rows (no description/start/end): {skipped_incomplete}")
    print(f"Skipped room_id null rows (filtered from mapped): {skipped_room_id_null}")
    print(f"Output rows: {len(mapped)}")
    print(f"Mapped OK: {len(mapped) - len(unmapped)}")
    print(f"Unmapped: {len(unmapped)}")
    print(f"Output: {output_json_path}")
    print(f"Unmapped output: {unmapped_json_path}")


if __name__ == "__main__":
    main()