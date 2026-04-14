"""
FastAPI server for ML-based price estimation.

Uses pre-trained models (Linear Regression, Random Forest, KMeans)
to predict device resale prices. Models are loaded from disk, not retrained on each request.

Run from backend directory:
    uvicorn price_ml_server:app --host 127.0.0.1 --port 8765

Or from repo root:
    cd backend && uvicorn price_ml_server:app --host 127.0.0.1 --port 8765
"""

from __future__ import annotations

from pathlib import Path
import sys

# Ensure backend directory is on path
_BACKEND = Path(__file__).resolve().parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from data_preprocessing import allowed_categories
from models.prediction_pipeline import predict_single, load_metrics, get_best_model

app = FastAPI(title="ML Price Estimator", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DeviceInput(BaseModel):
    """Input schema for price prediction."""
    Device_Type: str = Field(..., description="e.g., Laptop, Smartphone, Tablet")
    Brand: str = Field(..., description="e.g., Dell, Apple, Samsung")
    Model: str = Field(..., description="e.g., XPS 15, MacBook Pro")
    Age_Years: int = Field(..., ge=0, le=50, description="Device age in years")
    Condition_Label: str = Field(..., description="e.g., Excellent, Good, Fair, Poor")
    Condition_Score: int = Field(..., ge=0, le=100, description="Condition score 0-100")
    Screen_Damage: str = Field(..., description="Yes/No")
    Body_Damage: str = Field(..., description="Yes/No")
    Battery_Health: int = Field(..., ge=0, le=100, description="Battery health percentage")
    Original_Price: float = Field(..., ge=0, description="Original purchase price")
    Depreciation_Rate: float = Field(..., ge=0, le=1, description="Annual depreciation rate")
    Demand_Score: int = Field(..., ge=0, le=100, description="Market demand score")


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "ml-price-estimator"}


@app.get("/metrics")
def metrics() -> dict:
    """Return model evaluation metrics (R2, MAE, RMSE for each model)."""
    try:
        return load_metrics()
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Models not trained. Run: python models/train_models.py"
        ) from e


@app.get("/best-model")
def best_model() -> dict[str, str]:
    """Return the current best model based on R2 score."""
    try:
        metrics = load_metrics()
        best = get_best_model(metrics)
        return {
            "best_model": best,
            "model_name": {
                "linear_regression": "Linear Regression",
                "random_forest": "Random Forest",
                "kmeans": "KMeans Clustering"
            }.get(best, best)
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@app.get("/options")
def options() -> dict[str, list[str]]:
    """Return distinct values from training data for form dropdowns."""
    try:
        cats = allowed_categories()
        return {k: sorted(list(v)) for k, v in cats.items()}
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@app.post("/predict")
def predict(device: DeviceInput) -> dict:
    """
    Predict resale price using all 3 models.

    Returns predictions from Linear Regression, Random Forest, and KMeans,
    along with the best model selection based on R2 score.
    """
    try:
        result = predict_single(device.model_dump())
        return result
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Models not trained. Run: python models/train_models.py"
        ) from e
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/explain")
def predict_with_explanation(device: DeviceInput) -> dict:
    """
    Predict with human-readable explanation of model selection.
    """
    try:
        result = predict_single(device.model_dump())
        metrics = result["model_metrics"]
        best = result["best_model_key"]

        # Generate explanation
        best_r2 = metrics[best]["r2"]
        best_mae = metrics[best]["mae"]

        explanation = (
            f"The {result['best_model']} was selected as the best model "
            f"with R² = {best_r2:.4f} ({best_r2*100:.1f}% variance explained) "
            f"and MAE = Rs. {best_mae:,.0f}. "
            f"Recommended resale price: Rs. {result['best_price']:,.0f}"
        )

        result["explanation"] = explanation
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765)
