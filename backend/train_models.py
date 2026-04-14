"""
Train three estimators for device resale price:
- Linear Regression (sklearn)
- Random Forest Regressor (sklearn)
- K-Means: cluster devices in feature space only; predicted price is the **price centroid**
  (mean resale price of training points in that cluster), not a learned regression on features.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from data_preprocessing import (
    TARGET_COLUMN,
    build_preprocessor,
    feature_matrix,
    get_data_path,
    inject_missing_for_demo,
    load_dataset,
)

# --- Paths & hyperparameters -------------------------------------------------
MODEL_DIR = Path(__file__).resolve().parent / "models" / "price_estimation"
ARTIFACT_PREPROCESSOR = MODEL_DIR / "preprocessor.joblib"
ARTIFACT_LINEAR = MODEL_DIR / "linear_regression.joblib"
ARTIFACT_RF = MODEL_DIR / "random_forest.joblib"
ARTIFACT_KMEANS = MODEL_DIR / "kmeans.joblib"
# Mean training resale price per cluster (1D centroid of prices in that cluster)
ARTIFACT_CLUSTER_CENTROID_PRICES = MODEL_DIR / "cluster_centroid_prices.joblib"
ARTIFACT_CLUSTER_FEATURE_CENTROIDS = MODEL_DIR / "cluster_feature_centroids.joblib"
METRICS_PATH = MODEL_DIR / "metrics.json"

N_CLUSTERS = 8
RF_N_ESTIMATORS = 120
TEST_SIZE = 0.2
RANDOM_STATE = 42


def _ensure_model_dir() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)


def _regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    mae = mean_absolute_error(y_true, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    r2 = float(r2_score(y_true, y_pred))
    return {"mae": mae, "rmse": rmse, "r2": r2}


def train_and_persist(csv_path: Path | None = None, inject_missing: bool = True) -> dict:
    """
    Load data, preprocess, train all models, save artifacts and evaluation JSON.

    Returns the metrics dict written to metrics.json.
    """
    _ensure_model_dir()
    df = load_dataset(csv_path)
    if inject_missing:
        df = inject_missing_for_demo(df)

    X = feature_matrix(df)
    y = df[TARGET_COLUMN].values

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
    )

    # Linear regression — reuse its fitted preprocessor for K-Means (same feature space).
    linear = Pipeline(
        steps=[
            ("prep", build_preprocessor()),
            ("model", LinearRegression()),
        ]
    )
    linear.fit(X_train, y_train)
    lin_pred = linear.predict(X_test)

    preprocessor = linear.named_steps["prep"]
    X_train_t = preprocessor.transform(X_train)
    X_test_t = preprocessor.transform(X_test)

    # Random forest (separate pipeline; trained on raw features like linear).
    rf = Pipeline(
        steps=[
            ("prep", build_preprocessor()),
            (
                "model",
                RandomForestRegressor(
                    n_estimators=RF_N_ESTIMATORS,
                    random_state=RANDOM_STATE,
                    n_jobs=-1,
                ),
            ),
        ]
    )
    rf.fit(X_train, y_train)
    rf_pred = rf.predict(X_test)

    # K-Means on features only (transformed X). Price is not used to fit clusters.
    kmeans = KMeans(n_clusters=N_CLUSTERS, random_state=RANDOM_STATE, n_init=10)
    train_labels = kmeans.fit_predict(X_train_t)
    # Centroid price per cluster = mean resale_price of training rows in that cluster
    cluster_centroid_prices = np.zeros(N_CLUSTERS, dtype=float)
    for k in range(N_CLUSTERS):
        mask = train_labels == k
        cluster_centroid_prices[k] = float(y_train[mask].mean()) if np.any(mask) else float(np.mean(y_train))

    test_labels = kmeans.predict(X_test_t)
    km_pred = cluster_centroid_prices[test_labels]

    test_n = int(len(y_test))
    # Per-model test metrics (each model has its own y_pred → distinct MAE / RMSE / R²)
    model_metrics = {
        "linear_regression": {
            **_regression_metrics(y_test, lin_pred),
            "evaluation_points": test_n,
        },
        "random_forest": {
            **_regression_metrics(y_test, rf_pred),
            "evaluation_points": test_n,
        },
        "kmeans": {
            **_regression_metrics(y_test, km_pred),
            "evaluation_points": test_n,
        },
    }
    metrics = {
        **model_metrics,
        "n_clusters": N_CLUSTERS,
        "test_size": TEST_SIZE,
        "test_evaluation_n": test_n,
    }

    joblib.dump(preprocessor, ARTIFACT_PREPROCESSOR)
    joblib.dump(linear, ARTIFACT_LINEAR)
    joblib.dump(rf, ARTIFACT_RF)
    joblib.dump(kmeans, ARTIFACT_KMEANS)
    joblib.dump(cluster_centroid_prices, ARTIFACT_CLUSTER_CENTROID_PRICES)
    joblib.dump(kmeans.cluster_centers_, ARTIFACT_CLUSTER_FEATURE_CENTROIDS)

    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print("Saved models to:", MODEL_DIR)
    print("Metrics:", json.dumps(metrics, indent=2))
    return metrics


if __name__ == "__main__":
    train_and_persist(get_data_path())
