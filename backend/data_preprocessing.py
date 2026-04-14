"""
Feature engineering and preprocessing for electronic device resale price estimation.

Uses sorted_diverse_device_dataset.csv with proper column handling to avoid data leakage.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler, LabelEncoder

# Dataset columns
# Input features (X) - used for prediction
CATEGORICAL_FEATURES: list[str] = [
    "Device_Type",
    "Brand",
    "Model",
    "Condition_Label",
    "Screen_Damage",
    "Body_Damage"
]

NUMERIC_FEATURES: list[str] = [
    "Age_Years",
    "Condition_Score",
    "Battery_Health",
    "Original_Price",
    "Depreciation_Rate",
    "Demand_Score"
]

# Target variable (y)
TARGET_COLUMN: str = "Resale_Price"

# Columns to DROP to avoid data leakage
LEAKAGE_COLUMNS: list[str] = [
    "Current_Market_Price",
    "Exchange_Price",
    "Repair_Cost",
    "Refurbished_Price",
    "Profit_if_Repaired",
    "OLX_Resale_Price",
    "Cashify_Exchange_Price",
    "Price_Variation_%",
    "Best_Action"
]

ALL_FEATURES: list[str] = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def get_data_path() -> Path:
    """Default CSV path - sorted_diverse_device_dataset.csv"""
    return Path(__file__).resolve().parent / "data" / "sorted_diverse_device_dataset.csv"


def load_dataset(csv_path: Path | None = None) -> pd.DataFrame:
    """Load the electronics price dataset and drop leakage columns."""
    path = csv_path or get_data_path()
    df = pd.read_csv(path)
    _validate_columns(df)
    # Drop leakage columns
    df = df.drop(columns=[c for c in LEAKAGE_COLUMNS if c in df.columns])
    return df


def _validate_columns(df: pd.DataFrame) -> None:
    """Ensure all required columns exist."""
    required = set(ALL_FEATURES + [TARGET_COLUMN])
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Dataset missing columns: {sorted(missing)}")


def build_preprocessor() -> ColumnTransformer:
    """
    Build a sklearn ColumnTransformer for preprocessing:
    - Numeric: median impute + StandardScaler
    - Categorical: most_frequent impute + OneHotEncoder
    """
    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )

    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            (
                "encoder",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
            ),
        ]
    )

    return ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, NUMERIC_FEATURES),
            ("cat", categorical_pipeline, CATEGORICAL_FEATURES),
        ]
    )


def feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Select only model input columns."""
    return df[ALL_FEATURES].copy()


def target_vector(df: pd.DataFrame) -> np.ndarray:
    """Extract target variable."""
    return df[TARGET_COLUMN].values


def dataframe_from_input_row(row: dict) -> pd.DataFrame:
    """Turn a single prediction dict into a one-row DataFrame with correct columns."""
    data = {k: [row.get(k)] for k in ALL_FEATURES}
    return pd.DataFrame(data)


def allowed_categories() -> dict[str, Iterable[str]]:
    """Categories seen in the dataset for UI hints/validation."""
    df = load_dataset()
    result = {}
    for col in CATEGORICAL_FEATURES:
        result[col] = sorted(df[col].astype(str).unique())
    return result


def get_label_encoders() -> dict[str, LabelEncoder]:
    """Create label encoders for categorical columns."""
    df = load_dataset()
    encoders = {}
    for col in CATEGORICAL_FEATURES:
        le = LabelEncoder()
        le.fit(df[col].astype(str))
        encoders[col] = le
    return encoders
