import arabic_reshaper
from bidi.algorithm import get_display
import re
from datetime import datetime
import jdatetime
import logging

class PersianTextProcessor:
    """Processor for Persian text with RTL, Jalali calendar, and numeral support"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.persian_to_english_map = {
            '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
            '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9'
        }
        self.english_to_persian_map = {v: k for k, v in self.persian_to_english_map.items()}
        
    def normalize_persian_text(self, text: str) -> str:
        """Normalize Persian text for consistent processing"""
        if not text:
            return text
            
        try:
            # Reshape Arabic text for proper display
            reshaped_text = arabic_reshaper.reshape(text)
            # Handle bidirectional text
            display_text = get_display(reshaped_text)
            return display_text
        except Exception as e:
            self.logger.error(f"Error normalizing Persian text: {e}")
            return text
        
    def convert_persian_numerals(self, text: str) -> str:
        """Convert Persian numerals to English"""
        if not text:
            return text
            
        try:
            for persian, english in self.persian_to_english_map.items():
                text = text.replace(persian, english)
            return text
        except Exception as e:
            self.logger.error(f"Error converting Persian numerals: {e}")
            return text
            
    def convert_english_to_persian_numerals(self, text: str) -> str:
        """Convert English numerals to Persian"""
        if not text:
            return text
            
        try:
            for english, persian in self.english_to_persian_map.items():
                text = text.replace(english, persian)
            return text
        except Exception as e:
            self.logger.error(f"Error converting to Persian numerals: {e}")
            return text
        
    def parse_persian_price(self, price_text: str) -> dict:
        """Parse Persian price text and extract amount/currency"""
        try:
            # Convert numerals first
            price_text = self.convert_persian_numerals(price_text)
            
            # Extract numbers
            numbers = re.findall(r'[\d,]+', price_text)
            if not numbers:
                return {"amount": None, "currency": None}
                
            amount = int(numbers[0].replace(',', ''))
            
            # Detect currency
            currency = "IRR"  # Default
            if "دلار" in price_text or "USD" in price_text:
                currency = "USD"
            elif "یورو" in price_text or "EUR" in price_text:
                currency = "EUR"
            elif "درهم" in price_text or "AED" in price_text:
                currency = "AED"
            elif "لیر" in price_text or "TRY" in price_text:
                currency = "TRY"
                
            return {"amount": amount, "currency": currency}
        except Exception as e:
            self.logger.error(f"Error parsing Persian price: {e}")
            return {"amount": None, "currency": None}
        
    def convert_jalali_date(self, jalali_date_str: str) -> datetime:
        """Convert Jalali (Persian) date to Gregorian"""
        try:
            # Parse various Persian date formats
            formats = [
                '%Y/%m/%d',
                '%Y-%m-%d',
                '%d/%m/%Y',
                '%d-%m-%Y'
            ]
            
            for fmt in formats:
                try:
                    jalali_date = jdatetime.datetime.strptime(jalali_date_str, fmt)
                    return jalali_date.togregorian()
                except ValueError:
                    continue
                    
            raise ValueError(f"Could not parse Jalali date: {jalali_date_str}")
        except Exception as e:
            self.logger.error(f"Error converting Jalali date: {e}")
            return None
            
    def convert_gregorian_to_jalali(self, gregorian_date: datetime) -> str:
        """Convert Gregorian date to Jalali string"""
        try:
            jalali_date = jdatetime.date.fromgregorian(date=gregorian_date)
            return jalali_date.strftime('%Y/%m/%d')
        except Exception as e:
            self.logger.error(f"Error converting to Jalali date: {e}")
            return None
            
    def extract_flight_duration(self, duration_text: str) -> int:
        """Extract flight duration in minutes from Persian text"""
        try:
            duration_text = self.convert_persian_numerals(duration_text)
            
            hours = 0
            minutes = 0
            
            hour_match = re.search(r'(\d+)\s*ساعت', duration_text)
            if hour_match:
                hours = int(hour_match.group(1))
                
            minute_match = re.search(r'(\d+)\s*دقیقه', duration_text)
            if minute_match:
                minutes = int(minute_match.group(1))
                
            return hours * 60 + minutes
        except Exception as e:
            self.logger.error(f"Error extracting flight duration: {e}")
            return None
            
    def normalize_seat_class(self, class_text: str) -> str:
        """Normalize seat class text to standard format"""
        try:
            class_text = self.normalize_persian_text(class_text).lower()
            
            # Map Persian class names to standard English
            class_mapping = {
                'اکونومی': 'economy',
                'بیزنس': 'business',
                'فرست': 'first',
                'پریمیوم اکونومی': 'premium_economy',
                'کابین اقتصادی': 'economy',
                'کابین تجاری': 'business',
                'کابین اول': 'first'
            }
            
            for persian, english in class_mapping.items():
                if persian in class_text:
                    return english
                    
            return 'economy'  # Default to economy
        except Exception as e:
            self.logger.error(f"Error normalizing seat class: {e}")
            return 'economy'
            
    def parse_time(self, time_text: str) -> datetime:
        """Parse time from Persian text"""
        try:
            time_text = self.convert_persian_numerals(time_text)
            
            # Try different time formats
            formats = [
                '%H:%M',
                '%H:%M:%S',
                '%I:%M %p',
                '%I:%M:%S %p'
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(time_text.strip(), fmt)
                except ValueError:
                    continue
                    
            raise ValueError(f"Could not parse time: {time_text}")
        except Exception as e:
            self.logger.error(f"Error parsing time: {e}")
            return None 