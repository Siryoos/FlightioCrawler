"""Simplified wrapper exposing a unified memory monitor API."""
from __future__ import annotations

import logging

from monitoring import UnifiedMonitor
from adapters.base_adapters.enhanced_base_crawler import _resource_tracker


class UnifiedMemoryMonitor:
    def __init__(self, threshold_percent: int = 85) -> None:
        self.monitor = UnifiedMonitor()
        self.tracker = _resource_tracker
        self._logger = logging.getLogger(__name__)

    async def start(self) -> None:
        await self.monitor.start()

    async def stop(self) -> None:
        await self.monitor.stop()

    def get_metrics(self) -> dict:
        try:
            data = self.monitor.get_memory_status().get("latest_metrics", {})
        except Exception as exc:
            self._logger.exception("Error retrieving metrics: %s", exc)
            data = {}

        return {
            **data,
            "browser_count": self.tracker.browser_count,
            "context_count": self.tracker.context_count,
            "page_count": self.tracker.page_count,
        }
