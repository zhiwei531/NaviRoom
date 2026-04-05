import json
from datetime import datetime

import openpyxl


def _clean_str(v):
    if v is None:
        return None
    s = str(v).strip()
    return s if s != "" else None


def _to_iso_datetime(value):
    """
    Convert Excel cell value to ISO datetime string.
    Handles:
      - datetime objects (common for XLSX)
      - string datetimes in a few common formats
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.isoformat()

    s = _clean_str(value)
    if not s:
        return None

    # Try multiple formats (XLSX exports vary)
    time_formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%m/%d/%y %H:%M:%S",
        "%m/%d/%y %H:%M",
    ]
    for fmt in time_formats:
        try:
            return datetime.strptime(s, fmt).isoformat()
        except ValueError:
            continue

    return None


def _to_iso_date(value):
    """
    Convert Excel cell value to ISO date string (YYYY-MM-DD).
    Handles:
      - datetime/date objects
      - string dates in a few common formats
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date().isoformat()

    s = _clean_str(value)
    if not s:
        return None

    date_formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%m/%d/%Y",
        "%m/%d/%y",
    ]
    for fmt in date_formats:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue

    return None


def load_xlsx_rows(path, sheet_name=None):
    """
    Loads XLSX and returns a list of dict rows using the header row.
    """
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[sheet_name] if sheet_name else wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []

    headers = [(_clean_str(h) or "") for h in rows[0]]
    print(f"Detected Headers: {headers}")

    data = []
    for r in rows[1:]:
        row_dict = {}
        for idx, h in enumerate(headers):
            if not h:
                continue
            row_dict[h] = r[idx] if idx < len(r) else None
        # Skip fully empty rows
        if any(v is not None and str(v).strip() != "" for v in row_dict.values()):
            data.append(row_dict)
    return data


def normalize_booking_row(row):
    """
    Keep only:
      - description
      - Booking Start Time
      - Booking End Time
      - Request Date

    Filter:
      - description contains any of: study room, team room, multi-media booth (case-insensitive)
    """
    description = _clean_str(row.get("Description"))
    if not description:
        return None

    desc_lc = description.lower()
    allowed = ("study room", "team room", "multi-media booth")
    if not any(k in desc_lc for k in allowed):
        return None

    start_iso = _to_iso_datetime(row.get("Booking Start Time"))
    end_iso = _to_iso_datetime(row.get("Booking End Time"))
    req_date_iso = _to_iso_date(row.get("Request Date"))

    if not start_iso or not end_iso or not req_date_iso:
        print("Skip Error: Could not parse required datetime/date fields for a row.")
        return None

    return {
        "description": description,
        "booking_start_time": start_iso,
        "booking_end_time": end_iso,
        "request_date": req_date_iso,
    }


def save_bookings(data, path):
    """
    Filters out invalid entries and saves the result to a JSON file.
    """
    clean_data = [d for d in data if d is not None]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(clean_data, f, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    # Update these paths as needed
    input_path = "data_processing/data/dku_room_data/dku_library_reservation.xlsx"
    output_path = "data_processing/data/dku_room_data/dku_library_reservation.json"

    try:
        raw = load_xlsx_rows(input_path)
        processed = [normalize_booking_row(r) for r in raw]
        save_bookings(processed, output_path)
        print(f"Success! Processed {len([d for d in processed if d is not None])} records.")
    except FileNotFoundError:
        print(f"Error: Could not find the file at {input_path}")
    except Exception as e:
        print(f"Error: {e}")