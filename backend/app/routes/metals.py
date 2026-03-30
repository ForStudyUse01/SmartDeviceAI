"""Live commodity spot-style prices via yfinance (USD futures → INR display)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/metals", tags=["metals"])

# Approximate INR/USD for display (spot conversion).
INR_PER_USD = 83.0
TROY_OZ_G = 31.1035
LB_KG = 0.453592


def _safe_last_close(history) -> float | None:
    if history is None or history.empty:
        return None
    try:
        return float(history["Close"].iloc[-1])
    except Exception:
        return None


@router.get("/live")
async def metals_live() -> dict[str, Any]:
    """
    GC=F gold, SI=F silver, HG=F copper (COMEX futures, USD).
    Returns INR-friendly units for UI.
    """
    try:
        import yfinance as yf
    except ImportError:  # pragma: no cover
        return {
            "ok": False,
            "error": "yfinance not installed",
            "gold_inr_per_10g": None,
            "silver_inr_per_g": None,
            "copper_inr_per_kg": None,
            "raw_usd": {},
        }

    out: dict[str, Any] = {"ok": True, "error": None, "raw_usd": {}}
    try:
        gold = yf.Ticker("GC=F").history(period="5d")
        silver = yf.Ticker("SI=F").history(period="5d")
        copper = yf.Ticker("HG=F").history(period="5d")

        g_usd = _safe_last_close(gold)
        s_usd = _safe_last_close(silver)
        c_usd = _safe_last_close(copper)

        if g_usd is not None:
            out["raw_usd"]["gold_per_troy_oz"] = round(g_usd, 2)
            # USD per troy oz → INR per 10g
            out["gold_inr_per_10g"] = round((g_usd / TROY_OZ_G) * 10 * INR_PER_USD, 2)
        else:
            out["gold_inr_per_10g"] = None

        if s_usd is not None:
            out["raw_usd"]["silver_per_troy_oz"] = round(s_usd, 3)
            out["silver_inr_per_g"] = round((s_usd / TROY_OZ_G) * INR_PER_USD, 2)
        else:
            out["silver_inr_per_g"] = None

        if c_usd is not None:
            out["raw_usd"]["copper_per_lb"] = round(c_usd, 4)
            # USD per lb → INR per kg
            out["copper_inr_per_kg"] = round((c_usd / LB_KG) * INR_PER_USD, 2)
        else:
            out["copper_inr_per_kg"] = None

    except Exception as exc:  # pragma: no cover
        out["ok"] = False
        out["error"] = str(exc)
        out["gold_inr_per_10g"] = None
        out["silver_inr_per_g"] = None
        out["copper_inr_per_kg"] = None

    return out
