from __future__ import annotations

import argparse
import csv
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

from .data import build_slot_panel, load_dku_reservations


CATEGORICAL_COLUMNS = ["room_id", "room_type"]
NUMERIC_COLUMNS = [
    "floor",
    "capacity",
    "has_screen",
    "has_whiteboard",
    "metadata_inferred",
    "slot_minute",
    "day_of_week",
    "month",
    "is_weekend",
    "hour_sin",
    "hour_cos",
    "dow_sin",
    "dow_cos",
    "lag_1d",
    "lag_7d",
    "recent_7d_rate",
    "recent_28d_rate",
    "same_weekday_4w_rate",
]
FEATURE_COLUMNS = CATEGORICAL_COLUMNS + NUMERIC_COLUMNS


def _metrics(y_true: pd.Series, probability: np.ndarray, slot_minute: pd.Series) -> dict[str, float]:
    prediction = probability >= 0.5
    peak = slot_minute.between(14 * 60, 21 * 60)
    result = {
        "roc_auc": float(roc_auc_score(y_true, probability)),
        "average_precision": float(average_precision_score(y_true, probability)),
        "log_loss": float(log_loss(y_true, probability, labels=[0, 1])),
        "brier_score": float(brier_score_loss(y_true, probability)),
        "accuracy_at_0_5": float(accuracy_score(y_true, prediction)),
        "observed_rate": float(y_true.mean()),
        "predicted_rate": float(probability.mean()),
    }
    if peak.any() and y_true[peak].nunique() > 1:
        result["peak_roc_auc"] = float(roc_auc_score(y_true[peak], probability[peak]))
        result["peak_log_loss"] = float(log_loss(y_true[peak], probability[peak], labels=[0, 1]))
    return result


class HistoricalMeanModel:
    def fit(self, frame: pd.DataFrame, target: pd.Series) -> "HistoricalMeanModel":
        source = frame[["room_id", "day_of_week", "slot_minute"]].copy()
        source["target"] = target.to_numpy()
        self.exact = source.groupby(["room_id", "day_of_week", "slot_minute"])["target"].mean()
        self.room_slot = source.groupby(["room_id", "slot_minute"])["target"].mean()
        self.slot = source.groupby("slot_minute")["target"].mean()
        self.global_mean = float(target.mean())
        return self

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        probabilities = []
        for row in frame[["room_id", "day_of_week", "slot_minute"]].itertuples(index=False):
            value = self.exact.get((row.room_id, row.day_of_week, row.slot_minute), np.nan)
            if pd.isna(value):
                value = self.room_slot.get((row.room_id, row.slot_minute), np.nan)
            if pd.isna(value):
                value = self.slot.get(row.slot_minute, self.global_mean)
            probabilities.append(float(np.clip(value, 1e-6, 1 - 1e-6)))
        return np.asarray(probabilities)


def _logistic_pipeline() -> Pipeline:
    categorical = Pipeline(
        [("impute", SimpleImputer(strategy="most_frequent")), ("encode", OneHotEncoder(handle_unknown="ignore"))]
    )
    numeric = Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())])
    return Pipeline(
        [
            ("preprocess", ColumnTransformer([("categorical", categorical, CATEGORICAL_COLUMNS), ("numeric", numeric, NUMERIC_COLUMNS)])),
            ("classifier", LogisticRegression(max_iter=300, solver="lbfgs")),
        ]
    )


