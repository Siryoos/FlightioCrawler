# monitoring.py - Complete implementation
import logging
import time
from typing import Dict, List, Optional, Any
from collections import defaultdict, deque
from datetime import datetime, timedelta
import psycopg2
import redis
import asyncio
from dataclasses import dataclass
from config import config
from error_handler import ErrorHandler

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class CrawlerMetrics:
    """Metrics for a single crawler instance"""
    domain: str
    success_count: int = 0
    error_count: int = 0
    total_requests: int = 0
    total_response_time: float = 0.0
    last_success: Optional[datetime] = None
    last_error: Optional[datetime] = None
    last_error_type: Optional[str] = None
    circuit_open: bool = False
    circuit_open_time: Optional[datetime] = None

class CrawlerMonitor:
    """Monitor crawler performance"""

    def __init__(self):
        self.metrics: Dict[str, Dict] = {}
        self.error_handler = ErrorHandler()
        try:
            self.redis = redis.Redis(host=config.REDIS.HOST, port=config.REDIS.PORT, db=config.REDIS.DB)
        except Exception:
            self.redis = None
    
    def record_request(self, domain: str, duration: float) -> None:
        """Record request metrics"""
        try:
            # Initialize domain metrics if not exists
            if domain not in self.metrics:
                self.metrics[domain] = {
                    'total_requests': 0,
                    'successful_requests': 0,
                    'failed_requests': 0,
                    'total_duration': 0,
                    'min_duration': float('inf'),
                    'max_duration': 0,
                    'last_request': None,
                    'flights_scraped': 0
                }
            
            # Get metrics
            metrics = self.metrics[domain]
            
            # Update metrics
            metrics['total_requests'] += 1
            metrics['successful_requests'] += 1
            metrics['total_duration'] += duration
            metrics['min_duration'] = min(metrics['min_duration'], duration)
            metrics['max_duration'] = max(metrics['max_duration'], duration)
            metrics['last_request'] = datetime.now().isoformat()
            
        except Exception as e:
            logger.error(f"Error recording request metrics: {e}")
    
    def record_flights(self, domain: str, count: int) -> None:
        """Record flights scraped"""
        try:
            # Initialize domain metrics if not exists
            if domain not in self.metrics:
                self.metrics[domain] = {
                    'total_requests': 0,
                    'successful_requests': 0,
                    'failed_requests': 0,
                    'total_duration': 0,
                    'min_duration': float('inf'),
                    'max_duration': 0,
                    'last_request': None,
                    'flights_scraped': 0
                }
            
            # Get metrics
            metrics = self.metrics[domain]
            
            # Update metrics
            metrics['flights_scraped'] += count
            
        except Exception as e:
            logger.error(f"Error recording flights: {e}")
    
    def get_metrics(self, domain: str) -> Dict:
        """Get metrics for domain"""
        try:
            # Get metrics
            metrics = self.metrics.get(domain, {})
            
            # Calculate averages
            if metrics.get('total_requests', 0) > 0:
                metrics['avg_duration'] = metrics['total_duration'] / metrics['total_requests']
                metrics['success_rate'] = metrics['successful_requests'] / metrics['total_requests']
            else:
                metrics['avg_duration'] = 0
                metrics['success_rate'] = 0
            
            # Get error stats
            error_stats = self.error_handler.get_error_stats(domain)
            
            return {
                'domain': domain,
                'metrics': metrics,
                'error_stats': error_stats,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return {}
    
    def get_all_metrics(self) -> Dict[str, Dict]:
        """Get metrics for all domains"""
        try:
            return {
                domain: self.get_metrics(domain)
                for domain in config.SITES.keys()
            }
            
        except Exception as e:
            logger.error(f"Error getting all metrics: {e}")
            return {}
    
    def get_health_status(self) -> Dict:
        """Get overall health status"""
        try:
            # Get all metrics
            metrics = self.get_all_metrics()
            
            # Get error stats
            error_stats = self.error_handler.get_all_error_stats()
            
            # Calculate overall success rate
            total_requests = sum(m['metrics']['total_requests'] for m in metrics.values())
            successful_requests = sum(m['metrics']['successful_requests'] for m in metrics.values())
            success_rate = successful_requests / total_requests if total_requests > 0 else 0
            
            # Check circuit breakers
            circuit_breakers = {
                domain: self.error_handler.is_circuit_open(domain)
                for domain in config.SITES.keys()
            }
            
            # Determine overall status
            status = 'healthy'
            if success_rate < 0.8:
                status = 'degraded'
            if any(circuit_breakers.values()):
                status = 'unhealthy'
            
            return {
                'status': status,
                'success_rate': success_rate,
                'total_requests': total_requests,
                'successful_requests': successful_requests,
                'circuit_breakers': circuit_breakers,
                'metrics': metrics,
                'error_stats': error_stats,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting health status: {e}")
            return {}
    
    def reset_metrics(self, domain: str) -> None:
        """Reset metrics for domain"""
        try:
            # Reset metrics
            if domain in self.metrics:
                self.metrics[domain] = {
                    'total_requests': 0,
                    'successful_requests': 0,
                    'failed_requests': 0,
                    'total_duration': 0,
                    'min_duration': float('inf'),
                    'max_duration': 0,
                    'last_request': None,
                    'flights_scraped': 0
                }
            
        except Exception as e:
            logger.error(f"Error resetting metrics: {e}")
    
    def reset_all_metrics(self) -> None:
        """Reset all metrics"""
        try:
            # Reset metrics
            self.metrics.clear()
            
        except Exception as e:
            logger.error(f"Error resetting all metrics: {e}")
    
    def clean_old_metrics(self) -> None:
        """Clean old metrics"""
        try:
            # Get current time
            now = datetime.now()
            
            # Get cleanup window
            window = timedelta(seconds=config.MONITORING['interval'])
            
            # Clean metrics
            for domain, metrics in self.metrics.items():
                if metrics['last_request']:
                    last_request = datetime.fromisoformat(metrics['last_request'])
                    if now - last_request > window:
                        self.reset_metrics(domain)
            
        except Exception as e:
            logger.error(f"Error cleaning old metrics: {e}")
    
    def get_request_timeline(self, domain: str) -> List[Dict]:
        """Get request timeline for domain"""
        try:
            # Get metrics
            metrics = self.metrics.get(domain, {})
            
            # Get last request
            last_request = metrics.get('last_request')
            
            if last_request:
                return [{
                    'timestamp': last_request,
                    'duration': metrics.get('total_duration', 0) / metrics.get('total_requests', 1),
                    'success': True
                }]
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting request timeline: {e}")
            return []
    
    def get_all_request_timelines(self) -> Dict[str, List[Dict]]:
        """Get request timelines for all domains"""
        try:
            return {
                domain: self.get_request_timeline(domain)
                for domain in config.SITES.keys()
            }
            
        except Exception as e:
            logger.error(f"Error getting all request timelines: {e}")
            return {}
    
    def get_flight_timeline(self, domain: str) -> List[Dict]:
        """Get flight timeline for domain"""
        try:
            # Get metrics
            metrics = self.metrics.get(domain, {})
            
            # Get last request
            last_request = metrics.get('last_request')
            
            if last_request:
                return [{
                    'timestamp': last_request,
                    'count': metrics.get('flights_scraped', 0)
                }]
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting flight timeline: {e}")
            return []
    
    def get_all_flight_timelines(self) -> Dict[str, List[Dict]]:
        """Get flight timelines for all domains"""
        try:
            return {
                domain: self.get_flight_timeline(domain)
                for domain in config.SITES.keys()
            }
            
        except Exception as e:
            logger.error(f"Error getting all flight timelines: {e}")
            return {}

    def setup_logging(self):
        """Configure comprehensive logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
            handlers=[
                logging.FileHandler('crawler.log', encoding='utf-8'),
                logging.FileHandler('crawler_errors.log', level=logging.ERROR, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
    
    def setup_metrics(self):
        """Initialize metrics tracking"""
        self.metrics = {
            'requests_total': defaultdict(int),
            'requests_successful': defaultdict(int),
            'requests_failed': defaultdict(int),
            'response_times': defaultdict(list),
            'flights_scraped': defaultdict(int),
            'errors_by_type': defaultdict(int),
            'last_successful_crawl': defaultdict(float)
        }
        
        self.error_history = deque(maxlen=1000)
    
    def log_request(self, domain: str, success: bool, response_time: float, error: str = None):
        """Log request metrics"""
        self.metrics['requests_total'][domain] += 1
        
        if success:
            self.metrics['requests_successful'][domain] += 1
            self.metrics['last_successful_crawl'][domain] = time.time()
        else:
            self.metrics['requests_failed'][domain] += 1
            if error:
                self.metrics['errors_by_type'][error] += 1
                self.error_history.append({
                    'domain': domain,
                    'error': error,
                    'timestamp': time.time()
                })
        
        self.metrics['response_times'][domain].append(response_time)
        
        # Keep only recent response times (last 100)
        if len(self.metrics['response_times'][domain]) > 100:
            self.metrics['response_times'][domain] = self.metrics['response_times'][domain][-100:]
    
    def log_flights_scraped(self, domain: str, count: int):
        """Log successful flight scraping"""
        self.metrics['flights_scraped'][domain] += count
        self.logger.info(f"Scraped {count} flights from {domain}")
    
    async def track_request(self, domain: str, start_time: float) -> None:
        """Track successful request"""
        metrics = self.get_metrics(domain)
        metrics.success_count += 1
        metrics.total_requests += 1
        metrics.total_response_time += time.time() - start_time
        metrics.last_success = datetime.now()
        await self.update_metrics(domain, metrics)
    
    async def track_error(self, domain: str, error: Exception) -> None:
        """Track request error"""
        metrics = self.get_metrics(domain)
        metrics.error_count += 1
        metrics.total_requests += 1
        metrics.last_error = datetime.now()
        metrics.last_error_type = type(error).__name__
        await self.update_metrics(domain, metrics)
    
    def get_metrics(self, domain: str) -> CrawlerMetrics:
        """Get metrics for a domain"""
        key = f"crawler:metrics:{domain}"
        if not self.redis:
            return CrawlerMetrics(domain=domain)

        data = self.redis.hgetall(key)
        
        if not data:
            return CrawlerMetrics(domain=domain)
        
        return CrawlerMetrics(
            domain=domain,
            success_count=int(data.get('successful_requests', 0)),
            error_count=int(data.get('failed_requests', 0)),
            total_requests=int(data.get('total_requests', 0)),
            total_response_time=float(data.get('total_response_time', 0.0)),
            last_success=self._parse_datetime(data.get('last_request_time')),
            last_error=self._parse_datetime(data.get('last_request_time')),
            last_error_type=None,
            circuit_open=bool(data.get('circuit_open', 0)),
            circuit_open_time=self._parse_datetime(data.get('last_request_time'))
        )
    
    async def update_metrics(self, domain: str, metrics: CrawlerMetrics) -> None:
        """Update metrics for a domain"""
        key = f"crawler:metrics:{domain}"
        data = {
            'total_requests': metrics.total_requests,
            'successful_requests': metrics.success_count,
            'failed_requests': metrics.error_count,
            'total_response_time': metrics.total_response_time,
            'last_request_time': self._format_datetime(metrics.last_success)
        }
        if self.redis:
            self.redis.hmset(key, data)
            self.redis.expire(key, 86400)  # 24 hours TTL
    
    def get_domain_health_status(self, domain: str) -> Dict[str, Any]:
        """Get health status for a single domain"""
        metrics = self.get_metrics(domain)
        
        if metrics.total_requests == 0:
            return {
                'status': 'unknown',
                'success_rate': 0.0,
                'avg_response_time': 0.0,
                'last_success': None,
                'last_error': None,
                'circuit_open': False
            }
        
        success_rate = (metrics.success_count / metrics.total_requests) * 100
        avg_response_time = metrics.total_response_time / metrics.total_requests
        
        return {
            'status': 'healthy' if success_rate >= 95 and not metrics.circuit_open else 'degraded',
            'success_rate': success_rate,
            'avg_response_time': avg_response_time,
            'last_success': metrics.last_success,
            'last_error': metrics.last_error,
            'circuit_open': metrics.circuit_open
        }
    
    def get_all_domain_health_status(self) -> Dict[str, Dict[str, Any]]:
        """Get health status for all domains"""
        domains = ['flytoday.ir', 'alibaba.ir', 'safarmarket.com']
        return {domain: self.get_domain_health_status(domain) for domain in domains}
    
    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string from Redis"""
        if not dt_str:
            return None
        try:
            return datetime.fromisoformat(dt_str)
        except ValueError:
            return None
    
    def _format_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        """Format datetime for Redis storage"""
        if not dt:
            return None
        return dt.isoformat()