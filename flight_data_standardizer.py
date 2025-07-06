from typing import Any, List

from adapters.unified_crawler_interface import (
    CrawlerSystemType,
    FlightData,
    standardize_flight_data,
)


class FlightDataStandardizer:
    """Utility class to normalize flight data across all systems."""

    def __init__(self, source_system: CrawlerSystemType) -> None:
        """
        Initialize the FlightDataStandardizer with a specified source system.
        
        Parameters:
            source_system (CrawlerSystemType): Identifier for the source system from which flight data originates.
        """
        self.source_system = source_system

    def standardize(self, raw_data: Any) -> List[FlightData]:
        """
        Convert raw flight data from a specific source system into a list of standardized FlightData objects.
        
        Parameters:
        	raw_data: The raw flight data to be standardized.
        
        Returns:
        	A list of FlightData objects representing the normalized flight information.
        """
        return standardize_flight_data(raw_data, self.source_system)


class LegacyFlightDataStandardizer(FlightDataStandardizer):
    """Backward compatibility wrapper."""

    pass
