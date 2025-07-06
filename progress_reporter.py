from __future__ import annotations

from typing import Callable, List


class ProgressReporter:
    """Unified progress reporting for GUI, API, and CLI."""

    def __init__(self) -> None:
        """
        Initialize a new ProgressReporter with an empty list of callback listeners.
        """
        self._callbacks: List[Callable[[str], None]] = []

    def add_listener(self, callback: Callable[[str], None]) -> None:
        """
        Registers a new callback to receive progress messages if it is not already registered.
        
        Parameters:
            callback (Callable[[str], None]): A function that accepts a string message to handle progress updates.
        """
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def remove_listener(self, callback: Callable[[str], None]) -> None:
        """
        Removes a previously registered callback from the list of progress listeners.
        
        If the callback is not present, no action is taken.
        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def report(self, message: str) -> None:
        """
        Notify all registered listeners with the given progress message.
        
        Each listener callback receives the message string. Exceptions raised by individual listeners are suppressed to ensure all callbacks are invoked.
        """
        for cb in list(self._callbacks):
            try:
                cb(message)
            except Exception:
                pass


global_progress_reporter = ProgressReporter()
