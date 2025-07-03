"""
Refactored GUI Application for Advanced Crawler.

This module demonstrates complete separation of concerns using:
- MVC Pattern (Model-View-Controller)
- Observer Pattern for communication
- Command Pattern for actions
- Factory Pattern for object creation
- Template Method Pattern for workflows

Complete separation achieved:
- Model: AdvancedCrawlerRefactored (business logic)
- View: GUI components (presentation layer)
- Controller: CrawlerGUIController (coordination layer)
- Observer: Event-driven communication
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import sys
from typing import Dict, Any, Optional

# Import our modular components
from advanced_crawler_refactored import AdvancedCrawlerRefactored
from crawler_gui_controller import CrawlerGUIController
from crawler_gui_views import MainView, InputView, ProgressView, ResultsView
from crawler_gui_observer import (
    EventBus, ObserverManager, GUIObserver, ControllerObserver,
    EventType, create_gui_observer, create_controller_observer,
    observer_manager
)


class CrawlerApplication:
    """
    Main application class that coordinates all components.
    
    Implements:
    - Application Controller pattern
    - Dependency Injection
    - Configuration management
    - Lifecycle management
    """
    
    def __init__(self):
        """Initialize the crawler application."""
        # Application configuration
        self.config = {
            "app_title": "Advanced Crawler GUI v2.0",
            "app_geometry": "1200x800",
            "min_size": (800, 600),
            "theme": "clam",
            "debug_mode": False
        }
        
        # Core components
        self.root = None
        self.controller = None
        self.main_view = None
        self.event_bus = None
        self.observer_manager = None
        
        # Component observers
        self.gui_observers = {}
        self.controller_observer = None
        
        # Application state
        self.is_running = False
        self.is_shutting_down = False
        
        # Initialize application
        self.initialize_application()
    
    def initialize_application(self) -> None:
        """Initialize all application components."""
        try:
            # 1. Initialize GUI framework
            self.initialize_gui()
            
            # 2. Initialize event system
            self.initialize_event_system()
            
            # 3. Initialize controller
            self.initialize_controller()
            
            # 4. Initialize views
            self.initialize_views()
            
            # 5. Setup observers
            self.setup_observers()
            
            # 6. Configure application
            self.configure_application()
            
            print("✅ Application initialized successfully!")
            
        except Exception as e:
            self.handle_initialization_error(e)
    
    def initialize_gui(self) -> None:
        """Initialize the GUI framework."""
        self.root = tk.Tk()
        self.root.title(self.config["app_title"])
        self.root.geometry(self.config["app_geometry"])
        self.root.minsize(*self.config["min_size"])
        
        # Set application icon (if available)
        try:
            # self.root.iconbitmap("crawler_icon.ico")  # Uncomment if icon available
            pass
        except:
            pass
        
        # Configure style
        style = ttk.Style()
        style.theme_use(self.config["theme"])
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_window_close)
        
        # Configure grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
    
    def initialize_event_system(self) -> None:
        """Initialize the event system."""
        self.event_bus = EventBus()
        self.observer_manager = observer_manager  # Use global instance
        
        print("📡 Event system initialized")
    
    def initialize_controller(self) -> None:
        """Initialize the controller."""
        self.controller = CrawlerGUIController()
        
        # Configure controller with application settings
        controller_config = {
            "prefer_javascript": True,
            "timeout": 60,
            "headless": True,
            "save_dir": "./crawled_pages"
        }
        self.controller.set_crawler_config(controller_config)
        
        print("🎮 Controller initialized")
    
    def initialize_views(self) -> None:
        """Initialize all views."""
        # Create main view
        self.main_view = MainView(self.root, self.controller)
        
        # Store references to sub-views for easy access
        self.input_view = self.main_view.input_view
        self.progress_view = self.main_view.progress_view
        self.results_view = self.main_view.results_view
        
        print("👁️  Views initialized")
    
    def setup_observers(self) -> None:
        """Setup observer pattern connections."""
        # Create GUI observers for each view
        self.gui_observers["input"] = create_gui_observer(
            "input_view_observer", 
            self.input_view
        )
        
        self.gui_observers["progress"] = create_gui_observer(
            "progress_view_observer", 
            self.progress_view
        )
        
        self.gui_observers["results"] = create_gui_observer(
            "results_view_observer", 
            self.results_view
        )
        
        self.gui_observers["main"] = create_gui_observer(
            "main_view_observer", 
            self.main_view
        )
        
        # Create controller observer
        self.controller_observer = create_controller_observer(
            "controller_observer", 
            self.controller
        )
        
        # Register all observers with the manager
        for name, observer in self.gui_observers.items():
            self.observer_manager.register_observer(observer, "gui")
        
        self.observer_manager.register_observer(self.controller_observer, "controller")
        
        # Subscribe controller to GUI events
        self.controller_observer.subscribe_to_events([
            EventType.CRAWL_REQUESTED,
            EventType.STOP_REQUESTED,
            EventType.SUGGESTIONS_REQUESTED,
            EventType.CONFIG_CHANGED,
            EventType.URL_CHANGED,
            EventType.RESULTS_CLEARED
        ])
        
        # Setup bidirectional communication
        self.setup_controller_to_gui_communication()
        self.setup_gui_to_controller_communication()
        
        print("🔗 Observer pattern connections established")
    
    def setup_controller_to_gui_communication(self) -> None:
        """Setup communication from controller to GUI."""
        # Controller publishes these events, GUI observes them
        def controller_event_publisher(event_type: str, data: Dict[str, Any]) -> None:
            """Publish controller events to event bus."""
            try:
                # Convert string event types to EventType enum
                if isinstance(event_type, str):
                    try:
                        event_type_enum = EventType(event_type)
                    except ValueError:
                        print(f"Warning: Unknown event type: {event_type}")
                        return
                else:
                    event_type_enum = event_type
                
                self.observer_manager.publish_event(
                    event_type_enum, 
                    data, 
                    source="controller"
                )
            except Exception as e:
                print(f"Error publishing controller event: {e}")
        
        # Hook into controller's observer system
        self.controller.add_view_observer(controller_event_publisher)
        self.controller.add_progress_observer(
            lambda msg, pct=0: controller_event_publisher(
                EventType.PROGRESS_UPDATE, 
                {"message": msg, "percentage": pct}
            )
        )
        self.controller.add_state_observer(
            lambda new_state, old_state: controller_event_publisher(
                EventType.STATE_CHANGED,
                {"new_state": new_state, "old_state": old_state}
            )
        )
    
    def setup_gui_to_controller_communication(self) -> None:
        """Setup communication from GUI to controller."""
        # GUI publishes these events, controller observes them
        def gui_event_publisher(event_type: str, data: Dict[str, Any]) -> None:
            """Publish GUI events to event bus."""
            try:
                if isinstance(event_type, str):
                    try:
                        event_type_enum = EventType(event_type)
                    except ValueError:
                        print(f"Warning: Unknown event type: {event_type}")
                        return
                else:
                    event_type_enum = event_type
                
                self.observer_manager.publish_event(
                    event_type_enum, 
                    data, 
                    source="gui"
                )
            except Exception as e:
                print(f"Error publishing GUI event: {e}")
        
        # Hook into view observers
        for view in [self.input_view, self.progress_view, self.results_view, self.main_view]:
            if hasattr(view, 'add_observer'):
                view.add_observer(gui_event_publisher)
    
    def configure_application(self) -> None:
        """Configure application-specific settings."""
        # Setup error handling
        if self.config["debug_mode"]:
            self.setup_debug_mode()
        
        # Setup logging
        self.setup_application_logging()
        
        # Setup keyboard shortcuts
        self.setup_keyboard_shortcuts()
        
        print("⚙️  Application configuration completed")
    
    def setup_debug_mode(self) -> None:
        """Setup debug mode features."""
        # Add debug menu
        if hasattr(self.main_view, 'menu_bar'):
            debug_menu = tk.Menu(self.main_view.menu_bar, tearoff=0)
            self.main_view.menu_bar.add_cascade(label="Debug", menu=debug_menu)
            debug_menu.add_command(label="Show Event History", command=self.show_event_history)
            debug_menu.add_command(label="Show Observer Stats", command=self.show_observer_stats)
            debug_menu.add_command(label="Test Events", command=self.test_events)
    
    def setup_application_logging(self) -> None:
        """Setup application logging."""
        # This would typically setup proper logging
        # For now, we'll use simple print statements
        pass
    
    def setup_keyboard_shortcuts(self) -> None:
        """Setup keyboard shortcuts."""
        # Global shortcuts
        self.root.bind("<Control-q>", lambda e: self.shutdown())
        self.root.bind("<F5>", lambda e: self.refresh_application())
        self.root.bind("<F1>", lambda e: self.show_help())
    
    def run(self) -> None:
        """Start the application."""
        try:
            self.is_running = True
            print("🚀 Starting Advanced Crawler GUI...")
            print("=" * 50)
            
            # Show startup message
            self.show_startup_message()
            
            # Start the main event loop
            self.root.mainloop()
            
        except KeyboardInterrupt:
            print("\n⚠️  Application interrupted by user")
            self.shutdown()
        except Exception as e:
            print(f"❌ Fatal error: {e}")
            self.handle_fatal_error(e)
        finally:
            self.cleanup()
    
    def show_startup_message(self) -> None:
        """Show startup message."""
        if self.main_view and hasattr(self.main_view, 'update_status'):
            self.main_view.update_status("Application ready - Enter URL to start crawling")
        
        # Publish startup event
        self.observer_manager.publish_event(
            EventType.STATE_CHANGED, 
            {"new_state": "ready", "old_state": "initializing"},
            source="application"
        )
    
    def on_window_close(self) -> None:
        """Handle window close event."""
        if self.controller and self.controller.is_crawling():
            result = messagebox.askyesno(
                "Confirm Exit", 
                "A crawl is currently in progress. Do you want to exit anyway?"
            )
            if not result:
                return
        
        self.shutdown()
    
    def shutdown(self) -> None:
        """Shutdown the application gracefully."""
        if self.is_shutting_down:
            return
        
        self.is_shutting_down = True
        print("\n🔄 Shutting down application...")
        
        try:
            # Stop any running crawls
            if self.controller and self.controller.is_crawling():
                self.controller.stop_crawl()
            
            # Publish shutdown event
            if self.observer_manager:
                self.observer_manager.publish_event(
                    EventType.STATE_CHANGED,
                    {"new_state": "shutting_down", "old_state": "running"},
                    source="application"
                )
            
            # Cleanup components
            self.cleanup()
            
            # Close GUI
            if self.root:
                self.root.quit()
                self.root.destroy()
            
            print("✅ Application shutdown complete")
            
        except Exception as e:
            print(f"⚠️  Error during shutdown: {e}")
    
    def cleanup(self) -> None:
        """Cleanup application resources."""
        try:
            # Cleanup controller
            if self.controller:
                self.controller.cleanup()
            
            # Cleanup observers
            if self.observer_manager:
                self.observer_manager.cleanup()
            
            # Cleanup views
            if self.main_view:
                self.main_view.cleanup()
            
            self.is_running = False
            
        except Exception as e:
            print(f"⚠️  Error during cleanup: {e}")
    
    def refresh_application(self) -> None:
        """Refresh application state."""
        if self.main_view and hasattr(self.main_view, 'update_status'):
            self.main_view.update_status("Application refreshed")
    
    def show_help(self) -> None:
        """Show help dialog."""
        help_text = """Advanced Crawler GUI v2.0

