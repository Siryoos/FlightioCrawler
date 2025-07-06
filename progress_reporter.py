from __future__ import annotations

from typing import Callable, List


class ProgressReporter:
    """Unified progress reporting for GUI, API, and CLI."""

    def __init__(self) -> None:
        self._callbacks: List[Callable[[str], None]] = []

    def add_listener(self, callback: Callable[[str], None]) -> None:
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def remove_listener(self, callback: Callable[[str], None]) -> None:
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def report(self, message: str) -> None:
        for cb in list(self._callbacks):
            try:
                cb(message)
            except Exception:
                pass


global_progress_reporter = ProgressReporter()
