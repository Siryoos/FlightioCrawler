"""
Selenium Handler for managing browser automation and anti-detection measures.
"""

import time
import random
from typing import Dict, Tuple, Optional, List
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, WebDriverException
import undetected_chromedriver as uc


class SeleniumHandler:
    """
    Enhanced Selenium handler with anti-detection capabilities and resource management.
    
    Features:
    - Anti-bot detection evasion
    - Random user agents and delays
    - Proper resource cleanup
    - Performance monitoring
    - Multiple fallback strategies
    """
    
    def __init__(self, headless: bool = False, timeout: int = 20):
        """
        Initialize the Selenium handler.
        
        Args:
            headless: Whether to run browser in headless mode
            timeout: Default timeout for operations
        """
        self.driver: Optional[webdriver.Chrome] = None
        self.headless = headless
        self.timeout = timeout
        self.use_undetected = True
        
        # User agent pool for rotation
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        ]
    
    def setup_driver(self) -> None:
        """
        Setup Selenium driver with anti-detection measures.
        
        Raises:
            Exception: If driver setup fails
        """
        try:
            if self.use_undetected:
                self._setup_undetected_driver()
            else:
                self._setup_standard_driver()
            
            # Apply anti-detection measures
            self._apply_anti_detection_measures()
            
        except Exception as e:
            # Fallback to standard Chrome if undetected fails
            if self.use_undetected:
                self.use_undetected = False
                self._setup_standard_driver()
            else:
                raise Exception(f"Failed to setup driver: {str(e)}")
    
    def _setup_undetected_driver(self) -> None:
        """Setup undetected Chrome driver."""
        options = uc.ChromeOptions()
        
        # Basic options
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        # Performance options
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        
        # Random user agent
        options.add_argument(f"user-agent={random.choice(self.user_agents)}")
        
        if self.headless:
            options.add_argument("--headless")
        
        self.driver = uc.Chrome(options=options)
    
    def _setup_standard_driver(self) -> None:
        """Setup standard Chrome driver as fallback."""
        options = Options()
        
        # Basic options
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        
        # Random user agent
        options.add_argument(f"user-agent={random.choice(self.user_agents)}")
        
        if self.headless:
            options.add_argument("--headless")
        
        self.driver = webdriver.Chrome(options=options)
    
    def _apply_anti_detection_measures(self) -> None:
        """Apply JavaScript-based anti-detection measures."""
        if not self.driver:
            return
        
        try:
            self.driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {
                    "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en']
                    });
                    window.chrome = {
                        runtime: {}
                    };
                    Object.defineProperty(navigator, 'permissions', {
                        get: () => ({
                            query: () => Promise.resolve({state: 'granted'})
                        })
                    });
                """
                },
            )
        except Exception as e:
            # CDP commands might not work in all environments
            pass
    
    def human_like_delay(self, min_delay: float = 0.5, max_delay: float = 2.0) -> None:
        """
        Add random delay to mimic human behavior.
        
        Args:
            min_delay: Minimum delay in seconds
            max_delay: Maximum delay in seconds
        """
        time.sleep(random.uniform(min_delay, max_delay))
    
    def navigate_to_url(self, url: str) -> None:
        """
        Navigate to a URL with proper error handling.
        
        Args:
            url: URL to navigate to
            
        Raises:
            Exception: If navigation fails
        """
        if not self.driver:
            self.setup_driver()
        
        try:
            self.driver.get(url)
            self.human_like_delay()
        except Exception as e:
            raise Exception(f"Navigation failed: {str(e)}")
    
    def wait_for_page_load(self, additional_wait: int = 2) -> None:
        """
        Wait for page to load completely and trigger lazy loading.
        
        Args:
            additional_wait: Additional wait time between scrolls
        """
        if not self.driver:
            return
        
        # Wait for basic page load
        WebDriverWait(self.driver, self.timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        # Scroll to trigger lazy loading
        self._trigger_lazy_loading(additional_wait)
    
    def _trigger_lazy_loading(self, wait_time: int = 2) -> None:
        """
        Scroll through page to trigger lazy loading.
        
        Args:
            wait_time: Time to wait between scrolls
        """
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        
        while True:
            # Scroll to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(wait_time)
            
            # Check if new content loaded
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
    
    def extract_page_data(self, url: str) -> Tuple[str, Dict]:
        """
        Extract comprehensive page data using Selenium.
        
        Args:
            url: URL to extract data from
            
        Returns:
            Tuple of (HTML content, selenium data)
            
        Raises:
            Exception: If extraction fails
        """
        try:
            # Navigate to URL
            self.navigate_to_url(url)
            
            # Wait for page to load
            self.wait_for_page_load()
            
            # Get page source
            html = self.driver.page_source
            
            # Collect performance and network data
            selenium_data = self._collect_browser_data()
            
            return html, selenium_data
            
        except Exception as e:
            raise Exception(f"Selenium extraction failed: {str(e)}")
    
    def _collect_browser_data(self) -> Dict:
        """
        Collect comprehensive browser data.
        
        Returns:
            Dictionary containing browser performance and network data
        """
        data = {
            "final_url": self.driver.current_url,
            "javascript_enabled": True,
        }
        
        try:
            # Performance data
            performance_data = self.driver.execute_script(
                """
                return {
                    timing: performance.timing,
                    resources: performance.getEntriesByType('resource').map(r => ({
                        name: r.name,
                        type: r.initiatorType,
                        duration: r.duration
                    }))
                };
                """
            )
            data["performance"] = performance_data
        except Exception:
            data["performance"] = {}
        
        try:
            # Console logs
            console_logs = self.driver.get_log("browser")
            data["console_logs"] = console_logs
        except Exception:
            data["console_logs"] = []
        
        try:
            # Cookies
            cookies = self.driver.get_cookies()
            data["cookies"] = cookies
        except Exception:
            data["cookies"] = []
        
        try:
            # XHR endpoints
            xhr_endpoints = self.driver.execute_script(
                """
                return Array.from(performance.getEntriesByType('resource'))
                    .filter(r => r.initiatorType === 'xmlhttprequest' || r.initiatorType === 'fetch')
                    .map(r => r.name);
                """
            )
            data["xhr_endpoints"] = xhr_endpoints
        except Exception:
            data["xhr_endpoints"] = []
        
        return data
    
    def close_driver(self) -> None:
        """Close the Selenium driver if it's running."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                print(f"Error closing driver: {e}")
            finally:
                self.driver = None
    
    def is_driver_active(self) -> bool:
        """Check if driver is active and responsive."""
        if not self.driver:
            return False
        
        try:
            # Try to get current URL to test if driver is responsive
            _ = self.driver.current_url
            return True
        except Exception:
            return False
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.close_driver() 