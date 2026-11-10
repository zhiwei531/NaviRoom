from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


TARGET_SPACE_PATTERN = r"study room|team room|multi-media booth"
SLOT_MINUTES = 30
OPEN_MINUTE = 8 * 60
CLOSE_MINUTE = 22 * 60 + 30


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _room_id(description: str) -> str | None:
    booth = re.search(r"Booth No\.(\d+)", description, flags=re.IGNORECASE)
    if booth:
        return f"M{int(booth.group(1)):02d}"
    room = re.search(r"(?:Study|Team) Room (\d+)", description, flags=re.IGNORECASE)
    return f"R{room.group(1)}" if room else None


def _room_type(description: str) -> str:
    text = description.lower()
    if "multi-media booth" in text:
        return "multi-media booth"
    if "team room" in text:
        return "team room"
    return "study room"


def _capacity_upper_bound(description: str) -> int | None:
    match = re.search(r"(?:\d+\s*-\s*)?(\d+)\s+People", description, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def load_dku_reservations(
    workbook_path: str | Path,
    rooms_path: str | Path,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Load the original DKU export without changing the source workbook.

    The source has no real completion/cancellation field. Therefore this loader
    deliberately does not manufacture a reservation status.
    """
    workbook_path = Path(workbook_path)
    rooms_path = Path(rooms_path)
    raw = pd.read_excel(workbook_path)
    expected = {
        "Description",
        "Booking Start Time",
        "Booking End Time",
        "Request Date",
        "Request Time",
    }
    missing = expected.difference(raw.columns)
    if missing:
        raise ValueError(f"Missing workbook columns: {sorted(missing)}")

    selected = raw[
        raw["Description"].fillna("").str.contains(TARGET_SPACE_PATTERN, case=False, regex=True)
    ].copy()
    selected["room_id"] = selected["Description"].map(_room_id)
    selected["start_time"] = pd.to_datetime(selected["Booking Start Time"], errors="coerce")
    selected["end_time"] = pd.to_datetime(selected["Booking End Time"], errors="coerce")
    request_date = pd.to_datetime(selected["Request Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    selected["requested_at"] = pd.to_datetime(
        request_date + " " + selected["Request Time"].astype(str), errors="coerce"
    )
    selected = selected[
        selected["room_id"].notna()
        & selected["start_time"].notna()
        & selected["end_time"].notna()
        & selected["requested_at"].notna()
        & (selected["end_time"] > selected["start_time"])
    ].copy()
    selected["duration_minutes"] = (
        (selected["end_time"] - selected["start_time"]).dt.total_seconds() / 60.0
    )

    rooms = pd.read_csv(rooms_path, encoding="utf-8-sig")
    rooms.columns = [str(column).lstrip("\ufeff") for column in rooms.columns]
    rooms["room_id"] = rooms["room_id"].astype(str)
    rooms["room_type"] = rooms["room_type"].astype(str).str.strip().str.lower()
    for flag in ("has_screen", "has_whiteboard"):
        rooms[flag] = rooms[flag].astype(str).str.upper().eq("Y").astype(int)

    observed_ids = set(selected["room_id"])
    known_ids = set(rooms["room_id"])
    inferred_rows: list[dict[str, Any]] = []
    for room_id in sorted(observed_ids - known_ids):
        description = str(selected.loc[selected["room_id"] == room_id, "Description"].iloc[0])
        floor_match = re.match(r"R(\d)", room_id)
        inferred_rows.append(
            {
                "room_id": room_id,
                "floor": int(floor_match.group(1)) if floor_match else np.nan,
                "capacity": _capacity_upper_bound(description),
                "has_screen": 0,
                "has_whiteboard": 0,
                "room_type": _room_type(description),
                "metadata_inferred": 1,
            }
        )
    rooms["metadata_inferred"] = 0
    if inferred_rows:
        rooms = pd.concat([rooms, pd.DataFrame(inferred_rows)], ignore_index=True)
    rooms = rooms[rooms["room_id"].isin(observed_ids)].copy()

    same_window_duplicates = int(selected.duplicated(["room_id", "start_time", "end_time"]).sum())
    audit = {
        "raw_rows": int(len(raw)),
        "target_rows": int(len(selected)),
        "room_count": int(selected["room_id"].nunique()),
        "start_min": selected["start_time"].min().isoformat(),
        "start_max": selected["start_time"].max().isoformat(),
        "request_min": selected["requested_at"].min().isoformat(),
        "request_max": selected["requested_at"].max().isoformat(),
        "same_window_duplicate_rows": same_window_duplicates,
        "inferred_room_ids": sorted(observed_ids - known_ids),
        "source_has_real_status": False,
        "workbook_sha256": file_sha256(workbook_path),
        "rooms_sha256": file_sha256(rooms_path),
    }
    keep = ["room_id", "start_time", "end_time", "requested_at", "duration_minutes", "Description"]
    return selected[keep].reset_index(drop=True), rooms.reset_index(drop=True), audit


def build_slot_panel(reservations: pd.DataFrame, rooms: pd.DataFrame) -> pd.DataFrame:
    """Create a room-by-30-minute supervised panel with leakage-safe lag features."""
    first_date = reservations["start_time"].min().normalize()
    last_date = reservations["start_time"].max().normalize()
    dates = pd.date_range(first_date, last_date, freq="D")
    slot_minutes = np.arange(OPEN_MINUTE, CLOSE_MINUTE + 1, SLOT_MINUTES, dtype=int)

    index = pd.MultiIndex.from_product(
        [dates, rooms["room_id"].sort_values().tolist(), slot_minutes],
        names=["date", "room_id", "slot_minute"],
    )
    panel = index.to_frame(index=False)
    occupied_keys: set[tuple[pd.Timestamp, str, int]] = set()
    for row in reservations.itertuples(index=False):
        cursor = row.start_time.floor(f"{SLOT_MINUTES}min")
        while cursor < row.end_time:
            minute = cursor.hour * 60 + cursor.minute
            if OPEN_MINUTE <= minute <= CLOSE_MINUTE:
                occupied_keys.add((cursor.normalize(), row.room_id, minute))
            cursor += pd.Timedelta(minutes=SLOT_MINUTES)
    panel["occupied"] = [
        int((date, room_id, int(slot)) in occupied_keys)
        for date, room_id, slot in panel[["date", "room_id", "slot_minute"]].itertuples(index=False)
    ]

    room_features = rooms[
        ["room_id", "floor", "capacity", "has_screen", "has_whiteboard", "room_type", "metadata_inferred"]
    ]
    panel = panel.merge(room_features, on="room_id", how="left", validate="many_to_one")
    panel["day_of_week"] = panel["date"].dt.dayofweek
    panel["month"] = panel["date"].dt.month
    panel["is_weekend"] = panel["day_of_week"].isin([5, 6]).astype(int)
    hour = panel["slot_minute"] / 60.0
    panel["hour_sin"] = np.sin(2 * np.pi * hour / 24.0)
    panel["hour_cos"] = np.cos(2 * np.pi * hour / 24.0)
    panel["dow_sin"] = np.sin(2 * np.pi * panel["day_of_week"] / 7.0)
    panel["dow_cos"] = np.cos(2 * np.pi * panel["day_of_week"] / 7.0)

    panel = panel.sort_values(["room_id", "slot_minute", "date"]).reset_index(drop=True)
    groups = panel.groupby(["room_id", "slot_minute"], sort=False)["occupied"]
    panel["lag_1d"] = groups.shift(1)
    panel["lag_7d"] = groups.shift(7)
    panel["recent_7d_rate"] = groups.transform(lambda values: values.shift(1).rolling(7, min_periods=1).mean())
    panel["recent_28d_rate"] = groups.transform(lambda values: values.shift(1).rolling(28, min_periods=1).mean())
    panel["same_weekday_4w_rate"] = pd.concat(
        [groups.shift(days) for days in (7, 14, 21, 28)], axis=1
    ).mean(axis=1)
    return panel.sort_values(["date", "room_id", "slot_minute"]).reset_index(drop=True)
