# DKU room demand forecasting

This module trains a supervised baseline from the original DKU library export. It predicts whether a room will be reserved in each 30-minute slot. It does not treat the generated `completed` value in the normalized JSON as real attendance, because the source workbook has no status field.

## Run

```bash
python -m demand_forecasting.train --run-name YYYYMMDD_baseline_v1
```

Each run writes a small, Git-trackable record under `experiments/demand_forecasting/runs/<run-name>/`:

- `data_audit.json`: source hashes and known data-quality facts;
- `manifest.json`: environment, time split, features, model selection and metrics;
- `metrics.csv`: tidy validation and test metrics.

Model binaries and slot-level predictions are written under `artifacts/demand_forecasting/` and are intentionally excluded from Git.

## Evaluation rules

- The last 45 calendar days are the test set.
- The preceding 45 days are the validation set.
- Model selection uses validation log loss.
- Test results are reported once for the selected configuration.
- Lag and rolling features are shifted before calculation, so a row never uses its own target or a future target.
- R2008 is retained with metadata inferred from its reservation description and is flagged by `metadata_inferred=1`.

The current data measures recorded reservations, not failed searches, recommendation acceptance, check-in, cancellation or actual attendance.
