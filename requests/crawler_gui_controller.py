"""
GUI Controller for Advanced Crawler - implements MVC pattern.
"""

import threading
import time
from typing import Dict, Any, Optional, Callable, List
from urllib.parse import urlparse

from advanced_crawler_refactored import AdvancedCrawlerRefactored


class CrawlerGUIController:
    """
    Controller class that mediates between GUI Views and Crawler Model.
    
    Implements:
    - MVC Pattern (Controller layer)
    - Observer Pattern for GUI updates
    - Command Pattern for crawler operations
    - State Pattern for application state
    """
    
    def __init__(self):
        """Initialize the GUI controller."""
        # State management
        self.state = "idle"  # idle, crawling, error, completed
        self.current_url = ""
        self.current_config = {}
        self.crawl_results = {}
        self.crawl_thread: Optional[threading.Thread] = None
        
        # Crawler instance
        self.crawler: Optional[AdvancedCrawlerRefactored] = None
        
        # Observer pattern - GUI views that need updates
        self.view_observers: List[Callable] = []
        self.progress_observers: List[Callable] = []
        self.state_observers: List[Callable] = []
        
        # Command history for undo/redo functionality
        self.command_history = []
        self.current_command_index = -1
        
        # Statistics
        self.crawl_statistics = {
            "total_crawls": 0,
            "successful_crawls": 0,
            "failed_crawls": 0,
            "average_crawl_time": 0.0
        }
    
    # Observer Pattern Implementation
    
    def add_view_observer(self, observer: Callable) -> None:
        """Add a view observer for GUI updates."""
        if observer not in self.view_observers:
            self.view_observers.append(observer)
    
    def remove_view_observer(self, observer: Callable) -> None:
        """Remove a view observer."""
        if observer in self.view_observers:
            self.view_observers.remove(observer)
    
    def add_progress_observer(self, observer: Callable) -> None:
        """Add a progress observer for progress updates."""
        if observer not in self.progress_observers:
            self.progress_observers.append(observer)
    
    def add_state_observer(self, observer: Callable) -> None:
        """Add a state observer for state changes."""
        if observer not in self.state_observers:
            self.state_observers.append(observer)
    
    def notify_view_observers(self, event_type: str, data: Dict[str, Any]) -> None:
        """Notify all view observers of an event."""
        for observer in self.view_observers:
            try:
                observer(event_type, data)
            except Exception as e:
                print(f"Error notifying view observer: {e}")
    
    def notify_progress_observers(self, message: str, percentage: int = 0) -> None:
        """Notify all progress observers."""
        for observer in self.progress_observers:
            try:
                observer(message, percentage)
            except Exception as e:
                print(f"Error notifying progress observer: {e}")
    
    def notify_state_observers(self, new_state: str, old_state: str) -> None:
        """Notify all state observers."""
        for observer in self.state_observers:
            try:
                observer(new_state, old_state)
            except Exception as e:
                print(f"Error notifying state observer: {e}")
    
    # State Management
    
    def set_state(self, new_state: str) -> None:
        """Set new application state and notify observers."""
        old_state = self.state
        self.state = new_state
        self.notify_state_observers(new_state, old_state)
    
    def get_state(self) -> str:
        """Get current application state."""
        return self.state
    
    def is_crawling(self) -> bool:
        """Check if currently crawling."""
        return self.state == "crawling"
    
    def is_idle(self) -> bool:
        """Check if in idle state."""
        return self.state == "idle"
    
    # URL and Configuration Management
    
    def validate_url(self, url: str) -> tuple[bool, str]:
        """
        Validate URL format and accessibility.
        
        Args:
            url: URL to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not url or not url.strip():
            return False, "URL cannot be empty"
        
        url = url.strip()
        
        # Add protocol if missing
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        
        try:
            parsed = urlparse(url)
            if not parsed.netloc:
                return False, "Invalid URL format"
            
            # Additional validation using crawler
            if not self.crawler:
                temp_crawler = AdvancedCrawlerRefactored()
                is_valid = temp_crawler.validate_url(url)
                temp_crawler.cleanup()
            else:
                is_valid = self.crawler.validate_url(url)
            
            return is_valid, "" if is_valid else "URL is not accessible"
            
        except Exception as e:
            return False, f"URL validation error: {str(e)}"
    
    def set_url(self, url: str) -> bool:
        """
        Set the current URL after validation.
        
        Args:
            url: URL to set
            
        Returns:
            True if URL is valid and set
        """
        is_valid, error = self.validate_url(url)
        if is_valid:
            # Normalize URL
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            
            self.current_url = url
            self.notify_view_observers("url_changed", {"url": url})
            return True
        else:
            self.notify_view_observers("url_error", {"error": error})
            return False
    
    def get_url(self) -> str:
        """Get current URL."""
        return self.current_url
    
    def set_crawler_config(self, config: Dict[str, Any]) -> None:
        """
        Set crawler configuration.
        
        Args:
            config: Configuration dictionary
        """
        self.current_config = config.copy()
        self.notify_view_observers("config_changed", {"config": config})
    
    def get_crawler_config(self) -> Dict[str, Any]:
        """Get current crawler configuration."""
        return self.current_config.copy()
    
    # Crawler Management
    
    def create_crawler(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Create a new crawler instance.
        
        Args:
            config: Optional configuration override
        """
        if self.crawler:
            self.crawler.cleanup()
        
        final_config = self.current_config.copy()
        if config:
            final_config.update(config)
        
        self.crawler = AdvancedCrawlerRefactored(final_config)
        
        # Set up crawler observers
        self.crawler.set_progress_callback(self._crawler_progress_callback)
    
    def _crawler_progress_callback(self, message: str) -> None:
        """Internal callback for crawler progress updates."""
        self.notify_progress_observers(message)
    
    def get_crawler_suggestions(self, url: str) -> Dict[str, Any]:
        """
        Get crawler configuration suggestions for a URL.
        
        Args:
            url: URL to analyze
            
        Returns:
            Suggested configuration
        """
        if not self.crawler:
            temp_crawler = AdvancedCrawlerRefactored()
            strategy = temp_crawler.choose_crawling_strategy(url)
            js_required = temp_crawler.is_javascript_required(url)
            temp_crawler.cleanup()
        else:
            strategy = self.crawler.choose_crawling_strategy(url)
            js_required = self.crawler.is_javascript_required(url)
        
        return {
            "recommended_strategy": strategy.value,
            "javascript_required": js_required,
            "suggested_config": {
                "prefer_javascript": js_required,
                "timeout": 60 if js_required else 30,
                "headless": True
            }
        }
    
    # Crawling Operations (Command Pattern)
    
    def start_crawl(self, url: str = None, config: Dict[str, Any] = None) -> bool:
        """
        Start crawling operation.
        
        Args:
            url: URL to crawl (optional, uses current URL if not provided)
            config: Configuration override (optional)
            
        Returns:
            True if crawl started successfully
        """
        if self.is_crawling():
            self.notify_view_observers("crawl_error", {"error": "Already crawling"})
            return False
        
        # Use provided URL or current URL
        target_url = url or self.current_url
        if not target_url:
            self.notify_view_observers("crawl_error", {"error": "No URL specified"})
            return False
        
        # Validate URL
        is_valid, error = self.validate_url(target_url)
        if not is_valid:
            self.notify_view_observers("crawl_error", {"error": error})
            return False
        
        # Set state to crawling
        self.set_state("crawling")
        
        # Create crawler with config
        self.create_crawler(config)
        
        # Start crawl thread
        self.crawl_thread = threading.Thread(
            target=self._crawl_worker,
            args=(target_url,),
            daemon=True
        )
        self.crawl_thread.start()
        
        # Notify observers
        self.notify_view_observers("crawl_started", {"url": target_url})
        
        return True
    
    def _crawl_worker(self, url: str) -> None:
        """
        Worker thread for crawling operations.
        
        Args:
            url: URL to crawl
        """
        start_time = time.time()
        
        try:
            # Update statistics
            self.crawl_statistics["total_crawls"] += 1
            
            # Perform crawl
            success, data, message = self.crawler.crawl(url)
            
            crawl_time = time.time() - start_time
            
            if success:
                # Update statistics
                self.crawl_statistics["successful_crawls"] += 1
                self._update_average_crawl_time(crawl_time)
                
                # Store results
                self.crawl_results = data
                self.crawl_results["crawl_time"] = crawl_time
                
                # Add to command history
                self.command_history.append({
                    "type": "crawl",
                    "url": url,
                    "timestamp": time.time(),
                    "success": True,
                    "data": data
                })
                
                # Set state and notify
                self.set_state("completed")
                self.notify_view_observers("crawl_completed", {
                    "url": url,
                    "data": data,
                    "crawl_time": crawl_time
                })
                
            else:
                # Update statistics
                self.crawl_statistics["failed_crawls"] += 1
                
                # Add to command history
                self.command_history.append({
                    "type": "crawl",
                    "url": url,
                    "timestamp": time.time(),
                    "success": False,
                    "error": message
                })
                
                # Set state and notify
                self.set_state("error")
                self.notify_view_observers("crawl_failed", {
                    "url": url,
                    "error": message,
                    "crawl_time": crawl_time
                })
                
        except Exception as e:
            # Update statistics
            self.crawl_statistics["failed_crawls"] += 1
            
            # Set state and notify
            self.set_state("error")
            self.notify_view_observers("crawl_error", {
                "url": url,
                "error": str(e),
                "crawl_time": time.time() - start_time
            })
            
        finally:
            # Cleanup
            if self.crawler:
                self.crawler.cleanup()
    
    def stop_crawl(self) -> bool:
        """
        Stop current crawling operation.
        
        Returns:
            True if stopped successfully
        """
        if not self.is_crawling():
            return False
        
        # Note: This is a graceful stop request
        # The actual implementation depends on crawler's ability to be interrupted
        self.set_state("stopping")
        self.notify_view_observers("crawl_stopping", {})
        
        return True
    
    def _update_average_crawl_time(self, crawl_time: float) -> None:
        """Update average crawl time statistics."""
        successful_crawls = self.crawl_statistics["successful_crawls"]
        if successful_crawls == 1:
            self.crawl_statistics["average_crawl_time"] = crawl_time
        else:
            current_avg = self.crawl_statistics["average_crawl_time"]
            new_avg = ((current_avg * (successful_crawls - 1)) + crawl_time) / successful_crawls
            self.crawl_statistics["average_crawl_time"] = new_avg
    
    # Results Management
    
    def get_crawl_results(self) -> Dict[str, Any]:
        """Get current crawl results."""
        return self.crawl_results.copy()
    
    def has_results(self) -> bool:
        """Check if there are crawl results available."""
        return bool(self.crawl_results)
    
    def clear_results(self) -> None:
        """Clear current crawl results."""
        self.crawl_results = {}
        self.notify_view_observers("results_cleared", {})
    
    def export_results(self, format: str = "json") -> Optional[str]:
        """
        Export crawl results to specified format.
        
        Args:
            format: Export format (json, csv, xml)
            
        Returns:
            Exported data string or None if no results
        """
        if not self.has_results():
            return None
        
        if format == "json":
            import json
            return json.dumps(self.crawl_results, indent=2, ensure_ascii=False)
        elif format == "csv":
            # Basic CSV export of summary data
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write headers and data
            writer.writerow(["Field", "Value"])
            writer.writerow(["URL", self.crawl_results.get("url", "")])
            writer.writerow(["Title", self.crawl_results.get("metadata", {}).get("title", "")])
            writer.writerow(["Description", self.crawl_results.get("metadata", {}).get("description", "")])
            # Add more fields as needed
            
            return output.getvalue()
        
        return None
    
    # Statistics and History
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get crawling statistics."""
        return self.crawl_statistics.copy()
    
    def get_command_history(self) -> List[Dict[str, Any]]:
        """Get command history."""
        return self.command_history.copy()
    
    def clear_history(self) -> None:
        """Clear command history."""
        self.command_history = []
        self.current_command_index = -1
        self.notify_view_observers("history_cleared", {})
    
    # Cleanup
    
    def cleanup(self) -> None:
        """Cleanup resources."""
        if self.crawler:
            self.crawler.cleanup()
            self.crawler = None
        
        # Clear observers
        self.view_observers.clear()
        self.progress_observers.clear()
        self.state_observers.clear()
        
        # Reset state
        self.set_state("idle")
    
    def __del__(self):
        """Destructor - cleanup resources."""
        self.cleanup()


# Factory functions for creating specialized controllers

def create_basic_controller() -> CrawlerGUIController:
    """Create a basic GUI controller."""
    return CrawlerGUIController()


def create_advanced_controller() -> CrawlerGUIController:
    """Create an advanced GUI controller with enhanced features."""
    controller = CrawlerGUIController()
    
    # Set advanced default configuration
    controller.set_crawler_config({
        "prefer_javascript": True,
        "timeout": 60,
        "headless": True,
        "enable_performance_monitoring": True
    })
    
    return controller 