"""Predeclared temporal calibration comparison; never fit on evaluation labels."""
import json
import subprocess
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from .data import build_slot_panel, load_dku_reservations
from .train import FEATURE_COLUMNS, _logistic_pipeline, _metrics


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p)).reshape(-1, 1)


def smoothed(train, test, half_life=None, strength=5):
    source = train.copy()
    source['weight'] = 1.0 if half_life is None else np.power(
        0.5, (train.date.max() - train.date).dt.days / half_life)
    source['positive'] = source.weight * source.occupied
    # Parent prior shares evidence across rooms, but preserves type and hour.
    parent_keys = ['room_type', 'slot_minute']
    keys = ['room_id', 'day_of_week', 'slot_minute']
    parent = source.groupby(parent_keys)[['positive', 'weight']].sum()
    parent['prior'] = (parent.positive + 1) / (parent.weight + 2)
    stats = source.groupby(keys)[['positive', 'weight']].sum()
    joined = test.merge(parent[['prior']], on=parent_keys, how='left').merge(stats, on=keys, how='left')
    prior = joined.prior.fillna((source.positive.sum() + 1) / (source.weight.sum() + 2))
    return ((joined.positive.fillna(0) + strength * prior) /
            (joined.weight.fillna(0) + strength)).to_numpy()


def main():
    root = Path('experiments/demand_forecasting/runs/20261110_calibration_v3')
    root.mkdir(parents=True, exist_ok=False)
    config = dict(half_life_days=30, prior_strength=5, calibration_days=28,
                  protocol='Monthly weights, daily midnight lag updates; chronological 28-day calibration, base model frozen after calibration.',
                  evaluation='Exploratory reuse of six historical windows; no untouched holdout and no deployment.',
                  python=sys.version, commit=subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip())
    (root / 'config.json').write_text(json.dumps(config, indent=2))
    (root / 'environment.txt').write_text(subprocess.check_output([sys.executable,'-m','pip','freeze'], text=True))
    reservations, rooms, audit = load_dku_reservations('data_processing/data/dku_room_data/dku_library_reservation.xlsx', 'data_processing/data/dku_room_data/rooms.csv')
    if (reservations.requested_at > reservations.start_time).any():
        raise ValueError('Late entries require as-of reconstruction')
    panel = build_slot_panel(reservations, rooms)
    panel = panel[panel.date < reservations.requested_at.max().normalize()]
    (root / 'data_audit.json').write_text(json.dumps(audit, indent=2))
    rows, bins = [], []
    for start in pd.date_range('2025-09-01', '2026-02-01', freq='MS'):
        train = panel[panel.date < start]
        test = panel[(panel.date >= start) & (panel.date < start + pd.offsets.MonthBegin())]
        split = start - pd.Timedelta(days=28)
        fit, calibration = train[train.date < split], train[train.date >= split]
        predictions = {'smoothed_history': smoothed(train, test), 'recency_history': smoothed(train, test, 30)}
        full = _logistic_pipeline().fit(train[FEATURE_COLUMNS], train.occupied)
        predictions['logistic_full'] = full.predict_proba(test[FEATURE_COLUMNS])[:, 1]
        weighted = _logistic_pipeline().fit(train[FEATURE_COLUMNS], train.occupied,
            classifier__sample_weight=np.power(0.5, (train.date.max()-train.date).dt.days / 30))
        predictions['logistic_recency'] = weighted.predict_proba(test[FEATURE_COLUMNS])[:, 1]
        base = _logistic_pipeline().fit(fit[FEATURE_COLUMNS], fit.occupied)
        cp = base.predict_proba(calibration[FEATURE_COLUMNS])[:, 1]
        tp = base.predict_proba(test[FEATURE_COLUMNS])[:, 1]
        platt = LogisticRegression(C=1.0).fit(logit(cp), calibration.occupied)
        predictions['logistic_frozen_uncalibrated'] = tp
        predictions['logistic_platt'] = platt.predict_proba(logit(tp))[:, 1]
        for name, p in predictions.items():
            row = dict(month=str(start.date()), model=name, **_metrics(test.occupied, p, test.slot_minute))
            row['absolute_rate_error'] = abs(row['observed_rate'] - row['predicted_rate'])
            rows.append(row)
            for i in range(10):
                mask = (p >= i/10) & (p < (i+1)/10 if i < 9 else p <= 1)
                if mask.any():
                    bins.append(dict(month=str(start.date()), model=name, bin=i, count=int(mask.sum()),
                                     predicted=float(p[mask].mean()), observed=float(test.occupied.to_numpy()[mask].mean())))
        pd.DataFrame(rows).to_csv(root/'metrics.csv', index=False)
        print(str(start.date()) + ' completed', flush=True)
    pd.DataFrame(bins).to_csv(root/'reliability.csv', index=False)
    summary = pd.DataFrame(rows).groupby('model')[['log_loss','brier_score','roc_auc','peak_roc_auc','absolute_rate_error']].mean()
    summary.to_csv(root/'summary.csv')
    print(summary.to_string())


if __name__ == '__main__':
    main()
