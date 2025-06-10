import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import asyncio
import logging

from bs4 import BeautifulSoup

from data_manager import DataManager
from persian_text import PersianTextProcessor

logger = logging.getLogger(__name__)

PAGES_DIR = Path(__file__).resolve().parent.parent / "requests" / "pages"

processor = PersianTextProcessor()


def _parse_flightio(html: str, url: str) -> list[dict]:
    """Extract flight data from a saved Flightio results page."""
    soup = BeautifulSoup(html, "html.parser")
    flights = []
    for item in soup.select("div.resu"):
        try:
            price_el = item.select_one("div.price span")
            if not price_el:
                continue
            dep_el = item.select_one("div.date")
            departure_time = processor.parse_time(dep_el.text) if dep_el else None
            airline_el = item.select_one("strong.airline_name")
            airline = (
                processor.normalize_airline_name(airline_el.text) if airline_el else ""
            )
            flight_no_el = item.select_one("span.code_inn")
            flight_number = processor.process(flight_no_el.text) if flight_no_el else ""
            seat_class = item.select_one("div.price").get("rel", "")
            flights.append(
                {
                    "airline": airline,
                    "flight_number": flight_number,
                    "origin": "",
                    "destination": "",
                    "departure_time": departure_time,
                    "arrival_time": None,
                    "price": processor.extract_price(price_el.text)[0],
                    "currency": "IRR",
                    "seat_class": seat_class,
                    "duration_minutes": 0,
                    "source_url": url,
                }
            )
        except Exception as exc:  # pragma: no cover - best effort
            logger.error(f"Error parsing flight: {exc}")
    return flights


def _extract_params(url: str) -> tuple[str, str, str]:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    path_parts = parsed.path.strip("/").split("/")
    route = path_parts[-1]
    if "-" in route:
        origin, destination = route.split("-")[:2]
    else:
        origin = destination = ""
    depart = params.get("depart", [""])[0]
    return origin, destination, depart


def _parse_file(html_path: Path) -> list[dict]:
    meta_path = html_path.with_suffix(html_path.suffix + "_metadata.json")
    url = ""
    if meta_path.exists():
        with meta_path.open("r", encoding="utf-8") as fh:
            meta = json.load(fh)
            url = meta.get("url", "")
    with html_path.open("r", encoding="utf-8", errors="ignore") as fh:
        html = fh.read()
    flights = _parse_flightio(html, url)
    origin, destination, depart = _extract_params(url)
    for f in flights:
        if origin:
            f["origin"] = origin
        if destination:
            f["destination"] = destination
        if depart and f["departure_time"]:
            try:
                date_parts = [int(p) for p in depart.split("-")]
                f["departure_time"] = f["departure_time"].replace(
                    year=date_parts[0], month=date_parts[1], day=date_parts[2]
                )
            except Exception:
                pass
    return flights


def main() -> None:
    dm = DataManager()
    all_flights: list[dict] = []
    for html_file in PAGES_DIR.glob("*.html"):
        flights = _parse_file(html_file)
        if flights:
            all_flights.extend(flights)
    if all_flights:
        asyncio.run(dm.store_flights({"samples": all_flights}))
        print(f"Stored {len(all_flights)} flights")
    else:
        print("No flights parsed")


if __name__ == "__main__":
    main()
