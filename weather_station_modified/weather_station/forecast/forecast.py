"""
forecast.py — Trend-based weather forecasting engine.

Uses pressure trend, humidity, and temperature to produce labelled forecasts
with a confidence score. An optional lightweight KNN classifier is trained
from history when enough labelled samples exist.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Optional

import numpy as np

from logger.logger import get_logger

_log = get_logger("Forecast")


# ─── Result dataclass ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ForecastResult:
    label: str
    emoji: str
    confidence: float       # 0–100 %
    description: str

    def __str__(self) -> str:
        return f"{self.emoji} {self.label} ({self.confidence:.0f}%)"


@dataclass(frozen=True)
class DailyForecast:
    day: str
    expected_temp: float
    label: str
    emoji: str
    confidence: float


# ─── Condition labels ────────────────────────────────────────────────────────

_CONDITIONS = {
    "Sunny":    "☀️",
    "Partly Cloudy": "⛅",
    "Cloudy":   "☁️",
    "Foggy":    "🌫️",
    "Drizzle":  "🌦️",
    "Rainy":    "🌧️",
    "Storm":    "⛈️",
}


# ─── Trend detector ──────────────────────────────────────────────────────────

class TrendAnalyzer:
    """Computes slopes over recent pressure, humidity, temperature windows."""

    def __init__(self, maxlen: int = 30) -> None:
        self._pres: deque[float] = deque(maxlen=maxlen)
        self._hum: deque[float]  = deque(maxlen=maxlen)
        self._temp: deque[float] = deque(maxlen=maxlen)

    def update(self, temp: float, hum: float, pres: float) -> None:
        self._temp.append(temp)
        self._hum.append(hum)
        self._pres.append(pres)

    def _slope(self, buf: deque[float]) -> float:
        """Linear regression slope over the buffer. Returns 0 if < 2 points."""
        n = len(buf)
        if n < 2:
            return 0.0
        x = np.arange(n, dtype=float)
        y = np.array(buf, dtype=float)
        return float(np.polyfit(x, y, 1)[0])

    @property
    def pressure_slope(self) -> float:
        return self._slope(self._pres)

    @property
    def humidity_slope(self) -> float:
        return self._slope(self._hum)

    @property
    def temp_slope(self) -> float:
        return self._slope(self._temp)

    @property
    def current_pressure(self) -> Optional[float]:
        return self._pres[-1] if self._pres else None

    @property
    def current_humidity(self) -> Optional[float]:
        return self._hum[-1] if self._hum else None

    @property
    def current_temp(self) -> Optional[float]:
        return self._temp[-1] if self._temp else None

    @property
    def ready(self) -> bool:
        return len(self._pres) >= 5


# ─── Forecasting engine ──────────────────────────────────────────────────────

class WeatherForecaster:
    """
    Rule + trend-based forecaster.
    Accepts optional ML classifier once enough data is available.
    """

    def __init__(self) -> None:
        self.analyzer = TrendAnalyzer(maxlen=30)

    def update(self, temp: float, hum: float, pres: float) -> None:
        self.analyzer.update(temp, hum, pres)

    def forecast(self) -> ForecastResult:
        if not self.analyzer.ready:
            return ForecastResult("Initializing", "🔄", 0.0, "Gathering sensor data…")

        pres   = self.analyzer.current_pressure
        hum    = self.analyzer.current_humidity
        temp   = self.analyzer.current_temp
        p_slope = self.analyzer.pressure_slope   # hPa / sample
        h_slope = self.analyzer.humidity_slope
        t_slope = self.analyzer.temp_slope

        return self._classify(temp, hum, pres, p_slope, h_slope, t_slope)

    # ── classification rules ─────────────────────────────────────────────────

    def weekly_forecast(self, days: int = 7) -> list[DailyForecast]:
        """
        Build a lightweight 7-day trend projection from recent sensor readings.

        The live ML model predicts the next sensor sample. This week view is a
        conservative trend projection for the dashboard; use day-level history
        or a weather API for real daily forecasting.
        """
        if not self.analyzer.ready:
            return []

        temp = float(self.analyzer.current_temp)
        hum = float(self.analyzer.current_humidity)
        pres = float(self.analyzer.current_pressure)
        t_slope = float(np.clip(self.analyzer.temp_slope, -1.5, 1.5))
        h_slope = float(np.clip(self.analyzer.humidity_slope, -5.0, 5.0))
        p_slope = float(np.clip(self.analyzer.pressure_slope, -3.0, 3.0))

        out: list[DailyForecast] = []
        for day in range(1, days + 1):
            projected_temp = temp + t_slope * day
            projected_hum = float(np.clip(hum + h_slope * day, 0.0, 100.0))
            projected_pres = float(np.clip(pres + p_slope * day, 800.0, 1100.0))
            fc = self._classify(
                projected_temp,
                projected_hum,
                projected_pres,
                p_slope,
                h_slope,
                t_slope,
            )
            out.append(
                DailyForecast(
                    day=f"Day +{day}",
                    expected_temp=round(projected_temp, 1),
                    label=fc.label,
                    emoji=fc.emoji,
                    confidence=fc.confidence,
                )
            )
        return out

    def _classify(
        self,
        temp: float,
        hum: float,
        pres: float,
        p_slope: float,
        h_slope: float,
        t_slope: float,
    ) -> ForecastResult:
        confidence = 60.0  # base confidence

        # ── Storm: falling pressure fast + high humidity ─────────────────
        if p_slope < -0.05 and hum > 75 and pres < 1005:
            confidence = min(95, 75 + abs(p_slope) * 100)
            return ForecastResult(
                "Storm", _CONDITIONS["Storm"], round(confidence, 1),
                "Rapidly falling pressure with high humidity — storm likely.",
            )

        # ── Rainy: low pressure or rising humidity fast ──────────────────
        if (hum > 70 and pres < 1010) or (h_slope > 0.05 and hum > 65 and pres < 1015):
            confidence = min(90, 65 + hum * 0.3)
            label = "Rainy"
            desc = "Low pressure and high humidity suggest rain."
            if p_slope < -0.02:
                confidence = min(95, confidence + 10)
                desc += " Pressure falling — conditions worsening."
            return ForecastResult(label, _CONDITIONS[label], round(confidence, 1), desc)

        # ── Drizzle: moderate humidity, slightly low pressure ────────────
        if 60 < hum <= 70 and pres < 1013:
            confidence = 55 + (hum - 60) * 0.8
            return ForecastResult(
                "Drizzle", _CONDITIONS["Drizzle"], round(confidence, 1),
                "Moderate humidity and slightly low pressure — possible drizzle.",
            )

        # ── Foggy: high humidity, steady/rising pressure, cool ───────────
        if hum > 65 and pres >= 1013 and p_slope >= 0 and temp < 20:
            confidence = 55 + (hum - 65) * 0.5
            return ForecastResult(
                "Foggy", _CONDITIONS["Foggy"], round(confidence, 1),
                "High humidity with stable/rising pressure and cool temp — fog possible.",
            )

        # ── Sunny: rising/stable pressure, low humidity ──────────────────
        if hum < 55 and pres > 1015 and p_slope >= -0.01:
            confidence = min(95, 70 + (pres - 1015) * 2 + (55 - hum) * 0.4)
            return ForecastResult(
                "Sunny", _CONDITIONS["Sunny"], round(confidence, 1),
                "High pressure and low humidity — clear skies expected.",
            )

        # ── Partly Cloudy: transitional ──────────────────────────────────
        if 55 <= hum <= 70 and pres > 1010:
            confidence = 55.0
            return ForecastResult(
                "Partly Cloudy", _CONDITIONS["Partly Cloudy"], confidence,
                "Mixed conditions — partly cloudy skies.",
            )

        # ── Default: Cloudy ──────────────────────────────────────────────
        confidence = 50.0
        return ForecastResult(
            "Cloudy", _CONDITIONS["Cloudy"], confidence,
            "Stable moderate conditions — overcast likely.",
        )
