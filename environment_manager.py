"""
Environment Manager for handling Mock vs Real execution modes
"""

import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from config import config

logger = logging.getLogger(__name__)


class EnvironmentManager:
    """Manages execution environment and determines mock vs real data sources"""

    def __init__(self) -> None:
        self.use_mock: bool = config.USE_MOCK
        self.environment: str = config.ENVIRONMENT
        self.mock_data_dir: Path = Path("requests/pages")

        logger.info(
            f"Environment Manager initialized: USE_MOCK={self.use_mock}, ENV={self.environment}"
        )

    def should_use_mock_data(self) -> bool:
        """Determine if mock data should be used"""
        return self.use_mock

    def should_use_real_crawler(self) -> bool:
        """Determine if real web crawling should be used"""
        return not self.use_mock

    def get_mock_file_path(
        self, site_name: str, search_params: Dict[str, Any]
    ) -> Optional[Path]:
        """Get path to mock HTML file for given site and search parameters"""
        if not self.should_use_mock_data():
            return None

        # Generate filename based on site and parameters
        origin = search_params.get("origin", "UNK")
        destination = search_params.get("destination", "UNK")
        date = search_params.get("departure_date", "2025-01-01")

        # Look for existing mock files
        patterns = [
            f"{site_name}*{origin}*{destination}*.html",
            f"{site_name}*{origin}-{destination}*.html",
            f"www.{site_name}*{origin}*{destination}*.html",
        ]

        for pattern in patterns:
            matches = list(self.mock_data_dir.glob(pattern))
            if matches:
                logger.info(f"Found mock file for {site_name}: {matches[0]}")
                return matches[0]

        logger.warning(
            f"No mock file found for {site_name} with {origin}->{destination}"
        )
        return None

    def get_crawler_config(self, site_name: str) -> Dict[str, Any]:
        """Get crawler configuration based on environment"""
        base_config: Dict[str, Any] = {
            "use_selenium": True,
            "headless": True,
            "timeout": config.CRAWLER_TIMEOUT,
        }

        if self.should_use_real_crawler():
            # Production crawler settings
            base_config.update(
                {
                    "use_selenium": True,
                    "headless": True,
                    "anti_detection": True,
                    "random_delays": True,
                    "user_agent_rotation": True,
                }
            )
        else:
            # Mock/Test settings
            base_config.update(
                {
                    "use_selenium": False,
                    "use_mock_files": True,
                    "mock_data_dir": str(self.mock_data_dir),
                }
            )

        return base_config

    def log_execution_mode(self, site_name: str, action: str) -> None:
        """Log the execution mode for debugging"""
        mode = "REAL" if self.should_use_real_crawler() else "MOCK"
        logger.info(f"[{mode}] {site_name}: {action}")


# Global instance
env_manager: EnvironmentManager = EnvironmentManager()
