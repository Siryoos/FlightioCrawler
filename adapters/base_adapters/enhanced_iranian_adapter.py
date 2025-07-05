"""
Enhanced Iranian Airline Adapter

This adapter integrates the automated search form strategy with Persian text processing
for improved form filling capabilities on Iranian airline websites.
"""

import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

from adapters.base_adapters.enhanced_persian_adapter import EnhancedPersianAdapter
from adapters.strategies.automated_search_form_strategy import (
    AutomatedSearchFormStrategy, 
    FormSubmissionResult, 
    SearchFormStrategy
)
from adapters.base_adapters.enhanced_error_handler import (
    ErrorCategory, 
    ErrorSeverity, 
    error_handler_decorator
)


class EnhancedIranianAdapter(EnhancedPersianAdapter):
    """
    Enhanced adapter for Iranian airline websites with advanced form automation
    """
    
    def __init__(self, site_name: str, config: Dict[str, Any]):
        super().__init__(site_name, config)
        self.search_form_strategy: Optional[AutomatedSearchFormStrategy] = None
        self.form_submission_history: List[FormSubmissionResult] = []
        
        # Iranian-specific configuration
        self.iranian_config = {
            'enable_persian_calendar': config.get('persian_calendar', True),
            'enable_airport_mapping': config.get('airport_mapping', True),
            'enable_intelligent_retry': config.get('intelligent_retry', True),
            'max_form_retry_attempts': config.get('max_form_retry_attempts', 3),
            'form_timeout_seconds': config.get('form_timeout_seconds', 30),
            'captcha_handling': config.get('captcha_handling', True)
        }

    async def initialize_page(self) -> None:
        """Initialize page with search form strategy"""
        await super().initialize_page()
        
        if self.page:
            self.search_form_strategy = AutomatedSearchFormStrategy(
                self.page, 
                self.persian_processor
            )

    @error_handler_decorator(
        operation_name="crawl_flights",
        category=ErrorCategory.CRAWLING,
        severity=ErrorSeverity.HIGH,
        max_retries=2
    )
    async def crawl(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Enhanced crawling with automated form filling
        """
        try:
            # Validate and preprocess search parameters
            processed_params = await self._preprocess_search_params(search_params)
            
            # Navigate to search page
            await self._navigate_to_search_page()
            
            # Fill search form using automated strategy
            form_result = await self._fill_search_form_enhanced(processed_params)
            
            # Handle form submission result
            if not form_result.success:
                await self._handle_form_failure(form_result, processed_params)
            
            # Extract flight results
            results = await self._extract_flight_results()
            
            # Post-process and validate results
            validated_results = await self._post_process_results(results)
            
            # Log success metrics
            self._log_crawl_success(form_result, len(validated_results))
            
            return validated_results
            
        except Exception as e:
            self.logger.error(f"Enhanced crawling failed for {self.site_name}: {e}")
            self.monitoring.record_error()
            raise

    async def _preprocess_search_params(self, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Preprocess search parameters for Iranian sites
        """
        processed = search_params.copy()
        
        # Validate required fields
        required_fields = self._get_required_search_fields()
        for field in required_fields:
            if field not in processed:
                raise ValueError(f"Missing required search parameter: {field}")
        
        # Add default values
        processed.setdefault('passengers', 1)
        processed.setdefault('cabin_class', 'economy')
        processed.setdefault('trip_type', 'one_way')
        
        # Process dates for Persian calendar if needed
        if self.iranian_config['enable_persian_calendar']:
            processed = await self._process_dates_for_persian_calendar(processed)
        
        # Process airport codes if needed
        if self.iranian_config['enable_airport_mapping']:
            processed = await self._process_airport_codes(processed)
        
        self.logger.debug(f"Preprocessed search params: {processed}")
        return processed

    async def _process_dates_for_persian_calendar(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Process dates for Persian calendar sites"""
        date_fields = ['departure_date', 'return_date']
        
        for field in date_fields:
            if field in params:
                # Convert Gregorian to Persian if site uses Persian calendar
                params[field] = self.persian_processor.process_date(params[field])
        
        return params

    async def _process_airport_codes(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Process airport codes for Persian sites"""
        airport_fields = ['origin', 'destination']
        
        for field in airport_fields:
            if field in params:
                # Convert to Persian representation if needed
                params[field] = self._convert_airport_for_site(params[field])
        
        return params

    def _convert_airport_for_site(self, airport_code: str) -> str:
        """Convert airport code to site-specific format"""
        # This can be overridden by specific adapters
        return airport_code.upper()

    @error_handler_decorator(
        operation_name="fill_search_form_enhanced",
        category=ErrorCategory.FORM_FILLING,
        severity=ErrorSeverity.HIGH,
        max_retries=3
    )
    async def _fill_search_form_enhanced(self, search_params: Dict[str, Any]) -> FormSubmissionResult:
        """
        Fill search form using enhanced automated strategy
        """
        if not self.search_form_strategy:
            raise RuntimeError("Search form strategy not initialized")
        
        # Attempt form filling with retry logic
        for attempt in range(self.iranian_config['max_form_retry_attempts']):
            try:
                self.logger.info(f"Filling search form (attempt {attempt + 1})")
                
                result = await asyncio.wait_for(
                    self.search_form_strategy.fill_search_form(search_params),
                    timeout=self.iranian_config['form_timeout_seconds']
                )
                
                # Store result for analysis
                self.form_submission_history.append(result)
                
                if result.success:
                    self.logger.info(f"Form filled successfully in {result.execution_time_ms}ms")
                    return result
                else:
                    self.logger.warning(f"Form filling failed: {result.error_message}")
                    
                    # Wait before retry
                    if attempt < self.iranian_config['max_form_retry_attempts'] - 1:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
            except asyncio.TimeoutError:
                self.logger.error(f"Form filling timeout on attempt {attempt + 1}")
                continue
            except Exception as e:
                self.logger.error(f"Form filling error on attempt {attempt + 1}: {e}")
                continue
        
        # All attempts failed
        return FormSubmissionResult(
            success=False,
            strategy_used=SearchFormStrategy.DIRECT_SUBMIT,
            execution_time_ms=0,
            error_message="All form filling attempts failed"
        )

    async def _handle_form_failure(self, form_result: FormSubmissionResult, search_params: Dict[str, Any]) -> None:
        """
        Handle form submission failures with intelligent recovery
        """
        if not self.iranian_config['enable_intelligent_retry']:
            raise Exception(f"Form submission failed: {form_result.error_message}")
        
        self.logger.warning("Attempting intelligent form failure recovery")
        
        # Try alternative form filling strategies
        recovery_strategies = [
            self._try_manual_form_filling,
            self._try_javascript_form_filling,
            self._try_simplified_form_filling
        ]
        
        for strategy in recovery_strategies:
            try:
                self.logger.info(f"Trying recovery strategy: {strategy.__name__}")
                success = await strategy(search_params)
                if success:
                    self.logger.info("Form failure recovery successful")
                    return
            except Exception as e:
                self.logger.debug(f"Recovery strategy {strategy.__name__} failed: {e}")
                continue
        
        raise Exception("All form recovery strategies failed")

    async def _try_manual_form_filling(self, search_params: Dict[str, Any]) -> bool:
        """Fallback to manual form filling"""
        try:
            # Use the original form filling method as fallback
            await self._fill_search_form(search_params)
            return True
        except:
            return False

    async def _try_javascript_form_filling(self, search_params: Dict[str, Any]) -> bool:
        """Try filling form via JavaScript injection"""
        try:
            js_script = self._generate_form_filling_script(search_params)
            await self.page.evaluate(js_script)
            
            # Submit form
            await self.page.click('button[type="submit"], .search-button')
            await self.page.wait_for_load_state('networkidle', timeout=10000)
            
            return True
        except:
            return False

    async def _try_simplified_form_filling(self, search_params: Dict[str, Any]) -> bool:
        """Try filling only essential fields"""
        try:
            essential_fields = ['origin', 'destination', 'departure_date']
            simplified_params = {k: v for k, v in search_params.items() if k in essential_fields}
            
            # Try with minimal automation
            for field, value in simplified_params.items():
                selector = f'[name="{field}"], #{field}'
                await self.page.fill(selector, str(value))
            
            await self.page.click('button[type="submit"]')
            await self.page.wait_for_load_state('networkidle', timeout=10000)
            
            return True
        except:
            return False

    def _generate_form_filling_script(self, search_params: Dict[str, Any]) -> str:
        """Generate JavaScript to fill form fields"""
        script_parts = []
        
        for field, value in search_params.items():
            script_parts.append(f'''
                const {field}_field = document.querySelector('[name="{field}"], #{field}, [data-testid="{field}"]');
                if ({field}_field) {{
                    {field}_field.value = "{value}";
                    {field}_field.dispatchEvent(new Event('input'));
                    {field}_field.dispatchEvent(new Event('change'));
                }}
            ''')
        
        return '\n'.join(script_parts)

    async def _post_process_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Post-process flight results with enhanced validation
        """
        if not results:
            return results
        
        processed_results = []
        
        for flight in results:
            try:
                # Enhanced validation
                if await self._validate_flight_data_enhanced(flight):
                    # Process Persian text fields
                    processed_flight = await self._process_persian_fields(flight)
                    
                    # Add metadata
                    processed_flight['crawl_metadata'] = {
                        'adapter_name': self.site_name,
                        'crawl_timestamp': datetime.now().isoformat(),
                        'form_strategy_used': self._get_last_successful_strategy(),
                        'processing_version': '2.0'
                    }
                    
                    processed_results.append(processed_flight)
                    
            except Exception as e:
                self.logger.warning(f"Failed to process flight result: {e}")
                continue
        
        self.logger.info(f"Post-processed {len(processed_results)} valid flights")
        return processed_results

    async def _validate_flight_data_enhanced(self, flight: Dict[str, Any]) -> bool:
        """Enhanced flight data validation"""
        # Basic validation from parent class
        if not super()._validate_flight_data([flight]):
            return False
        
        # Enhanced validations
        validations = [
            self._validate_price_reasonableness(flight),
            self._validate_time_consistency(flight),
            self._validate_route_validity(flight),
            self._validate_persian_text_integrity(flight)
        ]
        
        return all(validations)

    def _validate_price_reasonableness(self, flight: Dict[str, Any]) -> bool:
        """Validate that price is reasonable"""
        price = flight.get('price', 0)
        
        # Basic range checks (these should be configurable)
        min_price = 50000  # IRR
        max_price = 50000000  # IRR
        
        return min_price <= price <= max_price

    def _validate_time_consistency(self, flight: Dict[str, Any]) -> bool:
        """Validate time consistency"""
        try:
            departure = flight.get('departure_time')
            arrival = flight.get('arrival_time')
            duration = flight.get('duration_minutes', 0)
            
            if not departure or not arrival:
                return False
            
            # Parse times if they're strings
            if isinstance(departure, str):
                departure = datetime.fromisoformat(departure.replace('Z', '+00:00'))
            if isinstance(arrival, str):
                arrival = datetime.fromisoformat(arrival.replace('Z', '+00:00'))
            
            # Check that arrival is after departure
            if arrival <= departure:
                return False
            
            # Check duration consistency (allow some tolerance)
            actual_duration = (arrival - departure).total_seconds() / 60
            if duration > 0 and abs(actual_duration - duration) > 60:  # 1 hour tolerance
                return False
            
            return True
            
        except Exception:
            return False

    def _validate_route_validity(self, flight: Dict[str, Any]) -> bool:
        """Validate route information"""
        origin = flight.get('origin_airport', '')
        destination = flight.get('destination_airport', '')
        
        # Check for valid airport codes
        if not origin or not destination or origin == destination:
            return False
        
        # Check format (3-letter IATA codes)
        if len(origin) != 3 or len(destination) != 3:
            return False
        
        return True

    def _validate_persian_text_integrity(self, flight: Dict[str, Any]) -> bool:
        """Validate Persian text fields"""
        persian_fields = ['airline_name', 'route_info', 'fare_conditions']
        
        for field in persian_fields:
            if field in flight:
                text = flight[field]
                if not self.persian_processor.validate_text(text):
                    return False
        
        return True

    async def _process_persian_fields(self, flight: Dict[str, Any]) -> Dict[str, Any]:
        """Process Persian text fields"""
        persian_fields = [
            'airline_name', 'route_info', 'fare_conditions',
            'aircraft_type', 'seat_class', 'meal_service'
        ]
        
        for field in persian_fields:
            if field in flight and isinstance(flight[field], str):
                flight[field] = self.persian_processor.process_text(flight[field])
        
        return flight

    def _get_last_successful_strategy(self) -> str:
        """Get the last successful form submission strategy"""
        successful_submissions = [
            result for result in self.form_submission_history 
            if result.success
        ]
        
        if successful_submissions:
            return successful_submissions[-1].strategy_used.value
        
        return 'unknown'

    def _log_crawl_success(self, form_result: FormSubmissionResult, result_count: int) -> None:
        """Log successful crawl metrics"""
        self.monitoring.record_success()
        
        self.logger.info(f"Crawl completed successfully for {self.site_name}")
        self.logger.info(f"Form strategy: {form_result.strategy_used.value}")
        self.logger.info(f"Form execution time: {form_result.execution_time_ms}ms")
        self.logger.info(f"Results extracted: {result_count}")
        
        if form_result.captcha_detected:
            self.logger.info("CAPTCHA was detected and handled")

    # Override abstract methods from parent class
    def _get_base_url(self) -> str:
        """Get base URL - to be implemented by specific adapters"""
        return self.config.get('base_url', '')

    def _extract_currency(self, element, config: Dict[str, Any]) -> str:
        """Extract currency - default to IRR for Iranian sites"""
        return 'IRR'

    def _get_required_search_fields(self) -> List[str]:
        """Get required search fields"""
        return ['origin', 'destination', 'departure_date']

    async def _navigate_to_search_page(self) -> None:
        """Navigate to search page - can be overridden by specific adapters"""
        if self.page:
            await self.page.goto(self._get_base_url())
            await self.page.wait_for_load_state('networkidle')

    async def _fill_search_form(self, search_params: Dict[str, Any]) -> None:
        """Fallback form filling method"""
        # This is the original method - kept for backward compatibility
        # Specific adapters should override this if needed
        raise NotImplementedError("Specific adapter must implement _fill_search_form") 