"""Simplified wrapper exposing a unified memory monitor API."""
from __future__ import annotations

from typing import Optional

from monitoring.production_memory_monitor import ProductionMemoryMonitor
from adapters.base_adapters.enhanced_base_crawler import _resource_tracker


class UnifiedMemoryMonitor:
    def __init__(self, threshold_percent: int = 85) -> None:
        self.production_monitor = ProductionMemoryMonitor(threshold_percent=threshold_percent)
        self.tracker = _resource_tracker

    async def start(self) -> None:
        await self.production_monitor.start()

    async def stop(self) -> None:
        await self.production_monitor.stop()

    def get_metrics(self) -> dict:
        data = self.production_monitor.metrics[-1] if self.production_monitor.metrics else {}
        return {
            **data,
            "browser_count": self.tracker.browser_count,
            "context_count": self.tracker.context_count,
            "page_count": self.tracker.page_count,
        }
