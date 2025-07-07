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
        
        # Enhanced real request settings
        self.enable_real_requests: bool = config.ENABLE_REAL_REQUESTS
        self.enable_anti_detection: bool = config.ENABLE_ANTI_DETECTION
        self.enable_proxy_rotation: bool = config.ENABLE_PROXY_ROTATION
        self.enable_user_agent_rotation: bool = config.ENABLE_USER_AGENT_ROTATION
        self.validate_real_requests: bool = config.VALIDATE_REAL_REQUESTS
        
        # New enhanced settings
        self.min_response_size: int = config.MIN_RESPONSE_SIZE
        self.max_response_time: int = config.MAX_RESPONSE_TIME
        self.enable_response_validation: bool = config.ENABLE_RESPONSE_VALIDATION
        self.enable_anti_bot_detection: bool = config.ENABLE_ANTI_BOT_DETECTION
        self.enable_request_statistics: bool = config.ENABLE_REQUEST_STATISTICS

        logger.info(
            f"Environment Manager initialized: USE_MOCK={self.use_mock}, ENV={self.environment}, "
            f"REAL_REQUESTS={self.enable_real_requests}, ANTI_DETECTION={self.enable_anti_detection}, "
            f"RESPONSE_VALIDATION={self.enable_response_validation}"
        )

    def should_use_mock_data(self) -> bool:
        """Determine if mock data should be used"""
        return self.use_mock and not self.enable_real_requests

    def should_use_real_crawler(self) -> bool:
        """Determine if real web crawling should be used"""
        return not self.use_mock or self.enable_real_requests

    def is_production_mode(self) -> bool:
        """Check if running in production mode"""
        return self.environment.lower() == "production"

    def should_validate_requests(self) -> bool:
        """Check if real requests should be validated"""
        return self.validate_real_requests and self.should_use_real_crawler()

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
            "timeout": config.REQUEST_TIMEOUT,
            "max_retries": config.MAX_RETRIES,
        }

        if self.should_use_real_crawler():
            # Production crawler settings
            base_config.update(
                {
                    "use_selenium": True,
                    "headless": True,
                    "anti_detection": self.enable_anti_detection,
                    "random_delays": True,
                    "user_agent_rotation": self.enable_user_agent_rotation,
                    "proxy_rotation": self.enable_proxy_rotation,
                    "enable_stealth": self.enable_anti_detection,
                    "respect_robots_txt": True,
                    "enable_circuit_breaker": True,
                    "enable_rate_limiting": True,
                    "enable_monitoring": True,
                    "enable_error_recovery": True,
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

    def validate_real_request_config(self) -> Dict[str, Any]:
        """Validate configuration for real requests"""
        validation_results = {
            "use_mock": self.use_mock,
            "enable_real_requests": self.enable_real_requests,
            "should_use_real_crawler": self.should_use_real_crawler(),
            "environment": self.environment,
            "anti_detection_enabled": self.enable_anti_detection,
            "proxy_rotation_enabled": self.enable_proxy_rotation,
            "user_agent_rotation_enabled": self.enable_user_agent_rotation,
            "validation_enabled": self.validate_real_requests,
            "response_validation_enabled": self.enable_response_validation,
            "anti_bot_detection_enabled": self.enable_anti_bot_detection,
            "request_statistics_enabled": self.enable_request_statistics,
            "min_response_size": self.min_response_size,
            "max_response_time": self.max_response_time,
        }
        
        logger.info(f"Real request validation: {validation_results}")
        return validation_results

    def get_real_request_config(self) -> Dict[str, Any]:
        """Get comprehensive real request configuration"""
        return {
            "use_selenium": True,
            "headless": True,
            "anti_detection": self.enable_anti_detection,
            "random_delays": True,
            "user_agent_rotation": self.enable_user_agent_rotation,
            "proxy_rotation": self.enable_proxy_rotation,
            "enable_stealth": self.enable_anti_detection,
            "respect_robots_txt": True,
            "enable_circuit_breaker": True,
            "enable_rate_limiting": True,
            "enable_monitoring": True,
            "enable_error_recovery": True,
            "enable_response_validation": self.enable_response_validation,
            "enable_anti_bot_detection": self.enable_anti_bot_detection,
            "enable_request_statistics": self.enable_request_statistics,
            "min_response_size": self.min_response_size,
            "max_response_time": self.max_response_time,
        }

    def should_validate_response(self) -> bool:
        """Check if response validation should be performed"""
        return self.enable_response_validation and self.should_use_real_crawler()

    def should_detect_anti_bot(self) -> bool:
        """Check if anti-bot detection should be performed"""
        return self.enable_anti_bot_detection and self.should_use_real_crawler()

    def should_track_statistics(self) -> bool:
        """Check if request statistics should be tracked"""
        return self.enable_request_statistics and self.should_use_real_crawler()


# Global instance
env_manager: EnvironmentManager = EnvironmentManager()
