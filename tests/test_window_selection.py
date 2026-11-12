import unittest
import pandas as pd
from pathlib import Path


class WindowSelectionTests(unittest.TestCase):
    def test_selected_parameters_use_only_inner_scores(self):
        root = Path('experiments/demand_forecasting/runs/20261112_window_v6')
        inner = pd.read_csv(root/'inner_scores.csv')
        selections = pd.read_csv(root/'selections.csv')
        for row in selections.itertuples():
            fold = inner[inner.outer == row.month]
            self.assertTrue((pd.to_datetime(fold.end_exclusive) <= pd.Timestamp(row.month)).all())
            means = fold.groupby(['group','C','window_days']).log_loss.mean()
            self.assertAlmostEqual(means.min(),row.inner_log_loss)
            self.assertAlmostEqual(means.loc[(row.group,row.C,row.window_days)],row.inner_log_loss)

    def test_expanding_control_reproduces_previous_round(self):
        root = Path('experiments/demand_forecasting/runs')
        old = pd.read_csv(root/'20261111_current_year_v5/metrics.csv')
        new = pd.read_csv(root/'20261112_window_v6/metrics.csv')
        old = old[old.model == 'selected'].set_index('month')
        new = new[new.model == 'expanding_selected'].set_index('month')
        for month in old.index:
            self.assertAlmostEqual(old.loc[month,'log_loss'],new.loc[month,'log_loss'],places=10)
