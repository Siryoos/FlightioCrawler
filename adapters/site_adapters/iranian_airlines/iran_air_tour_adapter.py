"""
Refactored Iran Air Tour adapter using EnhancedPersianAdapter.
"""

from typing import Dict, List, Optional, Any
from adapters.base_adapters.enhanced_persian_adapter import EnhancedPersianAdapter


class IranAirTourAdapter(EnhancedPersianAdapter):
    """Iran Air Tour adapter with minimal code duplication."""

    def _get_base_url(self) -> str:
        return "https://www.iranairtour.ir"

    def _extract_currency(self, element, config: Dict[str, Any]) -> str:
        return "IRR"

    def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
        """
        Parse Iran Air Tour specific flight element structure.

        Uses parent class for common parsing with Iranian text processing.
        """
        flight_data = super()._parse_flight_element(element)

        if flight_data:
            # Add Iran Air Tour specific fields
            config = self.config["extraction_config"]["results_parsing"]

            # Iran Air Tour specific: extensive additional fields
            additional_fields = [
                "fare_conditions",
                "available_seats",
                "aircraft_type",
                "baggage_allowance",
                "meal_service",
                "special_services",
                "refund_policy",
                "change_policy",
                "fare_rules",
                "booking_class",
                "fare_basis",
                "ticket_validity",
                "miles_earned",
                "miles_required",
                "promotion_code",
                "special_offers",
            ]

            for field in additional_fields:
                if field in config:
                    value = self._extract_text(element, config[field])
                    if value:
                        flight_data[field] = self.persian_processor.process_text(value)

            # Set airline name
            flight_data["airline"] = "Iran Air Tour"
            flight_data["airline_code"] = "B9"
            flight_data["is_tour_operator"] = True

        return flight_data

    def _get_required_search_fields(self) -> List[str]:
        return ["origin", "destination", "departure_date", "passengers", "seat_class"]
