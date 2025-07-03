"""
Base Crawler Interface for defining crawler contracts and common functionality.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple
from bs4 import BeautifulSoup
from enum import Enum


class CrawlerStatus(Enum):
    """Enumeration for crawler status."""
    IDLE = "idle"
    INITIALIZING = "initializing"
    CRAWLING = "crawling"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


class CrawlerType(Enum):
    """Enumeration for crawler types."""
    STATIC = "static"
    JAVASCRIPT = "javascript"
    HYBRID = "hybrid"


class BaseCrawlerInterface(ABC):
    """
    Abstract base class defining the interface for all crawler implementations.
    
    This interface ensures consistency across different crawler types and
    provides a foundation for the Strategy and Template Method patterns.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the crawler with configuration.
        
        Args:
            config: Configuration dictionary for the crawler
        """
        self.config = config or {}
        self.status = CrawlerStatus.IDLE
        self.crawler_type = CrawlerType.STATIC
        self.errors = []
        self.warnings = []
        self.metadata = {}
    
    @abstractmethod
    def crawl(self, url: str, **kwargs) -> Tuple[bool, Dict[str, Any], str]:
        """
        Main crawling method that must be implemented by all crawlers.
        
        Args:
            url: URL to crawl
            **kwargs: Additional parameters specific to crawler implementation
            
        Returns:
            Tuple of (success: bool, data: Dict, message: str)
        """
        pass
    
    @abstractmethod
    def extract_content(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """
        Extract content from parsed HTML.
        
        Args:
            soup: BeautifulSoup object of parsed HTML
            url: Original URL
            
        Returns:
            Dictionary containing extracted content
        """
        pass
    
    @abstractmethod
    def validate_url(self, url: str) -> bool:
        """
        Validate if the URL is suitable for this crawler.
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL is valid for this crawler
        """
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """
        Cleanup resources used by the crawler.
        
        This method should be called when the crawler is no longer needed.
        """
        pass
    
    # Template method pattern - common workflow
    def execute_crawl_workflow(self, url: str, **kwargs) -> Tuple[bool, Dict[str, Any], str]:
        """
        Template method that defines the standard crawling workflow.
        
        This method provides a consistent structure while allowing
        subclasses to customize specific steps.
        
        Args:
            url: URL to crawl
            **kwargs: Additional parameters
            
        Returns:
            Tuple of (success: bool, data: Dict, message: str)
        """
        try:
            # Step 1: Validation
            self.status = CrawlerStatus.INITIALIZING
            if not self.pre_crawl_validation(url):
                return False, {}, "Pre-crawl validation failed"
            
            # Step 2: Initialize
            self.initialize_crawler()
            
            # Step 3: Crawl
            self.status = CrawlerStatus.CRAWLING
            success, data, message = self.crawl(url, **kwargs)
            
            if not success:
                self.status = CrawlerStatus.ERROR
                return success, data, message
            
            # Step 4: Post-process
            self.status = CrawlerStatus.PROCESSING
            processed_data = self.post_process_data(data)
            
            # Step 5: Validate results
            if self.validate_results(processed_data):
                self.status = CrawlerStatus.COMPLETED
                return True, processed_data, "Crawl completed successfully"
            else:
                self.status = CrawlerStatus.ERROR
                return False, processed_data, "Result validation failed"
                
        except Exception as e:
            self.status = CrawlerStatus.ERROR
            self.add_error(f"Crawl workflow failed: {str(e)}")
            return False, {}, str(e)
        finally:
            self.cleanup()
    
    def pre_crawl_validation(self, url: str) -> bool:
        """
        Perform validation before crawling starts.
        
        Args:
            url: URL to validate
            
        Returns:
            True if validation passes
        """
        if not url or not isinstance(url, str):
            self.add_error("Invalid URL provided")
            return False
        
        if not self.validate_url(url):
            self.add_error(f"URL validation failed for: {url}")
            return False
        
        return True
    
    def initialize_crawler(self) -> None:
        """
        Initialize crawler-specific resources.
        
        Override this method to perform custom initialization.
        """
        self.errors.clear()
        self.warnings.clear()
        self.metadata.clear()
    
    def post_process_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Post-process extracted data.
        
        Args:
            data: Raw extracted data
            
        Returns:
            Processed data
        """
        # Default implementation - override for custom processing
        processed_data = data.copy()
        
        # Add common metadata
        processed_data.setdefault("crawler_metadata", {}).update({
            "crawler_type": self.crawler_type.value,
            "status": self.status.value,
            "errors": self.errors.copy(),
            "warnings": self.warnings.copy(),
        })
        
        return processed_data
    
    def validate_results(self, data: Dict[str, Any]) -> bool:
        """
        Validate the extracted results.
        
        Args:
            data: Extracted data to validate
            
        Returns:
            True if results are valid
        """
        # Basic validation - ensure data is not empty
        if not data:
            self.add_error("No data extracted")
            return False
        
        # Check for required fields (can be overridden)
        required_fields = self.get_required_fields()
        for field in required_fields:
            if field not in data:
                self.add_error(f"Required field missing: {field}")
                return False
        
        return True
    
    def get_required_fields(self) -> List[str]:
        """
        Get list of required fields in the extracted data.
        
        Override this method to specify crawler-specific requirements.
        
        Returns:
            List of required field names
        """
        return []  # Default: no required fields
    
    # Error and warning management
    def add_error(self, error: str) -> None:
        """Add an error message."""
        self.errors.append(error)
    
    def add_warning(self, warning: str) -> None:
        """Add a warning message."""
        self.warnings.append(warning)
    
    def has_errors(self) -> bool:
        """Check if crawler has any errors."""
        return len(self.errors) > 0
    
    def has_warnings(self) -> bool:
        """Check if crawler has any warnings."""
        return len(self.warnings) > 0
    
    def get_status(self) -> CrawlerStatus:
        """Get current crawler status."""
        return self.status
    
    def set_status(self, status: CrawlerStatus) -> None:
        """Set crawler status."""
        self.status = status
    
    # Configuration management
    def update_config(self, config: Dict[str, Any]) -> None:
        """
        Update crawler configuration.
        
        Args:
            config: Configuration updates
        """
        self.config.update(config)
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        return self.config.get(key, default)
    
    # Observer pattern support
    def add_observer(self, observer) -> None:
        """
        Add an observer for crawler events.
        
        Args:
            observer: Observer object with update method
        """
        if not hasattr(self, '_observers'):
            self._observers = []
        self._observers.append(observer)
    
    def remove_observer(self, observer) -> None:
        """
        Remove an observer.
        
        Args:
            observer: Observer to remove
        """
        if hasattr(self, '_observers') and observer in self._observers:
            self._observers.remove(observer)
    
    def notify_observers(self, event: str, data: Any = None) -> None:
        """
        Notify all observers of an event.
        
        Args:
            event: Event name
            data: Event data
        """
        if hasattr(self, '_observers'):
            for observer in self._observers:
                if hasattr(observer, 'update'):
                    observer.update(event, data)
    
    # Context manager support
    def __enter__(self):
        """Context manager entry."""
        self.initialize_crawler()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.cleanup()
    
    # String representation
    def __str__(self) -> str:
        """String representation of the crawler."""
        return f"{self.__class__.__name__}(status={self.status.value}, type={self.crawler_type.value})"
    
    def __repr__(self) -> str:
        """Detailed string representation."""
        return (f"{self.__class__.__name__}("
                f"status={self.status.value}, "
                f"type={self.crawler_type.value}, "
                f"errors={len(self.errors)}, "
                f"warnings={len(self.warnings)})")


