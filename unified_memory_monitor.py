"""Simplified wrapper exposing a unified memory monitor API."""
from __future__ import annotations

from typing import Optional

from monitoring.production_memory_monitor import ProductionMemoryMonitor
from adapters.base_adapters.enhanced_base_crawler import _resource_tracker


class UnifiedMemoryMonitor:
    def __init__(self, threshold_percent: int = 85) -> None:
        """
        Initialize the UnifiedMemoryMonitor with a specified memory usage threshold.
        
        Parameters:
            threshold_percent (int): The memory usage percentage threshold for triggering monitoring actions. Defaults to 85.
        """
        self.production_monitor = ProductionMemoryMonitor(threshold_percent=threshold_percent)
        self.tracker = _resource_tracker

    async def start(self) -> None:
        """
        Asynchronously starts the underlying memory monitoring process.
        """
        await self.production_monitor.start()

    async def stop(self) -> None:
        """
        Asynchronously stops the underlying memory monitoring process.
        """
        await self.production_monitor.stop()

    def get_metrics(self) -> dict:
        """
        Return the latest memory metrics combined with current browser, context, and page counts.
        
        Returns:
            dict: A dictionary containing the most recent memory metrics (if available) and the current counts of browsers, contexts, and pages.
        """
        data = self.production_monitor.metrics[-1] if self.production_monitor.metrics else {}
        return {
            **data,
            "browser_count": self.tracker.browser_count,
            "context_count": self.tracker.context_count,
            "page_count": self.tracker.page_count,
        }
