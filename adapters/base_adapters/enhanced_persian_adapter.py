"""
Enhanced Persian airline adapter with minimal code duplication.
"""

from typing import Dict, List, Optional, Any
from .enhanced_base_crawler import EnhancedBaseCrawler

# Fix import path
try:
    from data.transformers.persian_text_processor import PersianTextProcessor
except ImportError:
    try:
        from utils.persian_text_processor import PersianTextProcessor
    except ImportError:
        # Fallback - create a dummy processor
        class PersianTextProcessor:
            def process_text(self, text): return text
            def process_date(self, date): return date
            def process_price(self, price): return price
            def extract_number(self, text): return text


class EnhancedPersianAdapter(EnhancedBaseCrawler):
    """
    Enhanced base class for Persian airline adapters.
    
    This class eliminates all initialization duplication and provides
    Persian text processing capabilities.
    """
    
    def _initialize_adapter(self) -> None:
        """Initialize Persian text processor."""
        self.persian_processor = PersianTextProcessor()
    
    async def _fill_search_form(self, search_params: Dict[str, Any]) -> None:
        """
        Fill search form for Persian airlines with text processing.
        
        Standard implementation with Persian text processing.
        Override only if needed.
        """
        form_config = self.config["extraction_config"]["search_form"]
        
        # Origin with Persian processing
        if "origin_field" in form_config:
            processed_origin = self.persian_processor.process_text(search_params["origin"])
            await self.page.fill(form_config["origin_field"], processed_origin)
        
        # Destination with Persian processing
        if "destination_field" in form_config:
            processed_destination = self.persian_processor.process_text(search_params["destination"])
            await self.page.fill(form_config["destination_field"], processed_destination)
        
        # Date with Persian date processing
        if "date_field" in form_config:
            processed_date = self.persian_processor.process_date(search_params["departure_date"])
            await self.page.fill(form_config["date_field"], processed_date)
        
        # Passengers
        if "passengers" in search_params and "passengers_field" in form_config:
            await self.page.select_option(
                form_config["passengers_field"], 
                str(search_params["passengers"])
            )
        
        # Seat class with Persian processing
        if "seat_class" in search_params and "class_field" in form_config:
            processed_class = self.persian_processor.process_text(search_params["seat_class"])
            await self.page.select_option(form_config["class_field"], processed_class)
        
        # Trip type with Persian processing
        if "trip_type" in search_params and "trip_type_field" in form_config:
            processed_trip_type = self.persian_processor.process_text(search_params["trip_type"])
            await self.page.select_option(form_config["trip_type_field"], processed_trip_type)
        
        # Submit
        await self.page.click("button[type='submit']")
        await self.page.wait_for_load_state("networkidle")
    
    def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
        """
        Parse flight element for Persian airlines with text processing.
        
        Standard implementation with Persian text processing.
        Override to add airline-specific fields.
        """
        try:
            config = self.config["extraction_config"]["results_parsing"]
            
            # Extract basic fields with Persian processing
            flight_data = {
                "airline": self.persian_processor.process_text(
                    self._extract_text(element, config.get("airline"))
                ),
                "flight_number": self.persian_processor.process_text(
                    self._extract_text(element, config.get("flight_number"))
                ),
                "departure_time": self.persian_processor.process_text(
                    self._extract_text(element, config.get("departure_time"))
                ),
                "arrival_time": self.persian_processor.process_text(
                    self._extract_text(element, config.get("arrival_time"))
                ),
                "duration": self.persian_processor.process_text(
                    self._extract_text(element, config.get("duration"))
                ),
                "price": self.persian_processor.process_price(
                    self._extract_text(element, config.get("price"))
                ),
                "seat_class": self.persian_processor.process_text(
                    self._extract_text(element, config.get("seat_class"))
                ),
                "currency": "IRR"  # Iranian Rial
            }
            
            # Convert duration to minutes if needed
            if "duration" in flight_data:
                flight_data["duration_minutes"] = self._parse_duration(flight_data["duration"])
            
            # Extract optional fields with Persian processing
            self._extract_optional_fields_persian(element, flight_data, config)
            
            return flight_data
            
        except Exception as e:
            self.logger.error(f"Error parsing flight element: {str(e)}")
            return None
    
    def _extract_optional_fields_persian(
        self, 
        element, 
        flight_data: Dict[str, Any], 
        config: Dict[str, Any]
    ) -> None:
        """Extract optional fields with Persian text processing."""
        optional_fields = [
            "fare_conditions", "available_seats", "aircraft_type",
            "baggage_allowance", "meal_service", "special_services",
            "refund_policy", "change_policy", "fare_rules",
            "booking_class", "fare_basis", "ticket_validity",
            "miles_earned", "miles_required", "promotion_code",
            "special_offers"
        ]
        
        for field in optional_fields:
            if field in config:
                raw_text = self._extract_text(element, config[field])
                if raw_text:
                    processed_text = self.persian_processor.process_text(raw_text)
                    flight_data[field] = processed_text
    
    def _parse_duration(self, duration_text: str) -> int:
        """
        Parse Persian duration text to minutes.
        
        Override for custom duration parsing logic.
        """
        try:
            # Simple implementation - override in subclasses
            # Example: "2 ساعت و 30 دقیقه" -> 150
            hours = 0
            minutes = 0
            
            if "ساعت" in duration_text:
                hours_match = self.persian_processor.extract_number(duration_text.split("ساعت")[0])
                hours = int(hours_match) if hours_match else 0
            
            if "دقیقه" in duration_text:
                minutes_part = duration_text.split("ساعت")[-1] if "ساعت" in duration_text else duration_text
                minutes_match = self.persian_processor.extract_number(minutes_part.split("دقیقه")[0])
                minutes = int(minutes_match) if minutes_match else 0
            
            return hours * 60 + minutes
            
        except Exception:
            return 0
    
    def _get_required_search_fields(self) -> List[str]:
        """Required fields for Persian flights."""
        return ["origin", "destination", "departure_date", "passengers", "seat_class"]
    
    def _extract_price(self, price_text: str) -> float:
        """
        Extract price from Persian text.
        
        Uses Persian text processor for price extraction.
        """
        return self.persian_processor.process_price(price_text) 