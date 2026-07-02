"""
config.py — Centralized configuration for the Weather Station system.
All constants live here; edit this file to tune the system without touching logic.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ─── Project root ────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass
class SerialConfig:
    port: str = "COM6"
    baudrate: int = 9600
    timeout: float = 2.0
    reconnect_delay: float = 5.0
    max_reconnect_attempts: int = 10


@dataclass
class MLConfig:
    window_size: int = 5
    initial_batch_size: int = 500     # pretrain on more samples for faster convergence
    learning_rate: float = 0.05       # higher LR → predictions adapt faster
    save_every_seconds: int = 300
    model_file: Path = BASE_DIR / "models" / "online_model.joblib"
    rolling_metric_window: int = 50   # last N samples for MAE/RMSE/R²
    min_samples_for_metrics: int = 5  # don't show metrics below this count


@dataclass
class LogConfig:
    stream_log: Path = BASE_DIR / "data" / "stream_log.csv"
    history_csv: Path = BASE_DIR / "data" / "history.csv"
    app_log: Path = BASE_DIR / "logs" / "app.log"
    max_history_rows: int = 100_000   # rotate after this many rows
    write_buffer_size: int = 10       # flush every N records


@dataclass
class GUIConfig:
    plot_window: int = 80             # number of samples shown on graph
    refresh_ms: int = 1000            # GUI refresh interval
    window_title: str = "🌤  NASA Weather Station — Live Dashboard"
    dark_mode: bool = True
    temperature_axis_min: Optional[float] = 33.0  # min for Cairo summer
    temperature_axis_max: Optional[float] = 42.0  # max for Cairo summer


@dataclass
class APIConfig:
    url: str = "http://localhost/Final/Nasa_Oct/api_prediction.php"
    enabled: bool = True


@dataclass
class AppConfig:
    serial: SerialConfig = field(default_factory=SerialConfig)
    ml: MLConfig = field(default_factory=MLConfig)
    log: LogConfig = field(default_factory=LogConfig)
    gui: GUIConfig = field(default_factory=GUIConfig)
    api: APIConfig = field(default_factory=APIConfig)


# Singleton
CFG = AppConfig()

# ─── Ensure directories exist ────────────────────────────────────────────────
for _dir in (
    CFG.ml.model_file.parent,
    CFG.log.stream_log.parent,
    CFG.log.history_csv.parent,
    CFG.log.app_log.parent,
):
    _dir.mkdir(parents=True, exist_ok=True)
