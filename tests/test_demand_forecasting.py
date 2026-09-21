from __future__ import annotations

import pandas as pd

from demand_forecasting.data import build_slot_panel


def test_slot_panel_keeps_targets_out_of_lag_features():
    reservations = pd.DataFrame(
        [
            {
                "room_id": "R1",
                "start_time": pd.Timestamp("2026-01-01 10:00:00"),
                "end_time": pd.Timestamp("2026-01-01 10:30:00"),
                "requested_at": pd.Timestamp("2025-12-31 09:00:00"),
            },
            {
                "room_id": "R1",
                "start_time": pd.Timestamp("2026-01-02 10:00:00"),
                "end_time": pd.Timestamp("2026-01-02 10:30:00"),
                "requested_at": pd.Timestamp("2026-01-02 08:00:00"),
            },
        ]
    )
    rooms = pd.DataFrame(
        [
            {
                "room_id": "R1",
                "floor": 1,
                "capacity": 4,
                "has_screen": 1,
                "has_whiteboard": 1,
                "room_type": "study room",
                "metadata_inferred": 0,
            }
        ]
    )

    panel = build_slot_panel(reservations, rooms)
    rows = panel[(panel["room_id"] == "R1") & (panel["slot_minute"] == 600)].sort_values("date")
    assert rows["occupied"].tolist() == [1, 1]
    assert pd.isna(rows.iloc[0]["lag_1d"])
    assert rows.iloc[1]["lag_1d"] == 1
    assert rows.iloc[1]["recent_7d_rate"] == 1
