"""
Train three estimators for device resale price using sorted_diverse_device_dataset:
- Linear Regression (sklearn)
- Random Forest Regressor (sklearn)
- K-Means: cluster devices in feature space; predicted price = cluster centroid price

Models are trained once and saved for API use (no retraining on each request).
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

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data_preprocessing import (
    ALL_FEATURES,
    TARGET_COLUMN,
    build_preprocessor,
    feature_matrix,
    target_vector,
    load_dataset,
)

# --- Configuration -----------------------------------------------------------
MODEL_DIR = Path(__file__).resolve().parent / "saved"
ARTIFACT_PREPROCESSOR = MODEL_DIR / "preprocessor.pkl"
ARTIFACT_LINEAR = MODEL_DIR / "linear.pkl"
ARTIFACT_RF = MODEL_DIR / "rf.pkl"
ARTIFACT_KMEANS = MODEL_DIR / "kmeans.pkl"
ARTIFACT_CLUSTER_CENTROID_PRICES = MODEL_DIR / "cluster_centroid_prices.pkl"
METRICS_PATH = MODEL_DIR / "metrics.json"

N_CLUSTERS = 8
RF_N_ESTIMATORS = 100
TEST_SIZE = 0.2
RANDOM_STATE = 42


def ensure_model_dir() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """Calculate R2, MAE, RMSE."""
    mae = mean_absolute_error(y_true, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    r2 = float(r2_score(y_true, y_pred))
    return {"r2": r2, "mae": mae, "rmse": rmse}


def train_all_models(csv_path: Path | None = None) -> dict:
    """
    Load data, preprocess, train all 3 models, save artifacts and metrics.

    Returns metrics dict saved to metrics.json.
    """
    ensure_model_dir()

    # Load dataset
    df = load_dataset(csv_path)
    print(f"Loaded dataset: {len(df)} rows")

    # Prepare features and target
    X = feature_matrix(df)
    y = target_vector(df)

    # Train/test split (80/20)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE
    )
    print(f"Train: {len(X_train)}, Test: {len(X_test)}")

    # =========================================================================
    # Model 1: Linear Regression
    # =========================================================================
    print("\n--- Training Linear Regression ---")
    linear_pipeline = Pipeline(
        steps=[
            ("prep", build_preprocessor()),
            ("model", LinearRegression()),
        ]
    )
    linear_pipeline.fit(X_train, y_train)
    lin_pred = linear_pipeline.predict(X_test)
    lin_metrics = regression_metrics(y_test, lin_pred)
    print(f"Linear Regression - R2: {lin_metrics['r2']:.4f}, MAE: {lin_metrics['mae']:.2f}, RMSE: {lin_metrics['rmse']:.2f}")

    # Get fitted preprocessor for use by KMeans
    preprocessor = linear_pipeline.named_steps["prep"]
    X_train_t = preprocessor.transform(X_train)
    X_test_t = preprocessor.transform(X_test)

    # =========================================================================
    # Model 2: Random Forest Regressor
    # =========================================================================
    print("\n--- Training Random Forest ---")
    rf_pipeline = Pipeline(
        steps=[
            ("prep", build_preprocessor()),
            ("model", RandomForestRegressor(
                n_estimators=RF_N_ESTIMATORS,
                random_state=RANDOM_STATE,
                n_jobs=-1
            )),
        ]
    )
    rf_pipeline.fit(X_train, y_train)
    rf_pred = rf_pipeline.predict(X_test)
    rf_metrics = regression_metrics(y_test, rf_pred)
    print(f"Random Forest - R2: {rf_metrics['r2']:.4f}, MAE: {rf_metrics['mae']:.2f}, RMSE: {rf_metrics['rmse']:.2f}")

    # =========================================================================
    # Model 3: KMeans Clustering (cluster-based pricing)
    # =========================================================================
    print("\n--- Training KMeans Clustering ---")
    kmeans = KMeans(n_clusters=N_CLUSTERS, random_state=RANDOM_STATE, n_init=10)
    train_labels = kmeans.fit_predict(X_train_t)

    # Compute centroid price for each cluster (mean resale_price of training points)
    cluster_centroid_prices = np.zeros(N_CLUSTERS, dtype=float)
    for k in range(N_CLUSTERS):
        mask = train_labels == k
        if np.any(mask):
            cluster_centroid_prices[k] = float(y_train[mask].mean())
        else:
            cluster_centroid_prices[k] = float(np.mean(y_train))

    # Predict: assign test points to nearest cluster, return cluster's centroid price
    test_labels = kmeans.predict(X_test_t)
    km_pred = cluster_centroid_prices[test_labels]
    km_metrics = regression_metrics(y_test, km_pred)
    print(f"KMeans - R2: {km_metrics['r2']:.4f}, MAE: {km_metrics['mae']:.2f}, RMSE: {km_metrics['rmse']:.2f}")

    # =========================================================================
    # Save all models and artifacts
    # =========================================================================
    print("\n--- Saving Models ---")
    joblib.dump(preprocessor, ARTIFACT_PREPROCESSOR)
    joblib.dump(linear_pipeline, ARTIFACT_LINEAR)
    joblib.dump(rf_pipeline, ARTIFACT_RF)
    joblib.dump(kmeans, ARTIFACT_KMEANS)
    joblib.dump(cluster_centroid_prices, ARTIFACT_CLUSTER_CENTROID_PRICES)

    # Compile metrics
    metrics = {
        "linear_regression": {
            **lin_metrics,
            "evaluation_points": len(y_test)
        },
        "random_forest": {
            **rf_metrics,
            "evaluation_points": len(y_test)
        },
        "kmeans": {
            **km_metrics,
            "evaluation_points": len(y_test)
        },
        "n_clusters": N_CLUSTERS,
        "test_size": TEST_SIZE,
        "train_size": len(X_train),
        "test_size_actual": len(X_test),
        "dataset_rows": len(df)
    }

    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print(f"\nModels saved to: {MODEL_DIR}")
    print(f"Metrics saved to: {METRICS_PATH}")
    print("\n=== Training Summary ===")
    print(json.dumps(metrics, indent=2))

    return metrics


if __name__ == "__main__":
    train_all_models()
