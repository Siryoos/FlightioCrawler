import asyncio
from datetime import datetime, timedelta
from real_data_crawler import RealDataCrawler
from quality_checker import RealDataQualityChecker


def test_validate_extracted_data():
    crawler = RealDataCrawler.__new__(RealDataCrawler)
    raw = [
        {"price": 100000, "departure_time": datetime.now(), "arrival_time": datetime.now() + timedelta(hours=1)},
        {"price": -5},
        {"price": 500000000},
    ]
    valid = asyncio.run(crawler.validate_extracted_data(raw))
    assert len(valid) == 1


def test_real_data_quality_checker():
    qc = RealDataQualityChecker()
    flights = [
        {
            "price": 100000,
            "origin": "THR",
            "destination": "MHD",
            "flight_number": "IR123",
            "departure_time": datetime.now(),
            "arrival_time": datetime.now() + timedelta(hours=1),
        },
        {
            "price": -10,
            "origin": "BAD",
            "destination": "???",
            "flight_number": "XX",
            "departure_time": datetime.now(),
            "arrival_time": datetime.now() - timedelta(hours=1),
        },
    ]
    valid, report = asyncio.run(qc.validate_real_data_quality(flights))
    assert len(valid) == 1
    assert report["invalid"] == 1
