"""
Performance Profiling Script for the Flight Crawler.

This script uses cProfile to profile the execution of the main crawler
for a sample search scenario and saves the results for analysis.
"""
import asyncio
import cProfile
import pstats
import os
import sys
from io import StringIO

# Add project root to path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main_crawler import IranianFlightCrawler
from config import config  # Ensure config is loaded

async def profile_scenario():
    """Defines and runs the profiling scenario."""
    print("Initializing crawler for profiling...")
    # We need a running event loop to create the http_session
    import aiohttp
    async with aiohttp.ClientSession() as session:
        crawler = IranianFlightCrawler(http_session=session)

        search_params = {
            "origin": "THR",
            "destination": "MHD",
            "departure_date": "1403/08/10",  # Use a valid future date in Persian format
        }

        print(f"Starting profiling for search: {search_params}")
        
        # Run the crawl method under the profiler
        profiler = cProfile.Profile()
        profiler.enable()

        try:
            await crawler.crawl_all_sites(search_params)
        finally:
            profiler.disable()
            print("Profiling finished.")

            # Save and print stats
            s = StringIO()
            sortby = pstats.SortKey.CUMULATIVE
            ps = pstats.Stats(profiler, stream=s).sort_stats(sortby)
            ps.print_stats()

            # Save to file
            profile_file = "profile_results.prof"
            ps.dump_stats(profile_file)
            print(f"Profile stats saved to {profile_file}")

            # Print to console
            print("\n--- Top 20 cumulative time functions ---")
            ps.print_stats(20)

            # Close crawler resources
            await crawler.shutdown()

if __name__ == "__main__":
    # Ensure the environment is set up correctly (e.g., for DB connections)
    # This might require more specific setup depending on the project structure.
    config.load_configs()
    
    try:
        asyncio.run(profile_scenario())
    except KeyboardInterrupt:
        print("\nProfiling interrupted by user.") 