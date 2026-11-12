# Window-selection experiment

Command: `python -m demand_forecasting.current_year --select-window --run-name 20261112_window_v6`.

Adds a 42-day training window to the v5 expanding-history candidates. Same two inner 14-day windows, current-year-only data, feature groups and regularization grid. Each inner fit truncates training at its own origin; rolling features still use available prior current-year history. Model parameters are selected before outer evaluation. 120 inner fits and 15 outer fits completed.

The expanding control exactly reproduces v5. Four months choose expanding history; February alone chooses 42 days. Monthly-average loss increases from 0.395538 to 0.416283, Brier from 0.127868 to 0.131454, AUC falls from 0.826794 to 0.810294. Do not promote the window-selection extension. Retain v5 as the current experimental reference.

Inner February improvement is small (0.475048 to 0.470996) and fails to generalize to its outer month. Do not invent a switching threshold from this observed outer result. Further changes need predefined inner selection rules and paired controls. Repeated historical evaluation remains exploratory; no untouched holdout, online improvement, or production deployment is claimed.

Config, environment, data fingerprint, all inner candidate losses, chosen parameters and outer metrics are included. Compatibility deprecation warnings from pandas/NumPy date arithmetic did not interrupt training; tests confirm chronological boundaries and control reproduction.
