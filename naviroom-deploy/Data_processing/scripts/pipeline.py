"""
pipeline.py
===========

Unified data pipeline for NaviRoom.

Flow:
User Input
   ↓
Data Cleaning (reservations)
   ↓
Room Parsing (room_parser module)
   ↓
Per-dataset JSON + CSV Output
   ↓
Per-dataset MySQL Tables  (optional)

Usage:
    python pipeline.py --rooms rooms.csv --dataset-name dku
    python pipeline.py --rooms rooms.csv --reservations reservations.csv --dataset-name kaggle --save-to-db
"""

import json
import csv
from datetime import datetime
from pathlib import Path
import argparse

from db_manager import DBManager
from nlp_2_json_spacy import RoomParser


# =====================================================
# Reservation Cleaning
# =====================================================

def load_reservations(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)


def normalize_reservation(row):

    time_formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M"
    ]

    start_dt = None
    end_dt = None

    for fmt in time_formats:
        try:
            start_dt = datetime.strptime(row["start_date"], fmt)
            break
        except Exception:
            continue

    for fmt in time_formats:
        try:
            end_dt = datetime.strptime(row["end_date"], fmt)
            break
        except Exception:
            continue

    if not start_dt or not end_dt:
        return None

    try:
        duration_val = int(float(row["duration"]))

        return {
            "room_id": row["room_number"],
            "start_time": start_dt.isoformat(),
            "end_time": end_dt.isoformat(),
            "duration_minutes": duration_val,
            "status": row.get("status", "completed")
        }

    except Exception:
        return None


def process_reservations(path):

    raw = load_reservations(path)
    cleaned = [normalize_reservation(r) for r in raw]
    return [r for r in cleaned if r is not None]


# =====================================================
# Room Parsing
# =====================================================

def process_rooms(room_input):

    parser = RoomParser()

    rooms = parser.parse(room_input)

    return rooms


# =====================================================
# CSV Export  (per-dataset)
# =====================================================

ROOM_CSV_COLUMNS = [
    "room_id", "floor", "capacity", "room_type",
    "equipment", "layout", "use_cases", "accessibility", "raw_description"
]

RESERVATION_CSV_COLUMNS = [
    "room_id", "start_time", "end_time", "duration_minutes", "status"
]


def _export_csv(rows: list[dict], columns: list[str], path: Path):
    """将字典列表写入 CSV；列表类型的字段自动序列化为 JSON 字符串"""
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            out = {}
            for col in columns:
                val = row.get(col, "")
                if isinstance(val, (list, dict)):
                    val = json.dumps(val, ensure_ascii=False)
                out[col] = val
            writer.writerow(out)
    print(f"CSV 已导出 → {path}  ({len(rows)} 行)")


# =====================================================
# Pipeline
# =====================================================

def run_pipeline(room_input=None, reservation_input=None,
                 dataset_name="default", output_dir="output",
                 save_to_db=False, db_user='navi_user', db_password=None):

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    dataset = {}

    # ---------- rooms ----------
    if room_input:
        print("Parsing room features...")
        dataset["rooms"] = process_rooms(room_input)
        print(f"Parsed {len(dataset['rooms'])} rooms")

        _export_csv(dataset["rooms"], ROOM_CSV_COLUMNS,
                    out_dir / f"{dataset_name}_rooms.csv")

    # ---------- reservations ----------
    if reservation_input:
        print("Cleaning reservation records...")
        dataset["reservations"] = process_reservations(reservation_input)
        print(f"Processed {len(dataset['reservations'])} reservations")

        _export_csv(dataset["reservations"], RESERVATION_CSV_COLUMNS,
                    out_dir / f"{dataset_name}_reservations.csv")

    # ---------- JSON ----------
    json_path = out_dir / f"{dataset_name}_dataset.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=4, ensure_ascii=False)
    print(f"JSON 已导出 → {json_path}")

    # ---------- MySQL ----------
    if save_to_db:
        if not db_password:
            print("Error: MySQL password is required when save_to_db is True.")
            return

        db = DBManager(user=db_user, password=db_password)

        if "rooms" in dataset:
            db.save_rooms(dataset["rooms"], dataset_name)

        if "reservations" in dataset:
            db.save_reservations(dataset["reservations"], dataset_name)

        db.close()

    print(f"Pipeline completed for dataset '{dataset_name}'")


# =====================================================
# CLI
# =====================================================

if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--rooms",
        help="Room input (csv/xlsx/text)"
    )

    parser.add_argument(
        "--reservations",
        help="Reservation csv file"
    )

    parser.add_argument(
        "--dataset-name",
        default="default",
        help="Dataset identifier (e.g. dku, kaggle). "
             "Controls output file names and MySQL table prefix."
    )

    parser.add_argument(
        "--output-dir",
        default="output",
        help="Output directory for JSON/CSV files"
    )

    parser.add_argument(
        "--save-to-db",
        action="store_true",
        help="Save data to MySQL database"
    )

    parser.add_argument(
        "--db-user",
        default="navi_user",
        help="MySQL user (default: navi_user, the app account created by Ansible)"
    )

    parser.add_argument(
        "--db-password",
        default="",
        help="MySQL password for --db-user"
    )

    args = parser.parse_args()

    run_pipeline(
        room_input=args.rooms,
        reservation_input=args.reservations,
        dataset_name=args.dataset_name,
        output_dir=args.output_dir,
        save_to_db=args.save_to_db,
        db_user=args.db_user,
        db_password=args.db_password
    )