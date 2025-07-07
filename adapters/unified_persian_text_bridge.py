"""
Unified Persian Text Bridge

This module provides a comprehensive Persian text processing bridge that integrates
Persian text capabilities from all three systems (adapters, requests, crawlers) and
makes the advanced Persian processing features available across all systems.

Features:
- Unified Persian text processing interface
- Advanced Persian text normalization
- Jalali (Persian) calendar integration
- Persian airline and airport mappings
- Persian number conversion
- RTL text processing
- Date and time parsing
- Price and duration extraction
- Compatibility across all crawler systems
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import weakref

# Import the root Persian text processor
try:
    from persian_text import PersianTextProcessor
    ROOT_PERSIAN_AVAILABLE = True
except ImportError:
    ROOT_PERSIAN_AVAILABLE = False
    PersianTextProcessor = None

# Import Persian processing from adapters system
try:
    from .base_adapters.enhanced_persian_adapter import EnhancedPersianAdapter
    from .strategies.parsing_strategies import PersianParsingStrategy
    ADAPTER_PERSIAN_AVAILABLE = True
except ImportError:
    ADAPTER_PERSIAN_AVAILABLE = False
    EnhancedPersianAdapter = None
    PersianParsingStrategy = None

# Import Jalali date support
try:
    import jdatetime
    JALALI_AVAILABLE = True
except ImportError:
    JALALI_AVAILABLE = False

# Import RTL support
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    RTL_AVAILABLE = True
except ImportError:
    RTL_AVAILABLE = False

logger = logging.getLogger(__name__)


class PersianTextLevel(Enum):
    """Persian text processing levels."""
    BASIC = "basic"          # Basic number conversion only
    STANDARD = "standard"    # Numbers + basic text processing
    ADVANCED = "advanced"    # Full Persian processing with RTL
    COMPREHENSIVE = "comprehensive"  # All features including parsing strategies


@dataclass
class PersianProcessingConfig:
    """Configuration for Persian text processing."""
    level: PersianTextLevel = PersianTextLevel.STANDARD
    enable_rtl: bool = True
    enable_jalali_dates: bool = True
    enable_airline_mapping: bool = True
    enable_airport_mapping: bool = True
    enable_price_extraction: bool = True
    enable_duration_parsing: bool = True
    enable_time_parsing: bool = True
    enable_seat_class_mapping: bool = True
    fallback_to_basic: bool = True
    cache_results: bool = True
    system_integration: Dict[str, bool] = field(default_factory=lambda: {
        'adapters': True,
        'requests': True,
        'crawlers': True
    })


@dataclass
class PersianTextResult:
    """Result of Persian text processing."""
    original_text: str
    processed_text: str
    success: bool
    method_used: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


@dataclass
class PersianParsingResult:
    """Result of Persian parsing operations."""
    success: bool
    value: Any
    original_text: str
    method_used: str
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class UnifiedPersianTextBridge:
    """
    Unified Persian text processing bridge that integrates capabilities
    from all systems and provides a consistent interface for Persian text processing.
    """
    
    def __init__(self, config: Optional[PersianProcessingConfig] = None):
        self.config = config or PersianProcessingConfig()
        self.logger = logging.getLogger(__name__)
        
        # Initialize processors
        self.root_processor: Optional[PersianTextProcessor] = None
        self.adapter_capabilities: Dict[str, Any] = {}
        self.parsing_strategies: Dict[str, Any] = {}
        
        # Caching
        self.text_cache: Dict[str, PersianTextResult] = {} if self.config.cache_results else None
        self.parsing_cache: Dict[str, PersianParsingResult] = {} if self.config.cache_results else None
        
        # Performance tracking
        self.processing_stats = {
            'total_processed': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'errors': 0,
            'method_usage': {}
        }
        
        # Initialize Persian processing capabilities
        self._initialize_persian_capabilities()
        
        self.logger.info(f"Unified Persian Text Bridge initialized with level: {self.config.level.value}")

    def _initialize_persian_capabilities(self):
        """Initialize Persian processing capabilities from all systems."""
        try:
            # Initialize root Persian processor
            if ROOT_PERSIAN_AVAILABLE and self.config.level != PersianTextLevel.BASIC:
                self.root_processor = PersianTextProcessor()
                self.logger.info("Root Persian processor initialized")
            
            # Initialize adapter capabilities
            if ADAPTER_PERSIAN_AVAILABLE and self.config.level in [
                PersianTextLevel.ADVANCED, 
                PersianTextLevel.COMPREHENSIVE
            ]:
                self._initialize_adapter_capabilities()
            
            # Initialize parsing strategies
            if self.config.level == PersianTextLevel.COMPREHENSIVE:
                self._initialize_parsing_strategies()
                
        except Exception as e:
            self.logger.error(f"Failed to initialize Persian capabilities: {e}")
            if not self.config.fallback_to_basic:
                raise

    def _initialize_adapter_capabilities(self):
        """Initialize adapter Persian capabilities."""
        try:
            # Create a dummy adapter instance to access methods
            if EnhancedPersianAdapter:
                dummy_config = {'dummy': True}
                # Note: This would need to be adjusted based on actual adapter initialization
                self.adapter_capabilities = {
                    'enhanced_persian_adapter': True,
                    'persian_parsing_strategy': ADAPTER_PERSIAN_AVAILABLE
                }
                self.logger.info("Adapter Persian capabilities initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize adapter capabilities: {e}")

    def _initialize_parsing_strategies(self):
        """Initialize Persian parsing strategies."""
        try:
            if PersianParsingStrategy:
                self.parsing_strategies = {
                    'persian_strategy': True,
                    'comprehensive_parsing': True
                }
                self.logger.info("Persian parsing strategies initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize parsing strategies: {e}")

    # Core text processing methods
    
    def process_text(self, text: str, system_hint: str = None) -> PersianTextResult:
        """
        Process Persian text with unified processing capabilities.
        
        Args:
            text: Text to process
            system_hint: Hint about source system ('adapters', 'requests', 'crawlers')
        """
        if not text:
            return PersianTextResult(
                original_text="",
                processed_text="",
                success=True,
                method_used="no_processing"
            )
        
        # Check cache first
        cache_key = f"{text}:{system_hint}:{self.config.level.value}"
        if self.text_cache and cache_key in self.text_cache:
            self.processing_stats['cache_hits'] += 1
            return self.text_cache[cache_key]
        
        self.processing_stats['cache_misses'] += 1
        self.processing_stats['total_processed'] += 1
        
        try:
            # Choose processing method based on level and availability
            if self.config.level == PersianTextLevel.COMPREHENSIVE and self.root_processor:
                result = self._process_comprehensive(text, system_hint)
            elif self.config.level == PersianTextLevel.ADVANCED and self.root_processor:
                result = self._process_advanced(text)
            elif self.config.level == PersianTextLevel.STANDARD and self.root_processor:
                result = self._process_standard(text)
            else:
                result = self._process_basic(text)
            
            # Update method usage stats
            method = result.method_used
            self.processing_stats['method_usage'][method] = self.processing_stats['method_usage'].get(method, 0) + 1
            
            # Cache result
            if self.text_cache:
                self.text_cache[cache_key] = result
            
            return result
            
        except Exception as e:
            self.processing_stats['errors'] += 1
            self.logger.error(f"Persian text processing failed: {e}")
            
            # Fallback to basic processing
            if self.config.fallback_to_basic and self.config.level != PersianTextLevel.BASIC:
                return self._process_basic(text)
            
            return PersianTextResult(
                original_text=text,
                processed_text=text,
                success=False,
                method_used="error_fallback",
                errors=[str(e)]
            )

    def _process_comprehensive(self, text: str, system_hint: str = None) -> PersianTextResult:
        """Comprehensive Persian text processing using all available capabilities."""
        try:
            # Start with root processor
            processed = self.root_processor.process_text(text)
            
            # Apply system-specific enhancements
            if system_hint == 'adapters' and self.adapter_capabilities:
                processed = self._apply_adapter_enhancements(processed)
            elif system_hint == 'requests':
                processed = self._apply_requests_enhancements(processed)
            elif system_hint == 'crawlers':
                processed = self._apply_crawlers_enhancements(processed)
            
            # Apply RTL processing if enabled
            if self.config.enable_rtl and RTL_AVAILABLE:
                processed = self._apply_rtl_processing(processed)
            
            return PersianTextResult(
                original_text=text,
                processed_text=processed,
                success=True,
                method_used="comprehensive",
                metadata={
                    'rtl_applied': self.config.enable_rtl and RTL_AVAILABLE,
                    'system_hint': system_hint,
                    'capabilities_used': list(self.adapter_capabilities.keys())
                }
            )
            
        except Exception as e:
            return self._process_advanced(text)  # Fallback

    def _process_advanced(self, text: str) -> PersianTextResult:
        """Advanced Persian text processing using root processor."""
        try:
            processed = self.root_processor.process_text(text)
            
            # Apply RTL processing if enabled
            if self.config.enable_rtl and RTL_AVAILABLE:
                processed = self._apply_rtl_processing(processed)
            
            return PersianTextResult(
                original_text=text,
                processed_text=processed,
                success=True,
                method_used="advanced",
                metadata={'rtl_applied': self.config.enable_rtl and RTL_AVAILABLE}
            )
            
        except Exception as e:
            return self._process_standard(text)  # Fallback

    def _process_standard(self, text: str) -> PersianTextResult:
        """Standard Persian text processing using root processor."""
        try:
            processed = self.root_processor.process_text(text)
            
            return PersianTextResult(
                original_text=text,
                processed_text=processed,
                success=True,
                method_used="standard"
            )
            
        except Exception as e:
            return self._process_basic(text)  # Fallback

    def _process_basic(self, text: str) -> PersianTextResult:
        """Basic Persian text processing (number conversion only)."""
        try:
            # Basic Persian to English number conversion
            persian_to_english = {
                '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
                '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9',
                '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
                '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'
            }
            
            processed = text
            for persian, english in persian_to_english.items():
                processed = processed.replace(persian, english)
            
            # Basic whitespace normalization
            processed = re.sub(r'\s+', ' ', processed).strip()
            
            return PersianTextResult(
                original_text=text,
                processed_text=processed,
                success=True,
                method_used="basic"
            )
            
        except Exception as e:
            return PersianTextResult(
                original_text=text,
                processed_text=text,
                success=False,
                method_used="basic_fallback",
                errors=[str(e)]
            )

    def _apply_adapter_enhancements(self, text: str) -> str:
        """Apply adapter-specific Persian text enhancements."""
        # This would use specific adapter capabilities
        # For now, return the text as-is
        return text

    def _apply_requests_enhancements(self, text: str) -> str:
        """Apply requests-specific Persian text enhancements."""
        # This would apply requests system specific processing
        return text

    def _apply_crawlers_enhancements(self, text: str) -> str:
        """Apply crawlers-specific Persian text enhancements."""
        # This would apply crawlers system specific processing
        return text

    def _apply_rtl_processing(self, text: str) -> str:
        """Apply RTL (Right-to-Left) text processing."""
        try:
            if RTL_AVAILABLE:
                reshaped = arabic_reshaper.reshape(text)
                return get_display(reshaped)
            return text
        except Exception as e:
            self.logger.debug(f"RTL processing failed: {e}")
            return text

    # Specialized processing methods
    
    def process_airline_name(self, airline_text: str) -> PersianParsingResult:
        """Process and normalize Persian airline names."""
        try:
            if self.root_processor and hasattr(self.root_processor, 'normalize_airline_name'):
                normalized = self.root_processor.normalize_airline_name(airline_text)
                return PersianParsingResult(
                    success=True,
                    value=normalized,
                    original_text=airline_text,
                    method_used="root_processor_airline",
                    confidence=0.9
                )
            else:
                # Fallback airline mapping
                airline_mappings = {
                    "ایران ایر": "Iran Air",
                    "ماهان": "Mahan Air",
                    "آسمان": "Aseman Airlines",
                    "کاسپین": "Caspian Airlines",
                    "قشم ایر": "Qeshm Air",
                    "کارون": "Karun Airlines",
                    "سپهران": "Sepehran Airlines",
                    "وارش": "Varesh Airlines",
                    "تابان": "Taban Air",
                    "عطا": "Ata Airlines"
                }
                
                # Process text first
                processed_text = self.process_text(airline_text).processed_text
                
                # Check mappings
                for persian, english in airline_mappings.items():
                    if persian in processed_text:
                        return PersianParsingResult(
                            success=True,
                            value=english,
                            original_text=airline_text,
                            method_used="fallback_airline_mapping",
                            confidence=0.8
                        )
                
                return PersianParsingResult(
                    success=True,
                    value=processed_text,
                    original_text=airline_text,
                    method_used="text_processing_only",
                    confidence=0.6
                )
                
        except Exception as e:
            return PersianParsingResult(
                success=False,
                value=airline_text,
                original_text=airline_text,
                method_used="error_fallback",
                confidence=0.0,
                metadata={'error': str(e)}
            )

    def process_airport_code(self, airport_text: str) -> PersianParsingResult:
        """Process Persian airport names and codes."""
        try:
            if self.root_processor and hasattr(self.root_processor, 'get_airport_code'):
                code = self.root_processor.get_airport_code(airport_text)
                if code:
                    return PersianParsingResult(
                        success=True,
                        value=code,
                        original_text=airport_text,
                        method_used="root_processor_airport",
                        confidence=0.9
                    )
            
            # Fallback airport mapping
            airport_mappings = {
                "تهران": "THR", "مشهد": "MHD", "شیراز": "SYZ", "اصفهان": "IFN",
                "تبریز": "TBZ", "اهواز": "AWZ", "کرمان": "KER", "بندرعباس": "BND",
                "کیش": "KIH", "قشم": "QSH", "زاهدان": "ZAH", "یزد": "AZD"
            }
            
            processed_text = self.process_text(airport_text).processed_text
            
            for persian, code in airport_mappings.items():
                if persian in processed_text:
                    return PersianParsingResult(
                        success=True,
                        value=code,
                        original_text=airport_text,
                        method_used="fallback_airport_mapping",
                        confidence=0.8
                    )
            
            return PersianParsingResult(
                success=True,
                value=processed_text,
                original_text=airport_text,
                method_used="text_processing_only",
                confidence=0.6
            )
            
        except Exception as e:
            return PersianParsingResult(
                success=False,
                value=airport_text,
                original_text=airport_text,
                method_used="error_fallback",
                confidence=0.0,
                metadata={'error': str(e)}
            )

    def parse_persian_price(self, price_text: str) -> PersianParsingResult:
        """Parse Persian price text and extract amount and currency."""
        try:
            if self.root_processor and hasattr(self.root_processor, 'extract_price'):
                amount, currency = self.root_processor.extract_price(price_text)
                return PersianParsingResult(
                    success=True,
                    value={'amount': amount, 'currency': currency},
                    original_text=price_text,
                    method_used="root_processor_price",
                    confidence=0.9
                )
            
            # Fallback price parsing
            processed_text = self.process_text(price_text).processed_text
            
            # Extract numbers
            numbers = re.findall(r'[\d,]+', processed_text)
            if numbers:
                amount = float(numbers[0].replace(',', ''))
                
                # Detect currency
                currency = "IRR"  # Default
                if "تومان" in price_text:
                    currency = "IRR"
                    amount *= 10  # Convert toman to rial
                elif "دلار" in price_text:
                    currency = "USD"
                elif "یورو" in price_text:
                    currency = "EUR"
                
                return PersianParsingResult(
                    success=True,
                    value={'amount': amount, 'currency': currency},
                    original_text=price_text,
                    method_used="fallback_price_parsing",
                    confidence=0.7
                )
            
            return PersianParsingResult(
                success=False,
                value={'amount': 0, 'currency': 'IRR'},
                original_text=price_text,
                method_used="no_price_found",
                confidence=0.0
            )
            
        except Exception as e:
            return PersianParsingResult(
                success=False,
                value={'amount': 0, 'currency': 'IRR'},
                original_text=price_text,
                method_used="error_fallback",
                confidence=0.0,
                metadata={'error': str(e)}
            )

    def parse_persian_duration(self, duration_text: str) -> PersianParsingResult:
        """Parse Persian duration text and return minutes."""
        try:
            if self.root_processor and hasattr(self.root_processor, 'extract_duration'):
                minutes = self.root_processor.extract_duration(duration_text)
                return PersianParsingResult(
                    success=True,
                    value=minutes,
                    original_text=duration_text,
                    method_used="root_processor_duration",
                    confidence=0.9
                )
            
            # Fallback duration parsing
            processed_text = self.process_text(duration_text).processed_text
            
            hours = 0
            minutes = 0
            
            # Look for hours
            hour_match = re.search(r'(\d+)\s*(?:ساعت|hour)', processed_text, re.IGNORECASE)
            if hour_match:
                hours = int(hour_match.group(1))
            
            # Look for minutes
            minute_match = re.search(r'(\d+)\s*(?:دقیقه|minute)', processed_text, re.IGNORECASE)
            if minute_match:
                minutes = int(minute_match.group(1))
            
            # If no explicit hours/minutes, try HH:MM format
            if hours == 0 and minutes == 0:
                time_match = re.search(r'(\d{1,2}):(\d{2})', processed_text)
                if time_match:
                    hours = int(time_match.group(1))
                    minutes = int(time_match.group(2))
            
            total_minutes = hours * 60 + minutes
            
            return PersianParsingResult(
                success=total_minutes > 0,
                value=total_minutes,
                original_text=duration_text,
                method_used="fallback_duration_parsing",
                confidence=0.7 if total_minutes > 0 else 0.3
            )
            
        except Exception as e:
            return PersianParsingResult(
                success=False,
                value=0,
                original_text=duration_text,
                method_used="error_fallback",
                confidence=0.0,
                metadata={'error': str(e)}
            )

    def parse_persian_time(self, time_text: str) -> PersianParsingResult:
        """Parse Persian time text and return datetime."""
        try:
            if self.root_processor and hasattr(self.root_processor, 'parse_time'):
                parsed_time = self.root_processor.parse_time(time_text)
                if parsed_time:
                    return PersianParsingResult(
                        success=True,
                        value=parsed_time,
                        original_text=time_text,
                        method_used="root_processor_time",
                        confidence=0.9
                    )
            
            # Fallback time parsing
            processed_text = self.process_text(time_text).processed_text
            
            # Try standard time formats
            time_patterns = [
                r'(\d{1,2}):(\d{2})',
                r'(\d{1,2})\.(\d{2})',
                r'(\d{1,2})\s*(?::\s*(\d{2}))?'
            ]
            
            for pattern in time_patterns:
                match = re.search(pattern, processed_text)
                if match:
                    hour = int(match.group(1))
                    minute = int(match.group(2)) if match.group(2) else 0
                    
                    # Handle AM/PM indicators in Persian
                    if "بعد از ظهر" in time_text or "عصر" in time_text:
                        if hour < 12:
                            hour += 12
                    elif "بامداد" in time_text or "صبح" in time_text:
                        if hour == 12:
                            hour = 0
                    
                    time_obj = datetime.now().replace(
                        hour=hour, minute=minute, second=0, microsecond=0
                    )
                    
                    return PersianParsingResult(
                        success=True,
                        value=time_obj,
                        original_text=time_text,
                        method_used="fallback_time_parsing",
                        confidence=0.7
                    )
            
            return PersianParsingResult(
                success=False,
                value=None,
                original_text=time_text,
                method_used="no_time_found",
                confidence=0.0
            )
            
        except Exception as e:
            return PersianParsingResult(
                success=False,
                value=None,
                original_text=time_text,
                method_used="error_fallback",
                confidence=0.0,
                metadata={'error': str(e)}
            )

    def convert_jalali_date(self, jalali_date_str: str) -> PersianParsingResult:
        """Convert Jalali (Persian) date to Gregorian."""
        try:
            if self.root_processor and hasattr(self.root_processor, 'convert_jalali_date'):
                gregorian_date = self.root_processor.convert_jalali_date(jalali_date_str)
                return PersianParsingResult(
                    success=True,
                    value=gregorian_date,
                    original_text=jalali_date_str,
                    method_used="root_processor_jalali",
                    confidence=0.9
                )
            
            # Fallback Jalali conversion
            if JALALI_AVAILABLE:
                processed_text = self.process_text(jalali_date_str).processed_text
                
                # Try to parse various formats
                formats = ["%Y/%m/%d", "%Y-%m-%d", "%d/%m/%Y"]
                
                for fmt in formats:
                    try:
                        jalali_date = jdatetime.datetime.strptime(processed_text, fmt)
                        gregorian_date = jalali_date.togregorian()
                        
                        return PersianParsingResult(
                            success=True,
                            value=gregorian_date,
                            original_text=jalali_date_str,
                            method_used="fallback_jalali_conversion",
                            confidence=0.8
                        )
                    except ValueError:
                        continue
            
            return PersianParsingResult(
                success=False,
                value=None,
                original_text=jalali_date_str,
                method_used="jalali_conversion_failed",
                confidence=0.0
            )
            
        except Exception as e:
            return PersianParsingResult(
                success=False,
                value=None,
                original_text=jalali_date_str,
                method_used="error_fallback",
                confidence=0.0,
                metadata={'error': str(e)}
            )

    # Integration methods for different systems
    
    def integrate_with_requests_system(self, crawler_instance: Any) -> bool:
        """Integrate Persian text processing with requests system crawler."""
        try:
            # Add Persian processing methods to the crawler instance
            if not hasattr(crawler_instance, '_persian_bridge'):
                crawler_instance._persian_bridge = self
                
                # Add convenience methods
                crawler_instance.process_persian_text = lambda text: self.process_text(text, 'requests').processed_text
                crawler_instance.parse_persian_airline = lambda text: self.process_airline_name(text).value
                crawler_instance.parse_persian_price = lambda text: self.parse_persian_price(text).value
                crawler_instance.parse_persian_duration = lambda text: self.parse_persian_duration(text).value
                
                self.logger.info("Persian text processing integrated with requests system crawler")
                return True
            
        except Exception as e:
            self.logger.error(f"Failed to integrate with requests system: {e}")
            return False

    def integrate_with_crawlers_system(self, crawler_instance: Any) -> bool:
        """Integrate Persian text processing with crawlers system crawler."""
        try:
            # Add Persian processing methods to the crawler instance
            if not hasattr(crawler_instance, '_persian_bridge'):
                crawler_instance._persian_bridge = self
                
                # Add convenience methods
                crawler_instance.process_persian_text = lambda text: self.process_text(text, 'crawlers').processed_text
                crawler_instance.parse_persian_airport = lambda text: self.process_airport_code(text).value
                crawler_instance.parse_persian_time = lambda text: self.parse_persian_time(text).value
                crawler_instance.convert_jalali_date = lambda text: self.convert_jalali_date(text).value
                
                self.logger.info("Persian text processing integrated with crawlers system crawler")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to integrate with crawlers system: {e}")
            return False

    def integrate_with_adapters_system(self, adapter_instance: Any) -> bool:
        """Integrate Persian text processing with adapters system adapter."""
        try:
            # Enhance existing adapter with unified Persian processing
            if not hasattr(adapter_instance, '_unified_persian_bridge'):
                adapter_instance._unified_persian_bridge = self
                
                # Override Persian methods if they exist
                original_process = getattr(adapter_instance, 'process_persian_text', None)
                adapter_instance.process_persian_text_original = original_process
                adapter_instance.process_persian_text = lambda text: self.process_text(text, 'adapters').processed_text
                
                self.logger.info("Persian text processing integrated with adapters system adapter")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to integrate with adapters system: {e}")
            return False

    # Utility and monitoring methods
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get Persian text processing statistics."""
        cache_hit_rate = 0
        if self.processing_stats['total_processed'] > 0:
            cache_hit_rate = self.processing_stats['cache_hits'] / self.processing_stats['total_processed'] * 100
        
        return {
            'total_processed': self.processing_stats['total_processed'],
            'cache_hits': self.processing_stats['cache_hits'],
            'cache_misses': self.processing_stats['cache_misses'],
            'cache_hit_rate': round(cache_hit_rate, 2),
            'errors': self.processing_stats['errors'],
            'method_usage': dict(self.processing_stats['method_usage']),
            'config_level': self.config.level.value,
            'capabilities': {
                'root_processor': self.root_processor is not None,
                'adapter_capabilities': bool(self.adapter_capabilities),
                'parsing_strategies': bool(self.parsing_strategies),
                'rtl_support': RTL_AVAILABLE,
                'jalali_support': JALALI_AVAILABLE
            }
        }

    def clear_cache(self):
        """Clear Persian text processing cache."""
        if self.text_cache:
            self.text_cache.clear()
        if self.parsing_cache:
            self.parsing_cache.clear()
        self.logger.info("Persian text processing cache cleared")

    def test_capabilities(self) -> Dict[str, Any]:
        """Test Persian text processing capabilities."""
        test_cases = [
            ("هواپیمایی ایران ایر", "airline"),
            ("تهران", "airport"),
            ("۱۲:۳۰", "time"),
            ("۲ ساعت و ۳۰ دقیقه", "duration"),
            ("۱۰۰,۰۰۰ تومان", "price"),
            ("۱۴۰۲/۰۵/۱۵", "jalali_date")
        ]
        
        results = {}
        for test_text, test_type in test_cases:
            try:
                if test_type == "airline":
                    result = self.process_airline_name(test_text)
                elif test_type == "airport":
                    result = self.process_airport_code(test_text)
                elif test_type == "time":
                    result = self.parse_persian_time(test_text)
                elif test_type == "duration":
                    result = self.parse_persian_duration(test_text)
                elif test_type == "price":
                    result = self.parse_persian_price(test_text)
                elif test_type == "jalali_date":
                    result = self.convert_jalali_date(test_text)
                else:
                    result = self.process_text(test_text)
                
                results[test_type] = {
                    'test_text': test_text,
                    'success': result.success if hasattr(result, 'success') else True,
                    'method_used': result.method_used if hasattr(result, 'method_used') else 'text_processing',
                    'confidence': result.confidence if hasattr(result, 'confidence') else 1.0
                }
                
            except Exception as e:
                results[test_type] = {
                    'test_text': test_text,
                    'success': False,
                    'error': str(e)
                }
        
        return results

    def __repr__(self) -> str:
        """String representation of the Persian text bridge."""
        return (f"UnifiedPersianTextBridge("
                f"level={self.config.level.value}, "
                f"root_processor={self.root_processor is not None}, "
                f"processed={self.processing_stats['total_processed']})")


