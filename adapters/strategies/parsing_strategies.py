"""
Strategy Pattern implementation for different flight data parsing strategies.

This module provides various parsing strategies for different types of flight sites:
- Persian airlines with Persian text processing
- International airlines with multi-currency support
- Aggregator sites with multiple source handling
- Specialized parsing for specific airlines
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
import logging
import re
from bs4 import BeautifulSoup

# Import text processors
try:
    from data.transformers.persian_text_processor import PersianTextProcessor
except ImportError:
    try:
        from utils.persian_text_processor import PersianTextProcessor
    except ImportError:
        # Fallback processor
        class PersianTextProcessor:
            def process_text(self, text):
                return text

            def process_date(self, date):
                return date

            def process_price(self, price):
                return price

            def extract_number(self, text):
                return text

            def convert_persian_numbers(self, text):
                return text

            def normalize_airline_name(self, text):
                return text


logger = logging.getLogger(__name__)


class ParseContext(Enum):
    """Context for parsing operations."""

    SEARCH_FORM = "search_form"
    FLIGHT_RESULTS = "flight_results"
    FLIGHT_DETAILS = "flight_details"
    PRICE_COMPARISON = "price_comparison"


@dataclass
class ParseResult:
    """Result of parsing operation."""

    success: bool
    data: Dict[str, Any]
    errors: List[str]
    warnings: List[str]

    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []


class FlightParsingStrategy(ABC):
    """Abstract base class for flight parsing strategies."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def parse_flight_element(
        self, element: BeautifulSoup, context: ParseContext
    ) -> ParseResult:
        """Parse a flight element according to the strategy."""
        pass

    @abstractmethod
    def extract_price(self, element: BeautifulSoup, config: Dict[str, Any]) -> float:
        """Extract price from element."""
        pass

    @abstractmethod
    def extract_time(self, element: BeautifulSoup, selector: str) -> str:
        """Extract time from element."""
        pass

    @abstractmethod
    def validate_result(self, result: Dict[str, Any]) -> bool:
        """Validate parsed result."""
        pass

    def _extract_text(self, element: BeautifulSoup, selector: str) -> str:
        """Common text extraction method."""
        try:
            if not selector:
                return ""

            target_element = element.select_one(selector)
            if target_element:
                return target_element.get_text(strip=True)
            return ""
        except Exception as e:
            self.logger.debug(f"Error extracting text with selector '{selector}': {e}")
            return ""

    def _extract_attribute(
        self, element: BeautifulSoup, selector: str, attribute: str
    ) -> str:
        """Extract attribute value from element."""
        try:
            target_element = element.select_one(selector)
            if target_element:
                return target_element.get(attribute, "")
            return ""
        except Exception as e:
            self.logger.debug(f"Error extracting attribute '{attribute}': {e}")
            return ""


