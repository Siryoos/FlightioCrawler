"""Simplified wrapper exposing a unified memory monitor API."""
from __future__ import annotations

from typing import Optional
import logging

from monitoring.production_memory_monitor import ProductionMemoryMonitor
from adapters.base_adapters.enhanced_base_crawler import _resource_tracker


class UnifiedMemoryMonitor:
    def __init__(self, threshold_percent: int = 85) -> None:
        self.production_monitor = ProductionMemoryMonitor(threshold_percent=threshold_percent)
        self.tracker = _resource_tracker
        self._logger = logging.getLogger(__name__)

    async def start(self) -> None:
        await self.production_monitor.start_monitoring()

    async def stop(self) -> None:
        await self.production_monitor.stop_monitoring()

    def get_metrics(self) -> dict:
        try:
            data = self.production_monitor.get_metrics()
        except AttributeError:
            try:
                data = self.production_monitor.metrics_history[-1]
            except (AttributeError, IndexError) as exc:
                self._logger.debug("No metrics available: %s", exc)
                data = {}
        except Exception as exc:
            self._logger.exception("Error retrieving metrics: %s", exc)
            data = {}

        return {
            **data,
            "browser_count": self.tracker.browser_count,
            "context_count": self.tracker.context_count,
            "page_count": self.tracker.page_count,
        }
