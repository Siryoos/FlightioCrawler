import asyncio
import time
import random
from collections import defaultdict
from redis import Redis
import logging
from typing import Dict, Optional

class AdvancedRateLimiter:
    """Advanced rate limiter with adaptive delays and platform-specific configurations"""
    
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.platform_configs = {}
        self.logger = logging.getLogger(__name__)
        
    def configure_platform(self, platform_id: str, config: dict):
        """Configure rate limiting for specific platform"""
        self.platform_configs[platform_id] = {
            'requests_per_second': config.get('requests_per_second', 1),
            'burst_limit': config.get('burst_limit', 5),
            'backoff_factor': config.get('backoff_factor', 2),
            'max_delay': config.get('max_delay', 300),
            'jitter': config.get('jitter', True),
            'use_persian_ip': config.get('use_persian_ip', False)
        }
        
    async def wait(self, platform_id: str):
        """Intelligent rate limiting with adaptive delays"""
        config = self.platform_configs.get(platform_id, {})
        
        # Check if platform is in penalty mode
        penalty_key = f"rate_limit:penalty:{platform_id}"
        penalty = await self.redis.get(penalty_key)
        
        if penalty:
            delay = min(int(penalty), config.get('max_delay', 300))
            self.logger.info(f"Platform {platform_id} in penalty mode, waiting {delay}s")
            await asyncio.sleep(delay)
            
        # Normal rate limiting
        requests_per_second = config.get('requests_per_second', 1)
        base_delay = 1.0 / requests_per_second
        
        # Add jitter to avoid synchronized requests
        if config.get('jitter', True):
            jitter_factor = random.uniform(0.5, 1.5)
            delay = base_delay * jitter_factor
        else:
            delay = base_delay
            
        # Add extra delay for Persian IPs if configured
        if config.get('use_persian_ip', False):
            delay *= 1.5  # 50% extra delay for Persian IPs
            
        await asyncio.sleep(delay)
        
    async def handle_rate_limit_exceeded(self, platform_id: str):
        """Handle rate limit exceeded scenario"""
        config = self.platform_configs.get(platform_id, {})
        
        # Get current penalty level
        penalty_key = f"rate_limit:penalty:{platform_id}"
        current_penalty = await self.redis.get(penalty_key)
        
        if current_penalty:
            new_penalty = min(int(current_penalty) * config.get('backoff_factor', 2), 
                             config.get('max_delay', 300))
        else:
            new_penalty = config.get('initial_penalty', 60)
            
        # Set penalty with expiration
        await self.redis.setex(penalty_key, new_penalty * 2, new_penalty)
        self.logger.warning(f"Rate limit exceeded for {platform_id}, new penalty: {new_penalty}s")
        
    async def handle_success(self, platform_id: str):
        """Handle successful request to potentially reduce penalties"""
        penalty_key = f"rate_limit:penalty:{platform_id}"
        current_penalty = await self.redis.get(penalty_key)
        
        if current_penalty and int(current_penalty) > 60:
            # Gradually reduce penalty for successful requests
            new_penalty = max(int(current_penalty) * 0.9, 60)
            await self.redis.setex(penalty_key, new_penalty * 2, new_penalty)
            self.logger.info(f"Reduced penalty for {platform_id} to {new_penalty}s")
            
    async def get_platform_health(self, platform_id: str) -> Dict[str, float]:
        """Get platform health metrics"""
        success_key = f"rate_limit:success:{platform_id}"
        failure_key = f"rate_limit:failure:{platform_id}"
        
        success_count = int(await self.redis.get(success_key) or 0)
        failure_count = int(await self.redis.get(failure_key) or 0)
        
        total_requests = success_count + failure_count
        if total_requests == 0:
            return {
                'success_rate': 1.0,
                'failure_rate': 0.0,
                'total_requests': 0
            }
            
        return {
            'success_rate': success_count / total_requests,
            'failure_rate': failure_count / total_requests,
            'total_requests': total_requests
        }
        
    async def reset_platform_stats(self, platform_id: str):
        """Reset platform statistics"""
        keys = [
            f"rate_limit:success:{platform_id}",
            f"rate_limit:failure:{platform_id}",
            f"rate_limit:penalty:{platform_id}"
        ]
        
        await self.redis.delete(*keys)
        self.logger.info(f"Reset statistics for platform {platform_id}")
        
    async def get_wait_time(self, platform_id: str) -> Optional[int]:
        """Get current wait time for platform"""
        penalty_key = f"rate_limit:penalty:{platform_id}"
        penalty = await self.redis.get(penalty_key)
        
        if penalty:
            return int(penalty)
            
        config = self.platform_configs.get(platform_id, {})
        return int(1.0 / config.get('requests_per_second', 1))
        
    async def check_rate_limit(self, platform_id: str) -> bool:
        """Check if platform is within rate limits"""
        penalty_key = f"rate_limit:penalty:{platform_id}"
        penalty = await self.redis.get(penalty_key)
        
        return penalty is None 