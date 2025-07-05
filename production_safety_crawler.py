import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from urllib.robotparser import RobotFileParser
from datetime import datetime, timedelta
import time

from rate_limiter import RateLimiter
from error_handler import ErrorHandler
from monitoring import CrawlerMonitor
from site_crawlers import BaseSiteCrawler
from production_url_validator import ProductionURLValidator

logger = logging.getLogger(__name__)


class ProductionSafetyCrawler:
    """Enhanced safety measures for production crawling with comprehensive error handling."""

    def __init__(self, max_retries: int = 3, cooldown_period: int = 300):
        self.rate_limiters: Dict[str, RateLimiter] = {}
        self.circuit_breakers: Dict[str, ErrorHandler] = {}
        self.request_budgets: Dict[str, int] = {}
        self.monitor = CrawlerMonitor()
        self.validator = ProductionURLValidator()
        
        # Enhanced safety configuration
        self.max_retries = max_retries
        self.cooldown_period = cooldown_period
        self.site_health_status: Dict[str, Dict] = {}
        self.blocked_sites: Dict[str, datetime] = {}
        self.request_timing: Dict[str, List[float]] = {}
        
    async def _pre_crawl_check(self, site_name: str, base_url: str) -> Tuple[bool, str]:
        """Enhanced pre-crawl validation with detailed status reporting."""
        try:
            # Check if site is currently blocked
            if site_name in self.blocked_sites:
                blocked_until = self.blocked_sites[site_name]
                if datetime.now() < blocked_until:
                    remaining = (blocked_until - datetime.now()).total_seconds()
                    return False, f"Site blocked for {remaining:.0f} more seconds"
                else:
                    # Remove from blocked sites
                    del self.blocked_sites[site_name]
            
            # Validate target URLs
            validation = await self.validator.validate_target_urls()
            if not validation.get(site_name, False):
                return False, "URL validation failed"
            
            # Check site health history
            if site_name in self.site_health_status:
                health = self.site_health_status[site_name]
                if health.get('consecutive_failures', 0) >= self.max_retries:
                    last_failure = health.get('last_failure_time')
                    if last_failure and (datetime.now() - last_failure).total_seconds() < self.cooldown_period:
                        return False, "Site has consecutive failures, in cooldown period"
            
            return True, "All checks passed"
            
        except Exception as e:
            logger.error(f"Pre-crawl check failed for {site_name}: {e}")
            return False, f"Pre-crawl check error: {str(e)}"

    async def _update_site_health(self, site_name: str, success: bool, error_message: str = None):
        """Update site health tracking."""
        if site_name not in self.site_health_status:
            self.site_health_status[site_name] = {
                'consecutive_failures': 0,
                'total_requests': 0,
                'successful_requests': 0,
                'last_success_time': None,
                'last_failure_time': None,
                'last_error': None
            }
        
        health = self.site_health_status[site_name]
        health['total_requests'] += 1
        
        if success:
            health['consecutive_failures'] = 0
            health['successful_requests'] += 1
            health['last_success_time'] = datetime.now()
        else:
            health['consecutive_failures'] += 1
            health['last_failure_time'] = datetime.now()
            health['last_error'] = error_message
            
            # Block site if too many consecutive failures
            if health['consecutive_failures'] >= self.max_retries:
                block_until = datetime.now() + timedelta(seconds=self.cooldown_period)
                self.blocked_sites[site_name] = block_until
                logger.warning(f"Blocking site {site_name} until {block_until} due to consecutive failures")

    async def _track_request_timing(self, site_name: str, duration: float):
        """Track request timing for performance monitoring."""
        if site_name not in self.request_timing:
            self.request_timing[site_name] = []
        
        self.request_timing[site_name].append(duration)
        
        # Keep only last 100 requests
        if len(self.request_timing[site_name]) > 100:
            self.request_timing[site_name].pop(0)

    async def safe_crawl_with_verification(
        self, site_name: str, crawler: BaseSiteCrawler, search_params: dict
    ) -> List[Dict]:
        """Safe crawling with comprehensive verification and error handling."""
        start_time = time.time()
        base_url = getattr(crawler, "base_url", "")
        
        try:
            # Pre-crawl validation
            can_crawl, check_message = await self._pre_crawl_check(site_name, base_url)
            if not can_crawl:
                logger.warning(f"Pre-crawl validation failed for {site_name}: {check_message}")
                await self._update_site_health(site_name, False, check_message)
                return []

            # Initialize rate limiter and circuit breaker if not exists
            if site_name not in self.rate_limiters:
                self.rate_limiters[site_name] = RateLimiter()
            if site_name not in self.circuit_breakers:
                self.circuit_breakers[site_name] = ErrorHandler()

            # Rate limiting check
            if not await self.rate_limiters[site_name].check_rate_limit(site_name):
                wait_time = await self.rate_limiters[site_name].get_wait_time(site_name)
                logger.info(f"Rate limit exceeded for {site_name}, waiting {wait_time}s")
                await asyncio.sleep(wait_time)

            # Execute crawl operation
            flights = await crawler.search_flights(search_params)
            
            # Validate results
            if not flights:
                logger.warning(f"No flights returned from {site_name}")
                await self._update_site_health(site_name, False, "No flights returned")
                return []
            
            # Track successful request
            duration = time.time() - start_time
            await self._track_request_timing(site_name, duration)
            await self.monitor.track_request(site_name, start_time)
            await self._update_site_health(site_name, True)
            
            # Update request budget
            self.request_budgets[site_name] = self.request_budgets.get(site_name, 0) + 1
            
            logger.info(f"Successfully crawled {site_name}: {len(flights)} flights in {duration:.2f}s")
            return flights
            
        except Exception as exc:
            duration = time.time() - start_time
            error_message = f"Crawl failed for {site_name}: {str(exc)}"
            logger.error(error_message)
            
            # Track failed request
            await self._track_request_timing(site_name, duration)
            await self._update_site_health(site_name, False, str(exc))
            
            # Handle error through circuit breaker
            if site_name in self.circuit_breakers:
                await self.circuit_breakers[site_name].handle_error(site_name, str(exc))
            
            return []

    def get_health_status(self) -> Dict[str, Dict]:
        """Get comprehensive health status for all sites."""
        return {
            'site_health': self.site_health_status,
            'blocked_sites': {
                site: blocked_until.isoformat() 
                for site, blocked_until in self.blocked_sites.items()
            },
            'request_budgets': self.request_budgets,
            'performance_metrics': {
                site: {
                    'avg_response_time': sum(timings) / len(timings) if timings else 0,
                    'total_requests': len(timings)
                }
                for site, timings in self.request_timing.items()
            }
        }

    async def reset_site_health(self, site_name: str):
        """Reset health status for a specific site."""
        if site_name in self.site_health_status:
            del self.site_health_status[site_name]
        if site_name in self.blocked_sites:
            del self.blocked_sites[site_name]
        logger.info(f"Reset health status for {site_name}")

    async def cleanup(self):
        """Cleanup resources."""
        logger.info("Cleaning up ProductionSafetyCrawler resources")
        # Additional cleanup logic can be added here
