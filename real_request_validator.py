"""
Real Request Validator Module

This module provides comprehensive validation for real web requests,
including response validation, anti-bot detection, and request statistics.
"""

import asyncio
import logging
import time
import aiohttp
import ssl
import os
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path

from environment_manager import env_manager, EnvironmentManager

logger = logging.getLogger(__name__)
env_manager = EnvironmentManager()


@dataclass
class ValidationResult:
    """Result of a real request validation"""
    is_valid: bool
    reason: str
    response_time: float
    response_size: int
    status_code: int
    anti_bot_detected: bool
    anti_bot_measures: List[str]
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class RequestStatistics:
    """Statistics for a real request"""
    site_name: str
    url: str
    timestamp: datetime
    duration: float
    response_size: int
    status_code: int
    success: bool
    validation_passed: bool
    anti_bot_detected: bool


# Global SSL context configuration
def create_ssl_context(verify_ssl: bool = None) -> ssl.SSLContext:
    """Create SSL context based on environment configuration"""
    if verify_ssl is None:
        verify_ssl = os.getenv("SSL_VERIFY", "true").lower() == "true"
    
    if verify_ssl:
        # Production mode - verify SSL certificates
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = True
        ssl_context.verify_mode = ssl.CERT_REQUIRED
    else:
        # Development mode - bypass SSL verification
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        # Disable warnings about unverified HTTPS requests
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    return ssl_context