def _boosting_pipeline() -> Pipeline:
    categorical = Pipeline(
        [("impute", SimpleImputer(strategy="most_frequent")), ("encode", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1))]
    )
    numeric = Pipeline([("impute", SimpleImputer(strategy="median"))])
    return Pipeline(
        [
            ("preprocess", ColumnTransformer([("categorical", categorical, CATEGORICAL_COLUMNS), ("numeric", numeric, NUMERIC_COLUMNS)])),
            (
                "classifier",
                HistGradientBoostingClassifier(
                    learning_rate=0.08,
                    max_iter=120,
                    max_leaf_nodes=31,
                    min_samples_leaf=40,
                    l2_regularization=0.2,
                    random_state=42,
                    categorical_features=[0, 1],
                ),
            ),
        ]
    )


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def train(args: argparse.Namespace) -> dict[str, Any]:
    reservations, rooms, audit = load_dku_reservations(args.workbook, args.rooms)
    panel = build_slot_panel(reservations, rooms)
    last_date = panel["date"].max()
    test_start = last_date - pd.Timedelta(days=args.test_days - 1)
    validation_start = test_start - pd.Timedelta(days=args.validation_days)
    train_frame = panel[panel["date"] < validation_start]
    validation_frame = panel[(panel["date"] >= validation_start) & (panel["date"] < test_start)]
    train_validation_frame = panel[panel["date"] < test_start]
    test_frame = panel[panel["date"] >= test_start]
    if min(len(train_frame), len(validation_frame), len(test_frame)) == 0:
        raise ValueError("The requested time split produced an empty partition")

    factories = {
        "historical_mean": HistoricalMeanModel,
        "logistic_regression": _logistic_pipeline,
        "hist_gradient_boosting": _boosting_pipeline,
    }
    validation_metrics: dict[str, Any] = {}
    for name, factory in factories.items():
        model = factory()
        model.fit(train_frame[FEATURE_COLUMNS], train_frame["occupied"])
        probability = model.predict_proba(validation_frame[FEATURE_COLUMNS])
        if probability.ndim == 2:
            probability = probability[:, 1]
        validation_metrics[name] = _metrics(
            validation_frame["occupied"], probability, validation_frame["slot_minute"]
        )

    selected_model = min(validation_metrics, key=lambda name: validation_metrics[name]["log_loss"])
    test_metrics: dict[str, Any] = {}
    fitted_models: dict[str, Any] = {}
    prediction_output = test_frame[["date", "room_id", "slot_minute", "occupied"]].copy()
    for name, factory in factories.items():
        model = factory()
        model.fit(train_validation_frame[FEATURE_COLUMNS], train_validation_frame["occupied"])
        probability = model.predict_proba(test_frame[FEATURE_COLUMNS])
        if probability.ndim == 2:
            probability = probability[:, 1]
        test_metrics[name] = _metrics(test_frame["occupied"], probability, test_frame["slot_minute"])
        prediction_output[f"probability_{name}"] = probability
        fitted_models[name] = model

    run_dir = Path(args.track_dir) / args.run_name
    artifact_dir = Path(args.artifact_dir)
    run_dir.mkdir(parents=True, exist_ok=False)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": fitted_models[selected_model],
            "model_name": selected_model,
            "feature_columns": FEATURE_COLUMNS,
            "trained_through": str(test_start.date() - pd.Timedelta(days=1)),
            "slot_minutes": 30,
        },
        artifact_dir / "latest.joblib",
    )
    prediction_output.to_csv(artifact_dir / f"{args.run_name}_test_predictions.csv", index=False)

    manifest = {
        "run_name": args.run_name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit_before_run": _git_commit(),
        "python": platform.python_version(),
        "pandas": pd.__version__,
        "scikit_learn": sklearn.__version__,
        "target": "occupied in a room x 30-minute slot",
        "status_interpretation": "The source has no outcome status; rows are treated as recorded reservations, not verified attendance.",
        "split": {
            "train_start": str(train_frame["date"].min().date()),
            "train_end": str(train_frame["date"].max().date()),
            "validation_start": str(validation_frame["date"].min().date()),
            "validation_end": str(validation_frame["date"].max().date()),
            "test_start": str(test_frame["date"].min().date()),
            "test_end": str(test_frame["date"].max().date()),
        },
        "rows": {
            "train": int(len(train_frame)),
            "validation": int(len(validation_frame)),
            "train_validation": int(len(train_validation_frame)),
            "test": int(len(test_frame)),
        },
        "features": FEATURE_COLUMNS,
        "model_selection_metric": "validation log_loss (lower is better)",
        "selected_model": selected_model,
        "validation_metrics": validation_metrics,
        "test_metrics": test_metrics,
    }
    _write_json(run_dir / "data_audit.json", audit)
    _write_json(run_dir / "manifest.json", manifest)
    with open(run_dir / "metrics.csv", "w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(["split", "model", "metric", "value"])
        for split, results in (("validation", validation_metrics), ("test", test_metrics)):
            for model_name, model_metrics in results.items():
                for metric, value in model_metrics.items():
                    writer.writerow([split, model_name, metric, value])
    registry_path = Path(args.track_dir) / "index.csv"
    registry_exists = registry_path.exists()
    with open(registry_path, "a", newline="", encoding="utf-8") as output:
        writer = csv.writer(output, lineterminator="\n")
        if not registry_exists:
            writer.writerow(
                [
                    "run_name",
                    "created_at_utc",
                    "source_sha256",
                    "selected_model",
                    "validation_log_loss",
                    "test_log_loss",
                    "test_roc_auc",
                    "test_peak_roc_auc",
                ]
            )
        selected_test = test_metrics[selected_model]
        writer.writerow(
            [
                args.run_name,
                manifest["created_at_utc"],
                audit["workbook_sha256"],
                selected_model,
                validation_metrics[selected_model]["log_loss"],
                selected_test["log_loss"],
                selected_test["roc_auc"],
                selected_test.get("peak_roc_auc"),
            ]
        )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the NaviRoom DKU demand forecasting baseline")
    parser.add_argument("--workbook", default="data_processing/data/dku_room_data/dku_library_reservation.xlsx")
    parser.add_argument("--rooms", default="data_processing/data/dku_room_data/rooms.csv")
    parser.add_argument("--validation-days", type=int, default=45)
    parser.add_argument("--test-days", type=int, default=45)
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--track-dir", default="experiments/demand_forecasting/runs")
    parser.add_argument("--artifact-dir", default="artifacts/demand_forecasting")
    return parser.parse_args()


if __name__ == "__main__":
    result = train(parse_args())
    print(json.dumps(result, indent=2))
