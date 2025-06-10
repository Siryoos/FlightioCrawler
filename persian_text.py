import re
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import jdatetime
from config import config
from persian_tools import digits

# Configure logging
logger = logging.getLogger(__name__)

class PersianTextProcessor:
    """Process Persian text and dates"""
    
    def __init__(self):
        self.persian_numbers = {
            '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
            '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9',
            '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
            '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'
        }
        
        self.airline_names = {
            'هواپیمایی ایران ایر': 'Iran Air',
            'هواپیمایی ماهان': 'Mahan Air',
            'هواپیمایی آسمان': 'Aseman Airlines',
            'هواپیمایی کاسپین': 'Caspian Airlines',
            'هواپیمایی زاگرس': 'Zagros Airlines',
            'هواپیمایی کیش ایر': 'Kish Air',
            'هواپیمایی آتا': 'Ata Airlines',
            'هواپیمایی وارش': 'Varesh Airlines',
            'هواپیمایی قشم ایر': 'Qeshm Air',
            'هواپیمایی کیش': 'Kish Airline',
            'هواپیمایی معراج': 'Meraj Airlines',
            'هواپیمایی نفت': 'Naft Airlines',
            'هواپیمایی تابان': 'Taban Airlines',
            'هواپیمایی ساها': 'Saha Airlines',
            'هواپیمایی آریا': 'Aria Airlines',
            'هواپیمایی پارس': 'Pouya Air',
            'هواپیمایی کاسکو': 'Caspian Airlines',
            'هواپیمایی فارس ایر': 'Fars Air Qeshm',
            'هواپیمایی آسمان': 'Aseman Airlines',
            'هواپیمایی ایران ایرتور': 'Iran Airtour'
        }
        
        self.airport_codes = {
            'تهران': 'THR',
            'مشهد': 'MHD',
            'شیراز': 'SYZ',
            'اصفهان': 'IFN',
            'تبریز': 'TBZ',
            'اهواز': 'AWZ',
            'کرج': 'KIH',
            'کرمانشاه': 'KSH',
            'بندرعباس': 'BND',
            'بوشهر': 'BUZ',
            'چابهار': 'ZBR',
            'زاهدان': 'ZAH',
            'ساری': 'SRY',
            'سنندج': 'SNX',
            'شهرکرد': 'CQD',
            'کرمان': 'KER',
            'گرگان': 'GBT',
            'یزد': 'AZD',
            'ارومیه': 'OMH',
            'اهواز': 'AWZ',
            'بندر لنگه': 'BDH',
            'بوشهر': 'BUZ',
            'جهرم': 'JAR',
            'خرم آباد': 'KHD',
            'دزفول': 'DEF',
            'رامسر': 'RZR',
            'زنجان': 'JWN',
            'سیرجان': 'SYJ',
            'شاهرود': 'RUD',
            'قشم': 'QSH',
            'کیش': 'KIH',
            'لار': 'LRR',
            'لامرد': 'LFM',
            'ماهشهر': 'MRX',
            'نوشهر': 'NSH',
            'هوایی': 'THR'
        }
        
        self.seat_classes = {
            'اکونومی': 'economy',
            'بیزینس': 'business',
            'فرست کلاس': 'first class',
            'کلاس اقتصادی': 'economy',
            'کلاس تجاری': 'business',
            'کلاس اول': 'first class',
            'درجه یک': 'first class',
            'درجه دو': 'economy',
            'درجه سه': 'economy'
        }
        
        self.currency_symbols = {
            'تومان': 'IRR',
            'ریال': 'IRR',
            'دلار': 'USD',
            'یورو': 'EUR',
            'پوند': 'GBP',
            'درهم': 'AED'
        }
        
        self.time_formats = [
            r'(\d{1,2}):(\d{2})',
            r'(\d{1,2})\.(\d{2})',
            r'(\d{1,2}) بامداد',
            r'(\d{1,2}) صبح',
            r'(\d{1,2}) بعد از ظهر',
            r'(\d{1,2}) عصر'
        ]
    
    def process(self, text: str) -> str:
        """Process Persian text"""
        if not text:
            return text
        
        # Convert Persian numbers to English
        text = self._convert_numbers(text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def _convert_numbers(self, text: str) -> str:
        """Convert Persian and Arabic numbers to English"""
        for persian, english in self.persian_numbers.items():
            text = text.replace(persian, english)
        return text
    
    def parse_persian_date(self, date_str: str) -> datetime:
        """Parse Persian date string to datetime"""
        try:
            # Remove any non-numeric characters except /
            date_str = re.sub(r'[^\d/]', '', date_str)
            
            # Split date components
            year, month, day = map(int, date_str.split('/'))
            
            # Convert to Gregorian
            jdate = jdatetime.date(year, month, day)
            gdate = jdate.togregorian()
            
            return datetime.combine(gdate, datetime.min.time())
        except Exception as e:
            print(f"Error parsing Persian date {date_str}: {e}")
            return datetime.now()
    
    def format_persian_date(self, date: datetime) -> str:
        """Format datetime to Persian date string"""
        try:
            jdate = jdatetime.date.fromgregorian(
                year=date.year,
                month=date.month,
                day=date.day
            )
            return f"{jdate.year}/{jdate.month:02d}/{jdate.day:02d}"
        except Exception as e:
            print(f"Error formatting Persian date: {e}")
            return date.strftime("%Y/%m/%d")
    
    def parse_time(self, time_str: str) -> Optional[datetime]:
        """Parse time from various Persian formats"""
        time_str = self.process(time_str)
        
        for pattern in self.time_formats:
            match = re.search(pattern, time_str)
            if match:
                hour = int(match.group(1))
                minute = int(match.group(2)) if len(match.groups()) > 1 else 0
                
                # Handle AM/PM
                if 'بعد از ظهر' in time_str or 'عصر' in time_str:
                    if hour < 12:
                        hour += 12
                elif 'بامداد' in time_str or 'صبح' in time_str:
                    if hour == 12:
                        hour = 0
                
                return datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        return None
    
    def normalize_airline_name(self, name: str) -> str:
        """Normalize airline name"""
        name = self.process(name)
        return self.airline_names.get(name, name)
    
    def get_airport_code(self, city_name: str) -> Optional[str]:
        """Get airport code for city name"""
        city_name = self.process(city_name)
        return self.airport_codes.get(city_name)
    
    def normalize_seat_class(self, seat_class: str) -> str:
        """Normalize seat class"""
        seat_class = self.process(seat_class)
        return self.seat_classes.get(seat_class, seat_class.lower())
    
    def extract_price(self, price_text: str) -> Tuple[float, str]:
        """Extract price and currency from text"""
        try:
            # Find currency
            currency = 'IRR'  # Default to IRR
            for symbol, code in self.currency_symbols.items():
                if symbol in price_text:
                    currency = code
                    break
            
            # Remove currency symbols and commas
            price_text = re.sub(r'[^\d.]', '', self.process(price_text))
            
            # Convert to float
            price = float(price_text)
            
            # Convert to IRR if needed
            if currency == 'IRR' and price < 1000:  # Assume it's in Toman
                price *= 10
            
            return price, currency
        except Exception as e:
            print(f"Error extracting price from {price_text}: {e}")
            return 0.0, 'IRR'
    
    def extract_duration(self, duration_text: str) -> int:
        """Extract duration in minutes from text"""
        try:
            processed = self.process(duration_text)

            # Determine if the original text specified hours before
            is_hours = 'ساعت' in processed or 'hour' in processed.lower()

            # Remove non-numeric characters to extract the numeric part
            digits_only = re.sub(r'[^\d]', '', processed)
            if not digits_only:
                return 0

            minutes = int(digits_only)
            if is_hours:
                minutes *= 60

            return minutes
        except Exception as e:
            print(f"Error extracting duration from {duration_text}: {e}")
            return 0
    
    def calculate_duration(self, departure: datetime, arrival: datetime) -> int:
        """Calculate flight duration in minutes"""
        try:
            duration = arrival - departure
            return int(duration.total_seconds() / 60)
        except Exception as e:
            print(f"Error calculating duration: {e}")
            return 0 