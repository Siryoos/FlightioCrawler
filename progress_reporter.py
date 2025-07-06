from __future__ import annotations

from typing import Callable, List
import threading
import logging


class ProgressReporter:
    """Unified progress reporting for GUI, API, and CLI."""

    def __init__(self) -> None:
        self._callbacks: List[Callable[[str], None]] = []
        self._lock = threading.Lock()
        self._logger = logging.getLogger(__name__)

    def add_listener(self, callback: Callable[[str], None]) -> None:
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def remove_listener(self, callback: Callable[[str], None]) -> None:
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    def report(self, message: str) -> None:
        with self._lock:
            callbacks = list(self._callbacks)
        for cb in callbacks:
            try:
                cb(message)
            except (RuntimeError, ValueError) as exc:
                self._logger.exception("Progress callback %r failed: %s", cb, exc)


global_progress_reporter = ProgressReporter()
