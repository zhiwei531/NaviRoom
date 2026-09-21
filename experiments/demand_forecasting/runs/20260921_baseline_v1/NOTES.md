# Baseline v1 observations

Logistic regression was selected because it had the lowest validation log loss (0.5148). The held-out test period reached ROC AUC 0.8165 and peak-hour ROC AUC 0.7954, compared with 0.7241 and 0.6904 for the historical-mean baseline.

The validation period had a 21.4% occupied-slot rate, while the test period had 12.5%. This material seasonal shift means one split is not enough for a deployment claim. The next experiment should add expanding-window backtests and academic-calendar features.

HistGradientBoosting scored better than logistic regression on the test period, but it was not selected after seeing the test result. Changing selection on that basis would leak test information into model choice.
