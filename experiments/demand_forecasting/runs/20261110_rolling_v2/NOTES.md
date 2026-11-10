# Rolling v2

Run: `.venv/bin/python -m demand_forecasting.backtest`.

Six monthly expanding-window evaluations (September 2025–February 2026), 18 model fits. Summary metrics are unweighted monthly averages. Logistic regression has the lowest average log loss (0.4837), versus boosting (0.5062) and the unsmoothed historical baseline (0.7637). It improves log loss over the historical baseline in all six windows, and over boosting in four. The historical baseline's near-zero probabilities exaggerate its log-loss penalty; a smoothed/recency baseline remains necessary.

This is exploratory evaluation, not a fresh untouched holdout: February overlaps the v1 test period. No model is promoted or deployed. Probability calibration remains unstable (January actual 25.2%, logistic prediction 9.5%).

V1 caveats: its evaluation includes dates after the March 18 export boundary, so its headline numbers should not be used as a strict deployment benchmark. V2 excludes the incomplete final day and later dates. Weekly history now uses exactly days 7/14/21/28, including warm-up rows. Daily-origin predictions may use previous evaluation days once those days have elapsed; these are not fixed-origin month-ahead predictions.

Source workbook is unchanged. Existing unit check passed. Environment is recorded alongside the manifest. Analysis hours, zero-booking days and room metadata remain assumptions rather than verified historical opening/availability records.
