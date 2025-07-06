"""Unified monitoring package combining crawler metrics and production memory checks."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from prometheus_client import generate_latest

from .production_memory_monitor import ProductionMemoryMonitor

# Import CrawlerMonitor from root monitoring.py without causing circular import
from monitoring import CrawlerMonitor


class UnifiedMonitor:
    """Provide a single interface for crawler and memory monitoring."""

    def __init__(self, memory_config: Optional[str] = None) -> None:
        self.crawler_monitor = CrawlerMonitor()
        self.memory_monitor = ProductionMemoryMonitor(config_path=memory_config)

    async def start(self) -> None:
        """Start background memory monitoring."""
        await self.memory_monitor.start_monitoring()

    async def stop(self) -> None:
        """Stop background memory monitoring."""
        await self.memory_monitor.stop_monitoring()

    def record_request(
        self,
        domain: str,
        duration: float,
        success: bool = True,
        response_size: int = 0,
    ) -> None:
        """Record a crawler request."""
        self.crawler_monitor.record_request(domain, duration, success, response_size)

    def record_error(self, domain: str, error_type: str) -> None:
        """Record an error from a crawler."""
        self.crawler_monitor.record_error(domain, error_type)

    def record_flights(self, domain: str, count: int, route: str = "unknown") -> None:
        """Record flights scraped."""
        self.crawler_monitor.record_flights(domain, count, route)

    def get_crawler_metrics(self, domain: str) -> Dict[str, Any]:
        """Return metrics collected for a specific domain."""
        return self.crawler_monitor.get_metrics(domain)

    def get_memory_status(self) -> Dict[str, Any]:
        """Return the current memory monitoring status."""
        return self.memory_monitor.get_status()

    def get_prometheus_metrics(self) -> bytes:
        """Return combined Prometheus metrics for crawlers and memory."""
        return generate_latest()
