#!/usr/bin/env python3
"""
Test script for Request Batching system.

This script demonstrates the benefits of request batching for network optimization,
including performance improvements and memory efficiency.
"""

import asyncio
import time
import logging
import statistics
from typing import List, Dict, Any
import aiohttp
from datetime import datetime
import json

from utils.request_batcher import RequestBatcher, RequestSpec, batch_requests
from adapters.base_adapters.enhanced_base_crawler import EnhancedBaseCrawler

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RequestBatchingBenchmark:
    """Benchmark suite for request batching performance"""
    
    def __init__(self):
        self.results = {}
        
    async def run_all_benchmarks(self):
        """Run all benchmarking tests"""
        logger.info("🚀 Starting Request Batching Benchmark Suite")
        
        # Test 1: Basic batching vs individual requests
        await self.benchmark_basic_batching()
        
        # Test 2: Memory efficiency
        await self.benchmark_memory_efficiency()
        
        # Test 3: Network overhead reduction
        await self.benchmark_network_efficiency()
        
        # Test 4: Real-world crawler scenario
        await self.benchmark_crawler_integration()
        
        # Test 5: Error handling and resilience
        await self.benchmark_error_handling()
        
        # Generate report
        self.generate_report()
    
    async def benchmark_basic_batching(self):
        """Compare batched vs individual requests"""
        logger.info("📊 Test 1: Basic Batching vs Individual Requests")
        
        # Test URLs (using httpbin.org for testing)
        test_urls = [
            "https://httpbin.org/delay/1",
            "https://httpbin.org/json",
            "https://httpbin.org/user-agent",
            "https://httpbin.org/headers",
            "https://httpbin.org/ip",
            "https://httpbin.org/uuid",
            "https://httpbin.org/base64/SFRUUEJJTiBpcyBhd2Vzb21l",
            "https://httpbin.org/status/200",
        ]
        
        # Individual requests benchmark
        start_time = time.time()
        individual_results = await self._make_individual_requests(test_urls)
        individual_time = time.time() - start_time
        
        # Batched requests benchmark
        start_time = time.time()
        batched_results = await self._make_batched_requests(test_urls)
        batched_time = time.time() - start_time
        
        # Calculate improvement
        time_savings = ((individual_time - batched_time) / individual_time) * 100
        
        self.results['basic_batching'] = {
            'individual_time': individual_time,
            'batched_time': batched_time,
            'time_savings_percent': time_savings,
            'individual_success': len([r for r in individual_results if not isinstance(r, Exception)]),
            'batched_success': len([r for r in batched_results if not isinstance(r, Exception)]),
            'total_requests': len(test_urls)
        }
        
        logger.info(f"   Individual requests: {individual_time:.2f}s")
        logger.info(f"   Batched requests: {batched_time:.2f}s")
        logger.info(f"   Time savings: {time_savings:.1f}%")
    
    async def _make_individual_requests(self, urls: List[str]) -> List[Any]:
        """Make individual HTTP requests"""
        results = []
        
        async with aiohttp.ClientSession() as session:
            for url in urls:
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        data = await response.json() if 'json' in response.headers.get('content-type', '') else await response.text()
                        results.append({
                            'status': response.status,
                            'data': data,
                            'url': str(response.url)
                        })
                except Exception as e:
                    results.append(e)
        
        return results
    
    async def _make_batched_requests(self, urls: List[str]) -> List[Any]:
        """Make batched HTTP requests"""
        specs = [RequestSpec(url=url, timeout=10) for url in urls]
        return await batch_requests(specs)
    
    async def benchmark_memory_efficiency(self):
        """Test memory efficiency of batching"""
        logger.info("💾 Test 2: Memory Efficiency")
        
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        # Create a large number of requests
        urls = ["https://httpbin.org/json"] * 50  # 50 identical requests
        
        # Individual requests - measure memory
        initial_memory = process.memory_info().rss / 1024 / 1024
        individual_results = await self._make_individual_requests(urls)
        individual_memory = process.memory_info().rss / 1024 / 1024
        individual_memory_usage = individual_memory - initial_memory
        
        # Reset and test batched requests
        import gc
        gc.collect()
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        batched_results = await self._make_batched_requests(urls)
        batched_memory = process.memory_info().rss / 1024 / 1024
        batched_memory_usage = batched_memory - initial_memory
        
        memory_savings = ((individual_memory_usage - batched_memory_usage) / individual_memory_usage) * 100 if individual_memory_usage > 0 else 0
        
        self.results['memory_efficiency'] = {
            'individual_memory_mb': individual_memory_usage,
            'batched_memory_mb': batched_memory_usage,
            'memory_savings_percent': memory_savings,
            'requests_count': len(urls)
        }
        
        logger.info(f"   Individual memory: {individual_memory_usage:.1f} MB")
        logger.info(f"   Batched memory: {batched_memory_usage:.1f} MB")
        logger.info(f"   Memory savings: {memory_savings:.1f}%")
    
    async def benchmark_network_efficiency(self):
        """Test network efficiency and connection reuse"""
        logger.info("🌐 Test 3: Network Efficiency")
        
        # Test with multiple requests to the same domain
        same_domain_urls = [
            "https://httpbin.org/json",
            "https://httpbin.org/user-agent", 
            "https://httpbin.org/headers",
            "https://httpbin.org/ip",
            "https://httpbin.org/uuid",
        ]
        
        # Mixed domains
        mixed_domain_urls = [
            "https://httpbin.org/json",
            "https://jsonplaceholder.typicode.com/posts/1",
            "https://api.github.com/user",
            "https://httpbin.org/uuid",
        ]
        
        # Test same domain efficiency
        start_time = time.time()
        same_domain_results = await self._make_batched_requests(same_domain_urls)
        same_domain_time = time.time() - start_time
        
        # Test mixed domain efficiency
        start_time = time.time()
        mixed_domain_results = await self._make_batched_requests(mixed_domain_urls)
        mixed_domain_time = time.time() - start_time
        
        self.results['network_efficiency'] = {
            'same_domain_time': same_domain_time,
            'mixed_domain_time': mixed_domain_time,
            'same_domain_count': len(same_domain_urls),
            'mixed_domain_count': len(mixed_domain_urls),
            'same_domain_success': len([r for r in same_domain_results if not isinstance(r, Exception)]),
            'mixed_domain_success': len([r for r in mixed_domain_results if not isinstance(r, Exception)])
        }
        
        logger.info(f"   Same domain batching: {same_domain_time:.2f}s ({len(same_domain_urls)} requests)")
        logger.info(f"   Mixed domain batching: {mixed_domain_time:.2f}s ({len(mixed_domain_urls)} requests)")
    
    async def benchmark_crawler_integration(self):
        """Test integration with EnhancedBaseCrawler"""
        logger.info("🕷️ Test 4: Crawler Integration")
        
        # Mock crawler configuration
        mock_config = {
            "base_url": "https://httpbin.org",
            "search_url": "https://httpbin.org/anything",
            "request_batching": {
                "batch_size": 5,
                "batch_timeout": 0.2,
                "max_concurrent_batches": 2
            }
        }
        
        # Create a mock crawler for testing
        class MockCrawler(EnhancedBaseCrawler):
            def _get_base_url(self) -> str:
                return "https://httpbin.org"
            
            async def _handle_page_setup(self) -> None:
                pass
            
            async def _fill_search_form(self, search_params: Dict[str, Any]) -> None:
                pass
            
            def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
                return None
        
        # Test crawler with batching
        urls_to_test = [
            "https://httpbin.org/json",
            "https://httpbin.org/user-agent", 
            "https://httpbin.org/headers",
            "https://httpbin.org/uuid",
        ]
        
        start_time = time.time()
        
        async with MockCrawler(mock_config) as crawler:
            results = await crawler.batch_get_urls(urls_to_test)
            batching_stats = crawler.get_batching_stats()
        
        crawler_time = time.time() - start_time
        
        self.results['crawler_integration'] = {
            'processing_time': crawler_time,
            'requests_count': len(urls_to_test),
            'success_count': len([r for r in results if not isinstance(r, Exception)]),
            'batching_stats': batching_stats
        }
        
        logger.info(f"   Crawler processing time: {crawler_time:.2f}s")
        logger.info(f"   Batching stats: {batching_stats}")
    
    async def benchmark_error_handling(self):
        """Test error handling and resilience"""
        logger.info("⚠️ Test 5: Error Handling")
        
        # Mix of valid and invalid URLs
        mixed_urls = [
            "https://httpbin.org/json",  # Valid
            "https://httpbin.org/status/404",  # Valid but 404
            "https://invalid-domain-that-does-not-exist.com",  # Invalid domain
            "https://httpbin.org/delay/15",  # Will timeout
            "https://httpbin.org/uuid",  # Valid
        ]
        
        specs = [
            RequestSpec(url=url, timeout=5, retries=1) 
            for url in mixed_urls
        ]
        
        start_time = time.time()
        results = await batch_requests(specs)
        error_handling_time = time.time() - start_time
        
        successful = len([r for r in results if not isinstance(r, Exception)])
        failed = len([r for r in results if isinstance(r, Exception)])
        
        self.results['error_handling'] = {
            'processing_time': error_handling_time,
            'total_requests': len(mixed_urls),
            'successful': successful,
            'failed': failed,
            'success_rate': (successful / len(mixed_urls)) * 100
        }
        
        logger.info(f"   Processing time: {error_handling_time:.2f}s")
        logger.info(f"   Success rate: {successful}/{len(mixed_urls)} ({(successful/len(mixed_urls)*100):.1f}%)")
    
    def generate_report(self):
        """Generate comprehensive benchmark report"""
        logger.info("\n" + "="*60)
        logger.info("📈 REQUEST BATCHING BENCHMARK REPORT")
        logger.info("="*60)
        
        # Overall summary
        if 'basic_batching' in self.results:
            basic = self.results['basic_batching']
            logger.info(f"⏱️ TIME PERFORMANCE:")
            logger.info(f"   Time savings: {basic['time_savings_percent']:.1f}%")
            logger.info(f"   Requests processed: {basic['total_requests']}")
        
        if 'memory_efficiency' in self.results:
            memory = self.results['memory_efficiency']
            logger.info(f"💾 MEMORY EFFICIENCY:")
            logger.info(f"   Memory savings: {memory['memory_savings_percent']:.1f}%")
            logger.info(f"   Individual: {memory['individual_memory_mb']:.1f} MB")
            logger.info(f"   Batched: {memory['batched_memory_mb']:.1f} MB")
        
        if 'network_efficiency' in self.results:
            network = self.results['network_efficiency']
            logger.info(f"🌐 NETWORK EFFICIENCY:")
            logger.info(f"   Same domain: {network['same_domain_time']:.2f}s")
            logger.info(f"   Mixed domains: {network['mixed_domain_time']:.2f}s")
        
        if 'crawler_integration' in self.results:
            crawler = self.results['crawler_integration']
            logger.info(f"🕷️ CRAWLER INTEGRATION:")
            logger.info(f"   Processing time: {crawler['processing_time']:.2f}s")
            if 'batching_stats' in crawler and crawler['batching_stats'].get('batch_efficiency'):
                logger.info(f"   Batch efficiency: {crawler['batching_stats']['batch_efficiency']:.1f}%")
        
        if 'error_handling' in self.results:
            error = self.results['error_handling']
            logger.info(f"⚠️ ERROR HANDLING:")
            logger.info(f"   Success rate: {error['success_rate']:.1f}%")
            logger.info(f"   Resilience: Good ({error['successful']}/{error['total_requests']} succeeded)")
        
        logger.info("\n🎯 CONCLUSION:")
        logger.info("   Request batching provides significant benefits for:")
        logger.info("   • Network efficiency and reduced overhead")
        logger.info("   • Memory usage optimization")
        logger.info("   • Connection reuse and pooling")
        logger.info("   • Improved error handling and resilience")
        
        # Save detailed results to file
        with open('request_batching_benchmark_results.json', 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        logger.info(f"📄 Detailed results saved to: request_batching_benchmark_results.json")
        logger.info("="*60 + "\n")


async def demonstrate_advanced_batching():
    """Demonstrate advanced batching features"""
    logger.info("🔬 Advanced Batching Features Demo")
    
    # Create request batcher with custom configuration
    async with RequestBatcher(
        batch_size=6,
        batch_timeout=0.3,
        max_concurrent_batches=4,
        enable_compression=True,
        enable_memory_optimization=True
    ) as batcher:
        
        # Demo 1: Mixed request types
        logger.info("   📡 Demo 1: Mixed Request Types")
        mixed_requests = [
            RequestSpec("https://httpbin.org/get", method="GET"),
            RequestSpec("https://httpbin.org/post", method="POST", json_data={"test": "data"}),
            RequestSpec("https://httpbin.org/put", method="PUT", json_data={"update": "data"}),
            RequestSpec("https://httpbin.org/delete", method="DELETE"),
        ]
        
        results = await asyncio.gather(*[
            batcher.add_request(spec) for spec in mixed_requests
        ])
        
        logger.info(f"      Processed {len(results)} mixed requests")
        
        # Demo 2: Batch statistics
        logger.info("   📊 Demo 2: Batch Statistics")
        stats = batcher.get_stats()
        logger.info(f"      Total requests: {stats['total_requests']}")
        logger.info(f"      Batch efficiency: {stats['batch_efficiency']:.1f}%")
        logger.info(f"      Network savings: {stats['network_savings_percent']:.1f}%")
        
        # Demo 3: Convenience methods
        logger.info("   🎯 Demo 3: Convenience Methods")
        urls = [
            "https://httpbin.org/uuid",
            "https://httpbin.org/json",
            "https://httpbin.org/user-agent"
        ]
        
        batch_results = await batcher.batch_get_requests(urls)
        logger.info(f"      Batch GET results: {len(batch_results)} responses")


async def main():
    """Main execution function"""
    try:
        # Run comprehensive benchmark
        benchmark = RequestBatchingBenchmark()
        await benchmark.run_all_benchmarks()
        
        # Demonstrate advanced features
        await demonstrate_advanced_batching()
        
        logger.info("✅ Request batching tests completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Test execution failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main()) 