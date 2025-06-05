import asyncio
import random
import time
from typing import Dict, List, Optional
from collections import defaultdict, deque
import requests
from urllib.robotparser import RobotFileParser
import redis
from datetime import datetime, timedelta
import logging
from redis import Redis

from config import config

# Configure logging
logger = logging.getLogger(__name__)

class RespectfulRateLimiter:
    """Implements respectful rate limiting and anti-bot evasion"""
    
    def __init__(self):
        self.domain_delays = {
            'flytoday.ir': (3, 6),      # 3-6 seconds between requests
            'alibaba.ir': (2, 4),       # 2-4 seconds
            'safarmarket.com': (2, 5),  # 2-5 seconds
            'default': (1, 3)
        }
        
        self.last_request_time = defaultdict(float)
        self.request_counts = defaultdict(lambda: deque(maxlen=100))
        self.robots_cache = {}
        self.blocked_domains = set()
    
    async def wait_for_domain(self, domain: str):
        """Wait appropriate time before requesting from domain"""
        if domain in self.blocked_domains:
            raise Exception(f"Domain {domain} is temporarily blocked")
        
        min_delay, max_delay = self.domain_delays.get(domain, self.domain_delays['default'])
        
        # Calculate delay since last request
        elapsed = time.time() - self.last_request_time[domain]
        base_delay = random.uniform(min_delay, max_delay)
        
        # Add extra delay if we've been making frequent requests
        recent_requests = len([t for t in self.request_counts[domain] 
                             if time.time() - t < 300])  # Last 5 minutes
        
        if recent_requests > 20:
            base_delay *= 2  # Double delay for frequent requests
        
        if elapsed < base_delay:
            await asyncio.sleep(base_delay - elapsed)
        
        # Record this request
        self.last_request_time[domain] = time.time()
        self.request_counts[domain].append(time.time())
    
    def check_robots_txt(self, domain: str, path: str = "/", user_agent: str = "*") -> bool:
        """Check if path is allowed by robots.txt"""
        if domain not in self.robots_cache:
            try:
                rp = RobotFileParser()
                rp.set_url(f"https://{domain}/robots.txt")
                rp.read()
                self.robots_cache[domain] = rp
            except:
                # If robots.txt not accessible, assume allowed
                return True
        
        return self.robots_cache[domain].can_fetch(user_agent, path)
    
    def handle_rate_limit_response(self, domain: str, status_code: int):
        """Handle rate limiting responses"""
        if status_code in [429, 503, 504]:
            # Temporarily block domain
            self.blocked_domains.add(domain)
            
            # Remove block after delay
            asyncio.create_task(self.unblock_domain_later(domain, 300))  # 5 minutes
    
    async def unblock_domain_later(self, domain: str, delay: int):
        """Remove domain from blocked list after delay"""
        await asyncio.sleep(delay)
        self.blocked_domains.discard(domain)

class ProxyRotator:
    """Manages proxy rotation for distributed requests"""
    
    def __init__(self, proxy_list: List[str] = None):
        self.proxies = proxy_list or []
        self.current_proxy_index = 0
        self.proxy_failures = defaultdict(int)
        self.max_failures = 3
    
    def get_next_proxy(self) -> Dict[str, str]:
        """Get next available proxy"""
        if not self.proxies:
            return {}
        
        # Find next working proxy
        attempts = 0
        while attempts < len(self.proxies):
            proxy = self.proxies[self.current_proxy_index]
            
            if self.proxy_failures[proxy] < self.max_failures:
                self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
                return {
                    'http': f'http://{proxy}',
                    'https': f'https://{proxy}'
                }
            
            self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
            attempts += 1
        
        # All proxies failed, reset failures and try again
        self.proxy_failures.clear()
        return self.get_next_proxy()
    
    def report_proxy_failure(self, proxy: str):
        """Report proxy failure"""
        self.proxy_failures[proxy] += 1

