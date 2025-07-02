"""
Refactored Alibaba adapter using base classes.
This demonstrates how to reduce code duplication using inheritance.
"""

from typing import Dict, List, Optional, Any
from playwright.async_api import Page

from adapters.base_adapters.airline_crawler import AirlineCrawler


class AlibabaAdapterRefactored(AirlineCrawler):
    """
    Refactored Alibaba adapter using base classes.
    
    This version eliminates code duplication by inheriting from AirlineCrawler
    and only implementing site-specific logic.
    """
    
    def __init__(self, config: Dict[str, Any]):
        # Add site-specific configuration
        config.update({
            "base_url": "https://www.alibaba.ir",
            "site_name": "Alibaba"
        })
        super().__init__(config)
    
    async def crawl(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Main crawling method for Alibaba.
        
        This method is much simpler now as most logic is handled by the base class.
        """
        # The base class handles validation, error handling, and monitoring
        return await self._safe_crawl(search_params)
    
    async def _fill_search_form(self, page: Page, search_params: Dict[str, Any]) -> None:
        """
        Alibaba-specific form filling logic.
        
        Only implements the parts that are specific to Alibaba's website.
        """
        try:
            form_config = self.config["extraction_config"]["search_form"]
            
            # Alibaba-specific form filling
            await page.fill(form_config["origin_field"], search_params["origin"])
            await page.fill(form_config["destination_field"], search_params["destination"])
            await page.fill(form_config["departure_date_field"], search_params["departure_date"])
            
            if "return_date" in search_params:
                await page.fill(form_config["return_date_field"], search_params["return_date"])
            
            await page.select_option(form_config["cabin_class_field"], search_params["cabin_class"])
            
            # Submit form
            await page.click("button[type='submit']")
            await page.wait_for_load_state("networkidle")
            
        except Exception as e:
            self.logger.error(f"Error filling Alibaba search form: {e}")
            raise
    
    def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
        """
        Alibaba-specific flight element parsing.
        
        Only implements parsing logic specific to Alibaba's HTML structure.
        """
        try:
            parsing_config = self.config["extraction_config"]["results_parsing"]
            
            # Use base class parsing with Alibaba-specific selectors
            flight_data = {
                "airline": self._extract_text(element, parsing_config["airline"]),
                "flight_number": self._extract_text(element, parsing_config["flight_number"]),
                "departure_time": self._extract_text(element, parsing_config["departure_time"]),
                "arrival_time": self._extract_text(element, parsing_config["arrival_time"]),
                "duration": self._extract_text(element, parsing_config["duration"]),
                "price": self._extract_price(self._extract_text(element, parsing_config["price"])),
                "cabin_class": self._extract_text(element, parsing_config["cabin_class"])
            }
            
            return flight_data
            
        except Exception as e:
            self.logger.error(f"Error parsing Alibaba flight element: {e}")
            return None 