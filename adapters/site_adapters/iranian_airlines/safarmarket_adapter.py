"""
Refactored Safarmarket adapter using EnhancedPersianAdapter.
"""

from typing import Dict, List, Optional, Any
from adapters.base_adapters.enhanced_persian_adapter import EnhancedPersianAdapter


class SafarmarketAdapter(EnhancedPersianAdapter):
    """Safarmarket adapter with minimal code duplication."""

    def _get_base_url(self) -> str:
        return "https://www.safarmarket.com"

    def _extract_currency(self, element, config: Dict[str, Any]) -> str:
        return "IRR"

    def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
        """
        Parse Safarmarket specific flight element structure.

        Uses parent class for common parsing with Iranian text processing.
        """
        flight_data = super()._parse_flight_element(element)

        if flight_data:
            # Add Safarmarket specific fields
            config = self.config["extraction_config"]["results_parsing"]

            # Safarmarket specific: travel package info
            package_info = self._extract_text(element, config.get("package_info"))
            if package_info:
                flight_data["package_info"] = self.persian_processor.process_text(
                    package_info
                )
                flight_data["is_package"] = True

            # Safarmarket specific: discount information
            discount_info = self._extract_text(element, config.get("discount_info"))
            if discount_info:
                flight_data["discount_info"] = self.persian_processor.process_text(
                    discount_info
                )

            # Mark as aggregator result
            flight_data["is_aggregator"] = True
            flight_data["aggregator_name"] = "safarmarket"

        return flight_data

    def _get_required_search_fields(self) -> List[str]:
        return ["origin", "destination", "departure_date", "cabin_class"]
