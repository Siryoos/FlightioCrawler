"""
Advanced Automated Search Form Strategy for Iranian Airlines

This module provides intelligent form filling capabilities with:
- Dynamic field detection
- Persian text processing
- Autocomplete handling
- Multi-step form support
- Error recovery and retry logic
- CAPTCHA detection and handling
"""

import asyncio
import re
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import logging

try:
    from playwright.async_api import Page, ElementHandle, TimeoutError as PlaywrightTimeoutError
    from bs4 import BeautifulSoup
except ImportError:
    raise ImportError("Required dependencies missing. Install with: pip install playwright beautifulsoup4")

from persian_text import PersianTextProcessor
from adapters.base_adapters.enhanced_error_handler import ErrorCategory, ErrorSeverity, error_handler_decorator


class FormFieldType(Enum):
    """Types of form fields"""
    TEXT_INPUT = "text_input"
    SELECT_DROPDOWN = "select_dropdown"
    AUTOCOMPLETE = "autocomplete"
    DATE_PICKER = "date_picker"
    CHECKBOX = "checkbox"
    RADIO_BUTTON = "radio_button"
    BUTTON = "button"
    HIDDEN = "hidden"


class SearchFormStrategy(Enum):
    """Different strategies for form submission"""
    DIRECT_SUBMIT = "direct_submit"
    MULTI_STEP = "multi_step"
    AJAX_SUBMISSION = "ajax_submission"
    CAPTCHA_PROTECTED = "captcha_protected"


@dataclass
class FormField:
    """Represents a form field with metadata"""
    name: str
    field_type: FormFieldType
    selector: str
    required: bool = True
    persian_processing: bool = False
    validation_pattern: Optional[str] = None
    placeholder_text: Optional[str] = None
    error_selector: Optional[str] = None


@dataclass
class FormSubmissionResult:
    """Result of form submission attempt"""
    success: bool
    strategy_used: SearchFormStrategy
    execution_time_ms: int
    error_message: Optional[str] = None
    captcha_detected: bool = False
    redirect_url: Optional[str] = None