class PersianParsingStrategy(FlightParsingStrategy):
    """Strategy for parsing Persian airline flight data."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.persian_processor = PersianTextProcessor()

        # Persian number mappings
        self.persian_to_english = {
            "۰": "0",
            "۱": "1",
            "۲": "2",
            "۳": "3",
            "۴": "4",
            "۵": "5",
            "۶": "6",
            "۷": "7",
            "۸": "8",
            "۹": "9",
        }

        # Common Persian airline mappings
        self.airline_mappings = {
            "ایران ایر": "Iran Air",
            "ماهان": "Mahan Air",
            "آسمان": "Aseman Airlines",
            "کاسپین": "Caspian Airlines",
            "قشم ایر": "Qeshm Air",
            "کارون": "Karun Airlines",
            "سپهران": "Sepehran Airlines",
            "وارش": "Varesh Airlines",
            "تابان": "Taban Air",
            "عطا": "Ata Airlines",
        }

    def parse_flight_element(
        self, element: BeautifulSoup, context: ParseContext
    ) -> ParseResult:
        """Parse Persian flight element with Persian text processing."""
        errors = []
        warnings = []

        try:
            config = self.config.get("extraction_config", {}).get("results_parsing", {})

            # Extract basic flight information
            flight_data = {
                "flight_number": self._extract_flight_number_persian(element, config),
                "airline": self._extract_airline_persian(element, config),
                "departure_time": self._extract_time_persian(
                    element, config.get("departure_time")
                ),
                "arrival_time": self._extract_time_persian(
                    element, config.get("arrival_time")
                ),
                "duration_minutes": self._extract_duration_persian(element, config),
                "price": self.extract_price(element, config),
                "currency": "IRR",
                "seat_class": self._extract_seat_class_persian(element, config),
                "aircraft_type": self._extract_text(
                    element, config.get("aircraft_type")
                ),
                "route": self._extract_route_persian(element, config),
            }

            # Extract Persian-specific fields
            persian_fields = self._extract_persian_specific_fields(element, config)
            flight_data.update(persian_fields)

            # Process Persian text
            flight_data = self._process_persian_text_fields(flight_data)

            # Validate result
            is_valid = self.validate_result(flight_data)

            return ParseResult(
                success=is_valid, data=flight_data, errors=errors, warnings=warnings
            )

        except Exception as e:
            errors.append(f"Error parsing Persian flight element: {str(e)}")
            return ParseResult(success=False, data={}, errors=errors, warnings=warnings)

    def extract_price(self, element: BeautifulSoup, config: Dict[str, Any]) -> float:
        """Extract price with Persian number processing."""
        try:
            price_text = self._extract_text(element, config.get("price"))
            if not price_text:
                return 0.0

            # Process Persian text
            processed_text = self.persian_processor.process_price(price_text)

            # Convert Persian numbers to English
            for persian, english in self.persian_to_english.items():
                processed_text = processed_text.replace(persian, english)

            # Extract numeric value
            price_match = re.search(r"[\d,]+", processed_text.replace(",", ""))
            if price_match:
                return float(price_match.group().replace(",", ""))

            return 0.0

        except Exception as e:
            self.logger.warning(f"Error extracting Persian price: {e}")
            return 0.0

    def extract_time(self, element: BeautifulSoup, selector: str) -> str:
        """Extract time with Persian processing."""
        try:
            time_text = self._extract_text(element, selector)
            if not time_text:
                return ""

            # Process Persian time text
            processed_time = self.persian_processor.parse_time(time_text)

            # Convert Persian numbers
            for persian, english in self.persian_to_english.items():
                processed_time = processed_time.replace(persian, english)

            return processed_time

        except Exception as e:
            self.logger.warning(f"Error extracting Persian time: {e}")
            return ""

    def validate_result(self, result: Dict[str, Any]) -> bool:
        """Validate Persian flight result."""
        try:
            # Required fields for Persian flights
            required_fields = [
                "flight_number",
                "airline",
                "departure_time",
                "arrival_time",
                "price",
            ]

            for field in required_fields:
                if not result.get(field):
                    return False

            # Price validation
            price = result.get("price", 0)
            if price <= 0 or price > 50000000:  # Reasonable range for IRR
                return False

            # Time validation
            departure_time = result.get("departure_time", "")
            arrival_time = result.get("arrival_time", "")
            if not departure_time or not arrival_time:
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error validating Persian result: {e}")
            return False

    def _extract_flight_number_persian(
        self, element: BeautifulSoup, config: Dict[str, Any]
    ) -> str:
        """Extract flight number with Persian processing."""
        flight_number = self._extract_text(element, config.get("flight_number"))
        if flight_number:
            return self.persian_processor.clean_flight_number(flight_number)
        return ""

    def _extract_airline_persian(
        self, element: BeautifulSoup, config: Dict[str, Any]
    ) -> str:
        """Extract airline name with Persian mapping."""
        airline_text = self._extract_text(element, config.get("airline"))
        if airline_text:
            processed_airline = self.persian_processor.normalize_airline_name(
                airline_text
            )
            # Map Persian name to English if available
            return self.airline_mappings.get(processed_airline, processed_airline)
        return ""

    def _extract_time_persian(self, element: BeautifulSoup, selector: str) -> str:
        """Extract time with Persian text processing."""
        return self.extract_time(element, selector)

    def _extract_duration_persian(
        self, element: BeautifulSoup, config: Dict[str, Any]
    ) -> int:
        """Extract duration in minutes with Persian processing."""
        try:
            duration_text = self._extract_text(element, config.get("duration"))
            if duration_text:
                return self.persian_processor.extract_duration(duration_text)
            return 0
        except Exception as e:
            self.logger.warning(f"Error extracting Persian duration: {e}")
            return 0

    def _extract_seat_class_persian(
        self, element: BeautifulSoup, config: Dict[str, Any]
    ) -> str:
        """Extract seat class with Persian processing."""
        seat_class = self._extract_text(element, config.get("seat_class"))
        if seat_class:
            return self.persian_processor.normalize_seat_class(seat_class)
        return ""

    def _extract_route_persian(
        self, element: BeautifulSoup, config: Dict[str, Any]
    ) -> str:
        """Extract route information."""
        origin = self._extract_text(element, config.get("origin"))
        destination = self._extract_text(element, config.get("destination"))

        if origin and destination:
            return f"{origin}-{destination}"
        return ""

    def _extract_persian_specific_fields(
        self, element: BeautifulSoup, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract Persian airline specific fields."""
        fields = {}

        # Charter flight information
        charter_info = self._extract_text(element, config.get("charter_indicator"))
        if charter_info:
            fields["is_charter"] = (
                "چارتر" in charter_info or "charter" in charter_info.lower()
            )
            fields["charter_info"] = charter_info

        # Baggage information
        baggage_info = self._extract_text(element, config.get("baggage_allowance"))
        if baggage_info:
            fields["baggage_allowance"] = self.persian_processor.process_text(
                baggage_info
            )

        # Meal service
        meal_info = self._extract_text(element, config.get("meal_service"))
        if meal_info:
            fields["meal_service"] = self.persian_processor.process_text(meal_info)
            fields["has_meal"] = "وعده" in meal_info or "غذا" in meal_info

        return fields

    def _process_persian_text_fields(
        self, flight_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process all Persian text fields."""
        text_fields = ["airline", "aircraft_type", "seat_class"]

        for field in text_fields:
            if field in flight_data and flight_data[field]:
                flight_data[field] = self.persian_processor.process_text(
                    flight_data[field]
                )

        return flight_data


class InternationalParsingStrategy(FlightParsingStrategy):
    """Strategy for parsing international airline flight data."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)

        # Currency symbols mapping
        self.currency_symbols = {
            "USD": ["$", "USD", "US$"],
            "EUR": ["€", "EUR", "Euro"],
            "GBP": ["£", "GBP", "Pound"],
            "AED": ["AED", "د.إ"],
            "TRY": ["TRY", "₺", "TL"],
            "QAR": ["QAR", "ر.ق"],
            "CAD": ["CAD", "C$"],
            "AUD": ["AUD", "A$"],
            "JPY": ["JPY", "¥", "Yen"],
        }

    def parse_flight_element(
        self, element: BeautifulSoup, context: ParseContext
    ) -> ParseResult:
        """Parse international flight element."""
        errors = []
        warnings = []

        try:
            config = self.config.get("extraction_config", {}).get("results_parsing", {})

            # Extract basic flight information
            flight_data = {
                "flight_number": self._extract_text(
                    element, config.get("flight_number")
                ),
                "airline": self._extract_text(element, config.get("airline")),
                "departure_time": self.extract_time(
                    element, config.get("departure_time")
                ),
                "arrival_time": self.extract_time(element, config.get("arrival_time")),
                "duration_minutes": self._extract_duration_international(
                    element, config
                ),
                "price": self.extract_price(element, config),
                "currency": self._extract_currency(element, config),
                "seat_class": self._extract_text(element, config.get("seat_class")),
                "aircraft_type": self._extract_text(
                    element, config.get("aircraft_type")
                ),
                "route": self._extract_route(element, config),
            }

            # Extract international-specific fields
            international_fields = self._extract_international_specific_fields(
                element, config
            )
            flight_data.update(international_fields)

            # Validate result
            is_valid = self.validate_result(flight_data)

            return ParseResult(
                success=is_valid, data=flight_data, errors=errors, warnings=warnings
            )

        except Exception as e:
            errors.append(f"Error parsing international flight element: {str(e)}")
            return ParseResult(success=False, data={}, errors=errors, warnings=warnings)

    def extract_price(self, element: BeautifulSoup, config: Dict[str, Any]) -> float:
        """Extract price with multi-currency support."""
        try:
            price_text = self._extract_text(element, config.get("price"))
            if not price_text:
                return 0.0

            # Remove currency symbols and extract numeric value
            cleaned_price = re.sub(r"[^\d,.]", "", price_text)
            cleaned_price = cleaned_price.replace(",", "")

            if cleaned_price:
                return float(cleaned_price)

            return 0.0

        except Exception as e:
            self.logger.warning(f"Error extracting international price: {e}")
            return 0.0

    def extract_time(self, element: BeautifulSoup, selector: str) -> str:
        """Extract time for international flights."""
        try:
            time_text = self._extract_text(element, selector)
            if not time_text:
                return ""

            # Standardize time format
            time_match = re.search(r"(\d{1,2}):(\d{2})", time_text)
            if time_match:
                return f"{time_match.group(1).zfill(2)}:{time_match.group(2)}"

            return time_text

        except Exception as e:
            self.logger.warning(f"Error extracting international time: {e}")
            return ""

    def validate_result(self, result: Dict[str, Any]) -> bool:
        """Validate international flight result."""
        try:
            # Required fields
            required_fields = [
                "flight_number",
                "airline",
                "departure_time",
                "arrival_time",
                "price",
                "currency",
            ]

            for field in required_fields:
                if not result.get(field):
                    return False

            # Price validation
            price = result.get("price", 0)
            if (
                price <= 0 or price > 10000
            ):  # Reasonable range for international flights
                return False

            # Currency validation
            currency = result.get("currency", "")
            if currency not in self.currency_symbols:
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error validating international result: {e}")
            return False

    def _extract_currency(self, element: BeautifulSoup, config: Dict[str, Any]) -> str:
        """Extract currency from price text."""
        try:
            price_text = self._extract_text(element, config.get("price"))

            # Check for currency symbols
            for currency, symbols in self.currency_symbols.items():
                for symbol in symbols:
                    if symbol in price_text:
                        return currency

            # Default currency from config
            return config.get("default_currency", "USD")

        except Exception as e:
            self.logger.warning(f"Error extracting currency: {e}")
            return "USD"

    def _extract_duration_international(
        self, element: BeautifulSoup, config: Dict[str, Any]
    ) -> int:
        """Extract duration for international flights."""
        try:
            duration_text = self._extract_text(element, config.get("duration"))
            if not duration_text:
                return 0

            # Parse duration in format like "2h 30m" or "150 min"
            hours_match = re.search(r"(\d+)h", duration_text)
            minutes_match = re.search(r"(\d+)m", duration_text)

            hours = int(hours_match.group(1)) if hours_match else 0
            minutes = int(minutes_match.group(1)) if minutes_match else 0

            # Check for total minutes format
            if hours == 0 and minutes == 0:
                total_minutes_match = re.search(r"(\d+)\s*min", duration_text)
                if total_minutes_match:
                    minutes = int(total_minutes_match.group(1))

            return hours * 60 + minutes

        except Exception as e:
            self.logger.warning(f"Error extracting international duration: {e}")
            return 0

    def _extract_route(self, element: BeautifulSoup, config: Dict[str, Any]) -> str:
        """Extract route information."""
        origin = self._extract_text(element, config.get("origin"))
        destination = self._extract_text(element, config.get("destination"))

        if origin and destination:
            return f"{origin}-{destination}"
        return ""

    def _extract_international_specific_fields(
        self, element: BeautifulSoup, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract international airline specific fields."""
        fields = {}

        # Layover information
        layover_info = self._extract_text(element, config.get("layover_info"))
        if layover_info:
            fields["layover_info"] = layover_info
            fields["has_layover"] = (
                "stop" in layover_info.lower() or "layover" in layover_info.lower()
            )

        # Baggage information
        baggage_info = self._extract_text(element, config.get("baggage_info"))
        if baggage_info:
            fields["baggage_info"] = baggage_info

        # Miles/Points information
        miles_info = self._extract_text(element, config.get("miles_info"))
        if miles_info:
            fields["miles_info"] = miles_info

        # Lounge access
        lounge_access = self._extract_text(element, config.get("lounge_access"))
        if lounge_access:
            fields["lounge_access"] = lounge_access

        return fields


class AggregatorParsingStrategy(FlightParsingStrategy):
    """Strategy for parsing aggregator site flight data."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.persian_processor = PersianTextProcessor()

    def parse_flight_element(
        self, element: BeautifulSoup, context: ParseContext
    ) -> ParseResult:
        """Parse aggregator flight element with multiple source handling."""
        errors = []
        warnings = []

        try:
            config = self.config.get("extraction_config", {}).get("results_parsing", {})

            # Extract basic flight information
            flight_data = {
                "flight_number": self._extract_text(
                    element, config.get("flight_number")
                ),
                "airline": self._extract_text(element, config.get("airline")),
                "departure_time": self.extract_time(
                    element, config.get("departure_time")
                ),
                "arrival_time": self.extract_time(element, config.get("arrival_time")),
                "duration_minutes": self._extract_duration_aggregator(element, config),
                "price": self.extract_price(element, config),
                "currency": self._extract_currency_aggregator(element, config),
                "seat_class": self._extract_text(element, config.get("seat_class")),
                "route": self._extract_route(element, config),
                "is_aggregator": True,
            }

            # Extract aggregator-specific fields
            aggregator_fields = self._extract_aggregator_specific_fields(
                element, config
            )
            flight_data.update(aggregator_fields)

            # Process text based on detected language
            flight_data = self._process_aggregator_text_fields(flight_data)

            # Validate result
            is_valid = self.validate_result(flight_data)

            return ParseResult(
                success=is_valid, data=flight_data, errors=errors, warnings=warnings
            )

        except Exception as e:
            errors.append(f"Error parsing aggregator flight element: {str(e)}")
            return ParseResult(success=False, data={}, errors=errors, warnings=warnings)

    def extract_price(self, element: BeautifulSoup, config: Dict[str, Any]) -> float:
        """Extract price with aggregator-specific handling."""
        try:
            price_text = self._extract_text(element, config.get("price"))
            if not price_text:
                return 0.0

            # Check if it contains Persian numbers
            if any(persian_char in price_text for persian_char in "۰۱۲۳۴۵۶۷۸۹"):
                # Use Persian processing
                processed_text = self.persian_processor.process_price(price_text)
                persian_to_english = {
                    "۰": "0",
                    "۱": "1",
                    "۲": "2",
                    "۳": "3",
                    "۴": "4",
                    "۵": "5",
                    "۶": "6",
                    "۷": "7",
                    "۸": "8",
                    "۹": "9",
                }
                for persian, english in persian_to_english.items():
                    processed_text = processed_text.replace(persian, english)
                price_text = processed_text

            # Extract numeric value
            cleaned_price = re.sub(r"[^\d,.]", "", price_text)
            cleaned_price = cleaned_price.replace(",", "")

            if cleaned_price:
                return float(cleaned_price)

            return 0.0

        except Exception as e:
            self.logger.warning(f"Error extracting aggregator price: {e}")
            return 0.0

    def extract_time(self, element: BeautifulSoup, selector: str) -> str:
        """Extract time with aggregator-specific handling."""
        try:
            time_text = self._extract_text(element, selector)
            if not time_text:
                return ""

            # Check if it contains Persian numbers
            if any(persian_char in time_text for persian_char in "۰۱۲۳۴۵۶۷۸۹"):
                # Use Persian processing
                processed_time = self.persian_processor.parse_time(time_text)
                persian_to_english = {
                    "۰": "0",
                    "۱": "1",
                    "۲": "2",
                    "۳": "3",
                    "۴": "4",
                    "۵": "5",
                    "۶": "6",
                    "۷": "7",
                    "۸": "8",
                    "۹": "9",
                }
                for persian, english in persian_to_english.items():
                    processed_time = processed_time.replace(persian, english)
                time_text = processed_time

            # Standardize time format
            time_match = re.search(r"(\d{1,2}):(\d{2})", time_text)
            if time_match:
                return f"{time_match.group(1).zfill(2)}:{time_match.group(2)}"

            return time_text

        except Exception as e:
            self.logger.warning(f"Error extracting aggregator time: {e}")
            return ""

    def validate_result(self, result: Dict[str, Any]) -> bool:
        """Validate aggregator flight result."""
        try:
            # Required fields
            required_fields = [
                "flight_number",
                "airline",
                "departure_time",
                "arrival_time",
                "price",
            ]

            for field in required_fields:
                if not result.get(field):
                    return False

            # Price validation (broader range for aggregators)
            price = result.get("price", 0)
            if price <= 0 or price > 100000000:  # Very broad range
                return False

            # Must have source information for aggregators
            if not result.get("source_airline") and not result.get("booking_source"):
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error validating aggregator result: {e}")
            return False

    def _extract_currency_aggregator(
        self, element: BeautifulSoup, config: Dict[str, Any]
    ) -> str:
        """Extract currency for aggregator sites."""
        try:
            price_text = self._extract_text(element, config.get("price"))

            # Check for common currency indicators
            if "تومان" in price_text or "ریال" in price_text:
                return "IRR"
            elif "$" in price_text:
                return "USD"
            elif "€" in price_text:
                return "EUR"
            elif "£" in price_text:
                return "GBP"

            # Default from config
            return config.get("default_currency", "IRR")

        except Exception as e:
            self.logger.warning(f"Error extracting aggregator currency: {e}")
            return "IRR"

    def _extract_duration_aggregator(
        self, element: BeautifulSoup, config: Dict[str, Any]
    ) -> int:
        """Extract duration for aggregator sites."""
        try:
            duration_text = self._extract_text(element, config.get("duration"))
            if not duration_text:
                return 0

            # Check if it contains Persian text
            if any(persian_char in duration_text for persian_char in "ساعتدقیقه"):
                return self.persian_processor.extract_duration(duration_text)

            # Parse international format
            hours_match = re.search(r"(\d+)h", duration_text)
            minutes_match = re.search(r"(\d+)m", duration_text)

            hours = int(hours_match.group(1)) if hours_match else 0
            minutes = int(minutes_match.group(1)) if minutes_match else 0

            return hours * 60 + minutes

        except Exception as e:
            self.logger.warning(f"Error extracting aggregator duration: {e}")
            return 0

    def _extract_route(self, element: BeautifulSoup, config: Dict[str, Any]) -> str:
        """Extract route information."""
        origin = self._extract_text(element, config.get("origin"))
        destination = self._extract_text(element, config.get("destination"))

        if origin and destination:
            return f"{origin}-{destination}"
        return ""

    def _extract_aggregator_specific_fields(
        self, element: BeautifulSoup, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract aggregator-specific fields."""
        fields = {}

        # Source airline (original airline)
        source_airline = self._extract_text(element, config.get("source_airline"))
        if source_airline:
            fields["source_airline"] = source_airline

        # Booking source
        booking_source = self._extract_text(element, config.get("booking_source"))
        if booking_source:
            fields["booking_source"] = booking_source

        # Discount information
        discount_info = self._extract_text(element, config.get("discount_info"))
        if discount_info:
            fields["discount_info"] = discount_info

        # Booking reference
        booking_ref = self._extract_text(element, config.get("booking_reference"))
        if booking_ref:
            fields["booking_reference"] = booking_ref

        # Additional fees
        additional_fees = self._extract_text(element, config.get("additional_fees"))
        if additional_fees:
            fields["additional_fees"] = additional_fees

        return fields

    def _process_aggregator_text_fields(
        self, flight_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process text fields based on detected language."""
        text_fields = ["airline", "source_airline", "discount_info"]

        for field in text_fields:
            if field in flight_data and flight_data[field]:
                text = flight_data[field]
                # If contains Persian characters, process with Persian processor
                if any(
                    persian_char in text
                    for persian_char in "ابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی"
                ):
                    flight_data[field] = self.persian_processor.process_text(text)

        return flight_data


class ParsingStrategyFactory:
    """Factory for creating parsing strategies."""

    @staticmethod
    def create_strategy(
        strategy_type: str, config: Dict[str, Any]
    ) -> FlightParsingStrategy:
        """Create parsing strategy based on type."""
        strategies = {
            "persian": PersianParsingStrategy,
            "international": InternationalParsingStrategy,
            "aggregator": AggregatorParsingStrategy,
        }

        strategy_class = strategies.get(strategy_type.lower())
        if not strategy_class:
            raise ValueError(f"Unknown parsing strategy: {strategy_type}")

        return strategy_class(config)

    @staticmethod
    def auto_detect_strategy(config: Dict[str, Any]) -> FlightParsingStrategy:
        """Auto-detect parsing strategy based on config."""
        # Check for Persian indicators
        if config.get("currency") == "IRR" or config.get("language") == "persian":
            return PersianParsingStrategy(config)

        # Check for aggregator indicators
        if config.get("is_aggregator") or "aggregator" in config.get("features", []):
            return AggregatorParsingStrategy(config)

        # Default to international
        return InternationalParsingStrategy(config)
