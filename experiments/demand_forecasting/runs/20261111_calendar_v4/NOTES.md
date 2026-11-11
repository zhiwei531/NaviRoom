# Calendar ablation

Source: user-supplied 2025–26 DKU calendar, both pages visually checked. PDF hash in config.json; printed revision March 3, 2025 differs from the filename version. Original PDF is not redistributed. Transcribed features are in calendar_features.py; no-class periods are not library closure labels.

Reproduce with `python -m demand_forecasting.calendar_backtest --calendar /path/to/source.pdf --run-name NEW_RUN`. Initial training used the equivalent fixed local source path before the CLI portability patch.

Six monthly paired comparisons reuse the previous exploratory windows. No hyperparameter search or model promotion. Average AUC improves from 0.7850 to 0.8099 and peak AUC from 0.7627 to 0.7903, but log loss worsens from 0.4837 to 0.5188 and Brier from 0.1528 to 0.1632. December improves strongly (loss 0.3715 to 0.2253). January overcorrects: predicted coverage 54.25% versus actual 25.15%, compared with baseline 9.52%. Calendar does not yet justify replacing the baseline probability estimator.

Only August 2025 onward has verified calendar coverage. Earlier history is explicitly unknown. With one annual cycle and few examples of each event, extrapolation is fragile. The version's historical availability is unverified; results are retrospective calendar-conditioned experiments. Later March features are transcribed but not assessed in the six windows.

Next experiment should select calendar feature groups and regularization using inner temporal validation, leaving outer evaluations for reporting. Earlier academic-year calendar and additional annual cycles would improve event coverage. Keep the current baseline until probability calibration improves consistently.
