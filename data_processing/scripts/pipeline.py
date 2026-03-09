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
Unified JSON Output

Usage:
    python pipeline.py --rooms rooms.csv --reservations reservations.csv
"""

import json
import csv
from datetime import datetime
from pathlib import Path
import argparse

try:
    from .db_manager import DBManager
    from .nlp_2_json_spacy import RoomParser
except ImportError:
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
# Pipeline
# =====================================================

def run_pipeline(room_input=None, reservation_input=None, output="dataset.json", save_to_db=False, db_password=None):

    dataset = {}

    if room_input:
        print("Parsing room features...")
        dataset["rooms"] = process_rooms(room_input)
        print(f"Parsed {len(dataset['rooms'])} rooms")

    if reservation_input:
        print("Cleaning reservation records...")
        dataset["reservations"] = process_reservations(reservation_input)
        print(f"Processed {len(dataset['reservations'])} reservations")

    # 存储为json文件
    with open(output, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=4)
    
    # 存入MySQL数据库
    if save_to_db:
        if not db_password:
            print("Error: MySQL password is required when save_to_db is True.")
            return

        db = DBManager(password=db_password) 
        
        if "rooms" in dataset:
            db.save_rooms(dataset["rooms"])
        
        if "reservations" in dataset:
            # 只有房间存在时，存预约才有意义（因为有外键约束）
            db.save_reservations(dataset["reservations"])
            
        db.close()

    print(f"Pipeline completed → {output}")


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
        "--output",
        default="dataset.json",
        help="Output JSON file"
    )

    parser.add_argument(
        "--save-to-db",
        action="store_true",
        help="Save data to MySQL database"
    )

    parser.add_argument(
        "--db-password",
        default="Weeder123456",
        help="MySQL root password"
    )

    args = parser.parse_args()

    run_pipeline(
        room_input=args.rooms,
        reservation_input=args.reservations,
        output=args.output,
        save_to_db=args.save_to_db,
        db_password=args.db_password
    )