# Demand forecasting experiment tracking

`index.csv` is the run registry. Each directory under `runs/` contains immutable metrics and source fingerprints for one experiment.

The first baseline uses a chronological split and selects the model only from validation log loss. Test metrics are kept for final comparison and must not be used to retroactively change that run's selected model.

Large model and prediction files stay under `artifacts/demand_forecasting/` and are not committed.
