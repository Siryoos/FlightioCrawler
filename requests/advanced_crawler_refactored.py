"""
Refactored Advanced Crawler using design patterns and modular components.
"""

import os
import json
import time
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Callable
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# Import our modular components
from selenium_handler import SeleniumHandler
from metadata_extractor import MetadataExtractor
from content_analyzer import ContentAnalyzer
from resource_extractor import ResourceExtractor
from base_crawler_interface import HybridCrawlerInterface, CrawlerType, CrawlerStatus


class AdvancedCrawlerRefactored(HybridCrawlerInterface):
    """
    Refactored Advanced Crawler implementing design patterns.
    
    Features:
    - Modular design with separated concerns
    - Strategy pattern for crawling approach
    - Observer pattern for progress tracking
    - Template method pattern for consistent workflow
    - Factory pattern support
    - Comprehensive error handling
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the refactored crawler.
        
        Args:
            config: Configuration dictionary
        """
        super().__init__(config)
        
        # Configuration
        self.save_dir = self.get_config("save_dir") or os.path.join(os.path.dirname(__file__), "pages")
        self.prefer_javascript = self.get_config("prefer_javascript", True)
        self.timeout = self.get_config("timeout", 30)
        self.user_agent = self.get_config("user_agent", 
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
        
        # Ensure save directory exists
        os.makedirs(self.save_dir, exist_ok=True)
        
        # Initialize modular components
        self.selenium_handler: Optional[SeleniumHandler] = None
        self.metadata_extractor = MetadataExtractor()
        self.content_analyzer = ContentAnalyzer()
        self.resource_extractor = ResourceExtractor()
        
        # Progress callback for observer pattern
        self.progress_callback: Optional[Callable[[str], None]] = None
        
        # Crawling statistics
        self.stats = {
            "start_time": None,
            "end_time": None,
            "duration": 0,
            "strategy_used": None,
            "fallback_used": False,
            "data_size": 0,
        }
    
    def set_progress_callback(self, callback: Callable[[str], None]) -> None:
        """Set progress callback for observer pattern."""
        self.progress_callback = callback
    
    def _notify_progress(self, message: str) -> None:
        """Notify progress observers."""
        if self.progress_callback:
            self.progress_callback(message)
        self.notify_observers("progress", {"message": message, "status": self.status.value})
    
    # Interface implementation - abstract methods
    
    def validate_url(self, url: str) -> bool:
        """Validate if URL is suitable for crawling."""
        try:
            parsed = urlparse(url)
            return bool(parsed.scheme and parsed.netloc)
        except Exception:
            return False
    
    def cleanup(self) -> None:
        """Cleanup resources."""
        if self.selenium_handler:
            self.selenium_handler.close_driver()
            self.selenium_handler = None
    
    # Static crawler interface implementation
    
    def fetch_html(self, url: str) -> str:
        """Fetch HTML using requests."""
        self._notify_progress("Fetching HTML with requests...")
        
        headers = {"User-Agent": self.user_agent}
        response = requests.get(url, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        
        return response.text
    
    def parse_html(self, html: str) -> BeautifulSoup:
        """Parse HTML into BeautifulSoup object."""
        return BeautifulSoup(html, "html.parser")
    
    # JavaScript crawler interface implementation
    
    def setup_browser(self) -> None:
        """Setup browser for JavaScript crawling."""
        if not self.selenium_handler:
            selenium_config = {
                "headless": self.get_config("headless", False),
                "timeout": self.timeout
            }
            self.selenium_handler = SeleniumHandler(**selenium_config)
    
    def execute_javascript(self, script: str) -> Any:
        """Execute JavaScript in browser context."""
        if not self.selenium_handler or not self.selenium_handler.driver:
            raise RuntimeError("Browser not initialized")
        
        return self.selenium_handler.driver.execute_script(script)
    
    def wait_for_element(self, selector: str, timeout: int = 10) -> bool:
        """Wait for element to appear."""
        if not self.selenium_handler or not self.selenium_handler.driver:
            return False
        
        try:
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.common.by import By
            
            wait = WebDriverWait(self.selenium_handler.driver, timeout)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            return True
        except Exception:
            return False
    
    def close_browser(self) -> None:
        """Close browser."""
        if self.selenium_handler:
            self.selenium_handler.close_driver()
    
    # Hybrid crawler interface implementation
    
    def choose_crawling_strategy(self, url: str) -> CrawlerType:
        """Choose appropriate crawling strategy for URL."""
        # Simple heuristics - can be enhanced with ML
        domain = urlparse(url).netloc.lower()
        
        # Known JavaScript-heavy sites
        js_heavy_domains = [
            "alibaba.ir", "flytoday.ir", "snapptrip.com", 
            "flightio.com", "safarmarket.com"
        ]
        
        # Check if domain requires JavaScript
        if any(js_domain in domain for js_domain in js_heavy_domains):
            return CrawlerType.JAVASCRIPT
        
        # Default strategy based on configuration
        return CrawlerType.JAVASCRIPT if self.prefer_javascript else CrawlerType.STATIC
    
    def fallback_strategy(self, url: str, primary_failed: bool = False) -> Tuple[bool, Dict[str, Any], str]:
        """Fallback crawling strategy."""
        self.stats["fallback_used"] = True
        
        try:
            if primary_failed:
                self._notify_progress("Primary strategy failed, trying fallback...")
                
                # If JavaScript failed, try static
                if self.stats["strategy_used"] == CrawlerType.JAVASCRIPT:
                    return self._crawl_static(url)
                # If static failed, try JavaScript
                else:
                    return self._crawl_javascript(url)
            else:
                # Choose opposite of preferred strategy
                if self.prefer_javascript:
                    return self._crawl_static(url)
                else:
                    return self._crawl_javascript(url)
                    
        except Exception as e:
            return False, {}, f"Fallback strategy failed: {str(e)}"
    
    # Main crawling implementation
    
    def crawl(self, url: str, **kwargs) -> Tuple[bool, Dict[str, Any], str]:
        """Main crawling method implementing strategy pattern."""
        self.stats["start_time"] = time.time()
        
        try:
            # Choose strategy
            strategy = self.choose_crawling_strategy(url)
            self.stats["strategy_used"] = strategy
            
            self._notify_progress(f"Using {strategy.value} crawling strategy...")
            
            # Execute chosen strategy
            if strategy == CrawlerType.JAVASCRIPT:
                success, data, message = self._crawl_javascript(url)
            else:
                success, data, message = self._crawl_static(url)
            
            # Try fallback if primary failed
            if not success:
                success, data, message = self.fallback_strategy(url, primary_failed=True)
            
            return success, data, message
            
        except Exception as e:
            self.add_error(f"Crawl failed: {str(e)}")
            return False, {}, str(e)
        finally:
            self.stats["end_time"] = time.time()
            if self.stats["start_time"]:
                self.stats["duration"] = self.stats["end_time"] - self.stats["start_time"]
    
    def _crawl_javascript(self, url: str) -> Tuple[bool, Dict[str, Any], str]:
        """Crawl using JavaScript/Selenium."""
        try:
            self.setup_browser()
            self._notify_progress("Extracting content with JavaScript...")
            
            # Extract page data using Selenium
            html, selenium_data = self.selenium_handler.extract_page_data(url)
            
            # Parse and extract content
            soup = self.parse_html(html)
            extracted_data = self.extract_content(soup, url)
            
            # Merge selenium data
            extracted_data["selenium_data"] = selenium_data
            extracted_data["strategy_used"] = "javascript"
            
            # Save data
            self._save_crawled_data(url, html, extracted_data)
            
            return True, extracted_data, "JavaScript crawling completed successfully"
            
        except Exception as e:
            self.add_error(f"JavaScript crawling failed: {str(e)}")
            return False, {}, str(e)
    
    def _crawl_static(self, url: str) -> Tuple[bool, Dict[str, Any], str]:
        """Crawl using static requests."""
        try:
            # Fetch HTML
            html = self.fetch_html(url)
            
            # Parse and extract content
            soup = self.parse_html(html)
            extracted_data = self.extract_content(soup, url)
            
            # Add static crawling metadata
            extracted_data["selenium_data"] = {
                "final_url": url,
                "javascript_enabled": False,
            }
            extracted_data["strategy_used"] = "static"
            
            # Save data
            self._save_crawled_data(url, html, extracted_data)
            
            return True, extracted_data, "Static crawling completed successfully"
            
        except Exception as e:
            self.add_error(f"Static crawling failed: {str(e)}")
            return False, {}, str(e)
    
    def extract_content(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Extract all content using modular extractors."""
        self._notify_progress("Extracting metadata...")
        
        # Extract using modular components
        content_data = {
            "url": url,
            "timestamp": datetime.now().isoformat(),
            "crawler_info": {
                "crawler_type": self.crawler_type.value,
                "strategy_used": self.stats.get("strategy_used"),
                "fallback_used": self.stats.get("fallback_used", False),
            }
        }
        
        try:
            # Extract metadata
            self._notify_progress("Extracting metadata...")
            content_data["metadata"] = self.metadata_extractor.extract_metadata(soup, url)
            
            # Extract AJAX data
            content_data["ajax_data"] = self.metadata_extractor.extract_ajax_data(soup)
            
            # Analyze content
            self._notify_progress("Analyzing content structure...")
            content_data["content_analysis"] = self.content_analyzer.analyze_content(soup)
            
            # Extract resources and links
            self._notify_progress("Extracting resources and links...")
            resource_data = self.resource_extractor.extract_all_resources(soup, url)
            content_data.update(resource_data)
            
            # Add summaries
            content_data["metadata_summary"] = self.metadata_extractor.get_metadata_summary(content_data["metadata"])
            content_data["content_summary"] = self.content_analyzer.get_content_summary(content_data["content_analysis"])
            content_data["resource_summary"] = self.resource_extractor.get_resource_summary(resource_data)
            
            # Update statistics
            self.stats["data_size"] = len(json.dumps(content_data, ensure_ascii=False))
            
            return content_data
            
        except Exception as e:
            self.add_error(f"Content extraction failed: {str(e)}")
            raise
    
    def _save_crawled_data(self, url: str, html: str, data: Dict[str, Any]) -> Tuple[str, str]:
        """Save crawled data to files."""
        self._notify_progress("Saving crawled data...")
        
        # Generate filename
        from urllib.parse import quote
        base_filename = quote(url.replace('://', '_').replace('/', '_'), safe='')
        
        # Save HTML
        html_path = os.path.join(self.save_dir, f"{base_filename}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        
        # Save metadata
        json_path = os.path.join(self.save_dir, f"{base_filename}_metadata.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return html_path, json_path
    
    # Enhanced functionality
    
    def get_crawling_stats(self) -> Dict[str, Any]:
        """Get crawling statistics."""
        return self.stats.copy()
    
    def is_javascript_required(self, url: str) -> bool:
        """Heuristic to determine if JavaScript is required for a URL."""
        try:
            html = self.fetch_html(url)
            soup = self.parse_html(html)
            
            # Check for indicators of JavaScript dependence
            indicators = [
                len(soup.find_all("script")) > 5,  # Many scripts
                bool(soup.find(attrs={"data-reactroot": True})),  # React
                bool(soup.find(attrs={"ng-app": True})),  # Angular
                "Loading..." in soup.get_text(),  # Loading indicators
                len(soup.get_text().strip()) < 100,  # Minimal content
            ]
            
            return sum(indicators) >= 2
            
        except Exception:
            # If static fails, assume JavaScript is needed
            return True
    
    def get_required_fields(self) -> List[str]:
        """Define required fields for validation."""
        return ["url", "timestamp", "metadata", "content_analysis"]
    
    # Factory method for creating specialized crawlers
    
    @classmethod
    def create_for_domain(cls, domain: str, config: Optional[Dict[str, Any]] = None) -> "AdvancedCrawlerRefactored":
        """Factory method to create crawler optimized for specific domain."""
        config = config or {}
        
        # Domain-specific optimizations
        if "alibaba.ir" in domain:
            config.update({
                "prefer_javascript": True,
                "timeout": 60,
                "headless": False,
            })
        elif "flytoday.ir" in domain:
            config.update({
                "prefer_javascript": True,
                "timeout": 45,
            })
        elif any(static_domain in domain for static_domain in ["wikipedia.org", "github.com"]):
            config.update({
                "prefer_javascript": False,
                "timeout": 20,
            })
        
        return cls(config)
    
    def __repr__(self) -> str:
        """Detailed string representation."""
        return (f"AdvancedCrawlerRefactored("
                f"status={self.status.value}, "
                f"type={self.crawler_type.value}, "
                f"errors={len(self.errors)}, "
                f"prefer_js={self.prefer_javascript})")


# Convenience factory functions

def create_javascript_crawler(config: Optional[Dict[str, Any]] = None) -> AdvancedCrawlerRefactored:
    """Create a JavaScript-focused crawler."""
    config = config or {}
    config["prefer_javascript"] = True
    return AdvancedCrawlerRefactored(config)


def create_static_crawler(config: Optional[Dict[str, Any]] = None) -> AdvancedCrawlerRefactored:
    """Create a static HTML crawler."""
    config = config or {}
    config["prefer_javascript"] = False
    return AdvancedCrawlerRefactored(config)


def create_hybrid_crawler(config: Optional[Dict[str, Any]] = None) -> AdvancedCrawlerRefactored:
    """Create a hybrid crawler with intelligent strategy selection."""
    config = config or {}
    return AdvancedCrawlerRefactored(config) 