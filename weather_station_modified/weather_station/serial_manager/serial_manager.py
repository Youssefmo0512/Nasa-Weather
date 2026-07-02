"""
serial_manager.py — Robust serial communication with auto-reconnect logic.

Runs in its own daemon thread. Emits SensorSample objects into a Queue.
Exposes a status string and a connected flag for the GUI.
"""

from __future__ import annotations

import threading
import time
from enum import Enum, auto
from queue import Queue
from typing import Optional

try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

from config.config import SerialConfig
from logger.logger import get_logger
from utils.utils import SensorSample, parse_serial_line

_log = get_logger("SerialManager")


class SerialStatus(str, Enum):
    CONNECTING = "Connecting…"
    CONNECTED = "Connected ✔"
    DISCONNECTED = "Disconnected ✘"
    RECONNECTING = "Reconnecting…"
    DISABLED = "Serial Disabled"  # when pyserial not installed


class SerialManager:
    """
    Manages one serial port connection.
    Thread-safe status and queue output.
    Call start() once; call stop() on shutdown.
    """

    def __init__(self, cfg: SerialConfig, queue: Queue[SensorSample]) -> None:
        self._cfg = cfg
        self._queue = queue
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._status = SerialStatus.DISCONNECTED
        self._status_lock = threading.Lock()
        self._attempt = 0

    # ── public API ───────────────────────────────────────────────────────────

    @property
    def status(self) -> SerialStatus:
        with self._status_lock:
            return self._status

    @property
    def is_connected(self) -> bool:
        return self.status == SerialStatus.CONNECTED

    def start(self) -> None:
        if not SERIAL_AVAILABLE:
            _log.warning("pyserial not installed — serial disabled.")
            self._set_status(SerialStatus.DISABLED)
            return
        self._thread = threading.Thread(
            target=self._run, name="SerialThread", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    # ── internals ────────────────────────────────────────────────────────────

    def _set_status(self, s: SerialStatus) -> None:
        with self._status_lock:
            self._status = s

    def _run(self) -> None:
        while not self._stop_event.is_set():
            ser = self._connect()
            if ser is None:
                continue
            self._set_status(SerialStatus.CONNECTED)
            self._attempt = 0
            _log.info("Serial port %s opened at %d baud.", self._cfg.port, self._cfg.baudrate)
            try:
                self._read_loop(ser)
            finally:
                try:
                    ser.close()
                except Exception:
                    pass
                _log.warning("Serial connection lost.")
                self._set_status(SerialStatus.DISCONNECTED)

        _log.info("SerialManager stopped.")

    def _connect(self) -> Optional["serial.Serial"]:
        self._attempt += 1
        if self._attempt > self._cfg.max_reconnect_attempts:
            _log.error("Max reconnect attempts reached. Giving up.")
            self._stop_event.set()
            return None

        self._set_status(
            SerialStatus.CONNECTING if self._attempt == 1 else SerialStatus.RECONNECTING
        )
        _log.info(
            "Attempting serial connection (%d/%d) on %s…",
            self._attempt,
            self._cfg.max_reconnect_attempts,
            self._cfg.port,
        )
        try:
            ser = serial.Serial(
                self._cfg.port,
                self._cfg.baudrate,
                timeout=self._cfg.timeout,
            )
            time.sleep(1.5)  # let HC-05 stabilize
            return ser
        except Exception as exc:
            _log.error("Connection failed: %s", exc)
            delay = min(self._cfg.reconnect_delay * self._attempt, 60.0)
            _log.info("Retrying in %.1fs…", delay)
            self._stop_event.wait(timeout=delay)
            return None

    def _read_loop(self, ser: "serial.Serial") -> None:
        while not self._stop_event.is_set():
            try:
                raw = ser.readline().decode("utf-8", errors="ignore")
                if not raw.strip():
                    continue
                sample = parse_serial_line(raw)
                if sample is not None:
                    self._queue.put(sample)
                else:
                    _log.debug("Discarded malformed line: %r", raw[:80])
            except Exception as exc:
                _log.error("Read error: %s", exc)
                break  # triggers reconnect in outer loop
