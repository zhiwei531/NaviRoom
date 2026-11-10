import unittest
import numpy as np
import pandas as pd
from demand_forecasting.calibration_backtest import smoothed, logit


class CalibrationTests(unittest.TestCase):
    def test_unseen_room_has_finite_parent_prior(self):
        train = pd.DataFrame(dict(date=pd.to_datetime(['2025-01-01','2025-01-02']),
            room_id=['A','A'], room_type=['study','study'], slot_minute=[600,600],
            day_of_week=[2,3], occupied=[0,1]))
        test = train.iloc[[0]].copy()
        test['room_id'] = 'unseen'
        p = smoothed(train, test)
        self.assertAlmostEqual(p[0], 0.5)
        test['occupied'] = 999
        np.testing.assert_array_equal(p, smoothed(train, test))

    def test_logit_boundaries_are_finite(self):
        self.assertTrue(np.isfinite(logit(np.array([0., 0.5, 1.]))).all())


if __name__ == '__main__':
    unittest.main()
