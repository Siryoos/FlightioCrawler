import logging
from typing import Dict

from monitoring import CrawlerMonitor

logger = logging.getLogger(__name__)

class ProductionMonitoring:
    """Enhanced monitoring for real website crawling."""

    def __init__(self):
        self.monitor = CrawlerMonitor()

    async def monitor_real_crawling_health(self) -> Dict[str, Dict]:
        """Monitor real-time crawling health per site."""
        return self.monitor.get_all_metrics()

    async def alert_on_real_data_issues(
        self, issue_type: str, site_name: str, details: Dict
    ) -> None:
        """Alert system for real crawling issues."""
        message = f"{issue_type} detected on {site_name}: {details}"
        logger.warning(message)

