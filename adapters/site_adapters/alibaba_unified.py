"""
Alibaba.ir Adapter - Simplified using UnifiedBaseAdapter
"""

from typing import Dict, List, Any
from bs4 import BeautifulSoup
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from adapters.unified_base_adapter import UnifiedBaseAdapter


class AlibabaAdapter(UnifiedBaseAdapter):
    """Simplified Alibaba adapter - only implements site-specific logic"""
    
    def get_site_name(self) -> str:
        return "alibaba"
        
    def build_search_url(self, origin: str, destination: str, date: str,
                        return_date: str = None) -> str:
        """Build Alibaba-specific search URL"""
        # Alibaba uses specific format for dates (YYYY-MM-DD)
        formatted_date = self.format_date_for_site(date)
        
        if return_date:
            # Round trip
            return f"https://www.alibaba.ir/flights/{origin}-{destination}?departing={formatted_date}&returning={return_date}"
        else:
            # One way
            return f"https://www.alibaba.ir/flights/{origin}-{destination}?departing={formatted_date}"
            
    async def parse_search_results(self, content: str, origin: str, destination: str,
                                 date: str) -> List[Dict[str, Any]]:
        """Parse Alibaba search results"""
        soup = BeautifulSoup(content, 'html.parser')
        flights = []
        
        # Find flight cards
        flight_cards = soup.select('.available-flights__item')
        
        for card in flight_cards:
            try:
                flight = {
                    'airline': self.extract_text(card, '.airline-name__text'),
                    'flight_number': self.extract_text(card, '.flight-number'),
                    'origin': origin,
                    'destination': destination,
                    'departure_time': self.extract_text(card, '.departure-time'),
                    'arrival_time': self.extract_text(card, '.arrival-time'),
                    'price': self.extract_text(card, '.price-value'),
                    'currency': 'IRR',
                    'available_seats': self.extract_text(card, '.capacity', '9'),
                    'aircraft_type': self.extract_text(card, '.aircraft-type'),
                    'flight_class': 'economy',
                }
                
                flights.append(flight)
                
            except Exception as e:
                self.logger.warning(f"Error parsing flight card: {e}")
                continue
                
        return flights 