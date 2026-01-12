import csv
import json
from datetime import datetime

def load_reservations(path):
    """
    Loads the CSV file using utf-8-sig to handle the Byte Order Mark (BOM)
    and returns a list of dictionaries.
    """
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        print(f"Detected Headers: {reader.fieldnames}")
        return list(reader)

def normalize_reservation(row):
    """
    Normalizes a single row from the reservations CSV.
    Supports multiple date formats (hyphens/slashes) and handles
    float-to-int conversion for the duration field.
    """
    # Try multiple formats to handle discrepancies between raw data and Excel display
    time_formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M"
    ]

    start_dt = None
    end_dt = None

    # Parse start_date using the format list
    for fmt in time_formats:
        try:
            start_dt = datetime.strptime(row["start_date"], fmt)
            break
        except (ValueError, KeyError):
            continue

    # Parse end_date using the format list
    for fmt in time_formats:
        try:
            end_dt = datetime.strptime(row["end_date"], fmt)
            break
        except (ValueError, KeyError):
            continue

    # If date parsing fails, skip the row and print an error
    if not start_dt or not end_dt:
        print(f"Skip Error: Could not parse dates for row with room {row.get('room_number')}")
        return None

    try:
        # Convert duration: first to float, then to int to handle strings like '210.0'
        duration_val = int(float(row["duration"]))

        return {
            "room_id": row["room_number"],
            "start_time": start_dt.isoformat(),
            "end_time": end_dt.isoformat(),
            "duration_minutes": duration_val,
            "status": row.get("status", "completed")
        }
    except KeyError as e:
        print(f"Missing Column Error: {e}")
        return None
    except ValueError as e:
        print(f"Value Conversion Error in row {row.get('room_number')}: {e}")
        return None

def save_reservations(data, path):
    """
    Filters out invalid entries and saves the result to a JSON file.
    """
    with open(path, "w", encoding="utf-8") as f:
        clean_data = [d for d in data if d is not None]
        json.dump(clean_data, f, indent=4)

if __name__ == "__main__":
    # Updated paths based on your previous messages
    input_path = "../Kaggle_University_Room_Dataset/reservations.csv"
    output_path = "../Kaggle_University_Room_Dataset/reservations.json"

    try:
        raw = load_reservations(input_path)
        processed = [normalize_reservation(r) for r in raw]
        save_reservations(processed, output_path)
        print(f"Success! Processed {len([d for d in processed if d is not None])} records.")
    except FileNotFoundError:
        print(f"Error: Could not find the file at {input_path}")