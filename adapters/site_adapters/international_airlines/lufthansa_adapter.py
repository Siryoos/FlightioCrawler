"""
Refactored Lufthansa adapter using EnhancedInternationalAdapter.
"""

from typing import Dict, List, Optional, Any
from adapters.base_adapters.enhanced_international_adapter import (
    EnhancedInternationalAdapter,
)


class LufthansaAdapter(EnhancedInternationalAdapter):
    """
    Lufthansa adapter with minimal code duplication.

    Uses EnhancedInternationalAdapter for all common functionality.
    Only implements airline-specific logic.
    """

    def _get_base_url(self) -> str:
        """Get Lufthansa base URL."""
        return "https://www.lufthansa.com"

    def _extract_currency(self, element, config: Dict[str, Any]) -> str:
        """Extract currency - EUR for Lufthansa."""
        return "EUR"

    def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
        """
        Parse Lufthansa specific flight element structure.

        Uses parent class for common parsing.
        """
        flight_data = super()._parse_flight_element(element)

        if flight_data:
            # Add Lufthansa specific fields
            config = self.config["extraction_config"]["results_parsing"]

            # Lufthansa specific: Star Alliance miles
            star_alliance_miles = self._extract_text(
                element, config.get("star_alliance_miles")
            )
            if star_alliance_miles:
                flight_data["star_alliance_miles"] = star_alliance_miles

            # Lufthansa specific: aircraft type details
            aircraft_details = self._extract_text(
                element, config.get("aircraft_details")
            )
            if aircraft_details:
                flight_data["aircraft_details"] = aircraft_details

            # Lufthansa specific: lounge access
            lounge_access = self._extract_text(element, config.get("lounge_access"))
            if lounge_access:
                flight_data["lounge_access"] = lounge_access

        return flight_data

    def _get_required_search_fields(self) -> List[str]:
        """Required fields for Lufthansa search."""
        return ["origin", "destination", "departure_date", "cabin_class"]
