from dataclasses import dataclass
from typing import Dict, List, Tuple, Any, Optional
import asyncio
from datetime import datetime, timedelta


@dataclass
class SearchOptimization:
    """Configuration for search optimization strategies"""

    enable_multi_route: bool = True
    enable_date_range: bool = True
    date_range_days: int = 3
    enable_class_upgrade_detection: bool = True
    upgrade_threshold_percent: float = 20.0
    enable_seasonal_tracking: bool = True


@dataclass
class ConnectingFlight:
    """Represents a connecting flight option"""

    origin_flight: Dict
    connecting_flight: Dict
    layover_duration_minutes: int
    total_price: float
    total_duration_minutes: int
    airports_sequence: List[str]


class IntelligentSearchEngine:
    def __init__(self, main_crawler, db_manager):
        """Initialize the intelligent search engine."""
        self.main_crawler = main_crawler
        self.db_manager = db_manager

    async def optimize_search_strategy(
        self, search_params: Dict, optimization: SearchOptimization
    ) -> Dict:
        """Optimize the search strategy based on the given parameters and optimization config."""
        results = {}
        if optimization.enable_multi_route:
            results["connecting_flights"] = await self.discover_connecting_flights(
                search_params["origin"],
                search_params["destination"],
                search_params["departure_date"],
            )
        if optimization.enable_date_range:
            results["date_range"] = await self.search_date_range(
                search_params, optimization.date_range_days
            )
        if optimization.enable_class_upgrade_detection:
            results["class_upgrades"] = await self.detect_class_upgrades(
                results.get("date_range", []), optimization.upgrade_threshold_percent
            )
        if optimization.enable_seasonal_tracking:
            results["seasonal_trends"] = await self.get_seasonal_price_trends(
                search_params["origin"] + "-" + search_params["destination"]
            )
        return results

    async def discover_connecting_flights(
        self, origin: str, destination: str, date: str
    ) -> List[ConnectingFlight]:
        """Discover connecting flight options between origin and destination on a given date."""
        # Search for flights from origin to destination
        origin_flights = await self.main_crawler.crawl_all_sites(
            {"origin": origin, "destination": destination, "departure_date": date}
        )
        connecting_flights = []
        for origin_flight in origin_flights:
            # Search for connecting flights from destination to a final destination (e.g., a hub)
            final_destination = "FINAL_DEST"  # Replace with actual logic
            connecting_flight_list = await self.main_crawler.crawl_all_sites(
                {
                    "origin": destination,
                    "destination": final_destination,
                    "departure_date": date,
                }
            )
            for connecting_flight in connecting_flight_list:
                # Calculate layover duration
                layover_duration = (
                    datetime.fromisoformat(connecting_flight["departure_time"])
                    - datetime.fromisoformat(origin_flight["arrival_time"])
                ).total_seconds() / 60
                if (
                    60 <= layover_duration <= 240
                ):  # Filter by layover duration (1-4 hours)
                    connecting_flights.append(
                        ConnectingFlight(
                            origin_flight=origin_flight,
                            connecting_flight=connecting_flight,
                            layover_duration_minutes=int(layover_duration),
                            total_price=origin_flight["price"]
                            + connecting_flight["price"],
                            total_duration_minutes=int(
                                layover_duration
                                + (
                                    datetime.fromisoformat(
                                        connecting_flight["arrival_time"]
                                    )
                                    - datetime.fromisoformat(
                                        origin_flight["departure_time"]
                                    )
                                ).total_seconds()
                                / 60
                            ),
                            airports_sequence=[origin, destination, final_destination],
                        )
                    )
        return connecting_flights

    async def search_date_range(self, search_params: Dict, days_range: int = 3) -> Dict:
        """Search for flights over a range of dates."""
        date_results = {}
        base_date = datetime.fromisoformat(search_params["departure_date"])
        for i in range(days_range):
            current_date = (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
            date_results[current_date] = await self.main_crawler.crawl_all_sites(
                {**search_params, "departure_date": current_date}
            )
        return date_results

    async def detect_class_upgrades(
        self, flights: List[Dict], threshold: float = 20.0
    ) -> List[Dict]:
        """Detect possible class upgrades within a price threshold."""
        upgrades = []
        for flight in flights:
            if flight.get("seat_class") == "economy":
                # Simulate a business class price (e.g., 1.5x economy price)
                business_price = flight["price"] * 1.5
                if (business_price - flight["price"]) / flight[
                    "price"
                ] * 100 <= threshold:
                    upgrades.append({**flight, "upgrade_price": business_price})
        return upgrades

    async def get_seasonal_price_trends(
        self, route: str, historical_months: int = 12
    ) -> Dict:
        """Get seasonal price trends for a route."""
        # Query historical data from db_manager
        historical_data = await self.db_manager.get_historical_prices(
            route, historical_months
        )
        return {"route": route, "trends": historical_data}

    async def calculate_route_popularity_score(self, route: str) -> float:
        """Calculate a popularity score for a route."""
        # Query search history from db_manager
        search_count = await self.db_manager.get_search_count(route)
        return search_count / 100  # Normalize score

    async def recommend_alternative_dates(self, search_params: Dict) -> List[Dict]:
        """Recommend alternative dates for better prices or availability."""
        # Query historical data and recommend dates with lower prices
        historical_data = await self.db_manager.get_historical_prices(
            search_params["origin"] + "-" + search_params["destination"]
        )
        return [
            {"date": date, "price": price}
            for date, price in historical_data.items()
            if price < search_params.get("price", float("inf"))
        ]
