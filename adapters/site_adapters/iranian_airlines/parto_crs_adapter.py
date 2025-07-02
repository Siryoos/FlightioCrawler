"""
Refactored Parto CRS adapter using EnhancedPersianAdapter.
"""

from typing import Dict, List, Optional, Any
from adapters.base_adapters.enhanced_persian_adapter import EnhancedPersianAdapter


class PartoCRSAdapter(EnhancedPersianAdapter):
    """Parto CRS adapter with minimal code duplication."""

    def _get_base_url(self) -> str:
        return "https://www.partocrs.com"

    def _extract_currency(self, element, config: Dict[str, Any]) -> str:
        return "IRR"

    def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
        """
        Parse Parto CRS specific flight element structure.

        Uses parent class for common parsing with Iranian text processing.
        """
        flight_data = super()._parse_flight_element(element)

        if flight_data:
            # Add Parto CRS specific fields
            config = self.config["extraction_config"]["results_parsing"]

            # Parto CRS specific: CRS system integration info
            crs_info = self._extract_text(element, config.get("crs_info"))
            if crs_info:
                flight_data["crs_info"] = self.persian_processor.process_text(crs_info)

            # Parto CRS specific: booking reference
            booking_ref = self._extract_text(element, config.get("booking_reference"))
            if booking_ref:
                flight_data["booking_reference"] = self.persian_processor.process_text(
                    booking_ref
                )

            # Mark as aggregator result
            flight_data["is_aggregator"] = True
            flight_data["aggregator_name"] = "parto_crs"

        return flight_data

    def _get_required_search_fields(self) -> List[str]:
        return ["origin", "destination", "departure_date", "cabin_class"]
