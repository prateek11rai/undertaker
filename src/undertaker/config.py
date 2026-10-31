"""Settings shared by every command, from flags and UNDERTAKER_* env vars."""

import os
import re
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

TEMPORAL_BIN = os.environ.get("UNDERTAKER_TEMPORAL_BIN", "/opt/homebrew/bin/temporal")
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("UNDERTAKER_DATA", REPO_ROOT / ".data"))

_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def parse_duration(text: str) -> timedelta:
    """Parse '20s', '10m', '2h', '7d' or plain seconds into a timedelta.

    Args:
        text: The duration text.

    Returns:
        The duration.

    Raises:
        ValueError: If the text is not a duration.
    """
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([smhd]?)\s*", str(text))
    if not m:
        raise ValueError(f"not a duration: {text!r}")
    return timedelta(seconds=float(m.group(1)) * _UNITS[m.group(2) or "s"])


@dataclass
class Thresholds:
    """Rule thresholds."""

    quiet: timedelta = timedelta(minutes=10)
    attempts: int = 5
    poller_window: timedelta = timedelta(minutes=2)
    long_sleep: timedelta = timedelta(days=7)


@dataclass
class Settings:
    """Everything a command needs to know."""

    address: str = "127.0.0.1:7233"
    namespace: str = "default"
    model: str = "gemma4:e4b"
    ollama: str = "http://127.0.0.1:11434"
    source: Path | None = None
    allow_actions: bool = False
    no_model: bool = False
    every: timedelta = timedelta(seconds=30)
    thresholds: Thresholds = field(default_factory=Thresholds)
    data_dir: Path = DATA_DIR


DEMO_THRESHOLDS = {"quiet": "20s", "attempts": "3"}
