"""Durable JSON state file and thread-safe live hunt statistics.

The state file (.hunter_state.json) survives container restarts so the
network bootstrap and any caught instance are reused rather than recreated.

HuntStats is the in-memory mirror of the live hunt, shared with the
Telegram /status poller thread.
"""

import json
import threading
from pathlib import Path

from .config import APP_DIR
from .logging import log

STATE_FILE = APP_DIR / ".hunter_state.json"


def save_state(data):
    try:
        STATE_FILE.write_text(json.dumps(data, indent=2))
    except OSError as exc:
        log(f"could not write state file: {exc}")


def load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        return {}


class HuntStats:
    """Live hunt progress, safe for concurrent access from the /status thread."""

    def __init__(self):
        self._lock = threading.Lock()
        self._started_at = None  # monotonic seconds, set by run()
        self._attempt = 0
        self._ad = None  # short name of the AD being tried
        self._last_error = None  # human-readable last failure
        self._backoff = None  # description of current backoff, if any

    def start(self):
        import time

        with self._lock:
            self._started_at = time.monotonic()

    def record_attempt(self, ad_short):
        with self._lock:
            self._attempt += 1
            self._ad = ad_short
            self._backoff = None

    def record_result(self, launched=False, error=None, backoff=None):
        with self._lock:
            if launched:
                self._last_error = None
                self._backoff = None
            else:
                if error is not None:
                    self._last_error = error
                self._backoff = backoff

    def snapshot(self):
        import time

        with self._lock:
            uptime = None
            if self._started_at is not None:
                uptime = time.monotonic() - self._started_at
            return {
                "uptime": uptime,
                "attempts": self._attempt,
                "ad": self._ad,
                "last_error": self._last_error,
                "backoff": self._backoff,
            }
