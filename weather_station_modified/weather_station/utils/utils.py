"""
utils.py — Shared data structures, validation helpers, and feature engineering.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Sequence

import numpy as np


# ─── Sensor sample ───────────────────────────────────────────────────────────

@dataclass(slots=True)
class SensorSample:
    ts: float
    temperature: float
    humidity: float
    pressure: float
    raw_line: str = ""

    # ── validation bounds ──────────────────────────────────────────────────
    _T_RANGE = (-40.0, 85.0)
    _H_RANGE = (0.0, 100.0)
    _P_RANGE = (800.0, 1100.0)

    def is_valid(self) -> bool:
        return (
            self._T_RANGE[0] <= self.temperature <= self._T_RANGE[1]
            and self._H_RANGE[0] <= self.humidity <= self._H_RANGE[1]
            and self._P_RANGE[0] <= self.pressure <= self._P_RANGE[1]
            and not any(math.isnan(v) for v in [self.temperature, self.humidity, self.pressure])
        )


# ─── Parse raw serial line ────────────────────────────────────────────────────

def parse_serial_line(line: str) -> Optional[SensorSample]:
    """
    Parse a comma-separated serial line: ts,temperature,humidity,pressure
    Returns None if the line is malformed or out-of-range.
    """
    try:
        parts = line.strip().split(",")
        if len(parts) < 4:
            return None
        sample = SensorSample(
            ts=float(parts[0]),
            temperature=float(parts[1]),
            humidity=float(parts[2]),
            pressure=float(parts[3]),
            raw_line=line.strip(),
        )
        return sample if sample.is_valid() else None
    except (ValueError, IndexError):
        return None


# ─── Feature engineering ─────────────────────────────────────────────────────

def build_feature_vector(window: Sequence[SensorSample]) -> np.ndarray:
    """
    Flatten a sliding window of SensorSamples into a 1-D feature vector.
    Features per step: [temperature, humidity, pressure]
    Plus derived trend features appended at the end:
        - temp_slope  (linear regression slope over window temperatures)
        - hum_slope
        - pres_slope
    """
    base: list[float] = []
    temps, hums, pres = [], [], []

    for s in window:
        base.extend([s.temperature, s.humidity, s.pressure])
        temps.append(s.temperature)
        hums.append(s.humidity)
        pres.append(s.pressure)

    n = len(window)
    x = np.arange(n, dtype=float)

    def slope(vals: list[float]) -> float:
        if n < 2:
            return 0.0
        c = np.polyfit(x, vals, 1)
        return float(c[0])

    base.extend([slope(temps), slope(hums), slope(pres)])
    return np.array(base, dtype=float)


def safe_float(v, default: float = float("nan")) -> float:
    try:
        f = float(v)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default