Quick Start:
1. Enter a URL in the input field
2. Configure crawling options (JavaScript, timeout, etc.)
3. Click "Start Crawl" or press Enter
4. View results in the tabs below

Keyboard Shortcuts:
- Ctrl+Enter: Start crawl
- Escape: Stop crawl
- F5: Refresh
- F1: Show this help
- Ctrl+Q: Quit

Features:
- Intelligent strategy selection (JavaScript vs Static)
- Real-time progress updates
- Comprehensive content analysis
- Export results (JSON/CSV)
- Observer pattern for responsive UI

For more information, see the documentation."""
        
        messagebox.showinfo("Help", help_text)
    
    def show_event_history(self) -> None:
        """Show event history (debug feature)."""
        if not self.event_bus:
            return
        
        history = self.event_bus.get_event_history(limit=20)
        
        # Create a new window to display history
        history_window = tk.Toplevel(self.root)
        history_window.title("Event History")
        history_window.geometry("800x600")
        
        # Create text widget
        text_widget = tk.Text(history_window, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(history_window, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        # Layout
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Display history
        for event in history:
            text_widget.insert(tk.END, f"{event.timestamp}: {event.event_type.value}\n")
            text_widget.insert(tk.END, f"  Source: {event.source}\n")
            text_widget.insert(tk.END, f"  Data: {event.data}\n\n")
    
    def show_observer_stats(self) -> None:
        """Show observer statistics (debug feature)."""
        if not self.observer_manager:
            return
        
        stats = self.observer_manager.get_statistics()
        stats_text = f"""Observer Statistics:

