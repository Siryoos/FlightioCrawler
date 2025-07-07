import re
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import jdatetime
from config import config

# Try to import RTL text processing libraries
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    HAS_RTL_SUPPORT = True
except ImportError:
    HAS_RTL_SUPPORT = False

try:
    from persian_tools import digits
    HAS_PERSIAN_TOOLS = True
except ImportError:
    HAS_PERSIAN_TOOLS = False

# Configure logging
logger = logging.getLogger(__name__)


class PersianTextProcessor:
    """
    Unified Persian text processor with comprehensive functionality.
    
    This is the canonical implementation that combines all Persian text processing features:
    - Persian/Arabic numeral conversion
    - RTL text processing and bidirectional text support
    - Persian date handling (Jalali calendar)
    - Airline name normalization
    - Airport code mapping
    - Price extraction with currency detection
    - Time parsing with various formats
    - Duration parsing
    """

    def __init__(self):
        # Persian and Arabic number mappings
        self.persian_numbers = {
            "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
            "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
            "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
            "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
        }
        
        # Reverse mapping for English to Persian
        self.english_to_persian = {v: k for k, v in self.persian_numbers.items() if k.startswith('۰')}

        # Comprehensive airline name mappings
        self.airline_names = {
            "هواپیمایی ایران ایر": "Iran Air",
            "هواپیمایی ماهان": "Mahan Air",
            "هواپیمایی آسمان": "Aseman Airlines",
            "هواپیمایی کاسپین": "Caspian Airlines",
            "هواپیمایی زاگرس": "Zagros Airlines",
            "هواپیمایی کیش ایر": "Kish Air",
            "هواپیمایی آتا": "Ata Airlines",
            "هواپیمایی وارش": "Varesh Airlines",
            "هواپیمایی قشم ایر": "Qeshm Air",
            "هواپیمایی کیش": "Kish Airline",
            "هواپیمایی معراج": "Meraj Airlines",
            "هواپیمایی نفت": "Naft Airlines",
            "هواپیمایی تابان": "Taban Airlines",
            "هواپیمایی ساها": "Saha Airlines",
            "هواپیمایی آریا": "Aria Airlines",
            "هواپیمایی پارس": "Pouya Air",
            "هواپیمایی کاسکو": "Caspian Airlines",
            "هواپیمایی فارس ایر": "Fars Air Qeshm",
            "هواپیمایی ایران ایرتور": "Iran Airtour",
            "هواپیمایی کارون": "Karun Airlines",
            "هواپیمایی سپهران": "Sepehran Airlines",
            # Short versions
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

        # Comprehensive airport code mappings
        self.airport_codes = {
            "تهران": "THR", "مشهد": "MHD", "شیراز": "SYZ", "اصفهان": "IFN",
            "تبریز": "TBZ", "اهواز": "AWZ", "کرج": "KIH", "کرمانشاه": "KSH",
            "بندرعباس": "BND", "بوشهر": "BUZ", "چابهار": "ZBR", "زاهدان": "ZAH",
            "ساری": "SRY", "سنندج": "SNX", "شهرکرد": "CQD", "کرمان": "KER",
            "گرگان": "GBT", "یزد": "AZD", "ارومیه": "OMH", "بندر لنگه": "BDH",
            "جهرم": "JAR", "خرم آباد": "KHD", "دزفول": "DEF", "رامسر": "RZR",
            "زنجان": "JWN", "سیرجان": "SYJ", "شاهرود": "RUD", "قشم": "QSH",
            "کیش": "KIH", "لار": "LRR", "لامرد": "LFM", "ماهشهر": "MRX",
            "نوشهر": "NSH", "هوایی": "THR",
        }

        # Seat class mappings
        self.seat_classes = {
            "اکونومی": "economy",
            "بیزینس": "business",
            "فرست کلاس": "first class",
            "کلاس اقتصادی": "economy",
            "کلاس تجاری": "business",
            "کلاس اول": "first class",
            "درجه یک": "first class",
            "درجه دو": "economy",
            "درجه سه": "economy",
            "پریمیوم اکونومی": "premium_economy",
            "کابین اقتصادی": "economy",
            "کابین تجاری": "business",
            "کابین اول": "first",
        }

        # Currency symbol mappings
        self.currency_symbols = {
            "تومان": "IRR",
            "ریال": "IRR",
            "دلار": "USD",
            "یورو": "EUR",
            "پوند": "GBP",
            "درهم": "AED",
            "لیر": "TRY",
        }

        # Time parsing patterns
        self.time_formats = [
            r"(\d{1,2}):(\d{2})",
            r"(\d{1,2})\.(\d{2})",
            r"(\d{1,2}) بامداد",
            r"(\d{1,2}) صبح",
            r"(\d{1,2}) بعد از ظهر",
            r"(\d{1,2}) عصر",
        ]

    def process(self, text: str) -> str:
        """
        Main text processing method - legacy interface maintained for compatibility.
        """
        return self.process_text(text)

    def process_text(self, text: str) -> str:
        """
        Process Persian text with comprehensive normalization.
        """
        if not text:
            return text

        # Convert Persian numbers to English
        text = self.convert_persian_numerals(text)

        # Normalize Persian text for RTL display if supported
        if HAS_RTL_SUPPORT:
            text = self.normalize_persian_text(text)

        # Normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()

        return text

    def normalize_persian_text(self, text: str) -> str:
        """
        Normalize Persian text for consistent processing with RTL support.
        """
        if not text:
            return text

        try:
            if HAS_RTL_SUPPORT:
                # Reshape Arabic text for proper display
                reshaped_text = arabic_reshaper.reshape(text)
                # Handle bidirectional text
                display_text = get_display(reshaped_text)
                return display_text
            else:
                # Basic normalization without RTL support
                return text.strip()
        except Exception as e:
            logger.error(f"Error normalizing Persian text: {e}")
            return text

    def convert_persian_numerals(self, text: str) -> str:
        """
        Convert Persian and Arabic numerals to English.
        """
        if not text:
            return text

        try:
            for persian, english in self.persian_numbers.items():
                text = text.replace(persian, english)
            return text
        except Exception as e:
            logger.error(f"Error converting Persian numerals: {e}")
            return text

    def convert_english_to_persian_numerals(self, text: str) -> str:
        """
        Convert English numerals to Persian.
        """
        if not text:
            return text

        try:
            for english, persian in self.english_to_persian.items():
                text = text.replace(english, persian)
            return text
        except Exception as e:
            logger.error(f"Error converting to Persian numerals: {e}")
            return text

    def _convert_numbers(self, text: str) -> str:
        """
        Legacy method - delegates to convert_persian_numerals.
        """
        return self.convert_persian_numerals(text)

    def parse_persian_date(self, date_str: str) -> datetime:
        """
        Parse Persian date string to datetime.
        """
        try:
            # Remove any non-numeric characters except /
            date_str = re.sub(r"[^\d/]", "", date_str)

            # Split date components
            year, month, day = map(int, date_str.split("/"))

            # Convert to Gregorian
            jdate = jdatetime.date(year, month, day)
            gdate = jdate.togregorian()

            return datetime.combine(gdate, datetime.min.time())
        except Exception as e:
            logger.error(f"Error parsing Persian date {date_str}: {e}")
            return datetime.now()

    def convert_jalali_date(self, jalali_date_str: str) -> datetime:
        """
        Convert Jalali (Persian) date to Gregorian - enhanced version.
        """
        try:
            # Convert Persian numerals first
            jalali_date_str = self.convert_persian_numerals(jalali_date_str)
            
            # Parse various Persian date formats
            formats = ["%Y/%m/%d", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]

            for fmt in formats:
                try:
                    jalali_date = jdatetime.datetime.strptime(jalali_date_str, fmt)
                    return jalali_date.togregorian()
                except ValueError:
                    continue

            # Fallback to parse_persian_date
            return self.parse_persian_date(jalali_date_str)
        except Exception as e:
            logger.error(f"Error converting Jalali date: {e}")
            return datetime.now()

    def format_persian_date(self, date: datetime) -> str:
        """
        Format datetime to Persian date string.
        """
        try:
            jdate = jdatetime.date.fromgregorian(
                year=date.year, month=date.month, day=date.day
            )
            return f"{jdate.year}/{jdate.month:02d}/{jdate.day:02d}"
        except Exception as e:
            logger.error(f"Error formatting Persian date: {e}")
            return date.strftime("%Y/%m/%d")

    def convert_gregorian_to_jalali(self, gregorian_date: datetime) -> str:
        """
        Convert Gregorian date to Jalali string.
        """
        try:
            jalali_date = jdatetime.date.fromgregorian(date=gregorian_date)
            return jalali_date.strftime("%Y/%m/%d")
        except Exception as e:
            logger.error(f"Error converting to Jalali date: {e}")
            return gregorian_date.strftime("%Y/%m/%d")

    def parse_time(self, time_str: str) -> Optional[datetime]:
        """
        Parse time from various Persian formats.
        """
        time_str = self.process_text(time_str)

        # Try Persian time formats first
        for pattern in self.time_formats:
            match = re.search(pattern, time_str)
            if match:
                hour = int(match.group(1))
                minute = int(match.group(2)) if len(match.groups()) > 1 else 0

                # Handle AM/PM
                if "بعد از ظهر" in time_str or "عصر" in time_str:
                    if hour < 12:
                        hour += 12
                elif "بامداد" in time_str or "صبح" in time_str:
                    if hour == 12:
                        hour = 0

                return datetime.now().replace(
                    hour=hour, minute=minute, second=0, microsecond=0
                )

        # Try standard time formats
        try:
            formats = ["%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M:%S %p"]
            for fmt in formats:
                try:
                    return datetime.strptime(time_str.strip(), fmt)
                except ValueError:
                    continue
        except Exception as e:
            logger.debug(f"Error parsing time: {e}")

        return None

    def normalize_airline_name(self, name: str) -> str:
        """
        Normalize airline name with enhanced mapping.
        """
        name = self.process_text(name)
        
        # Check direct mappings first
        if name in self.airline_names:
            return self.airline_names[name]
        
        # Check partial matches
        for persian, english in self.airline_names.items():
            if persian in name:
                return english
                
        return name

    def get_airport_code(self, city_name: str) -> Optional[str]:
        """
        Get airport code for city name.
        """
        city_name = self.process_text(city_name)
        return self.airport_codes.get(city_name)

    def normalize_seat_class(self, seat_class: str) -> str:
        """
        Normalize seat class with enhanced mapping.
        """
        seat_class = self.process_text(seat_class).lower()
        
        # Check direct mappings
        for persian, english in self.seat_classes.items():
            if persian in seat_class:
                return english
                
        return seat_class.lower()

    def extract_price(self, price_text: str) -> Tuple[float, str]:
        """
        Extract price and currency from text.
        """
        try:
            # Find currency
            currency = "IRR"  # Default to IRR
            for symbol, code in self.currency_symbols.items():
                if symbol in price_text:
                    currency = code
                    break

            # Remove currency symbols and commas
            price_text = re.sub(r"[^\d.]", "", self.process_text(price_text))

            # Convert to float
            price = float(price_text)

            # Convert to IRR if needed
            if currency == "IRR" and price < 1000:  # Assume it's in Toman
                price *= 10

            return price, currency
        except Exception as e:
            logger.error(f"Error extracting price from {price_text}: {e}")
            return 0.0, "IRR"

    def parse_persian_price(self, price_text: str) -> dict:
        """
        Parse Persian price text and extract amount/currency - enhanced version.
        """
        try:
            # Convert numerals first
            price_text = self.convert_persian_numerals(price_text)

            # Extract numbers
            numbers = re.findall(r"[\d,]+", price_text)
            if not numbers:
                return {"amount": None, "currency": None}

            amount = int(numbers[0].replace(",", ""))

            # Detect currency
            currency = "IRR"  # Default
            for symbol, code in self.currency_symbols.items():
                if symbol in price_text:
                    currency = code
                    break

            return {"amount": amount, "currency": currency}
        except Exception as e:
            logger.error(f"Error parsing Persian price: {e}")
            return {"amount": None, "currency": None}

    def extract_duration(self, duration_text: str) -> int:
        """
        Extract duration in minutes from text with enhanced parsing.
        """
        try:
            processed = self.process_text(duration_text)

            # Look for explicit hours and minutes patterns first
            hours = 0
            minutes = 0

            # Persian duration patterns
            hour_match = re.search(r"(\d+)\s*(?:ساعت|hour)", processed, re.IGNORECASE)
            if hour_match:
                hours = int(hour_match.group(1))

            minute_match = re.search(r"(\d+)\s*(?:دقیقه|minute)", processed, re.IGNORECASE)
            if minute_match:
                minutes = int(minute_match.group(1))

            # If we found hours or minutes, return the total
            if hours > 0 or minutes > 0:
                return hours * 60 + minutes

            # Try to extract from HH:MM format
            time_match = re.search(r"(\d{1,2}):(\d{2})", processed)
            if time_match:
                return int(time_match.group(1)) * 60 + int(time_match.group(2))

            # Try to extract just a number (assume minutes)
            number_match = re.search(r"(\d+)", processed)
            if number_match:
                return int(number_match.group(1))

            return 0
        except Exception as e:
            logger.error(f"Error extracting duration from {duration_text}: {e}")
            return 0

    def extract_flight_duration(self, duration_text: str) -> int:
        """
        Extract flight duration in minutes from Persian text - alias for extract_duration.
        """
        return self.extract_duration(duration_text)

    def calculate_duration(self, departure: datetime, arrival: datetime) -> int:
        """
        Calculate duration between departure and arrival times.
        """
        try:
            if arrival < departure:
                # Handle next day arrivals
                arrival += timedelta(days=1)
            
            delta = arrival - departure
            return int(delta.total_seconds() / 60)
        except Exception as e:
            logger.error(f"Error calculating duration: {e}")
            return 0

    # Legacy method aliases for backward compatibility
    def process_date(self, date):
        """Legacy alias for parse_persian_date"""
        if isinstance(date, str):
            return self.parse_persian_date(date)
        return date

    def process_price(self, price):
        """Legacy alias for extract_price"""
        if isinstance(price, str):
            return self.extract_price(price)
        return price

    def extract_number(self, text):
        """Legacy alias for convert_persian_numerals"""
        return self.convert_persian_numerals(str(text))

    def convert_persian_numbers(self, text):
        """Legacy alias for convert_persian_numerals"""
        return self.convert_persian_numerals(str(text))

    def clean_flight_number(self, text):
        """Legacy method for cleaning flight numbers"""
        return self.process_text(str(text))
