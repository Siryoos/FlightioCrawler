import asyncio
import aiohttp
import time
import logging
from typing import Dict, List, Optional, Any, Callable, Tuple, Union, NamedTuple
from dataclasses import dataclass, field
from collections import defaultdict, deque
from urllib.parse import urlparse, urljoin
import json
import weakref
import gc
from concurrent.futures import ThreadPoolExecutor
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class RequestSpec:
    """Specification for a batched request"""
    url: str
    method: str = "GET"
    headers: Optional[Dict[str, str]] = None
    params: Optional[Dict[str, Any]] = None
    json_data: Optional[Dict[str, Any]] = None
    timeout: int = 30
    retries: int = 2
    priority: int = 1  # Higher = more priority
    batch_key: str = field(init=False)
    
    def __post_init__(self):
        """Generate batch key for grouping similar requests"""
        self.batch_key = self._generate_batch_key()
    
    def _generate_batch_key(self) -> str:
        """Generate a key for batching similar requests"""
        parsed = urlparse(self.url)
        domain = parsed.netloc
        path_parts = parsed.path.split('/')[:3]  # First 3 path parts
        
        # Include method and content type for batching
        content_type = ""
        if self.headers:
            content_type = self.headers.get('Content-Type', '')
        
        key_parts = [domain, self.method, '/'.join(path_parts), content_type]
        return hashlib.md5('|'.join(key_parts).encode()).hexdigest()[:8]


@dataclass
class BatchedRequest:
    """A batched request with metadata"""
    spec: RequestSpec
    future: asyncio.Future
    timestamp: float = field(default_factory=time.time)
    attempt: int = 0


@dataclass
class BatchStats:
    """Statistics for request batching"""
    total_requests: int = 0
    batched_requests: int = 0
    successful_batches: int = 0
    failed_batches: int = 0
    network_savings_percent: float = 0.0
    avg_batch_size: float = 0.0
    total_response_time: float = 0.0


