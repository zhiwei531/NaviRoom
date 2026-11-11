# Current academic year only

Run `python -m demand_forecasting.current_year`. Calendar definitions and PDF provenance remain in calendar_features.py and v4 config. Reservation rows before August 8, 2025 are removed BEFORE lag construction; the panel starts at the first subsequent recorded booking. Five outer months October–February allow within-year warm-up. Two preceding 14-day inner windows choose among two feature groups and three regularization values; all inner labels precede the outer month. Parameters are then refit on all preceding current-year rows.

Both arms omit numeric month, avoiding a December–January numerical discontinuity. This is a changed cohort and feature set, so comparisons to v2/v4 aggregates are not paired. The same-run base is the appropriate comparator. Calendar attribution alone requires a further controlled ablation.

Monthly macro-average loss: base 0.429461, selected 0.395538 (7.90% reduction); Brier 0.138143 to 0.127868; AUC 0.790646 to 0.826794. Selected improves loss in four of five months, with a small October regression. January coverage predicted 21.94% versus observed 25.15%. February still overpredicts (22.05% versus 17.44%). No automatic deployment or claim of improved real utilization.

Outer dates were examined in prior experiments; nested selection prevents within-run label leakage but does not make these dates an untouched holdout. Export completeness, historical metadata and opening-time assumptions remain unchanged. Initial attempt required 28 training days and stopped before fitting; its configuration is retained in the sibling initial_insufficient_history directory. The completed run permits 14 warm-up days, decided before outer scoring.
