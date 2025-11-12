from __future__ import annotations

import math
from typing import Optional


def infer_limit_pct(code: str, security_name: Optional[str] = None) -> float:
    """Infer limit percentage based on code pattern or name."""
    code = code.upper()
    if security_name and "ST" in security_name.upper():
        return 0.05
    if code.startswith("300") or code.startswith("301") or code.startswith("688"):
        return 0.20  # 创业板/科创板
    if code.endswith(".BJ"):
        return 0.20  # 北交所
    if code.startswith("ST"):
        return 0.05
    return 0.10


def infer_tick_size(code: str) -> float:
    code = code.upper()
    if code.endswith(".BJ"):
        return 0.001
    return 0.01


def calc_limit_price(reference_price: float, direction: str, pct: float, tick_size: float) -> float:
    multiplier = 1 + pct if direction.lower() == "buy" else 1 - pct
    raw_price = reference_price * multiplier
    if direction.lower() == "buy":
        adjusted = math.ceil(raw_price / tick_size - 1e-9) * tick_size
    else:
        adjusted = math.floor(raw_price / tick_size + 1e-9) * tick_size
    decimals = 3 if tick_size < 0.01 else 2
    return round(adjusted, decimals)
