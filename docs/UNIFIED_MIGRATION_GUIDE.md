# Migrating to the Unified Crawler Interface

This guide explains how to move existing code that relies on the legacy
`requests` or `crawlers` implementations to the new unified approach.

## Overview

The unified interface provides one set of classes for rate limiting,
progress reporting, session management and data validation.  Existing
modules continue to work thanks to compatibility wrappers.

## Steps

1. **Replace Legacy Imports**

   ```python
   # Old
   from base_crawler import BaseSiteCrawler
   
   # New
   from adapters.unified_crawler_interface import UnifiedCrawlerInterface
   ```

2. **Standardize Flight Data**

   Use `FlightDataStandardizer` to convert results from any system
   into the canonical `FlightData` model.

   ```python
   from flight_data_standardizer import FlightDataStandardizer
   from adapters.unified_crawler_interface import CrawlerSystemType

   standardizer = FlightDataStandardizer(CrawlerSystemType.REQUESTS)
   flights = standardizer.standardize(legacy_results)
   ```

3. **Validate Results**

   ```python
   from flight_data_validator import FlightDataValidator

   validator = FlightDataValidator()
   valid_flights = validator.validate([f.to_dict() for f in flights])
   ```

4. **Manage Sessions**

   ```python
   from session_manager import SessionManager
   session_manager = SessionManager()
   http_session = await session_manager.get_http_session()
   selenium = session_manager.get_selenium()
   ```

## Backward Compatibility

Wrapper classes such as `LegacyFlightDataStandardizer` allow old code to
continue functioning while migrating incrementally.

## Further Reading

See `UNIFIED_ARCHITECTURE_GUIDE.md` for an architectural overview of the
new components.
