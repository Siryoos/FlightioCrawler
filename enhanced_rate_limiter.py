#!/usr/bin/env python3
"""
Enhanced Rate Limiter for FlightioCrawler
Implements intelligent rate limiting with database integration and per-site configurations
"""

import time
import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from collections import defaultdict, deque
import threading
from urllib.parse import urlparse

# Redis for distributed rate limiting
import redis
import psycopg2
from psycopg2.extras import RealDictCursor

# Environment
import os
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class RateLimitRule:
    """Rate limiting rule for a specific site"""
    site_id: str
    site_name: str
    requests_per_minute: int
    requests_per_hour: int
    delay_seconds: float
    burst_limit: int
    cooldown_seconds: int
    active: bool = True

class RateLimitStatus:
    """Status of rate limiting for a site"""
    def __init__(self, site_id: str):
        self.site_id = site_id
        self.requests_made = 0
        self.last_request_time = 0
        self.requests_in_window = deque()
        self.requests_in_hour = deque()
        self.blocked_until = 0
        self.consecutive_errors = 0
        self.total_requests = 0
        self.total_blocked = 0
        self.lock = threading.Lock()

class EnhancedRateLimiter:
    """Enhanced rate limiter with database integration and intelligent throttling"""
    
    def __init__(self, 
                 redis_host: str = 'localhost',
                 redis_port: int = 6379,
                 redis_db: int = 0,
                 db_host: str = 'localhost',
                 db_port: int = 5432,
                 db_name: str = 'flight_data',
                 db_user: str = 'crawler',
                 db_password: str = 'secure_password'):
        
        self.redis_client = None
        self.db_conn = None
        self.site_rules: Dict[str, RateLimitRule] = {}
        self.site_status: Dict[str, RateLimitStatus] = {}
        self.global_lock = threading.Lock()
        
        # Database connection parameters
        self.db_params = {
            'host': db_host,
            'port': db_port,
            'database': db_name,
            'user': db_user,
            'password': db_password
        }
        
        # Initialize connections
        self._setup_redis(redis_host, redis_port, redis_db)
        self._setup_database()
        self._load_site_rules()
        
        logger.info("Enhanced Rate Limiter initialized")
    
    def _setup_redis(self, host: str, port: int, db: int):
        """Setup Redis connection for distributed rate limiting"""
        try:
            self.redis_client = redis.Redis(
                host=host,
                port=port,
                db=db,
                decode_responses=True
            )
            self.redis_client.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Using local rate limiting.")
            self.redis_client = None
    
    def _setup_database(self):
        """Setup database connection"""
        try:
            self.db_conn = psycopg2.connect(**self.db_params)
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            self.db_conn = None
    
    def _load_site_rules(self):
        """Load rate limiting rules from database"""
        if not self.db_conn:
            self._load_default_rules()
            return
        
        try:
            with self.db_conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT 
                        platform_code,
                        platform_name,
                        rate_limit_config,
                        is_active
                    FROM crawler.platforms
                    WHERE is_active = true
                """)
                
                rows = cursor.fetchall()
                
                for row in rows:
                    platform_code = row['platform_code']
                    platform_name = row['platform_name']
                    rate_config = row['rate_limit_config'] or {}
                    is_active = row['is_active']
                    
                    # Extract rate limiting parameters
                    requests_per_minute = rate_config.get('requests_per_minute', 10)
                    delay_seconds = rate_config.get('delay_seconds', 6)
                    requests_per_hour = rate_config.get('requests_per_hour', requests_per_minute * 60)
                    burst_limit = rate_config.get('burst_limit', requests_per_minute * 2)
                    cooldown_seconds = rate_config.get('cooldown_seconds', 300)  # 5 minutes
                    
                    rule = RateLimitRule(
                        site_id=platform_code,
                        site_name=platform_name,
                        requests_per_minute=requests_per_minute,
                        requests_per_hour=requests_per_hour,
                        delay_seconds=delay_seconds,
                        burst_limit=burst_limit,
                        cooldown_seconds=cooldown_seconds,
                        active=is_active
                    )
                    
                    self.site_rules[platform_code] = rule
                    self.site_status[platform_code] = RateLimitStatus(platform_code)
                    
                    logger.info(f"Loaded rate limit rule for {platform_name}: {requests_per_minute} req/min")
                
        except Exception as e:
            logger.error(f"Failed to load site rules from database: {e}")
            self._load_default_rules()
    
    def _load_default_rules(self):
        """Load default rate limiting rules"""
        default_rules = [
            ('alibaba', 'Alibaba', 10, 6),
            ('flytoday', 'FlyToday', 15, 4),
            ('snapptrip', 'SnappTrip', 12, 5),
            ('safarmarket', 'Safarmarket', 10, 6),
            ('mz724', 'MZ724', 8, 7),
            ('iran_air', 'Iran Air', 20, 3),
            ('mahan_air', 'Mahan Air', 15, 4),
            ('parto_crs', 'Parto CRS', 8, 7),
            ('parto_ticket', 'Parto Ticket', 8, 7),
            ('book_charter', 'Book Charter', 10, 6),
            ('book_charter_724', 'Book Charter 724', 8, 7),
            ('flightio', 'Flightio', 12, 5),
        ]
        
        for site_id, site_name, rpm, delay in default_rules:
            rule = RateLimitRule(
                site_id=site_id,
                site_name=site_name,
                requests_per_minute=rpm,
                requests_per_hour=rpm * 60,
                delay_seconds=delay,
                burst_limit=rpm * 2,
                cooldown_seconds=300,
                active=True
            )
            self.site_rules[site_id] = rule
            self.site_status[site_id] = RateLimitStatus(site_id)
            
        logger.info(f"Loaded {len(default_rules)} default rate limit rules")
    
    def get_site_id_from_url(self, url: str) -> str:
        """Extract site ID from URL"""
        domain = urlparse(url).netloc.lower()
        
        # Map domains to site IDs
        domain_mapping = {
            'alibaba.ir': 'alibaba',
            'www.alibaba.ir': 'alibaba',
            'flytoday.ir': 'flytoday',
            'www.flytoday.ir': 'flytoday',
            'snapptrip.com': 'snapptrip',
            'www.snapptrip.com': 'snapptrip',
            'safarmarket.com': 'safarmarket',
            'www.safarmarket.com': 'safarmarket',
            'mz724.com': 'mz724',
            'www.mz724.com': 'mz724',
            'iranair.com': 'iran_air',
            'www.iranair.com': 'iran_air',
            'mahan.aero': 'mahan_air',
            'www.mahan.aero': 'mahan_air',
            'crs.parto.ir': 'parto_crs',
            'ticket.parto.ir': 'parto_ticket',
            'bookcharter.ir': 'book_charter',
            'www.bookcharter.ir': 'book_charter',
            '724.bookcharter.ir': 'book_charter_724',
            'flightio.com': 'flightio',
            'www.flightio.com': 'flightio',
        }
        
        return domain_mapping.get(domain, 'unknown')
    
    def can_make_request(self, site_id: str) -> Tuple[bool, str]:
        """Check if a request can be made to the site"""
        if site_id not in self.site_rules:
            return True, "No rate limit rule found"
        
        rule = self.site_rules[site_id]
        status = self.site_status[site_id]
        
        if not rule.active:
            return False, "Site is inactive"
        
        current_time = time.time()
        
        with status.lock:
            # Check if site is in cooldown
            if current_time < status.blocked_until:
                remaining = int(status.blocked_until - current_time)
                return False, f"Site blocked for {remaining} seconds"
            
            # Clean old requests from minute window
            while (status.requests_in_window and 
                   current_time - status.requests_in_window[0] > 60):
                status.requests_in_window.popleft()
            
            # Clean old requests from hour window
            while (status.requests_in_hour and 
                   current_time - status.requests_in_hour[0] > 3600):
                status.requests_in_hour.popleft()
            
            # Check minute limit
            if len(status.requests_in_window) >= rule.requests_per_minute:
                return False, f"Rate limit exceeded: {rule.requests_per_minute} requests/minute"
            
            # Check hour limit
            if len(status.requests_in_hour) >= rule.requests_per_hour:
                return False, f"Rate limit exceeded: {rule.requests_per_hour} requests/hour"
            
            # Check minimum delay
            if (status.last_request_time > 0 and 
                current_time - status.last_request_time < rule.delay_seconds):
                remaining = rule.delay_seconds - (current_time - status.last_request_time)
                return False, f"Minimum delay not met: wait {remaining:.1f} seconds"
            
            return True, "OK"
    
    def record_request(self, site_id: str, success: bool = True):
        """Record a request made to the site"""
        if site_id not in self.site_rules:
            return
        
        status = self.site_status[site_id]
        current_time = time.time()
        
        with status.lock:
            # Record request
            status.requests_made += 1
            status.total_requests += 1
            status.last_request_time = current_time
            status.requests_in_window.append(current_time)
            status.requests_in_hour.append(current_time)
            
            # Handle success/failure
            if success:
                status.consecutive_errors = 0
            else:
                status.consecutive_errors += 1
                
                # Apply exponential backoff for consecutive errors
                if status.consecutive_errors >= 3:
                    rule = self.site_rules[site_id]
                    backoff_time = min(rule.cooldown_seconds * (2 ** (status.consecutive_errors - 3)), 1800)  # Max 30 minutes
                    status.blocked_until = current_time + backoff_time
                    logger.warning(f"Site {site_id} blocked for {backoff_time} seconds due to {status.consecutive_errors} consecutive errors")
            
            # Update Redis if available
            if self.redis_client:
                try:
                    key = f"rate_limit:{site_id}"
                    self.redis_client.hset(key, mapping={
                        'requests_made': status.requests_made,
                        'last_request_time': status.last_request_time,
                        'consecutive_errors': status.consecutive_errors,
                        'blocked_until': status.blocked_until
                    })
                    self.redis_client.expire(key, 3600)  # 1 hour TTL
                except Exception as e:
                    logger.warning(f"Failed to update Redis: {e}")
    
    def wait_for_rate_limit(self, site_id: str) -> float:
        """Wait for rate limit to allow request"""
        if site_id not in self.site_rules:
            return 0.0
        
        rule = self.site_rules[site_id]
        status = self.site_status[site_id]
        
        can_request, reason = self.can_make_request(site_id)
        if can_request:
            return 0.0
        
        # Calculate wait time
        current_time = time.time()
        wait_time = 0.0
        
        with status.lock:
            # Wait for cooldown
            if current_time < status.blocked_until:
                wait_time = status.blocked_until - current_time
            # Wait for minimum delay
            elif (status.last_request_time > 0 and 
                  current_time - status.last_request_time < rule.delay_seconds):
                wait_time = rule.delay_seconds - (current_time - status.last_request_time)
            # Wait for minute window
            elif status.requests_in_window and len(status.requests_in_window) >= rule.requests_per_minute:
                oldest_request = status.requests_in_window[0]
                wait_time = 60 - (current_time - oldest_request)
            
            wait_time = max(0, wait_time)
            
            if wait_time > 0:
                logger.info(f"Waiting {wait_time:.1f} seconds for rate limit on {site_id}")
                time.sleep(wait_time)
        
        return wait_time
    
    async def async_wait_for_rate_limit(self, site_id: str) -> float:
        """Async version of wait_for_rate_limit"""
        if site_id not in self.site_rules:
            return 0.0
        
        rule = self.site_rules[site_id]
        status = self.site_status[site_id]
        
        can_request, reason = self.can_make_request(site_id)
        if can_request:
            return 0.0
        
        # Calculate wait time
        current_time = time.time()
        wait_time = 0.0
        
        with status.lock:
            # Wait for cooldown
            if current_time < status.blocked_until:
                wait_time = status.blocked_until - current_time
            # Wait for minimum delay
            elif (status.last_request_time > 0 and 
                  current_time - status.last_request_time < rule.delay_seconds):
                wait_time = rule.delay_seconds - (current_time - status.last_request_time)
            # Wait for minute window
            elif status.requests_in_window and len(status.requests_in_window) >= rule.requests_per_minute:
                oldest_request = status.requests_in_window[0]
                wait_time = 60 - (current_time - oldest_request)
            
            wait_time = max(0, wait_time)
            
            if wait_time > 0:
                logger.info(f"Waiting {wait_time:.1f} seconds for rate limit on {site_id}")
                await asyncio.sleep(wait_time)
        
        return wait_time
    
    def get_rate_limit_info(self, site_id: str) -> Dict[str, Any]:
        """Get rate limit information for a site"""
        if site_id not in self.site_rules:
            return {"error": "Site not found"}
        
        rule = self.site_rules[site_id]
        status = self.site_status[site_id]
        current_time = time.time()
        
        with status.lock:
            # Clean old requests
            while (status.requests_in_window and 
                   current_time - status.requests_in_window[0] > 60):
                status.requests_in_window.popleft()
            
            while (status.requests_in_hour and 
                   current_time - status.requests_in_hour[0] > 3600):
                status.requests_in_hour.popleft()
            
            info = {
                'site_id': site_id,
                'site_name': rule.site_name,
                'active': rule.active,
                'limits': {
                    'requests_per_minute': rule.requests_per_minute,
                    'requests_per_hour': rule.requests_per_hour,
                    'delay_seconds': rule.delay_seconds,
                    'burst_limit': rule.burst_limit,
                    'cooldown_seconds': rule.cooldown_seconds
                },
                'current_usage': {
                    'requests_in_minute': len(status.requests_in_window),
                    'requests_in_hour': len(status.requests_in_hour),
                    'last_request_time': status.last_request_time,
                    'consecutive_errors': status.consecutive_errors,
                    'blocked_until': status.blocked_until,
                    'total_requests': status.total_requests,
                    'total_blocked': status.total_blocked
                },
                'can_make_request': self.can_make_request(site_id)
            }
            
            return info
    
    def get_all_rate_limit_info(self) -> Dict[str, Any]:
        """Get rate limit information for all sites"""
        return {
            site_id: self.get_rate_limit_info(site_id)
            for site_id in self.site_rules.keys()
        }
    
    def update_site_rule(self, site_id: str, **kwargs):
        """Update rate limit rule for a site"""
        if site_id not in self.site_rules:
            return False
        
        rule = self.site_rules[site_id]
        for key, value in kwargs.items():
            if hasattr(rule, key):
                setattr(rule, key, value)
        
        logger.info(f"Updated rate limit rule for {site_id}: {kwargs}")
        return True
    
    def reset_site_status(self, site_id: str):
        """Reset rate limit status for a site"""
        if site_id in self.site_status:
            with self.site_status[site_id].lock:
                status = self.site_status[site_id]
                status.requests_in_window.clear()
                status.requests_in_hour.clear()
                status.consecutive_errors = 0
                status.blocked_until = 0
                
                logger.info(f"Reset rate limit status for {site_id}")
    
    def cleanup(self):
        """Clean up resources"""
        if self.redis_client:
            self.redis_client.close()
        if self.db_conn:
            self.db_conn.close()

# Context manager for rate limiting
class RateLimitedRequest:
    """Context manager for rate-limited requests"""
    
    def __init__(self, rate_limiter: EnhancedRateLimiter, url: str):
        self.rate_limiter = rate_limiter
        self.url = url
        self.site_id = rate_limiter.get_site_id_from_url(url)
        self.start_time = None
        self.success = False
    
    def __enter__(self):
        self.start_time = time.time()
        self.rate_limiter.wait_for_rate_limit(self.site_id)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.success = exc_type is None
        self.rate_limiter.record_request(self.site_id, self.success)
        
        elapsed = time.time() - self.start_time
        logger.info(f"Request to {self.url} ({'success' if self.success else 'failed'}) took {elapsed:.2f}s")

# Example usage
async def test_rate_limiter():
    """Test the rate limiter"""
    limiter = EnhancedRateLimiter()
    
    # Test URLs
    test_urls = [
        'https://www.alibaba.ir',
        'https://www.flytoday.ir',
        'https://www.safarmarket.com'
    ]
    
    print("Rate Limiter Status:")
    print(json.dumps(limiter.get_all_rate_limit_info(), indent=2, default=str))
    
    # Test rate limiting
    for url in test_urls:
        site_id = limiter.get_site_id_from_url(url)
        print(f"\nTesting {url} (site_id: {site_id})")
        
        with RateLimitedRequest(limiter, url) as request:
            # Simulate request
            await asyncio.sleep(0.1)
            print(f"Made request to {url}")
    
    # Show final status
    print("\nFinal Status:")
    print(json.dumps(limiter.get_all_rate_limit_info(), indent=2, default=str))
    
    limiter.cleanup()

if __name__ == "__main__":
    asyncio.run(test_rate_limiter()) 