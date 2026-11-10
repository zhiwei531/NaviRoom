"""Expanding-window, daily-origin backtest; no production model promotion."""
import json
import subprocess
from pathlib import Path
import pandas as pd
from .data import load_dku_reservations, build_slot_panel
from .train import FEATURE_COLUMNS, HistoricalMeanModel, _logistic_pipeline, _boosting_pipeline, _metrics


def main():
    root = Path('experiments/demand_forecasting/runs/20261110_rolling_v2')
    root.mkdir(parents=True, exist_ok=False)
    reservations, rooms, audit = load_dku_reservations(
        'data_processing/data/dku_room_data/dku_library_reservation.xlsx',
        'data_processing/data/dku_room_data/rooms.csv')
    # The export stops during March 18. Later reservations are only partially
    # observed; do not label their missing bookings as negative examples.
    cutoff = reservations.requested_at.max().normalize()
    if (reservations.requested_at > reservations.start_time).any():
        raise ValueError('Late-entered reservations require as-of feature reconstruction')
    panel = build_slot_panel(reservations, rooms)
    panel = panel[panel.date < cutoff]
    factories = {'historical_mean': HistoricalMeanModel,
                 'logistic_regression': _logistic_pipeline,
                 'hist_gradient_boosting': _boosting_pipeline}
    results = []
    for start in pd.to_datetime(['2025-09-01', '2025-10-01', '2025-11-01', '2025-12-01', '2026-01-01', '2026-02-01']):
        end = start + pd.offsets.MonthBegin(1)
        train = panel[panel.date < start]
        test = panel[(panel.date >= start) & (panel.date < end)]
        for name, factory in factories.items():
            model = factory()
            model.fit(train[FEATURE_COLUMNS], train.occupied)
            probability = model.predict_proba(test[FEATURE_COLUMNS])
            if probability.ndim == 2:
                probability = probability[:, 1]
            row = dict(month=str(start.date()), model=name, train_rows=len(train), test_rows=len(test),
                       **_metrics(test.occupied, probability, test.slot_minute))
            results.append(row)
            print(json.dumps(row), flush=True)
            pd.DataFrame(results).to_csv(root / 'metrics.csv', index=False)
    manifest = dict(source=audit, git_commit=subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip(),
                    protocol='Weights fixed each month; lag features refreshed daily at midnight. Not a month-ahead forecast.',
                    cutoff_exclusive=str(cutoff), model_selection='None; exploratory historical backtest, overlaps prior v1 holdout.',
                    assumptions=['08:00–23:00 analysis window is not verified opening hours',
                                 'No-record days treated as zero recorded bookings; export completeness unverified',
                                 'Reservation coverage is not attendance', 'Static room metadata; historical validity unverified'])
    (root / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    pd.DataFrame(results).groupby('model')[['log_loss','brier_score','roc_auc','peak_roc_auc']].mean().to_csv(root / 'summary.csv')


if __name__ == '__main__':
    main()
