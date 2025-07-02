"""
Enhanced base adapters for flight crawling.
"""

# Only import the new enhanced classes
from .enhanced_base_crawler import EnhancedBaseCrawler
from .enhanced_international_adapter import EnhancedInternationalAdapter
from .enhanced_persian_adapter import EnhancedPersianAdapter

__all__ = [
    'EnhancedBaseCrawler',
    'EnhancedInternationalAdapter', 
    'EnhancedPersianAdapter'
] 