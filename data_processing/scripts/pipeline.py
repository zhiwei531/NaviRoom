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

from data_processing.scripts.nlp_2_json_spacy import RoomParser


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

def run_pipeline(room_input=None, reservation_input=None, output="dataset.json"):

    dataset = {}

    if room_input:
        print("Parsing room features...")
        dataset["rooms"] = process_rooms(room_input)
        print(f"Parsed {len(dataset['rooms'])} rooms")

    if reservation_input:
        print("Cleaning reservation records...")
        dataset["reservations"] = process_reservations(reservation_input)
        print(f"Processed {len(dataset['reservations'])} reservations")

    with open(output, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=4)

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

    args = parser.parse_args()

    run_pipeline(
        room_input=args.rooms,
        reservation_input=args.reservations,
        output=args.output
    )