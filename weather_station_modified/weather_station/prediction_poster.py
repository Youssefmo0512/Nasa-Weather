"""
prediction_poster.py — Headless background runner for weather predictions.

Loads configuration, connects to the serial manager, runs the online ML pipeline
and weather forecasting engine, logs to CSV files, and sends predictions to
api_prediction.php.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import threading
import time
import urllib.request
from collections import deque
from queue import Empty, Queue
from http.server import BaseHTTPRequestHandler, HTTPServer

# Thread-safe storage for HTTP live telemetry server
_http_server_lock = threading.Lock()
_latest_prediction_payload: dict = {}
_prediction_history: list[dict] = []

class LiveDataHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/live":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.end_headers()
            
            with _http_server_lock:
                latest = _latest_prediction_payload
                history = list(_prediction_history)
                
            response_data = {
                "latest": latest if latest else None,
                "history": list(reversed(history)),
                "status": "Running"
            }
            self.wfile.write(json.dumps(response_data).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()

    def log_message(self, format, *args):
        pass # Suppress command line logging of requests

# Project imports
from config.config import CFG
from forecast.forecast import WeatherForecaster
from logger.logger import CSVLogger, get_logger
from model_manager.model_manager import ModelManager
from serial_manager.serial_manager import SerialManager
from utils.utils import SensorSample

# Parse CLI arguments first
parser = argparse.ArgumentParser(description="Weather Station Headless Prediction Runner")
group = parser.add_mutually_exclusive_group()
group.add_argument("-q", "--quiet", action="store_true", help="Minimal technical logs only")
group.add_argument("-v", "--verbose", action="store_true", help="Verbose debug logging")
args = parser.parse_args()

# Setup Logging levels
if args.verbose:
    logging.getLogger().setLevel(logging.DEBUG)
elif args.quiet:
    logging.getLogger().setLevel(logging.ERROR)
else:
    logging.getLogger().setLevel(logging.WARNING)

_log = get_logger("PredictionPoster")


def log_technical(msg: str):
    """Outputs a timestamped message to console. Used for minimal logs."""
    # Always print these unless we are completely silent (which is not requested)
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def test_api_connection(url: str) -> bool:
    """Sends a quick GET request to test connection to PHP API."""
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.getcode() == 200
    except Exception as exc:
        _log.debug("API test connection failed: %s", exc)
        return False


def post_prediction(url: str, payload: dict) -> bool:
    """POSTs prediction payload to PHP API."""
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.getcode() == 200
    except Exception as exc:
        _log.debug("API POST failed: %s", exc)
        return False


def make_float_safe(val) -> float | None:
    """Converts value to a JSON-safe float, returning None if NaN or Infinite."""
    try:
        f = float(val)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def run_headless():
    log_technical("Script started")

    # Verify PHP API is reachable
    api_url = CFG.api.url
    if test_api_connection(api_url):
        log_technical("Connected to API")
    else:
        log_technical("API error")

    sample_queue: Queue[SensorSample] = Queue(maxsize=500)
    stop_event = threading.Event()

    # Start local HTTP server on port 8080/8081 for direct Pages connection (CORS enabled)
    def start_local_server():
        try:
            server = HTTPServer(("127.0.0.1", 8080), LiveDataHandler)
            log_technical("Local HTTP Server started on http://127.0.0.1:8080/live")
        except Exception as e:
            try:
                server = HTTPServer(("127.0.0.1", 8081), LiveDataHandler)
                log_technical("Local HTTP Server started on http://127.0.0.1:8081/live")
            except Exception as e2:
                log_technical(f"Could not bind HTTP server on port 8080 or 8081: {e2}")
                return
        
        server.timeout = 0.5
        while not stop_event.is_set():
            server.handle_request()
        server.server_close()
        log_technical("Local HTTP Server stopped")

    server_thread = threading.Thread(target=start_local_server, daemon=True)
    server_thread.start()

    # Loggers
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

    # ML Model
    model = ModelManager(CFG.ml)
    model.load_or_init()
    pretrained = model.pretrain_from_history(CFG.log.history_csv)
    if not args.quiet:
        _log.info("Pretrained on %d history samples.", pretrained)
    model.start_autosave()

    # Forecaster
    forecaster = WeatherForecaster()

    # Serial Manager
    serial_mgr = SerialManager(CFG.serial, sample_queue)
    serial_mgr.start()

    ws = CFG.ml.window_size
    window: deque[SensorSample] = deque(maxlen=ws)
    row_count = 0

    try:
        # ── Warm-up Phase ────────────────────────────────────────────────────
        if not args.quiet:
            _log.info("Warming up — collecting %d samples…", ws)
        
        while len(window) < ws and not stop_event.is_set():
            try:
                s = sample_queue.get(timeout=10)
                window.append(s)
                # Log raw even during warm-up
                stream_logger.write([s.ts, s.temperature, s.humidity, s.pressure, s.raw_line])
            except Empty:
                if not args.quiet:
                    _log.warning("No serial data received — waiting…")

        if not args.quiet:
            _log.info("Warm-up complete. Starting headless prediction loop.")

        # ── Main Processing Loop ──────────────────────────────────────────────
        while not stop_event.is_set():
            # 1. Get current sample
            try:
                current = sample_queue.get(timeout=CFG.serial.timeout * 2)
            except Empty:
                continue

            row_count += 1

            # 2. Log raw data to stream
            stream_logger.write([
                current.ts,
                current.temperature,
                current.humidity,
                current.pressure,
                current.raw_line,
            ])

            # 3. Predict next temperature
            pred_next = model.predict(list(window))

            # 4. Log to history (untrained prediction)
            history_logger.write([
                current.ts,
                current.temperature,
                current.humidity,
                current.pressure,
                pred_next if pred_next == pred_next else "",  # NaN -> empty
                "",  # MAE placeholder
                0,
            ])

            # 5. Update forecast engine
            forecaster.update(current.temperature, current.humidity, current.pressure)
            fc = forecaster.forecast()

            # 6. POST the prediction to the web API
            payload = {
                "predicted_temperature": make_float_safe(pred_next),
                "predicted_humidity": None,
                "predicted_pressure": None,
                "predicted_dew_point": None,
                "prediction": fc.label,
                "weather_condition": fc.label,
                "risk_level": None,
                "confidence": make_float_safe(fc.confidence),
                "source": "AI Prediction / Dataset",
                "dataset_row_index": row_count,
                "dataset_timestamp": make_float_safe(current.ts),
                "raw_input": {
                    "temperature": make_float_safe(current.temperature),
                    "humidity": make_float_safe(current.humidity),
                    "pressure": make_float_safe(current.pressure),
                    "timestamp": make_float_safe(current.ts),
                },
                "model_output": {
                    "predicted_temperature": make_float_safe(pred_next)
                }
            }

            # Update local telemetry server data
            global _latest_prediction_payload, _prediction_history
            with _http_server_lock:
                _latest_prediction_payload = payload
                _prediction_history.append(payload)
                if len(_prediction_history) > 100:
                    _prediction_history.pop(0)

            # Attempt posting prediction
            success = post_prediction(api_url, payload)
            if success:
                log_technical(f"Sent prediction successfully (row #{row_count})")
            else:
                log_technical("API error")

            # 7. Get next sample for training
            try:
                next_sample = sample_queue.get(timeout=CFG.serial.timeout * 5)
            except Empty:
                window.append(current)
                continue

            # 8. Train model on current window -> next_sample target
            window.append(current)
            model.train(list(window), next_sample.temperature)
            model.record_error(pred_next, next_sample.temperature)

            # 9. Update metrics
            m = model.metrics.summary()

            # 10. Log next_sample to stream + trained prediction to history
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

    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        serial_mgr.stop()
        model.stop_autosave()
        stream_logger.flush()
        history_logger.flush()
        log_technical("Stopped")


if __name__ == "__main__":
    run_headless()
