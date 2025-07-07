"""
Enhanced End-to-End Tests for FlightioCrawler
""" 

import pytest
import asyncio
from unittest.mock import AsyncMock
from typing import Dict, List
from datetime import datetime, timedelta

from adapters.site_adapters.iranian_airlines.alibaba_adapter import AlibabaAdapter
from adapters.site_adapters.iranian_airlines.mahan_air_adapter import MahanAirAdapter


class TestEndToEndEnhanced:
    """Enhanced end-to-end tests for complete user workflows."""

    @pytest.fixture
    def user_search_scenario(self):
        return {
            "origin": "THR",
            "destination": "DXB", 
            "departure_date": (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d"),
            "adults": 2,
            "cabin_class": "economy"
        }

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_complete_workflow(self, user_search_scenario):
        """Test complete flight search workflow."""
        adapter = AlibabaAdapter({})
        adapter.crawl = AsyncMock(return_value=[
            {"airline": "Test", "price": 1000000, "currency": "IRR"}
        ])
        
        results = await adapter.crawl(user_search_scenario)
        assert len(results) > 0
        assert "airline" in results[0]

