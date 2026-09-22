"""Mangrove detection baseline: Random Forest / Gradient Boosting on
per-pixel spectral-index features. Per the build strategy, this is the
model that must be working and validated before any UNet++ effort — UNet++
is gated on having real labeled Sentinel-2 tiles, which this sandbox does
not have (no GEE credentials, no ingested label imagery yet).

Trains and evaluates on whatever DataFrame it's given (synthetic fixture
today, real spatially-split training_labels once ingested — see
mangrove_ai.labels). Never claims a metric it did not measure: metrics are
computed from the actual held-out split passed in, not asserted.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score

from mangrove_ai.indices import compute_all_indices

FEATURE_COLUMNS = ["NDVI", "EVI", "MSAVI", "NDWI", "MNDWI", "NDMI", "MVI", "SI", "BSI"]
MODEL_DIR = Path(__file__).resolve().parent / "artifacts"


@dataclass
class TrainResult:
    algorithm: str
    metrics: dict = field(default_factory=dict)
    feature_importance: dict = field(default_factory=dict)
    n_train: int = 0
    n_val: int = 0
    model_path: str = ""


def _features_from_bands(df: pd.DataFrame) -> pd.DataFrame:
    bands = {c: df[c].to_numpy() for c in ["blue", "green", "red", "nir", "swir1"] if c in df.columns}
    indices = compute_all_indices(bands)
    return pd.DataFrame(indices)


def _iou(y_true: np.ndarray, y_pred: np.ndarray, positive_label) -> float:
    tp = int(np.sum((y_true == positive_label) & (y_pred == positive_label)))
    fp = int(np.sum((y_true != positive_label) & (y_pred == positive_label)))
    fn = int(np.sum((y_true == positive_label) & (y_pred != positive_label)))
    denom = tp + fp + fn
    return tp / denom if denom > 0 else 0.0


def train_and_evaluate(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    algorithm: str = "random_forest",
    label_col: str = "label",
) -> tuple[object, TrainResult]:
    """train_df/val_df must already be spatially split by the caller (no
    random shuffling of a single pool here — see mangrove_ai.labels for the
    spatial-split enforcement on real data)."""
    X_train = _features_from_bands(train_df)
    y_train = train_df[label_col].to_numpy()
    X_val = _features_from_bands(val_df)
    y_val = val_df[label_col].to_numpy()

    if algorithm == "random_forest":
        model = RandomForestClassifier(n_estimators=200, max_depth=12, random_state=42, class_weight="balanced")
    elif algorithm == "gradient_boosting":
        model = GradientBoostingClassifier(n_estimators=200, max_depth=3, random_state=42)
    else:
        raise ValueError(f"unsupported algorithm: {algorithm}")

    model.fit(X_train, y_train)
    y_pred = model.predict(X_val)

    labels_sorted = sorted(set(y_train) | set(y_val))
    cm = confusion_matrix(y_val, y_pred, labels=labels_sorted).tolist()
    ious = {str(lbl): _iou(y_val, y_pred, lbl) for lbl in labels_sorted}

    metrics = {
        "precision": float(precision_score(y_val, y_pred, average="binary", pos_label="mangrove", zero_division=0)),
        "recall": float(recall_score(y_val, y_pred, average="binary", pos_label="mangrove", zero_division=0)),
        "f1": float(f1_score(y_val, y_pred, average="binary", pos_label="mangrove", zero_division=0)),
        "iou_per_class": ious,
        "miou": float(np.mean(list(ious.values()))),
        "confusion_matrix": {"labels": labels_sorted, "matrix": cm},
    }

    feature_importance = {}
    if hasattr(model, "feature_importances_"):
        feature_importance = {col: float(imp) for col, imp in zip(FEATURE_COLUMNS, model.feature_importances_)}

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_DIR / f"{algorithm}.joblib"
    joblib.dump(model, model_path)

    result = TrainResult(
        algorithm=algorithm,
        metrics=metrics,
        feature_importance=feature_importance,
        n_train=len(train_df),
        n_val=len(val_df),
        model_path=str(model_path),
    )
    return model, result


def predict_proba(model, feature_df: pd.DataFrame) -> np.ndarray:
    """Returns P(mangrove) per row."""
    classes = list(model.classes_)
    idx = classes.index("mangrove")
    return model.predict_proba(feature_df[FEATURE_COLUMNS])[:, idx]


if __name__ == "__main__":
    from mangrove_ai.active_learning import register_candidate_model
    from mangrove_ai.fixtures import synthetic_band_pixels

    print("SMOKE TEST ONLY — training on mangrove_ai.fixtures synthetic data. "
          "These metrics are a software smoke test, not a scientific validation "
          "or production model performance. Pakistan mangrove labels have not "
          "been ingested; see mangrove_ai.labels for the real ingestion path.")

    df = synthetic_band_pixels(n=3000)
    split = int(len(df) * 0.7)
    train_df, val_df = df.iloc[:split], df.iloc[split:]
    _, result = train_and_evaluate(train_df, val_df, algorithm="random_forest")
    print(json.dumps({"metrics": result.metrics, "feature_importance": result.feature_importance}, indent=2))

    model_id = register_candidate_model(
        task="mangrove_classifier",
        version=f"smoke-test-{result.algorithm}-v0",
        algorithm=result.algorithm,
        metrics=result.metrics,
        feature_importance=result.feature_importance,
        training_data_ref="mangrove_ai.fixtures.synthetic_band_pixels (SMOKE TEST — not real Pakistan mangrove labels)",
        is_synthetic=True,
        created_by="system",
    )
    print(f"Registered as candidate model {model_id} (is_synthetic=true, not promotable).")
