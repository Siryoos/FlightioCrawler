"""
Enhanced international airline adapter with minimal code duplication.
"""

from typing import Dict, List, Optional, Any
from .enhanced_base_crawler import EnhancedBaseCrawler


class EnhancedInternationalAdapter(EnhancedBaseCrawler):
    """
    Enhanced base class for international airline adapters.
    
    This class eliminates all initialization duplication and provides
    a clean interface for international airline crawlers.
    """
    
    async def _fill_search_form(self, search_params: Dict[str, Any]) -> None:
        """
        Fill search form for international airlines.
        
        Standard implementation that works for most international airlines.
        Override only if needed.
        """
        form_config = self.config["extraction_config"]["search_form"]
        
        # Trip type
        if "trip_type" in search_params and "trip_type_field" in form_config:
            await self.page.select_option(
                form_config["trip_type_field"],
                search_params["trip_type"]
            )
        
        # Origin and destination
        await self.page.fill(form_config["origin_field"], search_params["origin"])
        await self.page.fill(form_config["destination_field"], search_params["destination"])
        
        # Dates
        await self.page.fill(
            form_config["departure_date_field"], 
            search_params["departure_date"]
        )
        
        if "return_date" in search_params and "return_date_field" in form_config:
            await self.page.fill(
                form_config["return_date_field"], 
                search_params["return_date"]
            )
        
        # Passengers
        if "passengers" in search_params and "passengers_field" in form_config:
            await self.page.select_option(
                form_config["passengers_field"], 
                str(search_params["passengers"])
            )
        
        # Cabin class
        if "cabin_class" in search_params and "cabin_class_field" in form_config:
            await self.page.select_option(
                form_config["cabin_class_field"], 
                search_params["cabin_class"]
            )
        
        # Submit
        await self.page.click("button[type='submit']")
        await self.page.wait_for_load_state("networkidle")
    
    def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
        """
        Parse flight element for international airlines.
        
        Standard implementation that extracts common fields.
        Override to add airline-specific fields.
        """
        try:
            config = self.config["extraction_config"]["results_parsing"]
            
            # Extract basic fields
            flight_data = {
                "airline": self._extract_text(element, config.get("airline")),
                "flight_number": self._extract_text(element, config.get("flight_number")),
                "departure_time": self._extract_text(element, config.get("departure_time")),
                "arrival_time": self._extract_text(element, config.get("arrival_time")),
                "duration": self._extract_text(element, config.get("duration")),
                "price": self._extract_price(
                    self._extract_text(element, config.get("price"))
                ),
                "cabin_class": self._extract_text(element, config.get("cabin_class")),
                "currency": self._extract_currency(element, config)
            }
            
            # Extract optional fields
            self._extract_optional_fields(element, flight_data, config)
            
            return flight_data
            
        except Exception as e:
            self.logger.error(f"Error parsing flight element: {str(e)}")
            return None
    
    def _extract_currency(self, element, config: Dict[str, Any]) -> str:
        """
        Extract currency from element.
        
        Override for specific currency extraction logic.
        """
        # Default to USD for international flights
        return "USD"
    
    def _extract_optional_fields(
        self, 
        element, 
        flight_data: Dict[str, Any], 
        config: Dict[str, Any]
    ) -> None:
        """Extract optional fields if available."""
        optional_fields = [
            "fare_conditions", "available_seats", "aircraft_type",
            "baggage_allowance", "meal_service", "special_services",
            "refund_policy", "change_policy", "fare_rules",
            "booking_class", "fare_basis", "ticket_validity",
            "miles_earned", "miles_required", "promotion_code",
            "special_offers", "layovers", "total_duration"
        ]
        
        for field in optional_fields:
            if field in config:
                value = self._extract_text(element, config[field])
                if value:
                    flight_data[field] = value
    
    def _get_required_search_fields(self) -> List[str]:
        """Required fields for international flights."""
        return ["origin", "destination", "departure_date", "cabin_class"] 