"""
Enhanced Performance Tests for FlightioCrawler
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock
from typing import Dict, List
from datetime import datetime, timedelta

from adapters.site_adapters.iranian_airlines.alibaba_adapter import AlibabaAdapter
from adapters.site_adapters.iranian_airlines.mahan_air_adapter import MahanAirAdapter


class TestPerformanceEnhanced:
    """Enhanced performance tests for FlightioCrawler."""

    @pytest.fixture
    def performance_config(self):
        return {
            "rate_limiting": {"requests_per_second": 5.0},
            "error_handling": {"max_retries": 1},
            "monitoring": {"enabled": False}
        }

    @pytest.fixture
    def sample_search_params(self):
        return {
            "origin": "THR",
            "destination": "IST", 
            "departure_date": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
            "adults": 1
        }

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_single_adapter_performance(self, performance_config, sample_search_params):
        """Test single adapter performance."""
        adapter = AlibabaAdapter(performance_config)
        
        # Mock large dataset
        large_results = [{"airline": f"Airline {i}", "price": 1000000 + i} for i in range(100)]
        adapter.crawl = AsyncMock(return_value=large_results)
        
        start_time = time.time()
        results = await adapter.crawl(sample_search_params)
        execution_time = time.time() - start_time
        
        assert execution_time < 5.0, f"Should complete in <5s, took {execution_time:.2f}s"
        assert len(results) == 100

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_concurrent_performance(self, performance_config, sample_search_params):
        """Test concurrent adapter performance."""
        adapters = [AlibabaAdapter(performance_config), MahanAirAdapter(performance_config)]
        
        for adapter in adapters:
            adapter.crawl = AsyncMock(return_value=[{"airline": "Test", "price": 1000000}])
        
        start_time = time.time()
        tasks = [adapter.crawl(sample_search_params) for adapter in adapters]
        results = await asyncio.gather(*tasks)
        execution_time = time.time() - start_time
        
        assert execution_time < 8.0, f"Concurrent should complete in <8s, took {execution_time:.2f}s"
        assert len(results) == 2

    @pytest.mark.performance
    def test_adapter_creation_performance(self):
        """Test adapter creation performance."""
        start_time = time.time()
        
        adapters = []
        for i in range(20):
            config = {
                "base_url": "https://test.com",
                "search_url": "https://test.com/search",
                "rate_limiting": {"requests_per_second": 1.0}
            }
            adapter = AlibabaAdapter(config)
            adapters.append(adapter)
        
        creation_time = time.time() - start_time
        
        assert creation_time < 2.0, f"Creating 20 adapters should take <2s, took {creation_time:.2f}s"
        assert len(adapters) == 20
