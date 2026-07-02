"""
gui.py — Professional dark-mode Tkinter dashboard with real-time metrics.

Layout:
  ┌─────────────────────────────────────────────────────────────┐
  │  HEADER: title + serial status                               │
  ├──────────┬──────────┬──────────┬──────────┬─────────────────┤
  │ Temp Now │ Pred Temp│ Humidity │ Pressure │    Forecast      │
  ├──────────┴──────────┴──────────┴──────────┴─────────────────┤
  │                   Dual-line Temperature Chart                 │
  ├─────────────────────────────────────────────────────────────┤
  │       MAE      │      RMSE      │      R²       │   Count    │
  └─────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import math
import threading
from collections import deque
from typing import Optional

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import tkinter as tk
from tkinter import ttk

from config.config import GUIConfig
from logger.logger import get_logger
from serial_manager.serial_manager import SerialStatus

_log = get_logger("GUI")

# ─── Palette ─────────────────────────────────────────────────────────────────
PAL = {
    "bg":           "#0D1117",
    "card":         "#161B22",
    "border":       "#30363D",
    "accent":       "#58A6FF",
    "accent2":      "#F78166",
    "green":        "#3FB950",
    "yellow":       "#D29922",
    "red":          "#F85149",
    "text_primary": "#E6EDF3",
    "text_muted":   "#8B949E",
    "chart_bg":     "#0D1117",
    "grid":         "#1C2128",
    "actual_line":  "#58A6FF",
    "pred_line":    "#FF7B72",
}


# ─── Shared data bus ─────────────────────────────────────────────────────────

class DataBus:
    """Thread-safe container that the main loop writes and the GUI reads."""

    def __init__(self, maxlen: int = 200) -> None:
        self._lock = threading.Lock()
        self.actual_temps:  deque[float] = deque(maxlen=maxlen)
        self.pred_temps:    deque[float] = deque(maxlen=maxlen)
        self.humidities:    deque[float] = deque(maxlen=maxlen)
        self.pressures:     deque[float] = deque(maxlen=maxlen)
        self._serial_status: SerialStatus = SerialStatus.DISCONNECTED
        self._forecast_label: str = "–"
        self._forecast_emoji: str = "🔄"
        self._forecast_conf:  float = 0.0
        self._weekly_forecast: list[dict] = []
        self._mae:  Optional[float] = None
        self._rmse: Optional[float] = None
        self._r2:   Optional[float] = None
        self._n:    int = 0

    # ── writers (called from background threads) ─────────────────────────────

    def push_sample(
        self,
        actual: float,
        pred: float,
        humidity: float,
        pressure: float,
    ) -> None:
        with self._lock:
            if math.isfinite(actual):
                self.actual_temps.append(actual)
            if math.isfinite(pred):
                self.pred_temps.append(pred)
            if math.isfinite(humidity):
                self.humidities.append(humidity)
            if math.isfinite(pressure):
                self.pressures.append(pressure)

    def set_serial_status(self, s: SerialStatus) -> None:
        with self._lock:
            self._serial_status = s

    def set_forecast(self, label: str, emoji: str, conf: float) -> None:
        with self._lock:
            self._forecast_label = label
            self._forecast_emoji = emoji
            self._forecast_conf  = conf

    def set_weekly_forecast(self, forecast: list) -> None:
        with self._lock:
            self._weekly_forecast = [
                {
                    "day": item.day,
                    "temp": item.expected_temp,
                    "label": item.label,
                    "emoji": item.emoji,
                    "confidence": item.confidence,
                }
                for item in forecast
            ]

    def set_metrics(self, mae, rmse, r2, n: int) -> None:
        with self._lock:
            self._mae  = mae
            self._rmse = rmse
            self._r2   = r2
            self._n    = n

    # ── readers (called from GUI thread) ─────────────────────────────────────

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "actual":    list(self.actual_temps),
                "pred":      list(self.pred_temps),
                "hum":       list(self.humidities),
                "pres":      list(self.pressures),
                "status":    self._serial_status,
                "fc_label":  self._forecast_label,
                "fc_emoji":  self._forecast_emoji,
                "fc_conf":   self._forecast_conf,
                "weekly":    list(self._weekly_forecast),
                "mae":       self._mae,
                "rmse":      self._rmse,
                "r2":        self._r2,
                "n":         self._n,
            }


# ─── Dashboard window ────────────────────────────────────────────────────────

class WeatherDashboard:
    """Professional dark-mode Tkinter dashboard."""

    def __init__(self, root: tk.Tk, bus: DataBus, cfg: GUIConfig) -> None:
        self._root = root
        self._bus  = bus
        self._cfg  = cfg
        self._setup_root()
        self._build_header()
        self._build_metric_cards()
        self._build_chart()
        self._build_weekly_forecast()
        self._build_metric_row()
        self._schedule_refresh()

    # ── setup ─────────────────────────────────────────────────────────────────

    def _setup_root(self) -> None:
        r = self._root
        r.title(self._cfg.window_title)
        r.configure(bg=PAL["bg"])
        r.geometry("1100x720")
        r.minsize(900, 600)

    # ── header ────────────────────────────────────────────────────────────────

    def _build_header(self) -> None:
        hdr = tk.Frame(self._root, bg=PAL["card"], pady=10)
        hdr.pack(fill="x", padx=12, pady=(12, 4))

        tk.Label(
            hdr,
            text="🌤  NASA Weather Station",
            font=("Courier New", 20, "bold"),
            fg=PAL["accent"],
            bg=PAL["card"],
        ).pack(side="left", padx=18)

        self._status_lbl = tk.Label(
            hdr,
            text="⬤  Connecting…",
            font=("Courier New", 11),
            fg=PAL["yellow"],
            bg=PAL["card"],
        )
        self._status_lbl.pack(side="right", padx=18)

        self._time_lbl = tk.Label(
            hdr,
            text="",
            font=("Courier New", 11),
            fg=PAL["text_muted"],
            bg=PAL["card"],
        )
        self._time_lbl.pack(side="right", padx=8)

    # ── metric cards row ──────────────────────────────────────────────────────

    def _build_metric_cards(self) -> None:
        row = tk.Frame(self._root, bg=PAL["bg"])
        row.pack(fill="x", padx=12, pady=4)

        cards_cfg = [
            ("🌡", "Current Temp",   "--",   "°C",  "accent"),
            ("🔮", "Predicted Temp", "--",   "°C",  "accent2"),
            ("💧", "Humidity",       "--",   "%",   "green"),
            ("⏱", "Pressure",       "--",   "hPa", "text_muted"),
            ("🌤", "Forecast",       "--",   "",    "yellow"),
        ]

        self._card_vals: dict[str, tk.StringVar] = {}
        for i, (icon, title, init, unit, color) in enumerate(cards_cfg):
            frame = tk.Frame(row, bg=PAL["card"], bd=0, relief="flat")
            frame.grid(row=0, column=i, sticky="nsew", padx=5, pady=4, ipady=10)
            row.columnconfigure(i, weight=1)

            tk.Label(frame, text=icon, font=("Segoe UI Emoji", 18), bg=PAL["card"],
                     fg=PAL[color]).pack(pady=(10, 0))
            tk.Label(frame, text=title, font=("Courier New", 9),
                     bg=PAL["card"], fg=PAL["text_muted"]).pack()

            var = tk.StringVar(value=init + (" " + unit if unit else ""))
            self._card_vals[title] = var
            tk.Label(frame, textvariable=var, font=("Courier New", 16, "bold"),
                     bg=PAL["card"], fg=PAL[color]).pack(pady=(2, 10))

    # ── chart ─────────────────────────────────────────────────────────────────

    def _build_chart(self) -> None:
        fig_frame = tk.Frame(self._root, bg=PAL["bg"])
        fig_frame.pack(fill="both", expand=True, padx=12, pady=4)

        plt.rcParams.update({
            "figure.facecolor":  PAL["chart_bg"],
            "axes.facecolor":    PAL["chart_bg"],
            "axes.edgecolor":    PAL["border"],
            "axes.labelcolor":   PAL["text_muted"],
            "xtick.color":       PAL["text_muted"],
            "ytick.color":       PAL["text_muted"],
            "grid.color":        PAL["grid"],
            "legend.facecolor":  PAL["card"],
            "legend.edgecolor":  PAL["border"],
            "legend.labelcolor": PAL["text_primary"],
            "text.color":        PAL["text_primary"],
        })

        self._fig, self._ax = plt.subplots(figsize=(10, 3.5))
        self._ax.set_title("Temperature — Actual vs Predicted", color=PAL["text_primary"],
                           fontsize=11, pad=8)
        self._ax.set_xlabel("Sample index", fontsize=9)
        self._ax.set_ylabel("Temperature (°C)", fontsize=9)
        self._ax.grid(True, linewidth=0.5)
        self._ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.2f"))

        self._line_actual, = self._ax.plot(
            [], [], label="Actual", color=PAL["actual_line"], linewidth=1.8, alpha=0.9
        )
        self._line_pred, = self._ax.plot(
            [], [], label="Predicted", color=PAL["pred_line"],
            linewidth=1.5, linestyle="--", alpha=0.85
        )
        self._ax.legend(loc="upper left", fontsize=9)

        self._canvas = FigureCanvasTkAgg(self._fig, master=fig_frame)
        self._canvas.get_tk_widget().pack(fill="both", expand=True)

    def _build_weekly_forecast(self) -> None:
        bar = tk.Frame(self._root, bg=PAL["bg"])
        bar.pack(fill="x", padx=12, pady=4)

        title = tk.Label(
            bar,
            text="7-Day Temperature Trend",
            font=("Courier New", 10, "bold"),
            bg=PAL["bg"],
            fg=PAL["text_muted"],
        )
        title.pack(anchor="w", padx=4)

        days_row = tk.Frame(bar, bg=PAL["bg"])
        days_row.pack(fill="x")

        self._weekly_vars: list[tk.StringVar] = []
        for i in range(7):
            var = tk.StringVar(value=f"Day +{i + 1}\n-- C\n--")
            self._weekly_vars.append(var)
            cell = tk.Frame(days_row, bg=PAL["card"], bd=0, relief="flat")
            cell.grid(row=0, column=i, sticky="nsew", padx=4, pady=4, ipady=6)
            days_row.columnconfigure(i, weight=1)
            tk.Label(
                cell,
                textvariable=var,
                justify="center",
                font=("Courier New", 9, "bold"),
                bg=PAL["card"],
                fg=PAL["text_primary"],
            ).pack(fill="both", expand=True, padx=4, pady=4)

    # ── bottom metrics row ────────────────────────────────────────────────────

    def _build_metric_row(self) -> None:
        bar = tk.Frame(self._root, bg=PAL["card"])
        bar.pack(fill="x", padx=12, pady=(4, 12))

        specs = [
            ("MAE",   "mae_var",  "°C",  PAL["accent"]),
            ("RMSE",  "rmse_var", "°C",  PAL["accent2"]),
            ("R²",    "r2_var",   "",    PAL["green"]),
            ("Samples","n_var",   "",    PAL["text_muted"]),
        ]
        self._metric_vars: dict[str, tk.StringVar] = {}
        for i, (name, attr, unit, color) in enumerate(specs):
            cell = tk.Frame(bar, bg=PAL["card"])
            cell.grid(row=0, column=i, sticky="nsew", padx=16, pady=6)
            bar.columnconfigure(i, weight=1)

            tk.Label(cell, text=name, font=("Courier New", 9),
                     bg=PAL["card"], fg=PAL["text_muted"]).pack()
            var = tk.StringVar(value="–")
            self._metric_vars[attr] = var
            tk.Label(cell, textvariable=var, font=("Courier New", 13, "bold"),
                     bg=PAL["card"], fg=color).pack()
            if unit:
                tk.Label(cell, text=unit, font=("Courier New", 8),
                         bg=PAL["card"], fg=PAL["text_muted"]).pack()

    # ── refresh cycle ─────────────────────────────────────────────────────────

    def _schedule_refresh(self) -> None:
        self._root.after(self._cfg.refresh_ms, self._refresh)

    def _refresh(self) -> None:
        try:
            snap = self._bus.snapshot()
            self._update_status(snap)
            self._update_cards(snap)
            self._update_chart(snap)
            self._update_weekly_forecast(snap)
            self._update_metrics(snap)
        except Exception as exc:
            _log.warning("GUI refresh error: %s", exc)
        finally:
            self._schedule_refresh()

    def _update_status(self, snap: dict) -> None:
        import time as _time
        self._time_lbl.config(text=_time.strftime("%H:%M:%S"))
        st: SerialStatus = snap["status"]
        color_map = {
            SerialStatus.CONNECTED:    PAL["green"],
            SerialStatus.DISCONNECTED: PAL["red"],
            SerialStatus.RECONNECTING: PAL["yellow"],
            SerialStatus.CONNECTING:   PAL["yellow"],
            SerialStatus.DISABLED:     PAL["text_muted"],
        }
        self._status_lbl.config(
            text=f"⬤  {st.value}",
            fg=color_map.get(st, PAL["text_muted"]),
        )

    def _update_cards(self, snap: dict) -> None:
        def last(lst: list, fmt: str = ".2f") -> str:
            return (f"{lst[-1]:{fmt}}" if lst else "--")

        self._card_vals["Current Temp"].set(last(snap["actual"]) + " °C")
        self._card_vals["Predicted Temp"].set(last(snap["pred"]) + " °C")
        self._card_vals["Humidity"].set(last(snap["hum"]) + " %")
        self._card_vals["Pressure"].set(last(snap["pres"], ".1f") + " hPa")

        fc = f"{snap['fc_emoji']} {snap['fc_label']}"
        if snap["fc_conf"] > 0:
            fc += f" {snap['fc_conf']:.0f}%"
        self._card_vals["Forecast"].set(fc)

    def _update_chart(self, snap: dict) -> None:
        pw = self._cfg.plot_window
        actual = snap["actual"][-pw:]
        pred   = snap["pred"][-pw:]

        if not actual:
            return

        xa = list(range(len(actual)))
        xp = list(range(len(pred)))

        self._line_actual.set_data(xa, actual)
        self._line_pred.set_data(xp, pred)

        all_vals = [v for v in (actual + pred) if math.isfinite(v)]
        if all_vals:
            margin = 0.1
            lo, hi = min(all_vals), max(all_vals)
            if self._cfg.temperature_axis_min is not None:
                lo = min(lo, self._cfg.temperature_axis_min)
            if self._cfg.temperature_axis_max is not None:
                hi = max(hi, self._cfg.temperature_axis_max)
            span = max(hi - lo, 0.5)
            self._ax.set_ylim(lo - margin * span, hi + margin * span)
        self._ax.set_xlim(0, max(pw, len(actual)))

        try:
            self._canvas.draw_idle()
        except Exception:
            pass

    def _update_weekly_forecast(self, snap: dict) -> None:
        weekly = snap.get("weekly", [])
        for i, var in enumerate(self._weekly_vars):
            if i < len(weekly):
                item = weekly[i]
                var.set(f"{item['day']}\n{item['temp']:.1f} C\n{item['label']}")
            else:
                var.set(f"Day +{i + 1}\n-- C\n--")

    def _update_metrics(self, snap: dict) -> None:
        def fmt(v, decimals=3) -> str:
            return f"{v:.{decimals}f}" if v is not None else "–"

        self._metric_vars["mae_var"].set(fmt(snap["mae"]))
        self._metric_vars["rmse_var"].set(fmt(snap["rmse"]))
        self._metric_vars["r2_var"].set(fmt(snap["r2"]))
        self._metric_vars["n_var"].set(str(snap["n"]))
