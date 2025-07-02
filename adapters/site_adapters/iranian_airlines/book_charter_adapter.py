"""
Refactored BookCharter adapter using EnhancedPersianAdapter.
"""

from typing import Dict, List, Optional, Any
from adapters.base_adapters.enhanced_persian_adapter import EnhancedPersianAdapter


class BookCharterAdapter(EnhancedPersianAdapter):
    """BookCharter adapter with minimal code duplication."""

    def _get_base_url(self) -> str:
        return "https://bookcharter.ir"

    def _extract_currency(self, element, config: Dict[str, Any]) -> str:
        return "IRR"

    def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
        """
        Parse BookCharter specific flight element structure.

        Uses parent class for common parsing with Iranian text processing.
        """
        flight_data = super()._parse_flight_element(element)

        if flight_data:
            # Add BookCharter specific fields
            config = self.config["extraction_config"]["results_parsing"]

            # BookCharter specific: charter flight info
            charter_info = self._extract_text(element, config.get("charter_info"))
            if charter_info:
                flight_data["charter_info"] = self.persian_processor.process_text(
                    charter_info
                )
                flight_data["is_charter"] = True

            # BookCharter specific: booking conditions
            booking_conditions = self._extract_text(
                element, config.get("booking_conditions")
            )
            if booking_conditions:
                flight_data["booking_conditions"] = self.persian_processor.process_text(
                    booking_conditions
                )

            # Mark as aggregator result
            flight_data["is_aggregator"] = True
            flight_data["aggregator_name"] = "bookcharter"

        return flight_data

    def _get_required_search_fields(self) -> List[str]:
        return ["origin", "destination", "departure_date", "cabin_class"]