Total Observers: {stats['total_observers']}
Observer Groups: {stats['observer_groups']}

Event Bus Statistics:
Total Events: {stats['event_bus_stats']['total_events']}
Errors: {stats['event_bus_stats']['errors']}

Events by Type:
"""
        for event_type, count in stats['event_bus_stats']['events_by_type'].items():
            stats_text += f"  {event_type}: {count}\n"
        
        messagebox.showinfo("Observer Statistics", stats_text)
    
    def test_events(self) -> None:
        """Test event system (debug feature)."""
        if not self.observer_manager:
            return
        
        # Publish test events
        test_events = [
            (EventType.PROGRESS_UPDATE, {"message": "Test progress", "percentage": 50}),
            (EventType.STATE_CHANGED, {"new_state": "test", "old_state": "idle"}),
        ]
        
        for event_type, data in test_events:
            self.observer_manager.publish_event(event_type, data, source="test")
        
        messagebox.showinfo("Test", "Test events published successfully!")
    
    def handle_initialization_error(self, error: Exception) -> None:
        """Handle initialization errors."""
        error_msg = f"Failed to initialize application: {str(error)}"
        print(f"❌ {error_msg}")
        
        # Try to show error dialog if possible
        try:
            if self.root:
                messagebox.showerror("Initialization Error", error_msg)
            else:
                print(f"GUI not available, error: {error_msg}")
        except:
            pass
        
        # Exit application
        sys.exit(1)
    
    def handle_fatal_error(self, error: Exception) -> None:
        """Handle fatal runtime errors."""
        error_msg = f"Fatal error occurred: {str(error)}"
        print(f"❌ {error_msg}")
        
        try:
            messagebox.showerror("Fatal Error", error_msg)
        except:
            pass
    
    def get_application_info(self) -> Dict[str, Any]:
        """Get application information."""
        return {
            "title": self.config["app_title"],
            "is_running": self.is_running,
            "is_shutting_down": self.is_shutting_down,
            "components": {
                "controller": self.controller is not None,
                "main_view": self.main_view is not None,
                "event_bus": self.event_bus is not None,
                "observer_manager": self.observer_manager is not None
            },
            "observers": {
                "gui_observers": len(self.gui_observers),
                "controller_observer": self.controller_observer is not None
            }
        }


def create_application(config: Dict[str, Any] = None) -> CrawlerApplication:
    """
    Factory function to create a crawler application.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        Configured crawler application
    """
    app = CrawlerApplication()
    
    if config:
        app.config.update(config)
        app.configure_application()
    
    return app


def create_debug_application() -> CrawlerApplication:
    """Create an application with debug features enabled."""
    debug_config = {
        "debug_mode": True,
        "app_title": "Advanced Crawler GUI v2.0 (Debug Mode)"
    }
    return create_application(debug_config)


def main():
    """Main entry point for the application."""
    print("🌟 Advanced Crawler GUI v2.0")
    print("=" * 40)
    print("Features:")
    print("  ✅ Complete MVC separation")
    print("  ✅ Observer pattern communication")
    print("  ✅ Modular component design")
    print("  ✅ Strategy pattern for crawling")
    print("  ✅ Command pattern for actions")
    print("  ✅ Factory pattern for objects")
    print("  ✅ Template method workflows")
    print("=" * 40)
    
    try:
        # Create and run application
        app = create_application()
        app.run()
        
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Application failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 