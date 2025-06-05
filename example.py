import asyncio
from main_crawler import IranianFlightCrawler

async def main():
    # Initialize crawler
    crawler = IranianFlightCrawler()

    class DummyCrawler:
        async def search_flights(self, params):
            await asyncio.sleep(0)
            return [{"flight_number": "XX123", "airline": "DemoAir"}]

    # Replace real site crawlers with dummy ones for the demo
    for key in list(crawler.crawlers.keys()):
        crawler.crawlers[key] = DummyCrawler()
    
    # Example search parameters
    search_params = {
        'origin': 'THR',  # Tehran
        'destination': 'MHD',  # Mashhad
        'departure_date': '1403/04/15',  # Persian date
        'passengers': 1,
        'seat_class': 'economy'
    }
    
    try:
        # Search for flights
        print("Searching for flights...")
        flights = await crawler.crawl_all_sites(search_params)
        
        # Print results
        print(f"\nFound {len(flights)} flights:")
        for flight in flights:
            if isinstance(flight, dict):
                airline = flight.get("airline")
                fn = flight.get("flight_number")
                origin = flight.get("origin")
                dest = flight.get("destination")
                price = flight.get("price")
                currency = flight.get("currency")
                seat = flight.get("seat_class")
                dep = flight.get("departure_time")
                arr = flight.get("arrival_time")
                duration = flight.get("duration")
            else:
                airline = flight.airline
                fn = flight.flight_number
                origin = flight.origin
                dest = flight.destination
                price = flight.price
                currency = flight.currency
                seat = flight.seat_class
                dep = flight.departure_time
                arr = flight.arrival_time
                duration = flight.duration_minutes

            print(f"\nFlight: {airline} {fn}")
            print(f"Route: {origin} -> {dest}")
            print(f"Time: {dep} - {arr}")
            print(f"Price: {price} {currency}")
            print(f"Class: {seat}")
            print(f"Duration: {duration} minutes")
            print("-" * 50)
        
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 