class StaticCrawlerInterface(BaseCrawlerInterface):
    """
    Interface for static HTML crawlers (requests-based).
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.crawler_type = CrawlerType.STATIC
    
    @abstractmethod
    def fetch_html(self, url: str) -> str:
        """
        Fetch HTML content from URL.
        
        Args:
            url: URL to fetch
            
        Returns:
            HTML content as string
        """
        pass
    
    @abstractmethod
    def parse_html(self, html: str) -> BeautifulSoup:
        """
        Parse HTML content into BeautifulSoup object.
        
        Args:
            html: HTML content
            
        Returns:
            BeautifulSoup object
        """
        pass


class JavaScriptCrawlerInterface(BaseCrawlerInterface):
    """
    Interface for JavaScript-enabled crawlers (Selenium/Playwright-based).
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.crawler_type = CrawlerType.JAVASCRIPT
    
    @abstractmethod
    def setup_browser(self) -> None:
        """Setup browser/driver for JavaScript crawling."""
        pass
    
    @abstractmethod
    def execute_javascript(self, script: str) -> Any:
        """
        Execute JavaScript in the browser context.
        
        Args:
            script: JavaScript code to execute
            
        Returns:
            Execution result
        """
        pass
    
    @abstractmethod
    def wait_for_element(self, selector: str, timeout: int = 10) -> bool:
        """
        Wait for element to appear on page.
        
        Args:
            selector: CSS selector for element
            timeout: Maximum wait time in seconds
            
        Returns:
            True if element found within timeout
        """
        pass
    
    @abstractmethod
    def close_browser(self) -> None:
        """Close browser/driver."""
        pass


class HybridCrawlerInterface(StaticCrawlerInterface, JavaScriptCrawlerInterface):
    """
    Interface for hybrid crawlers that can use both static and JavaScript approaches.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.crawler_type = CrawlerType.HYBRID
        self.prefer_javascript = config.get("prefer_javascript", False) if config else False
    
    @abstractmethod
    def choose_crawling_strategy(self, url: str) -> CrawlerType:
        """
        Determine which crawling strategy to use for a given URL.
        
        Args:
            url: URL to analyze
            
        Returns:
            Crawler type to use
        """
        pass
    
    @abstractmethod
    def fallback_strategy(self, url: str, primary_failed: bool = False) -> Tuple[bool, Dict[str, Any], str]:
        """
        Fallback crawling strategy when primary method fails.
        
        Args:
            url: URL to crawl
            primary_failed: Whether primary strategy failed
            
        Returns:
            Tuple of (success: bool, data: Dict, message: str)
        """
        pass 