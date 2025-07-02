from typing import List, Dict
import re
from datetime import datetime

class RealDataQualityChecker:
    """Ensures extracted data is genuine and high-quality."""

    VALID_IATA = re.compile(r"^[A-Z]{3}$")
    VALID_FLIGHT_NO = re.compile(r"^[A-Z0-9]{2,3}\s?\d{2,4}$")

    async def validate_real_data_quality(self, flights: List[Dict]) -> tuple:
        validated: List[Dict] = []
        invalid_reasons = []
        for flight in flights:
            reason = []
            price = float(flight.get("price", 0))
            if price <= 0 or price > 200000000:
                reason.append("price")
            dep = flight.get("departure_time")
            arr = flight.get("arrival_time")
            if dep and arr and isinstance(dep, datetime) and isinstance(arr, datetime):
                if arr <= dep:
                    reason.append("time")
            if not self.VALID_IATA.match(str(flight.get("origin", ""))):
                reason.append("origin")
            if not self.VALID_IATA.match(str(flight.get("destination", ""))):
                reason.append("destination")
            if not self.VALID_FLIGHT_NO.match(str(flight.get("flight_number", ""))):
                reason.append("flight_number")
            if reason:
                invalid_reasons.append({"flight": flight, "reasons": reason})
                continue
            validated.append(flight)
        report = {
            "total": len(flights),
            "valid": len(validated),
            "invalid": len(flights) - len(validated),
            "details": invalid_reasons,
        }
        return validated, report