class RealRequestValidator:
    """Comprehensive validator for real web requests"""

    def __init__(self):
        self.validation_history: List[ValidationResult] = []
        self.statistics_history: List[RequestStatistics] = []
        self.max_history_size = 1000
        
        # Configure SSL context based on environment
        self.ssl_context = create_ssl_context()
        logger.info(f"SSL verification: {'enabled' if self.ssl_context.verify_mode == ssl.CERT_REQUIRED else 'disabled'}")

    async def validate_request(
        self, 
        url: str, 
        site_name: str = "unknown",
        timeout: Optional[int] = None
    ) -> ValidationResult:
        """
        Validate a real request before making it
        
        Args:
            url: URL to validate
            site_name: Name of the site being crawled
            timeout: Request timeout in seconds
            
        Returns:
            ValidationResult with validation details
        """
        timeout = timeout or env_manager.max_response_time
        start_time = time.time()
        
        validation_result = ValidationResult(
            is_valid=True,
            reason="",
            response_time=0,
            response_size=0,
            status_code=0,
            anti_bot_detected=False,
            anti_bot_measures=[]
        )

        try:
            # Create connector with SSL context
            connector = aiohttp.TCPConnector(ssl=self.ssl_context)
            
            # Create session with custom headers and SSL context
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            timeout_config = aiohttp.ClientTimeout(total=timeout)
            
            async with aiohttp.ClientSession(
                connector=connector, 
                headers=headers,
                timeout=timeout_config
            ) as session:
                async with session.get(url) as response:
                    response_time = time.time() - start_time
                    content = await response.text()
                    
                    validation_result.response_time = response_time
                    validation_result.response_size = len(content)
                    validation_result.status_code = response.status

                    # Check response time
                    if response_time > env_manager.max_response_time:
                        validation_result.is_valid = False
                        validation_result.reason = f"Response time too slow: {response_time:.2f}s"

                    # Check response size
                    elif len(content) < env_manager.min_response_size:
                        validation_result.is_valid = False
                        validation_result.reason = f"Response too small: {len(content)} bytes"

                    # Check status code
                    elif response.status >= 400:
                        validation_result.is_valid = False
                        validation_result.reason = f"HTTP error: {response.status}"

                    # Anti-bot detection
                    if env_manager.should_detect_anti_bot():
                        anti_bot_result = self._detect_anti_bot_measures(content, response.status)
                        validation_result.anti_bot_detected = anti_bot_result["detected"]
                        validation_result.anti_bot_measures = anti_bot_result["measures"]

        except asyncio.TimeoutError:
            validation_result.is_valid = False
            validation_result.reason = f"Request timeout after {timeout}s"
        except ssl.SSLError as e:
            validation_result.is_valid = False
            validation_result.reason = f"SSL error: {str(e)}"
            logger.warning(f"SSL error for {url}: {e}")
        except aiohttp.ClientSSLError as e:
            validation_result.is_valid = False
            validation_result.reason = f"SSL connection error: {str(e)}"
            logger.warning(f"SSL connection error for {url}: {e}")
        except Exception as e:
            validation_result.is_valid = False
            validation_result.reason = f"Validation error: {str(e)}"
            logger.error(f"Validation error for {url}: {e}")

        # Store validation result
        self._store_validation_result(validation_result)
        
        return validation_result

    def _detect_anti_bot_measures(self, content: str, status_code: int) -> Dict[str, Any]:
        """Detect anti-bot measures in the response"""
        detection_result = {
            "detected": False,
            "measures": []
        }

        try:
            content_lower = content.lower()
            
            # Common anti-bot indicators
            anti_bot_indicators = [
                "captcha", "cloudflare", "bot detection", "security check",
                "please verify", "human verification", "access denied",
                "blocked", "suspicious activity", "rate limit", "robot check",
                "automated access", "please wait", "checking your browser"
            ]

            for indicator in anti_bot_indicators:
                if indicator in content_lower:
                    detection_result["detected"] = True
                    detection_result["measures"].append(indicator)

            # Check for suspicious response patterns
            if status_code in [403, 429, 503]:
                detection_result["detected"] = True
                detection_result["measures"].append(f"HTTP {status_code}")

            # Check for empty or very small responses
            if len(content.strip()) < 100:
                detection_result["detected"] = True
                detection_result["measures"].append("suspiciously small response")

        except Exception as e:
            logger.warning(f"Error detecting anti-bot measures: {e}")

        return detection_result

    def _store_validation_result(self, result: ValidationResult) -> None:
        """Store validation result in history"""
        self.validation_history.append(result)
        
        # Limit history size
        if len(self.validation_history) > self.max_history_size:
            self.validation_history.pop(0)

    def store_request_statistics(self, stats: RequestStatistics) -> None:
        """Store request statistics"""
        self.statistics_history.append(stats)
        
        # Limit history size
        if len(self.statistics_history) > self.max_history_size:
            self.statistics_history.pop(0)

    def get_validation_summary(self, site_name: Optional[str] = None) -> Dict[str, Any]:
        """Get validation summary for a site or all sites"""
        if site_name:
            # Filter by site name if provided
            filtered_results = [r for r in self.validation_history if hasattr(r, 'site_name') and r.site_name == site_name]
        else:
            filtered_results = self.validation_history

        if not filtered_results:
            return {"total": 0, "valid": 0, "invalid": 0, "success_rate": 0.0}

        total = len(filtered_results)
        valid = sum(1 for r in filtered_results if r.is_valid)
        invalid = total - valid
        success_rate = (valid / total) * 100 if total > 0 else 0

        return {
            "total": total,
            "valid": valid,
            "invalid": invalid,
            "success_rate": success_rate,
            "avg_response_time": sum(r.response_time for r in filtered_results) / total if total > 0 else 0,
            "avg_response_size": sum(r.response_size for r in filtered_results) / total if total > 0 else 0
        }

    def get_statistics_summary(self, site_name: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics summary for a site or all sites"""
        if site_name:
            filtered_stats = [s for s in self.statistics_history if s.site_name == site_name]
        else:
            filtered_stats = self.statistics_history

        if not filtered_stats:
            return {"total": 0, "successful": 0, "failed": 0, "success_rate": 0.0}

        total = len(filtered_stats)
        successful = sum(1 for s in filtered_stats if s.success)
        failed = total - successful
        success_rate = (successful / total) * 100 if total > 0 else 0

        return {
            "total": total,
            "successful": successful,
            "failed": failed,
            "success_rate": success_rate,
            "avg_duration": sum(s.duration for s in filtered_stats) / total if total > 0 else 0,
            "avg_response_size": sum(s.response_size for s in filtered_stats) / total if total > 0 else 0
        }

    def export_validation_history(self, filepath: str) -> None:
        """Export validation history to JSON file"""
        try:
            data = {
                "validation_history": [
                    {
                        "is_valid": r.is_valid,
                        "reason": r.reason,
                        "response_time": r.response_time,
                        "response_size": r.response_size,
                        "status_code": r.status_code,
                        "anti_bot_detected": r.anti_bot_detected,
                        "anti_bot_measures": r.anti_bot_measures,
                        "timestamp": r.timestamp.isoformat()
                    }
                    for r in self.validation_history
                ],
                "statistics_history": [
                    {
                        "site_name": s.site_name,
                        "url": s.url,
                        "timestamp": s.timestamp.isoformat(),
                        "duration": s.duration,
                        "response_size": s.response_size,
                        "status_code": s.status_code,
                        "success": s.success,
                        "validation_passed": s.validation_passed,
                        "anti_bot_detected": s.anti_bot_detected
                    }
                    for s in self.statistics_history
                ]
            }
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
                
            logger.info(f"Validation history exported to {filepath}")
            
        except Exception as e:
            logger.error(f"Error exporting validation history: {e}")

    def clear_history(self) -> None:
        """Clear validation and statistics history"""
        self.validation_history.clear()
        self.statistics_history.clear()
        logger.info("Validation and statistics history cleared")


# Global instance
real_request_validator = RealRequestValidator() 