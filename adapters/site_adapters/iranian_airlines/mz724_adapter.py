"""
Refactored Mz724 adapter using EnhancedPersianAdapter.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from adapters.base_adapters.enhanced_persian_adapter import EnhancedPersianAdapter


class Mz724Adapter(EnhancedPersianAdapter):
    """Mz724 adapter with minimal code duplication."""

    def _get_base_url(self) -> str:
        return "https://www.mz724.ir"

    def _extract_currency(self, element, config: Dict[str, Any]) -> str:
        return "IRR"

    def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
        """
        Parse Mz724 specific flight element structure.

        Uses parent class for common parsing with Iranian text processing.
        """
        flight_data = super()._parse_flight_element(element)

        if flight_data:
            # Add Mz724 specific fields using Persian text processing
            config = self.config["extraction_config"]["results_parsing"]

            # Mz724 specific: fare conditions
            fare_conditions_elem = element.select_one(".fare-conditions")
            if fare_conditions_elem:
                flight_data["fare_conditions"] = {
                    "cancellation": self._extract_text(
                        fare_conditions_elem, ".cancellation"
                    ),
                    "changes": self._extract_text(fare_conditions_elem, ".changes"),
                    "baggage": self._extract_text(fare_conditions_elem, ".baggage"),
                }

            # Mz724 specific: available seats
            seats_elem = element.select_one(".available-seats")
            if seats_elem:
                seats_text = seats_elem.text.strip()
                flight_data["available_seats"] = self.persian_processor.extract_number(
                    seats_text
                )

            # Mz724 specific: aircraft type
            aircraft_elem = element.select_one(".aircraft-type")
            if aircraft_elem:
                flight_data["aircraft_type"] = self.persian_processor.process_text(
                    aircraft_elem.text.strip()
                )

            # Mark as aggregator result
            flight_data["is_aggregator"] = True
            flight_data["aggregator_name"] = "mz724"

        return flight_data

    def _get_required_search_fields(self) -> List[str]:
        return ["origin", "destination", "departure_date", "passengers", "seat_class"]