class AutomatedSearchFormStrategy:
    """
    Advanced automated search form filling strategy for Iranian airline websites
    """
    
    def __init__(self, page: Page, persian_processor: Optional[PersianTextProcessor] = None):
        self.page = page
        self.persian_processor = persian_processor or PersianTextProcessor()
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Common Iranian airline form patterns
        self.form_patterns = {
            'origin': [
                '#origin', '[name="origin"]', '[data-testid="origin"]',
                '.origin-input', '[placeholder*="مبدا"]', '[placeholder*="origin"]',
                'input[aria-label*="origin" i]', 'input[aria-label*="مبدا"]'
            ],
            'destination': [
                '#destination', '[name="destination"]', '[data-testid="destination"]',
                '.destination-input', '[placeholder*="مقصد"]', '[placeholder*="destination"]',
                'input[aria-label*="destination" i]', 'input[aria-label*="مقصد"]'
            ],
            'departure_date': [
                '#departure-date', '[name="departure_date"]', '[data-testid="departure-date"]',
                '.departure-date-input', '[placeholder*="تاریخ رفت"]', '[placeholder*="departure"]',
                'input[type="date"]', '.date-picker-input'
            ],
            'return_date': [
                '#return-date', '[name="return_date"]', '[data-testid="return-date"]',
                '.return-date-input', '[placeholder*="تاریخ برگشت"]', '[placeholder*="return"]'
            ],
            'passengers': [
                '#passengers', '[name="passengers"]', '[data-testid="passengers"]',
                '.passenger-count', '[placeholder*="مسافر"]', '[placeholder*="passenger"]',
                'select[name*="adult"]'
            ],
            'cabin_class': [
                '#cabin-class', '[name="cabin_class"]', '[data-testid="cabin-class"]',
                '.cabin-class-select', 'select[name*="class"]', '[placeholder*="کلاس"]'
            ],
            'submit_button': [
                'button[type="submit"]', '[data-testid="search-submit"]',
                '.search-button', '.submit-btn', 'input[type="submit"]',
                'button:has-text("جستجو")', 'button:has-text("search")'
            ]
        }
        
        # Persian month mappings
        self.persian_months = {
            'فروردین': '01', 'اردیبهشت': '02', 'خرداد': '03',
            'تیر': '04', 'مرداد': '05', 'شهریور': '06',
            'مهر': '07', 'آبان': '08', 'آذر': '09',
            'دی': '10', 'بهمن': '11', 'اسفند': '12'
        }
        
        # Airport code mappings for Persian sites
        self.airport_mappings = {
            'THR': ['تهران', 'Tehran', 'IKA', 'Imam Khomeini'],
            'MHD': ['مشهد', 'Mashhad'],
            'SYZ': ['شیراز', 'Shiraz'],
            'IFN': ['اصفهان', 'Isfahan'],
            'TBZ': ['تبریز', 'Tabriz'],
            'AWZ': ['اهواز', 'Ahvaz'],
            'KER': ['کرمان', 'Kerman'],
            'BND': ['بندرعباس', 'Bandar Abbas'],
            'RAS': ['رشت', 'Rasht'],
            'KIH': ['کیش', 'Kish']
        }

    @error_handler_decorator(
        operation_name="detect_form_fields",
        category=ErrorCategory.FORM_FILLING,
        severity=ErrorSeverity.MEDIUM,
        max_retries=2
    )
    async def detect_form_fields(self) -> Dict[str, FormField]:
        """
        Intelligently detect form fields on the page
        """
        detected_fields = {}
        
        for field_name, selectors in self.form_patterns.items():
            field_info = await self._detect_single_field(field_name, selectors)
            if field_info:
                detected_fields[field_name] = field_info
        
        self.logger.info(f"Detected {len(detected_fields)} form fields")
        return detected_fields

    async def _detect_single_field(self, field_name: str, selectors: List[str]) -> Optional[FormField]:
        """Detect a single form field using multiple selector strategies"""
        for selector in selectors:
            try:
                element = await self.page.query_selector(selector)
                if element and await element.is_visible():
                    field_type = await self._determine_field_type(element)
                    
                    # Check if field requires Persian processing
                    persian_processing = await self._requires_persian_processing(element)
                    
                    return FormField(
                        name=field_name,
                        field_type=field_type,
                        selector=selector,
                        persian_processing=persian_processing,
                        placeholder_text=await element.get_attribute('placeholder')
                    )
            except Exception as e:
                self.logger.debug(f"Selector {selector} failed for {field_name}: {e}")
                continue
        
        return None

    async def _determine_field_type(self, element: ElementHandle) -> FormFieldType:
        """Determine the type of form field"""
        tag_name = await element.evaluate('el => el.tagName.toLowerCase()')
        input_type = await element.get_attribute('type') or ''
        class_list = await element.get_attribute('class') or ''
        
        if tag_name == 'select':
            return FormFieldType.SELECT_DROPDOWN
        elif tag_name == 'input':
            if input_type in ['date', 'datetime-local']:
                return FormFieldType.DATE_PICKER
            elif input_type == 'checkbox':
                return FormFieldType.CHECKBOX
            elif input_type == 'radio':
                return FormFieldType.RADIO_BUTTON
            elif 'autocomplete' in class_list or 'dropdown' in class_list:
                return FormFieldType.AUTOCOMPLETE
            else:
                return FormFieldType.TEXT_INPUT
        elif tag_name == 'button':
            return FormFieldType.BUTTON
        else:
            return FormFieldType.TEXT_INPUT

    async def _requires_persian_processing(self, element: ElementHandle) -> bool:
        """Check if field requires Persian text processing"""
        placeholder = await element.get_attribute('placeholder') or ''
        aria_label = await element.get_attribute('aria-label') or ''
        
        # Check for Persian characters
        persian_pattern = re.compile(r'[\u0600-\u06FF]')
        return bool(persian_pattern.search(placeholder + aria_label))

    @error_handler_decorator(
        operation_name="fill_search_form",
        category=ErrorCategory.FORM_FILLING,
        severity=ErrorSeverity.HIGH,
        max_retries=3
    )
    async def fill_search_form(self, search_params: Dict[str, Any]) -> FormSubmissionResult:
        """
        Fill search form with intelligent field detection and error recovery
        """
        start_time = datetime.now()
        
        try:
            # Detect form fields
            form_fields = await self.detect_form_fields()
            
            if not form_fields:
                raise ValueError("No form fields detected on the page")
            
            # Fill each field
            for field_name, field_info in form_fields.items():
                if field_name in search_params:
                    await self._fill_field(field_info, search_params[field_name])
            
            # Detect and handle CAPTCHA
            captcha_detected = await self._detect_captcha()
            if captcha_detected:
                await self._handle_captcha()
            
            # Submit form with appropriate strategy
            strategy = await self._determine_submission_strategy()
            success = await self._submit_form(strategy)
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return FormSubmissionResult(
                success=success,
                strategy_used=strategy,
                execution_time_ms=int(execution_time),
                captcha_detected=captcha_detected,
                redirect_url=self.page.url
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            return FormSubmissionResult(
                success=False,
                strategy_used=SearchFormStrategy.DIRECT_SUBMIT,
                execution_time_ms=int(execution_time),
                error_message=str(e)
            )

    async def _fill_field(self, field_info: FormField, value: Any) -> None:
        """Fill a single form field based on its type"""
        try:
            if field_info.field_type == FormFieldType.TEXT_INPUT:
                await self._fill_text_field(field_info, value)
            elif field_info.field_type == FormFieldType.SELECT_DROPDOWN:
                await self._fill_select_field(field_info, value)
            elif field_info.field_type == FormFieldType.AUTOCOMPLETE:
                await self._fill_autocomplete_field(field_info, value)
            elif field_info.field_type == FormFieldType.DATE_PICKER:
                await self._fill_date_field(field_info, value)
            elif field_info.field_type == FormFieldType.CHECKBOX:
                await self._fill_checkbox_field(field_info, value)
            elif field_info.field_type == FormFieldType.RADIO_BUTTON:
                await self._fill_radio_field(field_info, value)
                
        except Exception as e:
            self.logger.error(f"Failed to fill field {field_info.name}: {e}")
            raise

    async def _fill_text_field(self, field_info: FormField, value: str) -> None:
        """Fill a text input field"""
        processed_value = value
        
        if field_info.persian_processing:
            processed_value = self._process_for_persian_site(field_info.name, value)
        
        # Clear field first
        await self.page.fill(field_info.selector, '')
        await asyncio.sleep(0.1)
        
        # Fill with processed value
        await self.page.fill(field_info.selector, processed_value)
        
        # Trigger input events for dynamic forms
        await self.page.dispatch_event(field_info.selector, 'input')
        await self.page.dispatch_event(field_info.selector, 'change')

    async def _fill_autocomplete_field(self, field_info: FormField, value: str) -> None:
        """Fill an autocomplete field with dropdown handling"""
        processed_value = value
        
        if field_info.persian_processing:
            processed_value = self._process_for_persian_site(field_info.name, value)
        
        # Fill field
        await self.page.fill(field_info.selector, processed_value)
        
        # Wait for dropdown to appear
        await asyncio.sleep(0.5)
        
        # Try to select from dropdown
        dropdown_selectors = [
            '.autocomplete-dropdown li:first-child',
            '.suggestion-list li:first-child',
            '.dropdown-menu li:first-child',
            '[role="option"]:first-child'
        ]
        
        for selector in dropdown_selectors:
            try:
                element = await self.page.query_selector(selector)
                if element and await element.is_visible():
                    await element.click()
                    return
            except:
                continue
        
        # If no dropdown found, press Enter
        await self.page.press(field_info.selector, 'Enter')

    async def _fill_date_field(self, field_info: FormField, value: str) -> None:
        """Fill a date field with Persian calendar support"""
        if field_info.persian_processing:
            # Convert to Persian calendar if needed
            date_value = self._convert_date_for_persian_site(value)
        else:
            date_value = self._normalize_date_format(value)
        
        # Try different date filling strategies
        strategies = [
            lambda: self.page.fill(field_info.selector, date_value),
            lambda: self._fill_date_picker_manually(field_info.selector, date_value),
            lambda: self._fill_date_via_javascript(field_info.selector, date_value)
        ]
        
        for strategy in strategies:
            try:
                await strategy()
                return
            except:
                continue
        
        raise Exception(f"Failed to fill date field {field_info.name}")

    async def _fill_select_field(self, field_info: FormField, value: str) -> None:
        """Fill a select dropdown field"""
        processed_value = value
        
        if field_info.persian_processing:
            processed_value = self._process_for_persian_site(field_info.name, value)
        
        # Try different selection strategies
        strategies = [
            lambda: self.page.select_option(field_info.selector, processed_value),
            lambda: self.page.select_option(field_info.selector, label=processed_value),
            lambda: self._select_by_text_content(field_info.selector, processed_value)
        ]
        
        for strategy in strategies:
            try:
                await strategy()
                return
            except:
                continue
        
        self.logger.warning(f"Could not select value '{processed_value}' in {field_info.name}")

    def _process_for_persian_site(self, field_name: str, value: str) -> str:
        """Process value for Persian airline sites"""
        if field_name in ['origin', 'destination']:
            return self._convert_airport_code_to_persian(value)
        elif field_name == 'cabin_class':
            return self._convert_cabin_class_to_persian(value)
        elif 'date' in field_name:
            return self._convert_date_for_persian_site(value)
        
        return self.persian_processor.process_text(value)

    def _convert_airport_code_to_persian(self, airport_code: str) -> str:
        """Convert airport code to Persian representation"""
        airport_code = airport_code.upper()
        
        if airport_code in self.airport_mappings:
            # Return Persian name if available
            persian_names = self.airport_mappings[airport_code]
            return persian_names[0] if persian_names else airport_code
        
        return airport_code

    def _convert_cabin_class_to_persian(self, cabin_class: str) -> str:
        """Convert cabin class to Persian"""
        class_mappings = {
            'economy': 'اکونومی',
            'business': 'بیزینس',
            'first': 'فرست کلاس',
            'premium': 'پرمیوم'
        }
        
        return class_mappings.get(cabin_class.lower(), cabin_class)

    def _convert_date_for_persian_site(self, date_str: str) -> str:
        """Convert date for Persian calendar sites"""
        try:
            # Parse input date
            if isinstance(date_str, str):
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            else:
                date_obj = date_str
            
            # For now, return Gregorian format
            # In production, implement full Persian calendar conversion
            return date_obj.strftime('%Y/%m/%d')
            
        except:
            return date_str

    def _normalize_date_format(self, date_str: str) -> str:
        """Normalize date format for international sites"""
        try:
            if isinstance(date_str, str):
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            else:
                date_obj = date_str
            
            return date_obj.strftime('%Y-%m-%d')
        except:
            return date_str

    async def _detect_captcha(self) -> bool:
        """Detect if CAPTCHA is present on the page"""
        captcha_selectors = [
            '.captcha', '.recaptcha', '[data-sitekey]',
            'iframe[src*="recaptcha"]', '.h-captcha',
            'img[alt*="captcha" i]', '.captcha-image'
        ]
        
        for selector in captcha_selectors:
            try:
                element = await self.page.query_selector(selector)
                if element and await element.is_visible():
                    return True
            except:
                continue
        
        return False

    async def _handle_captcha(self) -> None:
        """Handle CAPTCHA challenges"""
        self.logger.warning("CAPTCHA detected - manual intervention required")
        
        # Wait for user to solve CAPTCHA (in production, integrate with CAPTCHA solving service)
        await asyncio.sleep(30)

    async def _determine_submission_strategy(self) -> SearchFormStrategy:
        """Determine the best form submission strategy"""
        # Check for AJAX indicators
        ajax_indicators = await self.page.evaluate('''
            () => {
                const scripts = document.querySelectorAll('script');
                for (let script of scripts) {
                    if (script.textContent.includes('ajax') || 
                        script.textContent.includes('fetch') ||
                        script.textContent.includes('XMLHttpRequest')) {
                        return true;
                    }
                }
                return false;
            }
        ''')
        
        if ajax_indicators:
            return SearchFormStrategy.AJAX_SUBMISSION
        
        # Check for multi-step indicators
        steps = await self.page.query_selector_all('.step, .form-step, [data-step]')
        if len(steps) > 1:
            return SearchFormStrategy.MULTI_STEP
        
        return SearchFormStrategy.DIRECT_SUBMIT

    async def _submit_form(self, strategy: SearchFormStrategy) -> bool:
        """Submit form using the determined strategy"""
        try:
            if strategy == SearchFormStrategy.AJAX_SUBMISSION:
                return await self._submit_ajax_form()
            elif strategy == SearchFormStrategy.MULTI_STEP:
                return await self._submit_multi_step_form()
            else:
                return await self._submit_direct_form()
                
        except Exception as e:
            self.logger.error(f"Form submission failed: {e}")
            return False

    async def _submit_direct_form(self) -> bool:
        """Submit form directly"""
        submit_selectors = self.form_patterns['submit_button']
        
        for selector in submit_selectors:
            try:
                element = await self.page.query_selector(selector)
                if element and await element.is_visible():
                    await element.click()
                    
                    # Wait for navigation or results
                    await self._wait_for_submission_result()
                    return True
            except:
                continue
        
        return False

    async def _submit_ajax_form(self) -> bool:
        """Submit AJAX form and wait for response"""
        # Monitor network requests
        responses = []
        
        def handle_response(response):
            responses.append(response)
        
        self.page.on('response', handle_response)
        
        try:
            await self._submit_direct_form()
            
            # Wait for AJAX response
            await asyncio.sleep(2)
            
            # Check for successful responses
            for response in responses:
                if response.status == 200 and 'json' in response.headers.get('content-type', ''):
                    return True
            
            return len(responses) > 0
            
        finally:
            self.page.remove_listener('response', handle_response)

    async def _submit_multi_step_form(self) -> bool:
        """Handle multi-step form submission"""
        steps = await self.page.query_selector_all('.step, .form-step, [data-step]')
        
        for i, step in enumerate(steps):
            # Click next/continue button
            next_button = await step.query_selector('button, .next-step, .continue')
            if next_button:
                await next_button.click()
                await asyncio.sleep(1)
        
        return True

    async def _wait_for_submission_result(self) -> None:
        """Wait for form submission to complete"""
        try:
            # Wait for either navigation or results to appear
            await asyncio.race([
                self.page.wait_for_navigation(timeout=30000),
                self.page.wait_for_selector('.results, .flight-list, .search-results', timeout=30000)
            ])
        except:
            # If no clear indication, wait a bit and assume success
            await asyncio.sleep(3)

    async def _select_by_text_content(self, selector: str, text: str) -> None:
        """Select option by text content"""
        await self.page.evaluate(f'''
            (selector, text) => {{
                const select = document.querySelector(selector);
                if (select) {{
                    for (let option of select.options) {{
                        if (option.textContent.includes(text)) {{
                            select.value = option.value;
                            select.dispatchEvent(new Event('change'));
                            return;
                        }}
                    }}
                }}
            }}
        ''', selector, text)

    async def _fill_date_picker_manually(self, selector: str, date_value: str) -> None:
        """Manually interact with date picker"""
        await self.page.click(selector)
        await asyncio.sleep(0.5)
        
        # Clear existing value
        await self.page.keyboard.press('Control+A')
        await self.page.keyboard.type(date_value)

    async def _fill_date_via_javascript(self, selector: str, date_value: str) -> None:
        """Fill date field via JavaScript"""
        await self.page.evaluate(f'''
            (selector, value) => {{
                const element = document.querySelector(selector);
                if (element) {{
                    element.value = value;
                    element.dispatchEvent(new Event('input'));
                    element.dispatchEvent(new Event('change'));
                }}
            }}
        ''', selector, date_value) 