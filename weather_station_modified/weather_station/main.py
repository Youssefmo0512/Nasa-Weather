"""
main.py — Application entry point.

Orchestrates:
  1. Serial manager (background daemon thread)
  2. Main processing loop (background daemon thread)
  3. Model manager (online learning + autosave)
  4. Forecast engine
  5. CSV loggers (stream_log + history)
  6. Tkinter GUI (main thread)
"""

from __future__ import annotations

import threading
import time
from collections import deque
from queue import Empty, Queue

import tkinter as tk

# ── project imports ──────────────────────────────────────────────────────────
from config.config import CFG
from forecast.forecast import WeatherForecaster
from gui.gui import DataBus, WeatherDashboard
from logger.logger import CSVLogger, get_logger
from model_manager.model_manager import ModelManager
from serial_manager.serial_manager import SerialManager
from utils.utils import SensorSample

_log = get_logger("Main")


# ─── Main processing loop ────────────────────────────────────────────────────

def processing_loop(
    sample_queue: Queue[SensorSample],
    model: ModelManager,
    forecaster: WeatherForecaster,
    stream_logger: CSVLogger,
    history_logger: CSVLogger,
    bus: DataBus,
    stop_event: threading.Event,
) -> None:
    """
    Continuously consumes samples from the serial queue.
    For each sample:
      - logs raw data to stream_log.csv
      - predicts next temperature
      - trains on the next incoming sample
      - updates metrics, forecast, and GUI data bus
    """
    ws = CFG.ml.window_size
    window: deque[SensorSample] = deque(maxlen=ws)

    # ── warm-up: fill window ─────────────────────────────────────────────────
    _log.info("Warming up — collecting %d samples…", ws)
    while len(window) < ws and not stop_event.is_set():
        try:
            s = sample_queue.get(timeout=10)
            window.append(s)
            _log.debug("Warm-up sample %d/%d", len(window), ws)
            # log raw even during warm-up
            stream_logger.write([s.ts, s.temperature, s.humidity, s.pressure, s.raw_line])
            bus.push_sample(s.temperature, float("nan"), s.humidity, s.pressure)
        except Empty:
            _log.warning("No serial data received — waiting…")

    _log.info("Warm-up complete. Starting prediction loop.")

    # ── main loop ────────────────────────────────────────────────────────────
    while not stop_event.is_set():
        # ① get current sample
        try:
            current = sample_queue.get(timeout=CFG.serial.timeout * 2)
        except Empty:
            continue

        # ② log raw data
        stream_logger.write([
            current.ts,
            current.temperature,
            current.humidity,
            current.pressure,
            current.raw_line,
        ])

        # ③ predict next temperature
        pred_next = model.predict(list(window))

        # ④ log to history (not yet trained)
        history_logger.write([
            current.ts,
            current.temperature,
            current.humidity,
            current.pressure,
            pred_next if pred_next == pred_next else "",  # nan → empty
            "",  # mae placeholder
            0,
        ])

        # ⑤ update forecast
        forecaster.update(current.temperature, current.humidity, current.pressure)
        fc = forecaster.forecast()
        bus.set_forecast(fc.label, fc.emoji, fc.confidence)
        bus.set_weekly_forecast(forecaster.weekly_forecast(days=7))

        # ⑥ push to GUI
        bus.push_sample(current.temperature, pred_next, current.humidity, current.pressure)

        # ⑦ get next sample for training
        try:
            next_sample = sample_queue.get(timeout=CFG.serial.timeout * 5)
        except Empty:
            window.append(current)
            continue

        # ⑧ train model on current window → next_sample target
        window.append(current)
        model.train(list(window), next_sample.temperature)
        model.record_error(pred_next, next_sample.temperature)

        # ⑨ update metrics in bus
        m = model.metrics.summary()
        bus.set_metrics(m["mae"], m["rmse"], m["r2"], m["n"])

        # ⑩ log next_sample to history (trained)
        stream_logger.write([
            next_sample.ts,
            next_sample.temperature,
            next_sample.humidity,
            next_sample.pressure,
            next_sample.raw_line,
        ])
        history_logger.write([
            next_sample.ts,
            next_sample.temperature,
            next_sample.humidity,
            next_sample.pressure,
            "",
            m["mae"] if m["mae"] is not None else "",
            1,
        ])

        window.append(next_sample)
        bus.push_sample(next_sample.temperature, pred_next, next_sample.humidity, next_sample.pressure)

    _log.info("Processing loop exited.")


# ─── Application entry point ─────────────────────────────────────────────────

def run_app() -> None:
    _log.info("=" * 60)
    _log.info("Weather Station starting…")
    _log.info("=" * 60)

    # ── Shared objects ───────────────────────────────────────────────────────
    sample_queue: Queue[SensorSample] = Queue(maxsize=500)
    stop_event = threading.Event()
    bus = DataBus(maxlen=CFG.gui.plot_window * 3)

    # ── Loggers ──────────────────────────────────────────────────────────────
    stream_logger = CSVLogger(
        path=CFG.log.stream_log,
        headers=CSVLogger.STREAM_HEADERS,
        buffer_size=CFG.log.write_buffer_size,
        max_rows=CFG.log.max_history_rows,
    )
    history_logger = CSVLogger(
        path=CFG.log.history_csv,
        headers=CSVLogger.HISTORY_HEADERS,
        buffer_size=CFG.log.write_buffer_size,
        max_rows=CFG.log.max_history_rows,
    )

    # ── Model ────────────────────────────────────────────────────────────────
    model = ModelManager(CFG.ml)
    model.load_or_init()
    pretrained = model.pretrain_from_history(CFG.log.history_csv)
    _log.info("Pretrained on %d history samples.", pretrained)
    model.start_autosave()

    # ── Forecaster ───────────────────────────────────────────────────────────
    forecaster = WeatherForecaster()

    # ── Serial manager ───────────────────────────────────────────────────────
    serial_mgr = SerialManager(CFG.serial, sample_queue)
    serial_mgr.start()

    # Mirror serial status to bus every second (lightweight)
    def _status_mirror() -> None:
        while not stop_event.is_set():
            bus.set_serial_status(serial_mgr.status)
            stop_event.wait(timeout=1.0)

    t_status = threading.Thread(target=_status_mirror, name="StatusMirror", daemon=True)
    t_status.start()

    # ── Processing loop thread ───────────────────────────────────────────────
    t_proc = threading.Thread(
        target=processing_loop,
        args=(sample_queue, model, forecaster, stream_logger, history_logger, bus, stop_event),
        name="ProcessingLoop",
        daemon=True,
    )
    t_proc.start()

    # ── GUI (must run on main thread) ─────────────────────────────────────────
    root = tk.Tk()
    dashboard = WeatherDashboard(root, bus, CFG.gui)  # noqa: F841

    def _on_close() -> None:
        _log.info("GUI closed — initiating clean shutdown…")
        stop_event.set()
        serial_mgr.stop()
        model.stop_autosave()
        stream_logger.flush()
        history_logger.flush()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", _on_close)

    _log.info("GUI ready. Entering Tk main loop.")
    root.mainloop()

    _log.info("Application exited cleanly.")


if __name__ == "__main__":
    run_app()
