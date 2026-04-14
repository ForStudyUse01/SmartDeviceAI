"""
Load trained models and produce price predictions.

All 3 models predict on each request; best model is selected by R2 score.
Models are loaded once per API call (not retrained).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data_preprocessing import (
    ALL_FEATURES,
    dataframe_from_input_row,
    feature_matrix,
)

# --- Model artifact paths ----------------------------------------------------
MODEL_DIR = Path(__file__).resolve().parent / "saved"
ARTIFACT_PREPROCESSOR = MODEL_DIR / "preprocessor.pkl"
ARTIFACT_LINEAR = MODEL_DIR / "linear.pkl"
ARTIFACT_RF = MODEL_DIR / "rf.pkl"
ARTIFACT_KMEANS = MODEL_DIR / "kmeans.pkl"
ARTIFACT_CLUSTER_CENTROID_PRICES = MODEL_DIR / "cluster_centroid_prices.pkl"
METRICS_PATH = MODEL_DIR / "metrics.json"

MODEL_DISPLAY_NAMES = {
    "linear_regression": "Linear Regression",
    "random_forest": "Random Forest",
    "kmeans": "KMeans Clustering"
}


def require_artifacts() -> None:
    """Check all required model files exist."""
    required = [
        ARTIFACT_PREPROCESSOR,
        ARTIFACT_LINEAR,
        ARTIFACT_RF,
        ARTIFACT_KMEANS,
        ARTIFACT_CLUSTER_CENTROID_PRICES,
        METRICS_PATH
    ]
    missing = [p for p in required if not p.is_file()]
    if missing:
        raise FileNotFoundError(
            f"Missing model artifacts: {missing}. "
            f"Run training first: python models/train_models.py"
        )


def load_metrics() -> dict[str, Any]:
    """Load metrics.json with model evaluation scores."""
    require_artifacts()
    return json.loads(METRICS_PATH.read_text(encoding="utf-8"))


def load_models() -> tuple[Any, Any, Any, Any, np.ndarray]:
    """Load all trained models and preprocessor."""
    require_artifacts()
    preprocessor = joblib.load(ARTIFACT_PREPROCESSOR)
    linear_model = joblib.load(ARTIFACT_LINEAR)
    rf_model = joblib.load(ARTIFACT_RF)
    kmeans_model = joblib.load(ARTIFACT_KMEANS)
    centroid_prices = joblib.load(ARTIFACT_CLUSTER_CENTROID_PRICES)
    return preprocessor, linear_model, rf_model, kmeans_model, centroid_prices


def get_best_model(metrics: dict[str, Any] | None = None) -> str:
    """
    Select best model by highest R2 score.
    Returns model key: 'linear_regression', 'random_forest', or 'kmeans'.
    """
    if metrics is None:
        metrics = load_metrics()

    best_r2 = -float("inf")
    best_model = "linear_regression"

    for model_key in ["linear_regression", "random_forest", "kmeans"]:
        if model_key in metrics:
            r2 = metrics[model_key].get("r2", 0)
            if r2 > best_r2:
                best_r2 = r2
                best_model = model_key

    return best_model


def predict_single(row: dict[str, Any]) -> dict[str, Any]:
    """
    Predict resale price for a single device using all 3 models.

    Returns dict with all predictions, best model, and accuracy info.
    """
    # Convert input dict to DataFrame
    df = dataframe_from_input_row(row)

    # Load models (from saved files, NOT retrained)
    preprocessor, linear_model, rf_model, kmeans_model, centroid_prices = load_models()

    # =========================================================================
    # Prediction: Linear Regression
    # =========================================================================
    linear_pred = float(linear_model.predict(df)[0])

    # =========================================================================
    # Prediction: Random Forest
    # =========================================================================
    rf_pred = float(rf_model.predict(df)[0])

    # =========================================================================
    # Prediction: KMeans (cluster-based)
    # =========================================================================
    X_transformed = preprocessor.transform(df)
    cluster_id = int(kmeans_model.predict(X_transformed)[0])
    kmeans_pred = float(centroid_prices[cluster_id])

    # =========================================================================
    # Load metrics and determine best model
    # =========================================================================
    metrics = load_metrics()
    best_model_key = get_best_model(metrics)

    # =========================================================================
    # Build response
    # =========================================================================
    predictions = [
        {
            "model": "Linear Regression",
            "model_key": "linear_regression",
            "price": round(max(0, linear_pred), 2),
            "accuracy": round(metrics["linear_regression"]["r2"], 4)
        },
        {
            "model": "Random Forest",
            "model_key": "random_forest",
            "price": round(max(0, rf_pred), 2),
            "accuracy": round(metrics["random_forest"]["r2"], 4)
        },
        {
            "model": "KMeans Clustering",
            "model_key": "kmeans",
            "price": round(max(0, kmeans_pred), 2),
            "accuracy": round(metrics["kmeans"]["r2"], 4),
            "cluster_id": cluster_id
        }
    ]

    # Find best model's prediction
    best_prediction = next(p for p in predictions if p["model_key"] == best_model_key)

    result = {
        "predictions": predictions,
        "best_model": MODEL_DISPLAY_NAMES[best_model_key],
        "best_model_key": best_model_key,
        "best_price": best_prediction["price"],
        "best_accuracy": best_prediction["accuracy"],
        "model_metrics": {
            "linear_regression": metrics["linear_regression"],
            "random_forest": metrics["random_forest"],
            "kmeans": metrics["kmeans"]
        }
    }

    return result


def predict_batch(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Predict for multiple devices."""
    return [predict_single(row) for row in rows]


# For testing
if __name__ == "__main__":
    # Test prediction with sample data
    test_input = {
        "Device_Type": "Laptop",
        "Brand": "Dell",
        "Model": "XPS 15",
        "Age_Years": 2,
        "Condition_Label": "Good",
        "Condition_Score": 85,
        "Screen_Damage": "No",
        "Body_Damage": "No",
        "Battery_Health": 90,
        "Original_Price": 120000,
        "Depreciation_Rate": 0.15,
        "Demand_Score": 75
    }

    result = predict_single(test_input)
    print(json.dumps(result, indent=2))
