import asyncio
from main_crawler import IranianFlightCrawler

async def main():
    # Initialize crawler
    crawler = IranianFlightCrawler()
    
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
            print(f"\nFlight: {flight.airline} {flight.flight_number}")
            print(f"Route: {flight.origin} -> {flight.destination}")
            print(f"Time: {flight.departure_time.strftime('%H:%M')} - {flight.arrival_time.strftime('%H:%M')}")
            print(f"Price: {flight.price:,} {flight.currency}")
            print(f"Class: {flight.seat_class}")
            print(f"Duration: {flight.duration_minutes} minutes")
            print("-" * 50)
        
        # Check crawler health
        health = crawler.monitor.get_health_status()
        print("\nCrawler Health Status:")
        print(f"Overall Status: {health['status']}")
        for domain, metrics in health['metrics'].items():
            print(f"\n{domain}:")
            print(f"  Status: {metrics['status']}")
            print(f"  Success Rate: {metrics['success_rate']}%")
            print(f"  Avg Response Time: {metrics['avg_response_time']}s")
            print(f"  Flights Scraped: {metrics['flights_scraped']}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 