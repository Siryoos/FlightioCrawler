"""
Refactored Pegasus adapter using EnhancedInternationalAdapter.
"""

from typing import Dict, List, Optional, Any
from adapters.base_adapters.enhanced_international_adapter import EnhancedInternationalAdapter


class PegasusAdapter(EnhancedInternationalAdapter):
    """Pegasus adapter with minimal code duplication."""
    
    def _get_base_url(self) -> str:
        return "https://www.flypgs.com"
    
    def _extract_currency(self, element, config: Dict[str, Any]) -> str:
        return "TRY"
    
    def _get_required_search_fields(self) -> List[str]:
        return ["origin", "destination", "departure_date", "cabin_class"]
