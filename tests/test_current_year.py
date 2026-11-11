import unittest
import pandas as pd
from demand_forecasting.current_year import inner_windows, model


class CurrentYearTests(unittest.TestCase):
    def test_selection_windows_end_before_outer_labels(self):
        outer = pd.Timestamp('2026-01-01')
        windows = inner_windows(outer)
        self.assertEqual(windows[0][1], windows[1][0])
        self.assertEqual(windows[-1][1], outer)
        for start,end in windows:
            self.assertEqual((end-start).days,14)
            self.assertLess(start,outer)

    def test_both_arms_exclude_numeric_month(self):
        for group in ['base','compact_calendar']:
            numeric = model(group,0.1).named_steps['features'].transformers[1][2]
            self.assertNotIn('month',numeric)
