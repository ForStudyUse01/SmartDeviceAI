"""
Load trained artifacts and produce predictions plus evaluation summaries.

Best model selection uses a weighted score over test metrics:
``0.6 * R² - 0.2 * norm(RMSE) - 0.2 * norm(MAE)`` with min–max normalization across models.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

import joblib
import numpy as np
import pandas as pd

from data_preprocessing import dataframe_from_input_row, feature_matrix

MODEL_DIR = Path(__file__).resolve().parent / "models" / "price_estimation"
ARTIFACT_PREPROCESSOR = MODEL_DIR / "preprocessor.joblib"
ARTIFACT_LINEAR = MODEL_DIR / "linear_regression.joblib"
ARTIFACT_RF = MODEL_DIR / "random_forest.joblib"
ARTIFACT_KMEANS = MODEL_DIR / "kmeans.joblib"
ARTIFACT_CLUSTER_CENTROID_PRICES = MODEL_DIR / "cluster_centroid_prices.joblib"
# Legacy filename from earlier training runs
ARTIFACT_CLUSTER_PRICES_LEGACY = MODEL_DIR / "cluster_mean_prices.joblib"
METRICS_PATH = MODEL_DIR / "metrics.json"

KMEANS_NOTE = (
    "K-Means estimates price by grouping similar devices and using cluster centroid price."
)

MODEL_DISPLAY_NAMES = {
    "linear_regression": "Linear Regression",
    "random_forest": "Random Forest",
    "kmeans": "K-Means",
}

MODEL_ORDER = ("linear_regression", "random_forest", "kmeans")

# Weighted selection weights (R² reward, error penalties on normalized scales)
W_R2 = 0.6
W_RMSE = 0.2
W_MAE = 0.2


def _require_artifacts() -> None:
    centroid_ok = ARTIFACT_CLUSTER_CENTROID_PRICES.is_file() or ARTIFACT_CLUSTER_PRICES_LEGACY.is_file()
    needed = [
        ARTIFACT_PREPROCESSOR,
        ARTIFACT_LINEAR,
        ARTIFACT_RF,
        ARTIFACT_KMEANS,
        METRICS_PATH,
    ]
    if not centroid_ok:
        needed.append(ARTIFACT_CLUSTER_CENTROID_PRICES)
    missing = [p for p in needed if not p.is_file()]
    if missing:
        names = ", ".join(str(p) for p in missing)
        raise FileNotFoundError(
            f"Missing model artifacts: {names}. Run: python train_models.py"
        )


def load_metrics() -> dict[str, Any]:
    _require_artifacts()
    return json.loads(METRICS_PATH.read_text(encoding="utf-8"))


def _safe_float(value: Any) -> float | None:
    try:
        x = float(value)
        if math.isfinite(x):
            return x
    except (TypeError, ValueError):
        pass
    return None


def _metrics_block(raw: dict[str, Any], key: str) -> dict[str, float]:
    """Return MAE, RMSE, R² for one model; NaNs if missing or invalid."""
    block = raw.get(key)
    out = {"mae": float("nan"), "rmse": float("nan"), "r2": float("nan")}
    if not isinstance(block, dict):
        return out
    for name in ("mae", "rmse", "r2"):
        v = _safe_float(block.get(name))
        if v is not None:
            out[name] = v
    return out


def _min_max_norm(values: list[float]) -> list[float]:
    """Min–max normalize to [0, 1]. If all values equal (or degenerate), use 0.5 each (no division by zero)."""
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi <= lo or not math.isfinite(lo) or not math.isfinite(hi):
        return [0.5] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def _weighted_scores_and_breakdown(
    data: dict[str, Any],
) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    """
    Composite score per model and viva-friendly breakdown:
    score = r2_weight - rmse_penalty - mae_penalty with normalized error terms.
    """
    keys: list[str] = []
    r2s: list[float] = []
    maes: list[float] = []
    rmses: list[float] = []
    for key in MODEL_ORDER:
        m = _metrics_block(data, key)
        if all(math.isfinite(m[k]) for k in ("r2", "mae", "rmse")):
            keys.append(key)
            r2s.append(m["r2"])
            maes.append(m["mae"])
            rmses.append(m["rmse"])
    if not keys:
        return {}, {}
    n_rmse = _min_max_norm(rmses)
    n_mae = _min_max_norm(maes)
    scores: dict[str, float] = {}
    breakdown: dict[str, dict[str, float]] = {}
    for i, k in enumerate(keys):
        r2_weight = W_R2 * r2s[i]
        rmse_penalty = W_RMSE * n_rmse[i]
        mae_penalty = W_MAE * n_mae[i]
        scores[k] = r2_weight - rmse_penalty - mae_penalty
        breakdown[k] = {
            "r2_weight": round(r2_weight, 6),
            "rmse_penalty": round(rmse_penalty, 6),
            "mae_penalty": round(mae_penalty, 6),
        }
    return scores, breakdown


def _weighted_scores_for_models(data: dict[str, Any]) -> dict[str, float]:
    """Backward-compatible: composite scores only."""
    s, _ = _weighted_scores_and_breakdown(data)
    return s


def get_best_model_and_score(metrics: dict[str, Any] | None = None) -> tuple[str, float]:
    """
    Return (best_model_key, best_score) using weighted metrics score.
    Falls back to highest R² then lowest RMSE if weighted scores unavailable.
    """
    data = metrics if metrics is not None else load_metrics()
    scores = _weighted_scores_for_models(data)
    if scores:
        best_key = max(scores, key=scores.get)
        return best_key, float(scores[best_key])

    # Fallback: R² only, then RMSE
    ranked: list[tuple[str, float, float]] = []
    for key in MODEL_DISPLAY_NAMES:
        m = _metrics_block(data, key)
        r2 = m["r2"]
        rmse = m["rmse"]
        if not math.isfinite(r2):
            continue
        rmse_tie = rmse if math.isfinite(rmse) else float("inf")
        ranked.append((key, r2, rmse_tie))
    if ranked:
        ranked.sort(key=lambda t: (-t[1], t[2]))
        k = ranked[0][0]
        return k, float(ranked[0][1])

    for key in MODEL_ORDER:
        if key in data and isinstance(data.get(key), dict):
            return key, 0.0
    return "linear_regression", 0.0


def get_best_model(metrics: dict[str, Any] | None = None) -> str:
    """Return the model key with best weighted composite score (backward compatible)."""
    return get_best_model_and_score(metrics)[0]


def _warn_metrics_consistency(data: dict[str, Any]) -> None:
    """Log if evaluation sample sizes are missing or inconsistent (does not raise)."""
    expected = data.get("test_evaluation_n")
    if expected is None:
        logger.warning(
            "metrics.json missing test_evaluation_n; re-run train_models.py. "
            "Cannot verify identical test-set size across models."
        )
        return
    try:
        exp_n = int(expected)
    except (TypeError, ValueError):
        logger.warning("test_evaluation_n is not an integer: %s", expected)
        return
    for key in MODEL_ORDER:
        block = data.get(key)
        if not isinstance(block, dict):
            logger.warning("Missing metrics block for model %s", key)
            continue
        ep = block.get("evaluation_points")
        if ep is None:
            continue
        try:
            if int(ep) != exp_n:
                logger.warning(
                    "evaluation_points for %s (%s) != test_evaluation_n (%s)",
                    key,
                    ep,
                    exp_n,
                )
        except (TypeError, ValueError):
            logger.warning("Invalid evaluation_points for %s: %s", key, ep)


def _finalize_price(raw: float | None) -> tuple[float | None, str | None]:
    """Clamp to non-negative, round; return error message if unusable."""
    if raw is None:
        return None, "Missing prediction"
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None, "Non-numeric prediction"
    if not math.isfinite(v) or math.isnan(v):
        return None, "Invalid prediction (NaN or infinity)"
    return round(max(0.0, v), 2), None


def _reason_score_comparison(best_key: str, scores: dict[str, float]) -> str:
    """One-line score comparison for viva-style explanations."""
    if not scores or best_key not in scores:
        return ""
    order = [k for k in MODEL_ORDER if k in scores]
    if len(order) < 2:
        return ""
    sb = scores[best_key]
    others = [k for k in order if k != best_key]
    other_strs = [f"{MODEL_DISPLAY_NAMES[k]} ({scores[k]:.2f})" for k in others]
    if len(other_strs) == 1:
        rest = other_strs[0]
    elif len(other_strs) == 2:
        rest = f"{other_strs[0]} and {other_strs[1]}"
    else:
        rest = ", ".join(other_strs[:-1]) + ", and " + other_strs[-1]
    return (
        f"Selected {MODEL_DISPLAY_NAMES[best_key]} (score: {sb:.2f}), outperforming {rest}."
    )


def _confidence_from_r2(r2: float) -> str:
    if not math.isfinite(r2):
        return "Low"
    if r2 > 0.9:
        return "High"
    if r2 >= 0.75:
        return "Medium"
    return "Low"


def _selection_reason(
    data: dict[str, Any],
    best_key: str,
    scores: dict[str, float],
) -> str:
    """Model-aware explanation for academic demos."""
    cmp_line = _reason_score_comparison(best_key, scores)
    m_best = _metrics_block(data, best_key)
    r2 = m_best["r2"]
    rmse = m_best["rmse"]
    r2_s = f"{r2:.4f}" if math.isfinite(r2) else "n/a"
    rmse_s = f"{rmse:,.0f}" if math.isfinite(rmse) else "n/a"

    # Rank others by R² for context
    others = [
        (k, _metrics_block(data, k)["r2"])
        for k in MODEL_ORDER
        if k != best_key and math.isfinite(_metrics_block(data, k)["r2"])
    ]
    others.sort(key=lambda t: -t[1])
    top_other = others[0] if others else None

    lines: list[str] = []

    if best_key == "kmeans":
        lines.append(
            f"K-Means was selected by the weighted score (R² vs. normalized errors). "
            f"It emphasizes stable peer-group structure; test R² was {r2_s} (RMSE {rmse_s}). "
            "Lower R² than parametric models is expected because clustering is not a direct regressor."
        )
    elif best_key == "random_forest":
        lines.append(
            f"Random Forest achieved the best composite score with strong test R² ({r2_s}) "
            f"and RMSE {rmse_s}, balancing non-linear fits with error penalties."
        )
    elif best_key == "linear_regression":
        lines.append(
            f"Linear Regression led on the weighted score with the highest effective R² ({r2_s}) "
            f"and RMSE {rmse_s} after normalizing errors across models."
        )

    if top_other and best_key != "kmeans":
        ok, or2 = top_other
        lines.append(
            f"Compared with {MODEL_DISPLAY_NAMES[ok]} (R² {or2:.4f}), "
            f"{MODEL_DISPLAY_NAMES[best_key]} ranked higher on the combined criterion."
        )

    if scores:
        s_best = scores.get(best_key)
        if s_best is not None and math.isfinite(s_best):
            lines.append(f"Composite score (0.6·R² − 0.2·norm RMSE − 0.2·norm MAE): {s_best:.4f}.")

    body = " ".join(lines) if lines else (
        f"Selected {MODEL_DISPLAY_NAMES[best_key]} (test R² {r2_s}, RMSE {rmse_s})."
    )
    if cmp_line:
        return f"{cmp_line} {body}".strip()
    return body


def get_best_model_display_name(metrics: dict[str, Any] | None = None) -> str:
    return MODEL_DISPLAY_NAMES[get_best_model(metrics)]


def _load_cluster_centroid_prices() -> np.ndarray:
    if ARTIFACT_CLUSTER_CENTROID_PRICES.is_file():
        return joblib.load(ARTIFACT_CLUSTER_CENTROID_PRICES)
    if ARTIFACT_CLUSTER_PRICES_LEGACY.is_file():
        return joblib.load(ARTIFACT_CLUSTER_PRICES_LEGACY)
    raise FileNotFoundError("No cluster centroid price file found.")


def _load_models() -> tuple[Any, Any, Any, Any, np.ndarray]:
    _require_artifacts()
    preprocessor = joblib.load(ARTIFACT_PREPROCESSOR)
    linear = joblib.load(ARTIFACT_LINEAR)
    rf = joblib.load(ARTIFACT_RF)
    kmeans = joblib.load(ARTIFACT_KMEANS)
    centroid_prices: np.ndarray = _load_cluster_centroid_prices()
    return preprocessor, linear, rf, kmeans, centroid_prices


def _err_msg(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


def _safe_predict_price_linear(linear: Any, df: pd.DataFrame) -> tuple[float | None, str | None]:
    try:
        return float(linear.predict(df)[0]), None
    except Exception as e:
        return None, _err_msg(e)


def _safe_predict_price_rf(rf: Any, df: pd.DataFrame) -> tuple[float | None, str | None]:
    try:
        return float(rf.predict(df)[0]), None
    except Exception as e:
        return None, _err_msg(e)


def _safe_predict_price_kmeans(
    preprocessor: Any,
    kmeans: Any,
    centroid_prices: np.ndarray,
    df: pd.DataFrame,
) -> tuple[float | None, int | None, str | None]:
    try:
        X_t = preprocessor.transform(df)
        cid = int(kmeans.predict(X_t)[0])
        return float(centroid_prices[cid]), cid, None
    except Exception as e:
        return None, None, _err_msg(e)


def predict_row(row: dict[str, Any]) -> dict[str, Any]:
    """
    Predict resale price for one device using all three approaches.

    Per-model prediction errors are caught so the API still returns partial results.
    """
    df = dataframe_from_input_row(row)

    price_linear = price_rf = None
    price_km = None
    cluster_id: int | None = None
    pred_errors: dict[str, str] = {}

    try:
        preprocessor, linear, rf, kmeans, centroid_prices = _load_models()
    except FileNotFoundError as e:
        raise e

    price_linear, err_l = _safe_predict_price_linear(linear, df)
    if err_l:
        pred_errors["linear_regression"] = err_l
        price_linear = None
    else:
        price_linear, fe = _finalize_price(price_linear)
        if fe:
            pred_errors["linear_regression"] = fe
            price_linear = None

    price_rf, err_r = _safe_predict_price_rf(rf, df)
    if err_r:
        pred_errors["random_forest"] = err_r
        price_rf = None
    else:
        price_rf, fe = _finalize_price(price_rf)
        if fe:
            pred_errors["random_forest"] = fe
            price_rf = None

    price_km, cluster_id, err_k = _safe_predict_price_kmeans(
        preprocessor, kmeans, centroid_prices, df
    )
    if err_k:
        pred_errors["kmeans"] = err_k
        price_km = None
        cluster_id = None
    else:
        price_km, fe = _finalize_price(price_km)
        if fe:
            pred_errors["kmeans"] = fe
            price_km = None

    metrics_blob = load_metrics()
    _warn_metrics_consistency(metrics_blob)
    scores, score_breakdown = _weighted_scores_and_breakdown(metrics_blob)
    best_key, best_score = get_best_model_and_score(metrics_blob)
    reason = _selection_reason(metrics_blob, best_key, scores)

    m_best = _metrics_block(metrics_blob, best_key)
    r2_best = m_best["r2"]
    confidence = _confidence_from_r2(r2_best) if math.isfinite(r2_best) else "Low"

    def comparison_entry(key: str, price: float | None, pred_err: str | None) -> dict[str, Any]:
        m = _metrics_block(metrics_blob, key)
        r2_pct = (
            max(0.0, min(100.0, m["r2"] * 100.0)) if math.isfinite(m["r2"]) else None
        )
        is_best = key == best_key
        name = MODEL_DISPLAY_NAMES[key]
        if is_best:
            row_status = "Best ✅"
        elif pred_err:
            row_status = "Error"
        else:
            row_status = "—"

        entry: dict[str, Any] = {
            "model_key": key,
            "model_name": name,
            "model": name,
            "predicted_price": round(price, 2) if price is not None else None,
            "price": round(price, 2) if price is not None else None,
            "r2": m["r2"] if math.isfinite(m["r2"]) else None,
            "r2_percent": round(r2_pct, 2) if r2_pct is not None else None,
            "mae": m["mae"] if math.isfinite(m["mae"]) else None,
            "rmse": m["rmse"] if math.isfinite(m["rmse"]) else None,
            "is_best": is_best,
            "status": row_status,
            "score": round(scores[key], 6) if key in scores else None,
        }
        if pred_err:
            entry["prediction_error"] = pred_err[:300]
            entry["prediction_failed"] = True
        return entry

    model_comparison = [
        comparison_entry("linear_regression", price_linear, pred_errors.get("linear_regression")),
        comparison_entry("random_forest", price_rf, pred_errors.get("random_forest")),
        comparison_entry("kmeans", price_km, pred_errors.get("kmeans")),
    ]

    best_price: float | None = None
    for r in model_comparison:
        if r.get("model_key") == best_key:
            pp = r.get("predicted_price")
            if pp is not None:
                best_price = float(pp)
            break
    if best_price is None:
        for r in model_comparison:
            pp = r.get("predicted_price")
            if pp is not None:
                best_price = float(pp)
                break

    out: dict[str, Any] = {
        "best_model": best_key,
        "best_model_name": MODEL_DISPLAY_NAMES[best_key],
        "best_score": round(best_score, 6),
        "confidence": confidence,
        "reason": reason,
        "kmeans_note": KMEANS_NOTE,
        "model_comparison": model_comparison,
        "rows": model_comparison,
        "best_model_key": best_key,
        "cluster_id": cluster_id,
        "best_price": round(best_price, 2) if best_price is not None else None,
    }
    if scores:
        out["model_scores"] = {k: round(v, 6) for k, v in scores.items()}
    if score_breakdown:
        out["score_breakdown"] = score_breakdown
    if pred_errors:
        out["prediction_warnings"] = {
            k: "skipped" for k in pred_errors
        }
    return out


def predict_batch(df: pd.DataFrame) -> pd.DataFrame:
    """Vectorized predictions for a dataframe with feature columns."""
    preprocessor, linear, rf, kmeans, centroid_prices = _load_models()
    X = feature_matrix(df)
    X_t = preprocessor.transform(X)
    out = pd.DataFrame(
        {
            "price_linear": linear.predict(X),
            "price_rf": rf.predict(X),
            "cluster": kmeans.predict(X_t),
        }
    )
    out["price_kmeans"] = centroid_prices[out["cluster"].values]
    return out
