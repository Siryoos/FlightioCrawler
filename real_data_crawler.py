from typing import List, Dict
import logging
from datetime import datetime
from adapters.base_adapters import BaseSiteCrawler


class RealDataCrawler(BaseSiteCrawler):
    """Production crawler for real website data"""

    async def extract_real_flight_data(self, search_params: dict) -> List[Dict]:
        """Extract actual flight data from live websites."""
        flights: List[Dict] = []
        try:
            flights = await self.search_flights(search_params)
        except Exception as exc:  # pragma: no cover - network dependent
            logging.getLogger(__name__).error(f"Extraction error: {exc}")
        return flights

    async def validate_extracted_data(self, raw_data: List[Dict]) -> List[Dict]:
        """Validate that extracted data is real and reasonable."""
        validated: List[Dict] = []
        for flight in raw_data:
            try:
                price = float(flight.get("price", 0))
                if price <= 0 or price > 200000000:
                    continue
                dep = flight.get("departure_time")
                arr = flight.get("arrival_time")
                if (
                    dep
                    and arr
                    and isinstance(dep, datetime)
                    and isinstance(arr, datetime)
                ):
                    if arr <= dep:
                        continue
                validated.append(flight)
            except Exception:  # pragma: no cover - simple validation
                continue
        return validated
