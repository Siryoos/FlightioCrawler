"""
Refactored Parto Ticket adapter using EnhancedPersianAdapter.
"""

from typing import Dict, List, Optional, Any
from adapters.base_adapters.enhanced_persian_adapter import EnhancedPersianAdapter
from adapters.site_adapters.iranian_airlines.parto_crs_adapter import PartoCRSAdapter


class PartoTicketAdapter(EnhancedPersianAdapter):
    """Parto Ticket adapter with minimal code duplication and CRS integration."""

    def _initialize_adapter(self) -> None:
        """Initialize Parto Ticket specific components."""
        super()._initialize_adapter()

        # Parto Ticket specific CRS integration
        self.enable_crs_integration = self.config.get("enable_crs_integration", False)
        self.crs_config = self.config.get("crs_config", {})
        self.crs_agency_code = self.config.get("crs_agency_code")
        self.crs_commission_rate = self.config.get("crs_commission_rate", 0)

        if self.enable_crs_integration:
            self.crs_adapter = PartoCRSAdapter(self.crs_config)

    def _get_base_url(self) -> str:
        return "https://www.parto-ticket.ir"

    def _extract_currency(self, element, config: Dict[str, Any]) -> str:
        return "IRR"

    def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
        """
        Parse Parto Ticket specific flight element structure.

        Uses parent class for common parsing with Iranian text processing.
        """
        flight_data = super()._parse_flight_element(element)

        if flight_data:
            # Add Parto Ticket specific fields
            config = self.config["extraction_config"]["results_parsing"]

            # Parto Ticket specific: fare conditions
            fare_conditions = self._extract_fare_conditions(element)
            if fare_conditions:
                flight_data["fare_conditions"] = fare_conditions

            # Parto Ticket specific: available seats
            available_seats = self._extract_available_seats(element)
            if available_seats:
                flight_data["available_seats"] = available_seats

            # Parto Ticket specific: ticket type
            ticket_type = self._extract_text(element, config.get("ticket_type"))
            if ticket_type:
                flight_data["ticket_type"] = self.persian_processor.process_text(
                    ticket_type
                )

            # Mark as aggregator result
            flight_data["is_aggregator"] = True
            flight_data["aggregator_name"] = "parto_ticket"

        return flight_data

    async def crawl(self, search_params: Dict) -> List[Dict]:
        """
        Enhanced crawl method with CRS integration.
        """
        results = await super().crawl(search_params)

        # Integrate with CRS if enabled
        if self.enable_crs_integration and results:
            results = await self._integrate_with_crs(results, search_params)

        return results

    def _extract_fare_conditions(self, element) -> Optional[Dict]:
        """Extract fare conditions from flight element."""
        try:
            fare_conditions = {}

            # Extract cancellation policy
            cancellation = self._extract_text(element, ".cancellation-policy")
            if cancellation:
                fare_conditions["cancellation"] = self.persian_processor.process_text(
                    cancellation
                )

            # Extract change policy
            changes = self._extract_text(element, ".change-policy")
            if changes:
                fare_conditions["changes"] = self.persian_processor.process_text(
                    changes
                )

            # Extract baggage allowance
            baggage = self._extract_text(element, ".baggage-allowance")
            if baggage:
                fare_conditions["baggage"] = self.persian_processor.process_text(
                    baggage
                )

            return fare_conditions if fare_conditions else None

        except Exception as e:
            self.logger.error(f"Error extracting fare conditions: {e}")
            return None

    def _extract_available_seats(self, element) -> Optional[int]:
        """Extract available seats from flight element."""
        try:
            seats_text = self._extract_text(element, ".available-seats")
            if seats_text:
                return self.persian_processor.extract_number(seats_text)
            return None

        except Exception as e:
            self.logger.error(f"Error extracting available seats: {e}")
            return None

    async def _integrate_with_crs(
        self, results: List[Dict], search_params: Dict
    ) -> List[Dict]:
        """Integrate flight results with CRS system."""
        try:
            enhanced_results = []

            for flight in results:
                # Get CRS data for each flight
                crs_data = await self._get_crs_data(flight, search_params)
                if crs_data:
                    flight.update(crs_data)

                enhanced_results.append(flight)

            return enhanced_results

        except Exception as e:
            self.logger.error(f"Error integrating with CRS: {e}")
            return results

    async def _get_crs_data(self, flight: Dict, search_params: Dict) -> Optional[Dict]:
        """Get additional data from CRS system."""
        try:
            if not self.crs_adapter:
                return None

            # Query CRS for additional flight information
            crs_results = await self.crs_adapter.crawl(search_params)

            # Match flight with CRS data
            for crs_flight in crs_results:
                if crs_flight.get("flight_number") == flight.get(
                    "flight_number"
                ) and crs_flight.get("departure_time") == flight.get("departure_time"):

                    return {
                        "crs_booking_reference": crs_flight.get("booking_reference"),
                        "crs_commission": self.crs_commission_rate,
                        "crs_agency_code": self.crs_agency_code,
                    }

            return None

        except Exception as e:
            self.logger.error(f"Error getting CRS data: {e}")
            return None

    def _get_required_search_fields(self) -> List[str]:
        return ["origin", "destination", "departure_date", "passengers", "seat_class"]
