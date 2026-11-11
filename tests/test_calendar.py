import unittest
import pandas as pd
from demand_forecasting.calendar_features import add_calendar


class CalendarTests(unittest.TestCase):
    def test_verified_boundaries_and_unknown_history(self):
        dates = ['2025-04-01','2025-10-08','2025-10-09','2026-01-02','2026-01-05','2026-02-13','2026-02-23','2026-02-24','2026-03-02']
        f = add_calendar(pd.DataFrame({'date':pd.to_datetime(dates)})).set_index('date')
        self.assertEqual(f.loc['2025-04-01','calendar_known'],0)
        self.assertEqual(f.loc['2025-10-08','no_classes'],1)
        self.assertEqual(f.loc['2025-10-09','no_classes'],0)
        self.assertEqual(f.loc['2025-10-09','schedule_day'],2)
        self.assertEqual(f.loc['2026-01-02','winter_halls_closed'],1)
        self.assertEqual(f.loc['2026-01-05','session_week'],1)
        self.assertEqual(f.loc['2026-02-13','schedule_day'],0)
        self.assertEqual(f.loc['2026-02-23','no_classes'],1)
        self.assertEqual(f.loc['2026-02-24','session_active'],1)
        self.assertEqual(f.loc['2026-03-02','ug_exam'],1)
