"""Current-year-only nested temporal model selection."""
import json
import subprocess
import sys
from pathlib import Path
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from .data import build_slot_panel, load_dku_reservations
from .calendar_features import add_calendar
from .train import NUMERIC_COLUMNS, CATEGORICAL_COLUMNS, _metrics

GROUPS = {'base': [], 'compact_calendar': ['no_classes','ug_reading','ug_exam','winter_halls_closed','session_active']}


def model(group, c):
    # Omit month: only one cycle, and a numeric month creates an artificial
    # discontinuity from December to January. Both arms use identical base inputs.
    nums = [x for x in NUMERIC_COLUMNS if x != 'month'] + GROUPS[group]
    return Pipeline([('features',ColumnTransformer([
        ('cat',OneHotEncoder(handle_unknown='ignore'),CATEGORICAL_COLUMNS),
        ('num',Pipeline([('impute',SimpleImputer(strategy='median')),('scale',StandardScaler())]),nums)])),
        ('classifier',LogisticRegression(C=c,max_iter=500))])


def inner_windows(outer):
    return [(outer-pd.Timedelta(days=d), outer-pd.Timedelta(days=d-14)) for d in [28,14]]


def main():
    root = Path('experiments/demand_forecasting/runs/20261111_current_year_v5')
    root.mkdir(parents=True,exist_ok=False)
    config = dict(start='2025-08-08', outer_months=['2025-10','2025-11','2025-12','2026-01','2026-02'],
        inner='Two preceding non-overlapping 14-day windows; expanding fits; minimum 28 training days.',
        candidates=[(g,c) for g in GROUPS for c in [0.01,0.1,1.0]],
        protocol='Daily midnight lag updates; monthly refit. No previous-academic-year rows or lags.',
        caveats=['Retrospective exploratory reused outer periods, not a fresh holdout',
                 'Opening hours and export completeness remain unverified; bookings are not attendance',
                 'Calendar version provenance and unknown equipment assumptions inherited from v4'],
        commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip())
    (root/'config.json').write_text(json.dumps(config,indent=2))
    (root/'environment.txt').write_text(subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True))
    r, rooms, audit = load_dku_reservations('data_processing/data/dku_room_data/dku_library_reservation.xlsx','data_processing/data/dku_room_data/rooms.csv')
    if (r.requested_at > r.start_time).any():
        raise ValueError('Late-entered booking')
    r = r[r.start_time >= pd.Timestamp(config['start'])]
    panel = add_calendar(build_slot_panel(r,rooms))
    panel = panel[panel.date < r.requested_at.max().normalize()]
    audit['current_year_reservations'] = len(r)
    (root/'audit.json').write_text(json.dumps(audit,indent=2))
    rows, inner, selections = [], [], []
    for outer in pd.to_datetime([m+'-01' for m in config['outer_months']]):
        scores = []
        for group,c in config['candidates']:
            losses = []
            for begin,end in inner_windows(outer):
                train = panel[panel.date < begin]
                valid = panel[(panel.date >= begin)&(panel.date < end)]
                assert train.date.nunique() >= 28 and train.date.max() < valid.date.min() and valid.date.max() < outer
                fitted = model(group,c).fit(train,train.occupied)
                loss = log_loss(valid.occupied,fitted.predict_proba(valid)[:,1])
                losses.append(loss)
                inner.append(dict(outer=str(outer.date()),group=group,C=c,start=str(begin.date()),end_exclusive=str(end.date()),log_loss=loss))
            scores.append((sum(losses)/len(losses),group,c))
        _,group,c = min(scores)
        selections.append(dict(month=str(outer.date()),group=group,C=c,inner_log_loss=min(scores)[0]))
        train = panel[panel.date < outer]
        test = panel[(panel.date >= outer)&(panel.date < outer+pd.offsets.MonthBegin())]
        for name,g,regularization in [('base', 'base',1.0),('selected',group,c)]:
            fitted = model(g,regularization).fit(train,train.occupied)
            p = fitted.predict_proba(test)[:,1]
            rows.append(dict(month=str(outer.date()),model=name,**_metrics(test.occupied,p,test.slot_minute)))
        for filename,data in [('metrics',rows),('inner_scores',inner),('selections',selections)]:
            pd.DataFrame(data).to_csv(root/(filename+'.csv'),index=False)
        print(selections[-1],flush=True)
    summary = pd.DataFrame(rows).groupby('model')[['log_loss','brier_score','roc_auc','peak_roc_auc']].mean()
    summary.to_csv(root/'summary.csv')
    print(summary.to_string())


if __name__ == '__main__':
    main()
