"""
Production-safe JSON serialization.
Fixes:
  - ValueError: Out of range float values (NaN, Infinity) not JSON compliant
  - fillcolor hex+alpha → rgba() (Plotly bug #4)
"""
import math, json
import numpy as np
import pandas as pd
from typing import Any
import orjson


def clean_float(v: Any) -> Any:
    """Replace NaN/Inf/−Inf with None for JSON safety."""
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
    if isinstance(v, (np.floating,)):
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, np.ndarray):
        return clean_value(v.tolist())
    return v


def clean_value(obj: Any) -> Any:
    """Recursively clean all NaN/Inf values in nested structures."""
    if isinstance(obj, dict):
        return {k: clean_value(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean_value(v) for v in obj]
    if isinstance(obj, float) or isinstance(obj, np.floating):
        return clean_float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return clean_value(obj.tolist())
    if isinstance(obj, pd.DataFrame):
        return clean_value(obj.where(pd.notnull(obj), None).to_dict(orient="records"))
    if isinstance(obj, pd.Series):
        return clean_value(obj.where(pd.notnull(obj), None).tolist())
    return obj


def safe_json_response(data: Any) -> dict:
    """Clean data structure for FastAPI JSONResponse."""
    return clean_value(data)


def orjson_dumps(data: Any) -> bytes:
    """Fast JSON serialization with orjson, NaN-safe."""
    cleaned = clean_value(data)
    return orjson.dumps(cleaned, option=orjson.OPT_NON_STR_KEYS | orjson.OPT_SERIALIZE_NUMPY)


# ─── Plotly fillcolor fix (Bug #4) ────────────────────────────────────────────
def hex_alpha_to_rgba(hex_color: str, alpha: float = 0.15) -> str:
    """
    Convert '#22C55E15' (hex+alpha) → 'rgba(34,197,94,0.15)'.
    Plotly requires rgba() not hex+alpha strings.
    """
    h = hex_color.lstrip("#")
    if len(h) == 8:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        a = int(h[6:8], 16) / 255
        return f"rgba({r},{g},{b},{a:.2f})"
    if len(h) == 6:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"
    return hex_color  # passthrough if already rgba or unknown


CHART_COLORS = {
    "green":      "rgba(34,197,94,1.0)",
    "green_fill": "rgba(34,197,94,0.12)",
    "red":        "rgba(239,68,68,1.0)",
    "red_fill":   "rgba(239,68,68,0.12)",
    "cyan":       "rgba(0,229,255,1.0)",
    "cyan_fill":  "rgba(0,229,255,0.08)",
    "purple":     "rgba(124,58,237,1.0)",
    "purple_fill":"rgba(124,58,237,0.08)",
    "amber":      "rgba(251,176,66,1.0)",
    "amber_fill": "rgba(251,176,66,0.10)",
}
