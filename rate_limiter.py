import asyncio
import random
import time
from typing import Dict, List, Optional
from collections import defaultdict, deque
import requests
from urllib.robotparser import RobotFileParser
import redis
from datetime import datetime, timedelta

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
    
    def __init__(self, redis_client: redis.Redis, max_requests: int = 10, period: int = 60):
        self.redis = redis_client
        self.max_requests = max_requests
        self.period = period
    
    def _get_key(self, domain: str) -> str:
        """Generate Redis key for rate limiting"""
        return f"rate_limit:{domain}:{int(time.time() / self.period)}"
    
    async def check_rate_limit(self, domain: str) -> bool:
        """Check if request is allowed under rate limit"""
        key = self._get_key(domain)
        current = self.redis.get(key)
        
        if current is None:
            # First request in this period
            self.redis.setex(key, self.period, 1)
            return True
        
        current = int(current)
        if current >= self.max_requests:
            return False
        
        # Increment counter
        self.redis.incr(key)
        return True
    
    async def get_wait_time(self, domain: str) -> Optional[int]:
        """Get time to wait before next request"""
        key = self._get_key(domain)
        current = self.redis.get(key)
        
        if current is None:
            return 0
        
        current = int(current)
        if current >= self.max_requests:
            # Calculate time until next period
            now = int(time.time())
            next_period = ((now // self.period) + 1) * self.period
            return next_period - now
        
        return 0
    
    def get_metrics(self, domain: str) -> Dict:
        """Get rate limiting metrics"""
        key = self._get_key(domain)
        current = self.redis.get(key)
        
        return {
            "domain": domain,
            "current_requests": int(current) if current else 0,
            "max_requests": self.max_requests,
            "period_seconds": self.period,
            "remaining_requests": max(0, self.max_requests - (int(current) if current else 0)),
            "reset_time": datetime.now() + timedelta(seconds=self.period)
        } 