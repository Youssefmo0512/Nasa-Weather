"""
logger.py — Thread-safe CSV logging for raw stream data and training history.
Handles file creation, header writing, buffered writes, and log rotation.
"""

import csv
import logging
import threading
from collections import deque
from pathlib import Path
from typing import Optional

# ─── Application logger ──────────────────────────────────────────────────────
_log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=_log_format)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


# ─── CSV Logger ──────────────────────────────────────────────────────────────
class CSVLogger:
    """Thread-safe, buffered CSV logger with optional row-count rotation."""

    STREAM_HEADERS = ["timestamp", "temperature", "humidity", "pressure", "raw_line"]
    HISTORY_HEADERS = [
        "timestamp", "temperature", "humidity", "pressure",
        "pred_next_temperature", "mae", "trained",
    ]

    def __init__(
        self,
        path: Path,
        headers: list[str],
        buffer_size: int = 10,
        max_rows: int = 100_000,
    ) -> None:
        self._path = path
        self._headers = headers
        self._buffer_size = buffer_size
        self._max_rows = max_rows
        self._lock = threading.Lock()
        self._buffer: deque[list] = deque()
        self._row_count = 0
        self._log = get_logger(f"CSVLogger[{path.name}]")
        self._ensure_file()

    # ── public API ──────────────────────────────────────────────────────────

    def write(self, row: list) -> None:
        """Append one row; flushes when buffer is full."""
        with self._lock:
            self._buffer.append(row)
            if len(self._buffer) >= self._buffer_size:
                self._flush_locked()

    def flush(self) -> None:
        """Force-flush remaining buffer to disk."""
        with self._lock:
            self._flush_locked()

    # ── internals ────────────────────────────────────────────────────────────

    def _ensure_file(self) -> None:
        if not self._path.exists():
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(self._headers)
            self._log.info("Created %s", self._path)
        else:
            # Count existing rows to track rotation
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._row_count = max(0, sum(1 for _ in f) - 1)  # minus header
            except Exception:
                self._row_count = 0

    def _flush_locked(self) -> None:
        if not self._buffer:
            return
        try:
            self._rotate_if_needed()
            with open(self._path, "a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                while self._buffer:
                    row = self._buffer.popleft()
                    w.writerow(row)
                    self._row_count += 1
        except Exception as exc:
            self._log.error("Failed to flush CSV: %s", exc)

    def _rotate_if_needed(self) -> None:
        if self._row_count < self._max_rows:
            return
        rotated = self._path.with_suffix(f".{self._row_count}.bak.csv")
        try:
            self._path.rename(rotated)
            self._log.info("Rotated log → %s", rotated)
            self._row_count = 0
            self._ensure_file()
        except Exception as exc:
            self._log.error("Rotation failed: %s", exc)
