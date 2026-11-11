"""Paired calendar ablation with identical daily-origin rolling evaluation."""
import json
import argparse
import subprocess
import sys
from pathlib import Path
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.linear_model import LogisticRegression
from .data import build_slot_panel, load_dku_reservations, file_sha256
from .train import FEATURE_COLUMNS, NUMERIC_COLUMNS, CATEGORICAL_COLUMNS, _logistic_pipeline, _metrics
from .calendar_features import add_calendar, CALENDAR_COLUMNS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--calendar', required=True, type=Path)
    parser.add_argument('--run-name', default='20261111_calendar_v4')
    args = parser.parse_args()
    root = Path('experiments/demand_forecasting/runs') / args.run_name
    root.mkdir(parents=True, exist_ok=False)
    source = args.calendar
    config = dict(calendar_file=source.name, calendar_sha256=file_sha256(source), printed_revision='March 3, 2025',
        pages=[1,2], source_commit=subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip(),
        protocol='Paired monthly expanding-window fits, daily midnight feature updates; fixed parameters; exploratory reused windows.',
        caveats=['Calendar version availability at historical decision dates unverified', 'Pre-August dates have unknown calendar; not labelled as holidays',
                 'No class and residence closure do not mean library closure', 'Static metadata and complete-export assumptions inherited from v2'],
        python=sys.version)
    (root/'config.json').write_text(json.dumps(config, indent=2))
    (root/'environment.txt').write_text(subprocess.check_output([sys.executable,'-m','pip','freeze'], text=True))
    reservations, rooms, audit = load_dku_reservations('data_processing/data/dku_room_data/dku_library_reservation.xlsx','data_processing/data/dku_room_data/rooms.csv')
    assert not (reservations.requested_at > reservations.start_time).any()
    panel = add_calendar(build_slot_panel(reservations, rooms))
    panel = panel[panel.date < reservations.requested_at.max().normalize()]
    (root/'data_audit.json').write_text(json.dumps(audit, indent=2))
    rows = []
    for start in pd.date_range('2025-09-01','2026-02-01',freq='MS'):
        train = panel[panel.date < start]
        test = panel[(panel.date >= start) & (panel.date < start + pd.offsets.MonthBegin())]
        for name in ['logistic_base','logistic_calendar']:
            cols = FEATURE_COLUMNS
            model = _logistic_pipeline()
            if name == 'logistic_calendar':
                cols = FEATURE_COLUMNS + CALENDAR_COLUMNS
                model = Pipeline([('features', ColumnTransformer([
                    ('cat',OneHotEncoder(handle_unknown='ignore'),CATEGORICAL_COLUMNS),
                    ('num',Pipeline([('fill',SimpleImputer(strategy='median')),('scale',StandardScaler())]),NUMERIC_COLUMNS+CALENDAR_COLUMNS)])),
                    ('model',LogisticRegression(max_iter=300))])
            model.fit(train[cols], train.occupied)
            p = model.predict_proba(test[cols])[:,1]
            rows.append(dict(month=str(start.date()), model=name, **_metrics(test.occupied,p,test.slot_minute)))
        pd.DataFrame(rows).to_csv(root/'metrics.csv',index=False)
        print(str(start.date())+' completed',flush=True)
    summary = pd.DataFrame(rows).groupby('model')[['log_loss','brier_score','roc_auc','peak_roc_auc']].mean()
    summary.to_csv(root/'summary.csv')
    print(summary.to_string())


if __name__ == '__main__':
    main()
