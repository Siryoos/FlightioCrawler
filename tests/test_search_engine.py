import asyncio
import pytest
from intelligent_search import IntelligentSearchEngine


class DummyCrawler:
    async def crawl_all_sites(self, params):
        return [
            {
                "seat_class": params.get("seat_class", "economy"),
                "price": 100,
            }
        ]


class DummyDB:
    async def get_historical_prices(self, route, months=12):
        return {"2024-01": 200}

    async def get_search_count(self, route):
        return 5


@pytest.mark.asyncio
async def test_detect_class_upgrades():
    engine = IntelligentSearchEngine(DummyCrawler(), DummyDB())
    flights = [
        {"seat_class": "economy", "price": 100},
        {"seat_class": "economy", "price": 150},
    ]
    upgrades = await engine.detect_class_upgrades(flights, threshold=60)
    assert len(upgrades) == 2
