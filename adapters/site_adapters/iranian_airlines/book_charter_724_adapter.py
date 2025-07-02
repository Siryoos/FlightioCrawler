"""
Refactored BookCharter724 adapter using EnhancedPersianAdapter.
"""

from typing import Dict, List, Optional, Any
from adapters.base_adapters.enhanced_persian_adapter import EnhancedPersianAdapter


class BookCharter724Adapter(EnhancedPersianAdapter):
    """BookCharter724 adapter with minimal code duplication."""

    def _get_base_url(self) -> str:
        return "https://bookcharter724.ir"

    def _extract_currency(self, element, config: Dict[str, Any]) -> str:
        return "IRR"

    def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
        """
        Parse BookCharter724 specific flight element structure.

        Uses parent class for common parsing with Iranian text processing.
        """
        flight_data = super()._parse_flight_element(element)

        if flight_data:
            # Add BookCharter724 specific fields
            config = self.config["extraction_config"]["results_parsing"]

            # BookCharter724 specific: charter flight info with 724 system
            charter_info = self._extract_text(element, config.get("charter_info"))
            if charter_info:
                flight_data["charter_info"] = self.persian_processor.process_text(
                    charter_info
                )
                flight_data["is_charter"] = True

            # BookCharter724 specific: 724 system booking ID
            booking_id_724 = self._extract_text(element, config.get("booking_id_724"))
            if booking_id_724:
                flight_data["booking_id_724"] = self.persian_processor.process_text(
                    booking_id_724
                )

            # Mark as aggregator result
            flight_data["is_aggregator"] = True
            flight_data["aggregator_name"] = "bookcharter724"

        return flight_data

    def _get_required_search_fields(self) -> List[str]:
        return ["origin", "destination", "departure_date", "cabin_class"]