class RequestBatcher:
    """Advanced request batching system for network optimization"""
    
    def __init__(
        self,
        http_session: Optional[aiohttp.ClientSession] = None,
        batch_size: int = 10,
        batch_timeout: float = 0.5,  # Wait 500ms to collect more requests
        max_concurrent_batches: int = 5,
        enable_compression: bool = True,
        enable_memory_optimization: bool = True
    ):
        self.http_session = http_session
        self._own_session = http_session is None
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.max_concurrent_batches = max_concurrent_batches
        self.enable_compression = enable_compression
        self.enable_memory_optimization = enable_memory_optimization
        
        # Batching queues grouped by batch_key
        self.request_queues: Dict[str, deque] = defaultdict(deque)
        self.batch_timers: Dict[str, asyncio.Task] = {}
        
        # Concurrency control
        self.batch_semaphore = asyncio.Semaphore(max_concurrent_batches)
        
        # Statistics
        self.stats = BatchStats()
        
        # Memory management
        self.response_cache: Dict[str, Any] = {}
        self.cache_cleanup_interval = 300  # 5 minutes
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # Thread pool for CPU-intensive operations
        self.thread_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="batch_worker")
        
        logger.info(f"RequestBatcher initialized - batch_size: {batch_size}, timeout: {batch_timeout}s")
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self._setup_session()
        if self.enable_memory_optimization:
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
    
    async def _setup_session(self):
        """Setup HTTP session if not provided"""
        if not self.http_session:
            connector = aiohttp.TCPConnector(
                limit=50,  # Higher limit for batching
                limit_per_host=20,
                ttl_dns_cache=300,
                use_dns_cache=True,
                keepalive_timeout=60,  # Longer keepalive for batching
                enable_cleanup_closed=True
            )
            
            timeout = aiohttp.ClientTimeout(total=60, connect=15)
            
            self.http_session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={
                    'User-Agent': 'FlightCrawler-Batch/1.0',
                    'Accept-Encoding': 'gzip, deflate, br' if self.enable_compression else 'identity',
                    'Connection': 'keep-alive'
                }
            )
            self._own_session = True
    
    async def add_request(self, spec: RequestSpec) -> Any:
        """Add a request to the batching system"""
        if not self.http_session:
            await self._setup_session()
        
        future = asyncio.Future()
        batched_request = BatchedRequest(spec=spec, future=future)
        
        # Add to appropriate queue
        self.request_queues[spec.batch_key].append(batched_request)
        self.stats.total_requests += 1
        
        # Start batch timer if not already running
        if spec.batch_key not in self.batch_timers:
            self.batch_timers[spec.batch_key] = asyncio.create_task(
                self._batch_timer(spec.batch_key)
            )
        
        # Check if batch is full
        if len(self.request_queues[spec.batch_key]) >= self.batch_size:
            await self._execute_batch(spec.batch_key)
        
        return await future
    
    async def _batch_timer(self, batch_key: str):
        """Timer to execute batch after timeout"""
        try:
            await asyncio.sleep(self.batch_timeout)
            if batch_key in self.request_queues and self.request_queues[batch_key]:
                await self._execute_batch(batch_key)
        except asyncio.CancelledError:
            pass  # Timer was cancelled because batch was executed
        finally:
            self.batch_timers.pop(batch_key, None)
    
    async def _execute_batch(self, batch_key: str):
        """Execute a batch of requests"""
        if batch_key not in self.request_queues or not self.request_queues[batch_key]:
            return
        
        # Cancel timer
        if batch_key in self.batch_timers:
            self.batch_timers[batch_key].cancel()
            self.batch_timers.pop(batch_key, None)
        
        # Extract requests from queue
        requests = []
        while self.request_queues[batch_key] and len(requests) < self.batch_size:
            requests.append(self.request_queues[batch_key].popleft())
        
        if not requests:
            return
        
        self.stats.batched_requests += len(requests)
        self.stats.avg_batch_size = (
            (self.stats.avg_batch_size * self.stats.successful_batches + len(requests)) / 
            (self.stats.successful_batches + 1)
        )
        
        # Execute batch with semaphore control
        async with self.batch_semaphore:
            await self._process_batch(requests)
    
    async def _process_batch(self, requests: List[BatchedRequest]):
        """Process a batch of requests concurrently"""
        start_time = time.time()
        
        try:
            # Group requests by similarity for further optimization
            grouped_requests = self._group_similar_requests(requests)
            
            # Execute grouped requests
            tasks = []
            for group in grouped_requests:
                if len(group) == 1:
                    # Single request
                    task = asyncio.create_task(self._execute_single_request(group[0]))
                else:
                    # Multiple similar requests - can be optimized
                    task = asyncio.create_task(self._execute_similar_requests(group))
                tasks.append(task)
            
            # Wait for all requests in batch
            await asyncio.gather(*tasks, return_exceptions=True)
            
            self.stats.successful_batches += 1
            
        except Exception as e:
            logger.error(f"Batch processing error: {e}")
            self.stats.failed_batches += 1
            
            # Set exceptions for all futures
            for req in requests:
                if not req.future.done():
                    req.future.set_exception(e)
        
        finally:
            batch_time = time.time() - start_time
            self.stats.total_response_time += batch_time
            
            # Calculate network savings
            individual_time_estimate = len(requests) * 0.1  # Assume 100ms per individual request
            self.stats.network_savings_percent = (
                (individual_time_estimate - batch_time) / individual_time_estimate * 100
                if individual_time_estimate > 0 else 0
            )
    
    def _group_similar_requests(self, requests: List[BatchedRequest]) -> List[List[BatchedRequest]]:
        """Group similar requests for further optimization"""
        groups = defaultdict(list)
        
        for req in requests:
            # Group by URL domain and method
            parsed = urlparse(req.spec.url)
            group_key = f"{parsed.netloc}_{req.spec.method}"
            groups[group_key].append(req)
        
        return list(groups.values())
    
    async def _execute_single_request(self, req: BatchedRequest):
        """Execute a single request"""
        try:
            result = await self._make_http_request(req.spec)
            req.future.set_result(result)
        except Exception as e:
            if req.attempt < req.spec.retries:
                req.attempt += 1
                # Retry after delay
                await asyncio.sleep(0.1 * (2 ** req.attempt))  # Exponential backoff
                await self._execute_single_request(req)
            else:
                req.future.set_exception(e)
    
    async def _execute_similar_requests(self, requests: List[BatchedRequest]):
        """Execute similar requests with optimization"""
        # For now, execute them concurrently
        # In future, could implement request combination for APIs that support it
        tasks = []
        for req in requests:
            task = asyncio.create_task(self._execute_single_request(req))
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _make_http_request(self, spec: RequestSpec) -> Any:
        """Make the actual HTTP request"""
        try:
            method = spec.method.upper()
            kwargs = {
                'timeout': aiohttp.ClientTimeout(total=spec.timeout),
                'headers': spec.headers or {}
            }
            
            if spec.params:
                kwargs['params'] = spec.params
            
            if spec.json_data:
                kwargs['json'] = spec.json_data
            
            async with getattr(self.http_session, method.lower())(spec.url, **kwargs) as response:
                content_type = response.headers.get('Content-Type', '')
                
                if 'application/json' in content_type:
                    data = await response.json()
                else:
                    data = await response.text()
                
                return {
                    'status': response.status,
                    'headers': dict(response.headers),
                    'data': data,
                    'url': str(response.url)
                }
        
        except Exception as e:
            logger.error(f"HTTP request error for {spec.url}: {e}")
            raise
    
    async def batch_get_requests(self, urls: List[str], **kwargs) -> List[Any]:
        """Convenience method for batching GET requests"""
        requests = [
            RequestSpec(url=url, method="GET", **kwargs)
            for url in urls
        ]
        
        tasks = [self.add_request(spec) for spec in requests]
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    async def batch_post_requests(self, requests_data: List[Dict[str, Any]]) -> List[Any]:
        """Convenience method for batching POST requests"""
        requests = [
            RequestSpec(
                url=data['url'],
                method="POST",
                json_data=data.get('json'),
                headers=data.get('headers'),
                **{k: v for k, v in data.items() if k not in ['url', 'json', 'headers']}
            )
            for data in requests_data
        ]
        
        tasks = [self.add_request(spec) for spec in requests]
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _periodic_cleanup(self):
        """Periodic cleanup of memory"""
        while True:
            try:
                await asyncio.sleep(self.cache_cleanup_interval)
                
                # Clean up empty queues
                empty_keys = [
                    key for key, queue in self.request_queues.items() 
                    if not queue
                ]
                for key in empty_keys:
                    del self.request_queues[key]
                
                # Clear response cache
                self.response_cache.clear()
                
                # Force garbage collection
                gc.collect()
                
                logger.debug("RequestBatcher memory cleanup completed")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get batching statistics"""
        return {
            'total_requests': self.stats.total_requests,
            'batched_requests': self.stats.batched_requests,
            'successful_batches': self.stats.successful_batches,
            'failed_batches': self.stats.failed_batches,
            'network_savings_percent': round(self.stats.network_savings_percent, 2),
            'avg_batch_size': round(self.stats.avg_batch_size, 2),
            'batch_efficiency': round(
                (self.stats.batched_requests / self.stats.total_requests * 100)
                if self.stats.total_requests > 0 else 0, 2
            ),
            'active_queues': len(self.request_queues),
            'pending_requests': sum(len(q) for q in self.request_queues.values())
        }
    
    async def flush_all_batches(self):
        """Flush all pending batches immediately"""
        batch_keys = list(self.request_queues.keys())
        tasks = [self._execute_batch(key) for key in batch_keys if self.request_queues[key]]
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def close(self):
        """Close the request batcher and cleanup resources"""
        try:
            # Flush all pending batches
            await self.flush_all_batches()
            
            # Cancel cleanup task
            if self._cleanup_task:
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except asyncio.CancelledError:
                    pass
            
            # Cancel all timers
            for timer in self.batch_timers.values():
                timer.cancel()
            
            # Close HTTP session if we own it
            if self.http_session and self._own_session:
                await self.http_session.close()
            
            # Shutdown thread pool
            self.thread_pool.shutdown(wait=False)
            
            logger.info("RequestBatcher closed successfully")
            
        except Exception as e:
            logger.error(f"Error closing RequestBatcher: {e}")


# Global request batcher instance
_request_batcher: Optional[RequestBatcher] = None


async def get_request_batcher(
    http_session: Optional[aiohttp.ClientSession] = None,
    **kwargs
) -> RequestBatcher:
    """Get or create global request batcher instance"""
    global _request_batcher
    
    if _request_batcher is None:
        _request_batcher = RequestBatcher(http_session=http_session, **kwargs)
        await _request_batcher._setup_session()
    
    return _request_batcher


async def batch_requests(requests: List[RequestSpec]) -> List[Any]:
    """Convenience function for batching requests"""
    batcher = await get_request_batcher()
    tasks = [batcher.add_request(spec) for spec in requests]
    return await asyncio.gather(*tasks, return_exceptions=True)


async def cleanup_global_batcher():
    """Cleanup global request batcher"""
    global _request_batcher
    
    if _request_batcher:
        await _request_batcher.close()
        _request_batcher = None 