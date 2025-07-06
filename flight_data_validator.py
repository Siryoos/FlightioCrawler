from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ValidationConfig:
    required_fields: List[str] = field(default_factory=lambda: ["airline", "price"])
    price_range: Dict[str, Any] = field(default_factory=lambda: {"min": 0, "max": float("inf")})
    duration_range: Dict[str, Any] = field(default_factory=lambda: {"min": 0, "max": 24 * 60})


class FlightDataValidator:
    """Validate flight data using unified rules."""

    def __init__(self, config: ValidationConfig | None = None) -> None:
        """
        Initialize the FlightDataValidator with a given validation configuration.
        
        If no configuration is provided, uses the default ValidationConfig.
        """
        self.config = config or ValidationConfig()

    def validate(self, flights: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Validate a list of flight records, returning only those that meet required field presence and configured value ranges.
        
        Each flight must contain all required fields with truthy values, a price convertible to float within the configured price range, and, if present, a duration in minutes convertible to int within the configured duration range.
        
        Parameters:
            flights (List[Dict[str, Any]]): List of flight data dictionaries to validate.
        
        Returns:
            List[Dict[str, Any]]: Filtered list of valid flight records.
        """
        valid: List[Dict[str, Any]] = []
        for flight in flights:
            if not all(flight.get(field) for field in self.config.required_fields):
                continue

            try:
                price = float(flight.get("price", 0))
            except (ValueError, TypeError):
                continue
            if not (self.config.price_range["min"] <= price <= self.config.price_range["max"]):
                continue

            if "duration_minutes" in flight:
                try:
                    dur = int(flight["duration_minutes"])
                except (ValueError, TypeError):
                    continue
                if not (self.config.duration_range["min"] <= dur <= self.config.duration_range["max"]):
                    continue

            valid.append(flight)
        return valid
