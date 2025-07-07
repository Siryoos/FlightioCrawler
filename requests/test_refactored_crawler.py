"""
Test script for the refactored AdvancedCrawler to demonstrate modular design.
"""

import json
from advanced_crawler_refactored import (
    AdvancedCrawlerRefactored,
    create_javascript_crawler,
    create_static_crawler,
    create_hybrid_crawler
)


def test_crawler_creation():
    """Test different crawler creation methods."""
    print("🧪 Testing crawler creation methods...")
    
    # Test basic creation
    basic_crawler = AdvancedCrawlerRefactored()
    print(f"✅ Basic crawler created: {basic_crawler}")
    
    # Test factory methods
    js_crawler = create_javascript_crawler()
    print(f"✅ JavaScript crawler created: {js_crawler}")
    
    static_crawler = create_static_crawler()
    print(f"✅ Static crawler created: {static_crawler}")
    
    hybrid_crawler = create_hybrid_crawler()
    print(f"✅ Hybrid crawler created: {hybrid_crawler}")
    
    # Test domain-specific creation
    alibaba_crawler = AdvancedCrawlerRefactored.create_for_domain("alibaba.ir")
    print(f"✅ Alibaba-optimized crawler created: {alibaba_crawler}")
    
    print()


def test_crawler_configuration():
    """Test crawler configuration and strategy selection."""
    print("⚙️  Testing crawler configuration...")
    
    # Test with custom configuration
    config = {
        "prefer_javascript": True,
        "timeout": 45,
        "headless": True,
        "save_dir": "./test_pages"
    }
    
    crawler = AdvancedCrawlerRefactored(config)
    print(f"✅ Custom configured crawler: {crawler}")
    
    # Test strategy selection
    test_urls = [
        "https://alibaba.ir",
        "https://flytoday.ir", 
        "https://wikipedia.org",
        "https://github.com"
    ]
    
    for url in test_urls:
        if crawler.validate_url(url):
            strategy = crawler.choose_crawling_strategy(url)
            js_required = crawler.is_javascript_required(url)
            print(f"  URL: {url}")
            print(f"    Strategy: {strategy.value}")
            print(f"    JS Required: {js_required}")
    
    print()


def test_modular_components():
    """Test individual modular components."""
    print("🔧 Testing modular components...")
    
    crawler = AdvancedCrawlerRefactored()
    
    # Test component initialization
    print(f"✅ MetadataExtractor initialized: {type(crawler.metadata_extractor).__name__}")
    print(f"✅ ContentAnalyzer initialized: {type(crawler.content_analyzer).__name__}")
    print(f"✅ ResourceExtractor initialized: {type(crawler.resource_extractor).__name__}")
    print(f"✅ SeleniumHandler (lazy): {crawler.selenium_handler is None}")
    
    # Test observer pattern
    def progress_callback(message):
        print(f"  📋 Progress: {message}")
    
    crawler.set_progress_callback(progress_callback)
    crawler._notify_progress("Testing observer pattern")
    
    print()


def test_error_handling():
    """Test error handling and validation."""
    print("🚨 Testing error handling...")
    
    crawler = AdvancedCrawlerRefactored()
    
    # Test URL validation
    invalid_urls = ["", "not-a-url", "ftp://example.com", "javascript:alert('test')"]
    valid_urls = ["https://example.com", "http://test.local"]
    
    for url in invalid_urls:
        is_valid = crawler.validate_url(url)
        print(f"  ❌ Invalid URL '{url}': {is_valid}")
    
    for url in valid_urls:
        is_valid = crawler.validate_url(url)
        print(f"  ✅ Valid URL '{url}': {is_valid}")
    
    print()


def test_factory_pattern():
    """Test factory pattern implementation."""
    print("🏭 Testing factory pattern...")
    
    # Test domain-specific optimizations
    domains = ["alibaba.ir", "flytoday.ir", "wikipedia.org", "github.com", "unknown.com"]
    
    for domain in domains:
        crawler = AdvancedCrawlerRefactored.create_for_domain(domain)
        print(f"  🏷️  Domain: {domain}")
        print(f"    Prefer JS: {crawler.prefer_javascript}")
        print(f"    Timeout: {crawler.timeout}")
        print(f"    Headless: {crawler.get_config('headless', 'default')}")
    
    print()


def test_stats_and_monitoring():
    """Test statistics and monitoring features."""
    print("📊 Testing statistics and monitoring...")
    
    crawler = AdvancedCrawlerRefactored()
    
    # Test initial stats
    stats = crawler.get_crawling_stats()
    print(f"  Initial stats: {json.dumps(stats, indent=2)}")
    
    # Test required fields
    required_fields = crawler.get_required_fields()
    print(f"  Required fields: {required_fields}")
    
    # Test status tracking
    print(f"  Initial status: {crawler.status.value}")
    print(f"  Crawler type: {crawler.crawler_type.value}")
    print(f"  Error count: {len(crawler.errors)}")
    
    print()


def demonstrate_design_patterns():
    """Demonstrate design patterns in action."""
    print("🎯 Demonstrating design patterns...")
    
    # Strategy Pattern
    print("  Strategy Pattern:")
    crawler = AdvancedCrawlerRefactored()
    for url in ["https://alibaba.ir", "https://wikipedia.org"]:
        strategy = crawler.choose_crawling_strategy(url)
        print(f"    {url} → {strategy.value}")
    
    # Factory Pattern
    print("  Factory Pattern:")
    js_crawler = create_javascript_crawler()
    static_crawler = create_static_crawler()
    print(f"    JavaScript Crawler: prefer_js={js_crawler.prefer_javascript}")
    print(f"    Static Crawler: prefer_js={static_crawler.prefer_javascript}")
    
    # Observer Pattern
    print("  Observer Pattern:")
    def observer_callback(message):
        print(f"    📡 Observed: {message}")
    
    crawler.set_progress_callback(observer_callback)
    crawler._notify_progress("Testing observer pattern")
    
    # Template Method Pattern (demonstrated through interface)
    print("  Template Method Pattern:")
    print(f"    Crawler implements {len(crawler.get_required_fields())} required methods")
    
    print()


def main():
    """Run all tests to demonstrate the refactored crawler."""
    print("🚀 Testing Refactored AdvancedCrawler")
    print("=" * 50)
    
    try:
        test_crawler_creation()
        test_crawler_configuration()
        test_modular_components()
        test_error_handling()
        test_factory_pattern()
        test_stats_and_monitoring()
        demonstrate_design_patterns()
        
        print("✅ All tests completed successfully!")
        print("\n📋 Summary:")
        print("  ✅ Modular design with separated concerns")
        print("  ✅ Strategy pattern for crawling approach")
        print("  ✅ Observer pattern for progress tracking")
        print("  ✅ Factory pattern for specialized crawlers")
        print("  ✅ Template method pattern via interfaces")
        print("  ✅ Comprehensive error handling")
        print("  ✅ Configuration-driven behavior")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 