# Global unified Persian text bridge instance
_global_persian_bridge: Optional[UnifiedPersianTextBridge] = None


def get_persian_bridge(config: PersianProcessingConfig = None) -> UnifiedPersianTextBridge:
    """Get the global unified Persian text bridge instance."""
    global _global_persian_bridge
    if _global_persian_bridge is None:
        _global_persian_bridge = UnifiedPersianTextBridge(config)
    return _global_persian_bridge


def initialize_persian_bridge(config: PersianProcessingConfig) -> UnifiedPersianTextBridge:
    """Initialize the global unified Persian text bridge with configuration."""
    global _global_persian_bridge
    _global_persian_bridge = UnifiedPersianTextBridge(config)
    return _global_persian_bridge


# Convenience functions for direct integration

def integrate_persian_with_crawler(crawler_instance: Any, system_type: str = "unknown") -> bool:
    """
    Integrate Persian text processing with a crawler instance.
    
    Args:
        crawler_instance: The crawler instance to integrate with
        system_type: Type of system ('adapters', 'requests', 'crawlers')
    """
    bridge = get_persian_bridge()
    
    if system_type == 'adapters':
        return bridge.integrate_with_adapters_system(crawler_instance)
    elif system_type == 'requests':
        return bridge.integrate_with_requests_system(crawler_instance)
    elif system_type == 'crawlers':
        return bridge.integrate_with_crawlers_system(crawler_instance)
    else:
        # Try to auto-detect and integrate
        if hasattr(crawler_instance, 'unified_crawler_interface'):
            return bridge.integrate_with_adapters_system(crawler_instance)
        elif hasattr(crawler_instance, 'selenium_handler'):
            return bridge.integrate_with_requests_system(crawler_instance)
        else:
            return bridge.integrate_with_crawlers_system(crawler_instance)


def process_persian_text_unified(text: str, system_hint: str = None) -> str:
    """
    Process Persian text using the unified bridge - convenience function.
    
    Args:
        text: Text to process
        system_hint: Hint about source system
    """
    bridge = get_persian_bridge()
    result = bridge.process_text(text, system_hint)
    return result.processed_text 