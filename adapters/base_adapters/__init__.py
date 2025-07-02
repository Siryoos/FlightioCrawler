"""
Enhanced base adapters for flight crawling with common utilities.
"""

# Only import the new enhanced classes
from .enhanced_base_crawler import EnhancedBaseCrawler
from .enhanced_international_adapter import EnhancedInternationalAdapter
from .enhanced_persian_adapter import EnhancedPersianAdapter

# Common utilities and helper functions
from typing import Dict, List, Optional, Any, Union
import re
import logging
from datetime import datetime, timedelta


class AdapterUtils:
    """
    Common utility functions for all adapters.

    This class provides shared functionality that can be used
    across different adapter implementations.
    """

    @staticmethod
    def normalize_airport_code(airport_code: str) -> str:
        """
        Normalize airport code to standard 3-letter IATA format.

        Args:
            airport_code: Raw airport code

        Returns:
            Normalized 3-letter airport code
        """
        if not airport_code:
            return ""

        # Remove extra spaces and convert to uppercase
        normalized = airport_code.strip().upper()

        # Extract 3-letter code if longer string
        if len(normalized) > 3:
            # Look for 3 consecutive uppercase letters
            match = re.search(r"[A-Z]{3}", normalized)
            if match:
                normalized = match.group()
            else:
                # Take first 3 characters
                normalized = normalized[:3]

        return normalized

    @staticmethod
    def parse_flight_number(flight_number: str) -> Dict[str, str]:
        """
        Parse flight number into airline code and number.

        Args:
            flight_number: Raw flight number (e.g., "BA123", "IR 456")

        Returns:
            Dictionary with 'airline_code' and 'number'
        """
        if not flight_number:
            return {"airline_code": "", "number": ""}

        # Clean the flight number
        cleaned = flight_number.strip().upper().replace(" ", "")

        # Extract airline code (letters) and number (digits)
        match = re.match(r"([A-Z]+)(\d+)", cleaned)
        if match:
            return {"airline_code": match.group(1), "number": match.group(2)}

        return {"airline_code": "", "number": cleaned}

    @staticmethod
    def standardize_time_format(time_str: str) -> str:
        """
        Standardize time format to HH:MM.

        Args:
            time_str: Raw time string

        Returns:
            Standardized time in HH:MM format
        """
        if not time_str:
            return ""

        # Remove extra spaces and common separators
        cleaned = time_str.strip().replace(".", ":").replace("-", ":")

        # Extract time pattern
        time_patterns = [
            r"(\d{1,2}):(\d{2})",  # HH:MM or H:MM
            r"(\d{4})",  # HHMM
            r"(\d{1,2})(\d{2})",  # HMM or HHMM without separator
        ]

        for pattern in time_patterns:
            match = re.search(pattern, cleaned)
            if match:
                if len(match.groups()) == 2:
                    hours, minutes = match.groups()
                else:
                    # HHMM format
                    time_digits = match.group(1)
                    if len(time_digits) == 4:
                        hours = time_digits[:2]
                        minutes = time_digits[2:]
                    else:
                        hours = time_digits[:-2] if len(time_digits) > 2 else "0"
                        minutes = time_digits[-2:]

                # Validate and format
                try:
                    h = int(hours)
                    m = int(minutes)
                    if 0 <= h <= 23 and 0 <= m <= 59:
                        return f"{h:02d}:{m:02d}"
                except ValueError:
                    pass

        return time_str  # Return original if no valid pattern found

    @staticmethod
    def calculate_duration_minutes(departure: str, arrival: str) -> int:
        """
        Calculate flight duration in minutes from departure and arrival times.

        Args:
            departure: Departure time (HH:MM)
            arrival: Arrival time (HH:MM)

        Returns:
            Duration in minutes
        """
        try:
            # Parse times
            dep_match = re.match(r"(\d{1,2}):(\d{2})", departure)
            arr_match = re.match(r"(\d{1,2}):(\d{2})", arrival)

            if not (dep_match and arr_match):
                return 0

            dep_hours, dep_minutes = map(int, dep_match.groups())
            arr_hours, arr_minutes = map(int, arr_match.groups())

            # Convert to total minutes
            dep_total = dep_hours * 60 + dep_minutes
            arr_total = arr_hours * 60 + arr_minutes

            # Handle next day arrival
            if arr_total < dep_total:
                arr_total += 24 * 60

            return arr_total - dep_total

        except Exception:
            return 0

    @staticmethod
    def extract_numeric_value(text: str) -> float:
        """
        Extract first numeric value from text.

        Args:
            text: Text containing numeric value

        Returns:
            Extracted numeric value
        """
        if not text:
            return 0.0

        # Remove common non-numeric characters but keep decimal separators
        cleaned = re.sub(r"[^\d.,\-]", "", text)

        # Handle different decimal separators
        if "," in cleaned and "." in cleaned:
            # Assume comma is thousands separator
            cleaned = cleaned.replace(",", "")
        elif "," in cleaned and cleaned.count(",") == 1:
            # Comma as decimal separator
            cleaned = cleaned.replace(",", ".")

        # Extract first number
        match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
        if match:
            try:
                return float(match.group())
            except ValueError:
                pass

        return 0.0

    @staticmethod
    def validate_date_format(date_str: str) -> bool:
        """
        Validate if date string is in acceptable format.

        Args:
            date_str: Date string to validate

        Returns:
            True if valid format
        """
        if not date_str:
            return False

        # Common date formats
        date_patterns = [
            r"\d{4}-\d{2}-\d{2}",  # YYYY-MM-DD
            r"\d{2}/\d{2}/\d{4}",  # DD/MM/YYYY or MM/DD/YYYY
            r"\d{2}-\d{2}-\d{4}",  # DD-MM-YYYY
            r"\d{4}/\d{2}/\d{2}",  # YYYY/MM/DD
        ]

        for pattern in date_patterns:
            if re.match(pattern, date_str.strip()):
                return True

        return False

    @staticmethod
    def clean_text(text: str) -> str:
        """
        Clean and normalize text content.

        Args:
            text: Raw text

        Returns:
            Cleaned text
        """
        if not text:
            return ""

        # Remove extra whitespace
        cleaned = re.sub(r"\s+", " ", text.strip())

        # Remove common unwanted characters
        cleaned = re.sub(r"[^\w\s\-.:,/()&]", "", cleaned)

        return cleaned

    @staticmethod
    def format_currency(amount: float, currency: str = "USD") -> str:
        """
        Format currency amount for display.

        Args:
            amount: Currency amount
            currency: Currency code

        Returns:
            Formatted currency string
        """
        if amount == 0:
            return f"0 {currency}"

        # Format with thousands separator
        if amount >= 1000:
            formatted = f"{amount:,.0f}"
        else:
            formatted = f"{amount:.2f}"

        return f"{formatted} {currency}"

    @staticmethod
    def merge_flight_data(
        base_data: Dict[str, Any], additional_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge flight data from multiple sources.

        Args:
            base_data: Base flight data
            additional_data: Additional data to merge

        Returns:
            Merged flight data
        """
        merged = base_data.copy()

        for key, value in additional_data.items():
            if key not in merged or not merged[key]:
                merged[key] = value
            elif isinstance(value, dict) and isinstance(merged[key], dict):
                merged[key] = {**merged[key], **value}

        return merged

    @staticmethod
    def create_flight_id(flight_data: Dict[str, Any]) -> str:
        """
        Create unique flight identifier.

        Args:
            flight_data: Flight data dictionary

        Returns:
            Unique flight identifier
        """
        components = [
            flight_data.get("airline", ""),
            flight_data.get("flight_number", ""),
            flight_data.get("departure_time", ""),
            flight_data.get("arrival_time", ""),
        ]

        # Clean and join components
        clean_components = [str(comp).strip() for comp in components if comp]
        flight_id = "_".join(clean_components)

        # Add hash for uniqueness
        import hashlib

        hash_suffix = hashlib.md5(flight_id.encode()).hexdigest()[:8]

        return f"{flight_id}_{hash_suffix}"


class ConfigurationHelper:
    """
    Helper class for adapter configuration management.
    """

    @staticmethod
    def validate_config(config: Dict[str, Any]) -> List[str]:
        """
        Validate adapter configuration.

        Args:
            config: Configuration dictionary

        Returns:
            List of validation errors
        """
        errors = []

        # Required top-level keys
        required_keys = ["extraction_config", "data_validation"]
        for key in required_keys:
            if key not in config:
                errors.append(f"Missing required configuration key: {key}")

        # Validate extraction config
        if "extraction_config" in config:
            extraction_config = config["extraction_config"]

            if "search_form" not in extraction_config:
                errors.append("Missing search_form in extraction_config")

            if "results_parsing" not in extraction_config:
                errors.append("Missing results_parsing in extraction_config")

            # Validate search form config
            if "search_form" in extraction_config:
                search_form = extraction_config["search_form"]
                required_form_fields = [
                    "origin_field",
                    "destination_field",
                    "date_field",
                ]

                for field in required_form_fields:
                    if field not in search_form:
                        errors.append(f"Missing {field} in search_form config")

            # Validate results parsing config
            if "results_parsing" in extraction_config:
                results_config = extraction_config["results_parsing"]

                if "container" not in results_config:
                    errors.append(
                        "Missing container selector in results_parsing config"
                    )

        return errors

    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        """
        Get default configuration template.

        Returns:
            Default configuration dictionary
        """
        return {
            "rate_limiting": {
                "requests_per_second": 2,
                "burst_limit": 5,
                "cooldown_period": 60,
            },
            "error_handling": {
                "max_retries": 3,
                "retry_delay": 5,
                "circuit_breaker": {},
            },
            "monitoring": {},
            "extraction_config": {
                "search_form": {
                    "origin_field": "",
                    "destination_field": "",
                    "date_field": "",
                    "passengers_field": "",
                    "submit_button": "button[type='submit']",
                },
                "results_parsing": {
                    "container": "",
                    "airline": "",
                    "flight_number": "",
                    "departure_time": "",
                    "arrival_time": "",
                    "duration": "",
                    "price": "",
                },
            },
            "data_validation": {
                "required_fields": ["airline", "price"],
                "price_range": {"min": 0, "max": 100000},
                "duration_range": {"min": 0, "max": 1440},
            },
        }

    @staticmethod
    def merge_config(
        base_config: Dict[str, Any], override_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge configuration with overrides.

        Args:
            base_config: Base configuration
            override_config: Override configuration

        Returns:
            Merged configuration
        """

        def deep_merge(base: Dict, override: Dict) -> Dict:
            result = base.copy()

            for key, value in override.items():
                if (
                    key in result
                    and isinstance(result[key], dict)
                    and isinstance(value, dict)
                ):
                    result[key] = deep_merge(result[key], value)
                else:
                    result[key] = value

            return result

        return deep_merge(base_config, override_config)


class ErrorReportingHelper:
    """
    Helper class for consistent error reporting across adapters.
    """

    @staticmethod
    def create_error_report(
        adapter_name: str, error: Exception, context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Create standardized error report.

        Args:
            adapter_name: Name of the adapter
            error: Exception that occurred
            context: Additional context information

        Returns:
            Error report dictionary
        """
        report = {
            "adapter": adapter_name,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.now().isoformat(),
            "context": context or {},
        }

        # Add stack trace for debugging
        import traceback

        report["stack_trace"] = traceback.format_exc()

        return report

    @staticmethod
    def log_error_report(report: Dict[str, Any], logger: logging.Logger) -> None:
        """
        Log error report with appropriate level.

        Args:
            report: Error report dictionary
            logger: Logger instance
        """
        error_msg = (
            f"[{report['adapter']}] {report['error_type']}: {report['error_message']}"
        )

        # Log context if available
        if report.get("context"):
            error_msg += f" | Context: {report['context']}"

        logger.error(error_msg)

        # Log stack trace at debug level
        if report.get("stack_trace"):
            logger.debug(
                f"Stack trace for {report['adapter']}: {report['stack_trace']}"
            )


__all__ = [
    "EnhancedBaseCrawler",
    "EnhancedInternationalAdapter",
    "EnhancedPersianAdapter",
    "AdapterUtils",
    "ConfigurationHelper",
    "ErrorReportingHelper",
]
