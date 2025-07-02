"""
Refactored Iran Aseman Air adapter using EnhancedPersianAdapter.
"""

from typing import Dict, List, Optional, Any
from adapters.base_adapters.enhanced_persian_adapter import EnhancedPersianAdapter


class IranAsemanAirAdapter(EnhancedPersianAdapter):
    """Iran Aseman Air adapter with minimal code duplication."""
    
    def _get_base_url(self) -> str:
        return "https://www.iaa.ir"
    
    def _extract_currency(self, element, config: Dict[str, Any]) -> str:
        return "IRR"
    
    def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
        """
        Parse Iran Aseman Air specific flight element structure.
        
        Uses parent class for common parsing with Iranian text processing.
        """
        flight_data = super()._parse_flight_element(element)
        
        if flight_data:
            # Add Iran Aseman Air specific fields
            config = self.config["extraction_config"]["results_parsing"]
            
            # Iran Aseman Air specific: route information
            route_info = self._extract_text(element, config.get("route_info"))
            if route_info:
                flight_data["route_info"] = self.persian_processor.process_text(route_info)
            
            # Iran Aseman Air specific: service class details
            service_details = self._extract_text(element, config.get("service_details"))
            if service_details:
                flight_data["service_details"] = self.persian_processor.process_text(service_details)
            
            # Set airline name
            flight_data["airline"] = "Iran Aseman Air"
            flight_data["airline_code"] = "EP"
        
        return flight_data
    
    def _get_required_search_fields(self) -> List[str]:
        return ["origin", "destination", "departure_date", "cabin_class"]
