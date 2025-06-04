import re
from typing import Dict, List
from datetime import datetime
import jdatetime

class PersianTextProcessor:
    """Process Persian text and dates"""
    
    def __init__(self):
        self.persian_numbers = {
            '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
            '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9'
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
            'هواپیمایی کیش': 'Kish Airline'
        }
        
        self.seat_classes = {
            'اکونومی': 'economy',
            'بیزینس': 'business',
            'فرست کلاس': 'first class'
        }
    
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
        """Convert Persian numbers to English"""
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
    
    def normalize_airline_name(self, name: str) -> str:
        """Normalize airline name"""
        name = self.process(name)
        return self.airline_names.get(name, name)
    
    def normalize_seat_class(self, seat_class: str) -> str:
        """Normalize seat class"""
        seat_class = self.process(seat_class)
        return self.seat_classes.get(seat_class, seat_class.lower())
    
    def extract_price(self, price_text: str) -> float:
        """Extract price from text"""
        try:
            # Remove currency symbols and commas
            price_text = re.sub(r'[^\d.]', '', self.process(price_text))
            return float(price_text)
        except Exception as e:
            print(f"Error extracting price from {price_text}: {e}")
            return 0.0
    
    def extract_duration(self, duration_text: str) -> int:
        """Extract duration in minutes from text"""
        try:
            # Remove non-numeric characters
            duration_text = re.sub(r'[^\d]', '', self.process(duration_text))
            return int(duration_text)
        except Exception as e:
            print(f"Error extracting duration from {duration_text}: {e}")
            return 0 