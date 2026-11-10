# Recency and calibration comparison

Reproduce: `.venv/bin/python -m demand_forecasting.calibration_backtest`.

Six monthly windows, six configurations, parameters fixed before this run. Monthly averages are unweighted. Evaluation reuses historical windows and is exploratory, not an independent final holdout.

Full-history logistic regression remains the comparison baseline: mean log loss 0.483659, Brier 0.152811. Recency-weighted logistic regression scores 0.498592/0.163795; recency-smoothed history 0.530111/0.170403; smoothed history 0.596926/0.180322. No candidate is promoted.

Platt calibration uses only the preceding 28 days, after fitting the base estimator on earlier days. The base is not refitted after calibration. Its appropriate paired comparator is the frozen uncalibrated model: mean loss improves from 0.651888 to 0.559605, but is still worse than full-history logistic regression. January calibration predicts 1.48% against 25.15% recorded coverage, illustrating failure under seasonal change. Recency logistic predicts 39.07% in January, overshooting despite better loss than full-history logistic.

`reliability.csv` records fixed probability-bin counts, observed fractions and predicted probabilities for every model/month. `metrics.csv` includes monthly probability bias and peak metrics. Environment, source hashes, configuration and training source commit are retained.

Limitations inherited from v2: daily-origin historical feature updates, unverified opening hours/export completeness/static metadata, recorded bookings rather than attendance, and no recommendation feedback. No production service changes. Next useful experiment: calendar-aware features or time-window selection using nested temporal validation, with calibration evaluated across term transitions.
