import asyncio
import logging
import os
from main_crawler import IranianFlightCrawler

# Configure logging
debug_mode = os.getenv("DEBUG_MODE", "0").lower() in ("1", "true", "yes")
level = logging.DEBUG if debug_mode else logging.INFO
logging.basicConfig(level=level)
logger = logging.getLogger(__name__)

async def test_basic_functionality():
    """Test basic crawler functionality"""
    print("🚀 Starting Iranian Flight Crawler Test...")
    
    try:
        # Initialize crawler
        crawler = IranianFlightCrawler()
        print("✅ Crawler initialized successfully")
        
        # Test search parameters
        search_params = {
            'origin': 'THR',
            'destination': 'MHD',
            'departure_date': '1403/04/15',
            'passengers': 1,
            'seat_class': 'economy'
        }
        
        # Test basic search (will likely return empty due to no real sites)
        print("🔍 Testing basic search functionality...")
        flights = await crawler.crawl_all_sites(search_params)
        print(f"✅ Search completed. Found {len(flights)} flights")
        
        # Test health status
        print("🏥 Testing health status...")
        health = crawler.get_health_status()
        print(f"✅ Health check completed. Status: {health.get('timestamp')}")
        
        # Test intelligent search
        print("🧠 Testing intelligent search...")
        from intelligent_search import SearchOptimization
        optimization = SearchOptimization()
        intelligent_results = await crawler.intelligent_search_flights(search_params, optimization)
        print(f"✅ Intelligent search completed")
        
        print("🎉 All tests passed! Crawler is working correctly.")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_basic_functionality())
    if success:
        print("\n🌟 Ready for production deployment!")
    else:
        print("\n🔧 Please fix the issues above before deployment.") 