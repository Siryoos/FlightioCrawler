"""
Refactored Flytoday adapter using EnhancedPersianAdapter.
"""

from typing import Dict, List, Optional, Any
from adapters.base_adapters.enhanced_persian_adapter import EnhancedPersianAdapter


class FlytodayAdapter(EnhancedPersianAdapter):
    """
    Flytoday.ir adapter with minimal code duplication.
    
    Uses EnhancedPersianAdapter for all common functionality.
    Only implements aggregator-specific logic.
    """
    
    def _get_base_url(self) -> str:
        """Get Flytoday base URL."""
        return "https://www.flytoday.ir"
    
    def _extract_currency(self, element, config: Dict[str, Any]) -> str:
        """Extract currency - always IRR for Flytoday."""
        return "IRR"
    
    def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
        """
        Parse Flytoday specific flight element structure.
        
        Uses parent class for common parsing with Iranian text processing.
        """
        flight_data = super()._parse_flight_element(element)
        
        if flight_data:
            # Add Flytoday specific fields
            config = self.config["extraction_config"]["results_parsing"]
            
            # Flytoday specific: refund policies
            refund_policy = self._extract_text(element, config.get("refund_policy"))
            if refund_policy:
                flight_data["refund_policy"] = self.persian_processor.process_text(refund_policy)
            
            # Flytoday specific: cancellation policies
            cancel_policy = self._extract_text(element, config.get("cancel_policy"))
            if cancel_policy:
                flight_data["cancel_policy"] = self.persian_processor.process_text(cancel_policy)
            
            # Mark as aggregator result
            flight_data["is_aggregator"] = True
            flight_data["aggregator_name"] = "flytoday"
        
        return flight_data
    
    def _get_required_search_fields(self) -> List[str]:
        """Required fields for Flytoday search."""
        return ["origin", "destination", "departure_date", "passengers"]
