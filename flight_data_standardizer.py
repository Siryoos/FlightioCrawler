from typing import Any, List

from adapters.unified_crawler_interface import (
    CrawlerSystemType,
    FlightData,
    standardize_flight_data,
)


class FlightDataStandardizer:
    """Utility class to normalize flight data across all systems."""

    def __init__(self, source_system: CrawlerSystemType) -> None:
        self.source_system = source_system

    def standardize(self, raw_data: Any) -> List[FlightData]:
        """Return a list of standardized FlightData objects."""
        return standardize_flight_data(raw_data, self.source_system)


class LegacyFlightDataStandardizer(FlightDataStandardizer):
    """Backward compatibility wrapper."""

    pass
