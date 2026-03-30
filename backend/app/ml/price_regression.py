"""
Train RandomForest on sorted_diverse_device_dataset (CSV or XLSX).
Saves model.pkl and exposes predict_value(input_data).

Run from repo `backend` folder:
  python -m app.ml.price_regression
"""
from __future__ import annotations

import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

warnings.filterwarnings("ignore", category=UserWarning)

# Resolve backend/ directory (parent of app/)
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_DATA_CSV = _BACKEND_DIR / "data" / "sorted_diverse_device_dataset.csv"
_DATA_XLSX = _BACKEND_DIR / "data" / "sorted_device_dataset.xlsx"
_DOWNLOADS_CSV = Path(r"c:\Users\Asus\Downloads\sorted_diverse_device_dataset.csv")
_DOWNLOADS_XLSX = Path(r"c:\Users\Asus\Downloads\sorted_device_dataset.xlsx")

MODEL_PATH = Path(__file__).resolve().parent / "model.pkl"

# If True, ignores dataset labels and sets random condition (good/average/poor) and age (1–5).
# Leave False to use real `Condition_Label` and `Age_Years` (recommended; better MAE).
FORCE_RANDOM_CONDITION_AGE = False

TARGET = "Resale_Price"

# Features used for training (device / model / specs + engineered condition & age)
CAT_COLS = [
    "Device_Type",
    "Brand",
    "Model",
    "condition",
    "Screen_Damage",
    "Body_Damage",
    "Best_Action",
]
NUM_COLS = [
    "age",
    "Condition_Score",
    "Battery_Health",
    "Original_Price",
    "Depreciation_Rate",
    "Demand_Score",
]

# Drop from X (targets / derived prices / leakage)
DROP_FROM_X = {
    TARGET,
    "Current_Market_Price",
    "Exchange_Price",
    "OLX_Resale_Price",
    "Cashify_Exchange_Price",
    "Repair_Cost",
    "Refurbished_Price",
    "Profit_if_Repaired",
    "Price_Variation_%",
}


def _find_dataset_path() -> Path:
    for p in (_DATA_CSV, _DATA_XLSX, _DOWNLOADS_CSV, _DOWNLOADS_XLSX):
        if p.exists():
            return p
    raise FileNotFoundError(
        "Dataset not found. Place sorted_diverse_device_dataset.csv under backend/data/ "
        "or keep a copy in Downloads."
    )


def load_dataset() -> pd.DataFrame:
    path = _find_dataset_path()
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    return pd.read_csv(path)


def add_condition_and_age(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """
    Ensure `condition` (good/average/poor) and `age` (1–5) exist.
    Uses dataset columns when present; fills missing with random (assignment spec).
    """
    out = df.copy()
    if FORCE_RANDOM_CONDITION_AGE:
        out["condition"] = rng.choice(["good", "average", "poor"], size=len(out))
        out["age"] = rng.integers(1, 6, size=len(out))
        return out

    if "Condition_Label" in out.columns:
        out["condition"] = (
            out["Condition_Label"].astype(str).str.strip().str.lower().replace(
                {"good": "good", "average": "average", "poor": "poor"}
            )
        )
    else:
        out["condition"] = np.nan

    if "Age_Years" in out.columns:
        out["age"] = pd.to_numeric(out["Age_Years"], errors="coerce").clip(1, 5)
    else:
        out["age"] = np.nan

    miss_c = out["condition"].isna() | (out["condition"] == "")
    if miss_c.any():
        out.loc[miss_c, "condition"] = rng.choice(["good", "average", "poor"], size=miss_c.sum())

    miss_a = out["age"].isna()
    if miss_a.any():
        out.loc[miss_a, "age"] = rng.integers(1, 6, size=miss_a.sum())

    out["age"] = out["age"].astype(int)
    return out


def build_feature_matrix(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    y = pd.to_numeric(df[TARGET], errors="coerce")
    X = df[[c for c in CAT_COLS + NUM_COLS if c in df.columns]].copy()
    for c in NUM_COLS:
        if c in X.columns:
            X[c] = pd.to_numeric(X[c], errors="coerce")
            X[c] = X[c].fillna(X[c].median())
    for c in CAT_COLS:
        if c in X.columns:
            X[c] = X[c].astype(str).fillna("unknown")
    valid = y.notna()
    return X.loc[valid], y.loc[valid]


def train_and_save() -> None:
    rng = np.random.default_rng(42)
    df = load_dataset()
    print("df.columns:")
    print(df.columns.tolist())
    print()

    df = add_condition_and_age(df, rng)

    X, y = build_feature_matrix(df)
    print("Using features:", CAT_COLS + NUM_COLS)
    print("Target:", TARGET)
    print("Samples:", len(X))

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False, max_categories=40),
                [c for c in CAT_COLS if c in X.columns],
            ),
            ("num", StandardScaler(), [c for c in NUM_COLS if c in X.columns]),
        ],
        remainder="drop",
    )

    model = RandomForestRegressor(
        n_estimators=120,
        max_depth=20,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1,
    )

    pipeline = Pipeline([("prep", preprocessor), ("rf", model)])
    pipeline.fit(X_train, y_train)

    pred = pipeline.predict(X_test)
    mae = mean_absolute_error(y_test, pred)
    print("MAE (test):", round(mae, 2))

    artifact = {
        "pipeline": pipeline,
        "feature_columns": list(X.columns),
        "target": TARGET,
    }
    joblib.dump(artifact, MODEL_PATH)
    print("Saved:", MODEL_PATH)


def predict_value(input_data: dict) -> float:
    """
    Predict resale value from one row of inputs.
    `input_data` must include keys matching training feature columns (see feature_columns in pickle).
    Example:
        predict_value({
            "Device_Type": "Laptop", "Brand": "Acer", "Model": "Aspire 7",
            "condition": "good", "Screen_Damage": "No", "Body_Damage": "No",
            "Best_Action": "Repair",
            "age": 3, "Condition_Score": 90, "Battery_Health": 72,
            "Original_Price": 70000, "Depreciation_Rate": 0.17, "Demand_Score": 69,
        })
    """
    artifact = joblib.load(MODEL_PATH)
    pipeline = artifact["pipeline"]
    columns = artifact["feature_columns"]
    row = pd.DataFrame([{k: input_data.get(k) for k in columns}])
    for c in columns:
        if c not in row.columns:
            row[c] = np.nan
    row = row[columns]
    return float(pipeline.predict(row)[0])


if __name__ == "__main__":
    train_and_save()
