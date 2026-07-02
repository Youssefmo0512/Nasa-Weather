"""
model_manager.py — Online machine learning pipeline.

- SGDRegressor for online learning (primary)
- Accurate rolling metrics: MAE, RMSE, R²
- Feature engineering via utils.build_feature_vector
- Pretraining from history CSV
- Periodic model persistence with joblib
- Thread-safe prediction + training interface
"""

from __future__ import annotations

import threading
import time
from collections import deque
from pathlib import Path
from typing import Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import SGDRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler

from config.config import MLConfig
from logger.logger import get_logger
from utils.utils import SensorSample, build_feature_vector

_log = get_logger("ModelManager")


# ─── Metrics snapshot ────────────────────────────────────────────────────────

class MetricsTracker:
    """Rolling MAE, RMSE, R² over the last N predictions."""

    def __init__(self, maxlen: int = 50, min_samples: int = 5) -> None:
        self._preds: deque[float] = deque(maxlen=maxlen)
        self._actuals: deque[float] = deque(maxlen=maxlen)
        self._min = min_samples

    def add(self, predicted: float, actual: float) -> None:
        if np.isfinite(predicted) and np.isfinite(actual):
            self._preds.append(predicted)
            self._actuals.append(actual)

    @property
    def ready(self) -> bool:
        return len(self._preds) >= self._min

    @property
    def mae(self) -> Optional[float]:
        if not self.ready:
            return None
        return float(mean_absolute_error(self._actuals, self._preds))

    @property
    def rmse(self) -> Optional[float]:
        if not self.ready:
            return None
        return float(np.sqrt(mean_squared_error(self._actuals, self._preds)))

    @property
    def r2(self) -> Optional[float]:
        if not self.ready:
            return None
        try:
            return float(r2_score(self._actuals, self._preds))
        except Exception:
            return None

    def summary(self) -> dict:
        return {
            "mae":  self.mae,
            "rmse": self.rmse,
            "r2":   self.r2,
            "n":    len(self._preds),
        }


# ─── Model Manager ───────────────────────────────────────────────────────────

class ModelManager:
    """
    Thread-safe online learning manager.

    Usage:
        mm = ModelManager(cfg)
        mm.load_or_init()
        mm.pretrain_from_history(history_path)
        mm.start_autosave()

        # In main loop:
        pred = mm.predict_and_train(window, next_sample)
        metrics = mm.metrics.summary()
    """

    def __init__(self, cfg: MLConfig) -> None:
        self._cfg = cfg
        self._lock = threading.Lock()
        self._model: Optional[SGDRegressor] = None
        self._scaler: Optional[StandardScaler] = None
        self.metrics = MetricsTracker(
            maxlen=cfg.rolling_metric_window,
            min_samples=cfg.min_samples_for_metrics,
        )
        self._save_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    # ── init ─────────────────────────────────────────────────────────────────

    def load_or_init(self) -> None:
        path = self._cfg.model_file
        if path.exists():
            try:
                saved = joblib.load(path)
                self._model = saved["model"]
                self._scaler = saved["scaler"]
                _log.info("Loaded model from %s", path)
                return
            except Exception as exc:
                _log.warning("Could not load model (%s) — initializing fresh.", exc)
        self._init_fresh()

    def _init_fresh(self) -> None:
        self._model = SGDRegressor(
            max_iter=1,
            tol=None,
            learning_rate="constant",
            eta0=self._cfg.learning_rate,
            warm_start=True,
            loss="huber",           # robust to outliers
            epsilon=0.1,
        )
        self._scaler = StandardScaler()
        _log.info("Initialized fresh SGDRegressor.")

    # ── pretraining ──────────────────────────────────────────────────────────

    def pretrain_from_history(self, path: Path) -> int:
        if not path.exists():
            _log.info("No history file at %s — skipping pretraining.", path)
            return 0
        try:
            df = pd.read_csv(path)
        except Exception as exc:
            _log.error("Could not read history: %s", exc)
            return 0

        required = {"temperature", "humidity", "pressure"}
        if not required.issubset(df.columns):
            _log.warning("history.csv missing columns %s — skipping.", required - set(df.columns))
            return 0

        df = df.dropna(subset=list(required))
        ws = self._cfg.window_size
        X_list, y_list = [], []

        for i in range(len(df) - ws - 1):
            window_rows = df.iloc[i : i + ws]
            target_temp = df.iloc[i + ws]["temperature"]
            samples = [
                SensorSample(
                    ts=float(row.get("timestamp", 0)),
                    temperature=float(row["temperature"]),
                    humidity=float(row["humidity"]),
                    pressure=float(row["pressure"]),
                )
                for row in window_rows.to_dict("records")
            ]
            feat = build_feature_vector(samples)
            X_list.append(feat)
            y_list.append(target_temp)
            if len(X_list) >= self._cfg.initial_batch_size:
                break

        if not X_list:
            return 0

        X = np.vstack(X_list)
        y = np.array(y_list)

        with self._lock:
            self._scaler.partial_fit(X)
            self._model.partial_fit(self._scaler.transform(X), y)

        _log.info("Pretrained on %d samples from history.", len(y))
        return len(y)

    # ── predict + train ──────────────────────────────────────────────────────

    def predict(self, window: list[SensorSample]) -> float:
        """Predict next temperature from window. Returns nan on failure."""
        feat = build_feature_vector(window)
        with self._lock:
            try:
                self._scaler.partial_fit(feat.reshape(1, -1))
                X_scaled = self._scaler.transform(feat.reshape(1, -1))
                return float(self._model.predict(X_scaled)[0])
            except Exception as exc:
                _log.debug("Prediction error: %s", exc)
                return float("nan")

    def train(self, window: list[SensorSample], actual_next_temp: float) -> None:
        """Online update with a ground-truth next temperature."""
        feat = build_feature_vector(window)
        with self._lock:
            try:
                X_scaled = self._scaler.transform(feat.reshape(1, -1))
                self._model.partial_fit(X_scaled, np.array([actual_next_temp]))
            except Exception as exc:
                _log.warning("Training error: %s", exc)

    def record_error(self, predicted: float, actual: float) -> None:
        self.metrics.add(predicted, actual)

    # ── persistence ──────────────────────────────────────────────────────────

    def save(self) -> None:
        path = self._cfg.model_file
        try:
            with self._lock:
                joblib.dump({"model": self._model, "scaler": self._scaler}, path)
            _log.info("Model saved → %s", path)
        except Exception as exc:
            _log.error("Model save failed: %s", exc)

    def start_autosave(self) -> None:
        self._save_thread = threading.Thread(
            target=self._autosave_loop, name="ModelSaver", daemon=True
        )
        self._save_thread.start()

    def stop_autosave(self) -> None:
        self._stop_event.set()

    def _autosave_loop(self) -> None:
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=self._cfg.save_every_seconds)
            if not self._stop_event.is_set():
                self.save()
        self.save()  # final save on exit
        _log.info("Model autosave thread exited.")