class RateLimiter:
    """Rate limiter for crawler requests"""
    
    def __init__(self):
        # Initialize Redis
        redis_cfg = config.REDIS
        redis_url = f"redis://{redis_cfg.HOST}:{redis_cfg.PORT}/{redis_cfg.DB}"
        if redis_cfg.PASSWORD:
            redis_url = (
                f"redis://:{redis_cfg.PASSWORD}@{redis_cfg.HOST}:{redis_cfg.PORT}/"
                f"{redis_cfg.DB}"
            )
        try:
            self.redis = Redis.from_url(redis_url)
        except Exception:
            self.redis = Redis.from_url("redis://localhost:6379/0")
    
    def check_rate_limit(self, domain: str) -> bool:
        """Check if request is allowed"""
        try:
            # Get rate limit settings
            rate_limit = config.SITES[domain]['rate_limit']
            rate_period = config.SITES[domain]['rate_period']
            
            # Get current count
            key = f"rate_limit:{domain}"
            count = int(self.redis.get(key) or 0)
            
            # Check if limit exceeded
            if count >= rate_limit:
                return False
            
            # Increment count
            pipe = self.redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, rate_period)
            pipe.execute()
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return True
    
    def get_wait_time(self, domain: str) -> int:
        """Get time to wait before next request"""
        try:
            # Get key TTL
            key = f"rate_limit:{domain}"
            ttl = self.redis.ttl(key)
            
            return max(0, ttl)
            
        except Exception as e:
            logger.error(f"Error getting wait time: {e}")
            return 0
    
    def reset_rate_limit(self, domain: str) -> None:
        """Reset rate limit for domain"""
        try:
            # Delete key
            key = f"rate_limit:{domain}"
            self.redis.delete(key)
            
        except Exception as e:
            logger.error(f"Error resetting rate limit: {e}")
    
    def get_rate_limit_stats(self, domain: str) -> Dict:
        """Get rate limit statistics"""
        try:
            # Get rate limit settings
            rate_limit = config.SITES[domain]['rate_limit']
            rate_period = config.SITES[domain]['rate_period']
            
            # Get current count
            key = f"rate_limit:{domain}"
            count = int(self.redis.get(key) or 0)
            
            # Get TTL
            ttl = self.redis.ttl(key)
            
            return {
                'domain': domain,
                'current_count': count,
                'max_requests': rate_limit,
                'period_seconds': rate_period,
                'time_to_reset': ttl
            }
            
        except Exception as e:
            logger.error(f"Error getting rate limit stats: {e}")
            return {}
    
    def get_all_rate_limit_stats(self) -> Dict[str, Dict]:
        """Get rate limit statistics for all domains"""
        try:
            return {
                domain: self.get_rate_limit_stats(domain)
                for domain in config.SITES.keys()
            }
            
        except Exception as e:
            logger.error(f"Error getting all rate limit stats: {e}")
            return {}
    
    def is_rate_limited(self, domain: str) -> bool:
        """Check if domain is rate limited"""
        try:
            # Get current count
            key = f"rate_limit:{domain}"
            count = int(self.redis.get(key) or 0)
            
            # Get rate limit
            rate_limit = config.SITES[domain]['rate_limit']
            
            return count >= rate_limit
            
        except Exception as e:
            logger.error(f"Error checking rate limit status: {e}")
            return False
    
    def get_remaining_requests(self, domain: str) -> int:
        """Get remaining requests for domain"""
        try:
            # Get current count
            key = f"rate_limit:{domain}"
            count = int(self.redis.get(key) or 0)
            
            # Get rate limit
            rate_limit = config.SITES[domain]['rate_limit']
            
            return max(0, rate_limit - count)
            
        except Exception as e:
            logger.error(f"Error getting remaining requests: {e}")
            return 0
    
    def get_reset_time(self, domain: str) -> Optional[datetime]:
        """Get time when rate limit resets"""
        try:
            # Get TTL
            key = f"rate_limit:{domain}"
            ttl = self.redis.ttl(key)
            
            if ttl > 0:
                return datetime.now() + timedelta(seconds=ttl)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting reset time: {e}")
            return None
    
    def get_all_reset_times(self) -> Dict[str, Optional[datetime]]:
        """Get reset times for all domains"""
        try:
            return {
                domain: self.get_reset_time(domain)
                for domain in config.SITES.keys()
            }
            
        except Exception as e:
            logger.error(f"Error getting all reset times: {e}")
            return {}
    
    def clear_rate_limits(self) -> None:
        """Clear all rate limits"""
        try:
            # Delete all rate limit keys
            for domain in config.SITES.keys():
                key = f"rate_limit:{domain}"
                self.redis.delete(key)
            
        except Exception as e:
            logger.error(f"Error clearing rate limits: {e}")
    
    def get_rate_limit_keys(self) -> Dict[str, str]:
        """Get rate limit keys for all domains"""
        try:
            return {
                domain: f"rate_limit:{domain}"
                for domain in config.SITES.keys()
            }
            
        except Exception as e:
            logger.error(f"Error getting rate limit keys: {e}")
            return {} 