"""
GUI Views for Advanced Crawler - implements MVC pattern View layer.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import json
from typing import Dict, Any, Optional, Callable, List
from abc import ABC, abstractmethod


class BaseView(ABC):
    """
    Abstract base class for all GUI views.
    
    Implements:
    - Template Method pattern for view lifecycle
    - Observer pattern for view updates
    - Command pattern for UI actions
    """
    
    def __init__(self, parent: tk.Widget, controller: Optional[object] = None):
        """Initialize the base view."""
        self.parent = parent
        self.controller = controller
        self.widgets = {}
        self.observers = []
        self.is_initialized = False
        
        # Style configuration
        self.style = ttk.Style()
        self.setup_styles()
        
        # Initialize the view
        self.initialize_view()
    
    def setup_styles(self) -> None:
        """Setup custom styles for the view."""
        self.style.theme_use("clam")
        
        # Custom styles
        self.style.configure("Title.TLabel", font=("Helvetica", 12, "bold"))
        self.style.configure("Success.TLabel", foreground="green")
        self.style.configure("Error.TLabel", foreground="red")
        self.style.configure("Warning.TLabel", foreground="orange")
    
    def initialize_view(self) -> None:
        """Template method for view initialization."""
        if not self.is_initialized:
            self.create_widgets()
            self.layout_widgets()
            self.bind_events()
            self.configure_widgets()
            self.is_initialized = True
    
    @abstractmethod
    def create_widgets(self) -> None:
        """Create the widgets for this view."""
        pass
    
    @abstractmethod
    def layout_widgets(self) -> None:
        """Layout the widgets in the view."""
        pass
    
    def bind_events(self) -> None:
        """Bind events to widgets (optional override)."""
        pass
    
    def configure_widgets(self) -> None:
        """Configure widget properties (optional override)."""
        pass
    
    def add_observer(self, observer: Callable) -> None:
        """Add an observer to this view."""
        if observer not in self.observers:
            self.observers.append(observer)
    
    def remove_observer(self, observer: Callable) -> None:
        """Remove an observer from this view."""
        if observer in self.observers:
            self.observers.remove(observer)
    
    def notify_observers(self, event_type: str, data: Dict[str, Any]) -> None:
        """Notify all observers of an event."""
        for observer in self.observers:
            try:
                observer(event_type, data)
            except Exception as e:
                print(f"Error notifying observer: {e}")
    
    def update_view(self, event_type: str, data: Dict[str, Any]) -> None:
        """Update the view based on controller events."""
        # Override in subclasses
        pass
    
    def cleanup(self) -> None:
        """Cleanup resources."""
        self.observers.clear()


class InputView(BaseView):
    """
    View for URL input, configuration, and crawl controls.
    
    Contains:
    - URL entry field
    - JavaScript checkbox
    - Crawl button
    - Configuration options
    """
    
    def __init__(self, parent: tk.Widget, controller: Optional[object] = None):
        """Initialize the input view."""
        super().__init__(parent, controller)
        
        # State variables
        self.url_var = tk.StringVar()
        self.js_var = tk.BooleanVar(value=True)
        self.timeout_var = tk.IntVar(value=30)
        self.headless_var = tk.BooleanVar(value=True)
        
        # Bind variables to callbacks
        self.url_var.trace_add("write", self.on_url_changed)
        self.js_var.trace_add("write", self.on_config_changed)
        self.timeout_var.trace_add("write", self.on_config_changed)
        self.headless_var.trace_add("write", self.on_config_changed)
    
    def create_widgets(self) -> None:
        """Create input widgets."""
        # Main frame
        self.main_frame = ttk.LabelFrame(self.parent, text="URL Input & Configuration", padding="10")
        self.widgets["main_frame"] = self.main_frame
        
        # URL input section
        self.url_label = ttk.Label(self.main_frame, text="URL:")
        self.url_entry = ttk.Entry(self.main_frame, textvariable=self.url_var, width=60)
        self.url_suggestions = ttk.Combobox(self.main_frame, width=20, state="readonly")
        self.widgets.update({
            "url_label": self.url_label,
            "url_entry": self.url_entry,
            "url_suggestions": self.url_suggestions
        })
        
        # Quick URL suggestions
        self.url_suggestions["values"] = (
            "https://alibaba.ir",
            "https://flytoday.ir",
            "https://snapptrip.com",
            "https://safarmarket.com",
            "https://flightio.com"
        )
        
        # Configuration section
        self.config_frame = ttk.LabelFrame(self.main_frame, text="Configuration", padding="5")
        self.js_check = ttk.Checkbutton(self.config_frame, text="Enable JavaScript", variable=self.js_var)
        self.headless_check = ttk.Checkbutton(self.config_frame, text="Headless Mode", variable=self.headless_var)
        
        # Timeout setting
        self.timeout_label = ttk.Label(self.config_frame, text="Timeout (seconds):")
        self.timeout_spin = ttk.Spinbox(self.config_frame, from_=10, to=300, textvariable=self.timeout_var, width=10)
        
        self.widgets.update({
            "config_frame": self.config_frame,
            "js_check": self.js_check,
            "headless_check": self.headless_check,
            "timeout_label": self.timeout_label,
            "timeout_spin": self.timeout_spin
        })
        
        # Action buttons
        self.button_frame = ttk.Frame(self.main_frame)
        self.crawl_button = ttk.Button(self.button_frame, text="Start Crawl", command=self.on_crawl_clicked)
        self.stop_button = ttk.Button(self.button_frame, text="Stop", command=self.on_stop_clicked, state="disabled")
        self.suggestions_button = ttk.Button(self.button_frame, text="Get Suggestions", command=self.on_suggestions_clicked)
        
        self.widgets.update({
            "button_frame": self.button_frame,
            "crawl_button": self.crawl_button,
            "stop_button": self.stop_button,
            "suggestions_button": self.suggestions_button
        })
    
    def layout_widgets(self) -> None:
        """Layout the input widgets."""
        # Main frame
        self.main_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # URL input row
        self.url_label.grid(row=0, column=0, sticky=tk.W, padx=5)
        self.url_entry.grid(row=0, column=1, padx=5, sticky=(tk.W, tk.E))
        self.url_suggestions.grid(row=0, column=2, padx=5)
        
        # Configuration frame
        self.config_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        # Configuration options
        self.js_check.grid(row=0, column=0, sticky=tk.W, padx=5)
        self.headless_check.grid(row=0, column=1, sticky=tk.W, padx=5)
        self.timeout_label.grid(row=0, column=2, sticky=tk.W, padx=5)
        self.timeout_spin.grid(row=0, column=3, padx=5)
        
        # Button frame
        self.button_frame.grid(row=2, column=0, columnspan=3, pady=10)
        self.crawl_button.grid(row=0, column=0, padx=5)
        self.stop_button.grid(row=0, column=1, padx=5)
        self.suggestions_button.grid(row=0, column=2, padx=5)
        
        # Configure grid weights
        self.main_frame.columnconfigure(1, weight=1)
        self.config_frame.columnconfigure(4, weight=1)
    
    def bind_events(self) -> None:
        """Bind events to widgets."""
        # URL entry events
        self.url_entry.bind("<Return>", lambda e: self.on_crawl_clicked())
        self.url_entry.bind("<FocusOut>", lambda e: self.on_url_focus_out())
        
        # URL suggestions
        self.url_suggestions.bind("<<ComboboxSelected>>", self.on_suggestion_selected)
        
        # Keyboard shortcuts
        self.main_frame.bind("<Control-Return>", lambda e: self.on_crawl_clicked())
        self.main_frame.bind("<Escape>", lambda e: self.on_stop_clicked())
    
    def configure_widgets(self) -> None:
        """Configure widget properties."""
        # Make main frame focusable for keyboard shortcuts
        self.main_frame.focus_set()
        
        # Configure entry validation
        self.url_entry.configure(validate="key", validatecommand=(self.url_entry.register(self.validate_url_input), "%P"))
    
    def validate_url_input(self, value: str) -> bool:
        """Validate URL input in real-time."""
        # Basic validation - allow typing
        return True
    
    def on_url_changed(self, *args) -> None:
        """Handle URL change events."""
        url = self.url_var.get()
        if url:
            self.notify_observers("url_input_changed", {"url": url})
    
    def on_config_changed(self, *args) -> None:
        """Handle configuration change events."""
        config = self.get_config()
        self.notify_observers("config_changed", {"config": config})
    
    def on_url_focus_out(self) -> None:
        """Handle URL entry focus out."""
        url = self.url_var.get().strip()
        if url:
            self.notify_observers("url_focus_out", {"url": url})
    
    def on_suggestion_selected(self, event) -> None:
        """Handle URL suggestion selection."""
        selected_url = self.url_suggestions.get()
        if selected_url:
            self.url_var.set(selected_url)
            self.notify_observers("url_selected", {"url": selected_url})
    
    def on_crawl_clicked(self) -> None:
        """Handle crawl button click."""
        url = self.url_var.get().strip()
        config = self.get_config()
        
        if not url:
            messagebox.showerror("Error", "Please enter a URL")
            return
        
        self.notify_observers("crawl_requested", {"url": url, "config": config})
    
    def on_stop_clicked(self) -> None:
        """Handle stop button click."""
        self.notify_observers("stop_requested", {})
    
    def on_suggestions_clicked(self) -> None:
        """Handle suggestions button click."""
        url = self.url_var.get().strip()
        if url:
            self.notify_observers("suggestions_requested", {"url": url})
        else:
            messagebox.showwarning("Warning", "Please enter a URL first")
    
    def get_config(self) -> Dict[str, Any]:
        """Get current configuration."""
        return {
            "prefer_javascript": self.js_var.get(),
            "headless": self.headless_var.get(),
            "timeout": self.timeout_var.get()
        }
    
    def set_config(self, config: Dict[str, Any]) -> None:
        """Set configuration values."""
        self.js_var.set(config.get("prefer_javascript", True))
        self.headless_var.set(config.get("headless", True))
        self.timeout_var.set(config.get("timeout", 30))
    
    def get_url(self) -> str:
        """Get current URL."""
        return self.url_var.get().strip()
    
    def set_url(self, url: str) -> None:
        """Set URL value."""
        self.url_var.set(url)
    
    def set_crawling_state(self, is_crawling: bool) -> None:
        """Update UI state for crawling."""
        state = "disabled" if is_crawling else "normal"
        self.crawl_button.config(state=state)
        self.url_entry.config(state=state)
        self.js_check.config(state=state)
        self.headless_check.config(state=state)
        self.timeout_spin.config(state=state)
        self.suggestions_button.config(state=state)
        
        # Enable/disable stop button
        self.stop_button.config(state="normal" if is_crawling else "disabled")
    
    def update_view(self, event_type: str, data: Dict[str, Any]) -> None:
        """Update view based on controller events."""
        if event_type == "crawl_started":
            self.set_crawling_state(True)
        elif event_type in ["crawl_completed", "crawl_failed", "crawl_error"]:
            self.set_crawling_state(False)
        elif event_type == "url_error":
            messagebox.showerror("URL Error", data.get("error", "Unknown error"))
        elif event_type == "suggestions_received":
            self.show_suggestions(data.get("suggestions", {}))
    
    def show_suggestions(self, suggestions: Dict[str, Any]) -> None:
        """Show crawler suggestions."""
        message = f"""Crawler Suggestions:

Recommended Strategy: {suggestions.get('recommended_strategy', 'Unknown')}
JavaScript Required: {suggestions.get('javascript_required', 'Unknown')}

Suggested Configuration:
- JavaScript: {suggestions.get('suggested_config', {}).get('prefer_javascript', 'Unknown')}
- Timeout: {suggestions.get('suggested_config', {}).get('timeout', 'Unknown')}s
- Headless: {suggestions.get('suggested_config', {}).get('headless', 'Unknown')}

Would you like to apply these suggestions?"""
        
        result = messagebox.askyesno("Crawler Suggestions", message)
        if result:
            self.set_config(suggestions.get('suggested_config', {}))


class ProgressView(BaseView):
    """
    View for displaying progress updates and status.
    
    Contains:
    - Progress bar
    - Status label
    - Progress percentage
    - Elapsed time
    """
    
    def __init__(self, parent: tk.Widget, controller: Optional[object] = None):
        """Initialize the progress view."""
        super().__init__(parent, controller)
        
        # State variables
        self.progress_var = tk.StringVar(value="Ready")
        self.percentage_var = tk.IntVar(value=0)
        self.elapsed_var = tk.StringVar(value="00:00")
        
        # Timing
        self.start_time = None
        self.update_job = None
    
    def create_widgets(self) -> None:
        """Create progress widgets."""
        # Main frame
        self.main_frame = ttk.LabelFrame(self.parent, text="Progress", padding="10")
        self.widgets["main_frame"] = self.main_frame
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(
            self.main_frame,
            variable=self.percentage_var,
            maximum=100,
            mode="determinate"
        )
        
        # Status label
        self.status_label = ttk.Label(self.main_frame, textvariable=self.progress_var, style="Title.TLabel")
        
        # Progress info frame
        self.info_frame = ttk.Frame(self.main_frame)
        self.percentage_label = ttk.Label(self.info_frame, text="0%")
        self.elapsed_label = ttk.Label(self.info_frame, textvariable=self.elapsed_var)
        
        self.widgets.update({
            "progress_bar": self.progress_bar,
            "status_label": self.status_label,
            "info_frame": self.info_frame,
            "percentage_label": self.percentage_label,
            "elapsed_label": self.elapsed_label
        })
    
    def layout_widgets(self) -> None:
        """Layout progress widgets."""
        # Main frame
        self.main_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Status label
        self.status_label.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=2)
        
        # Progress bar
        self.progress_bar.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=2)
        
        # Info frame
        self.info_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=2)
        self.percentage_label.grid(row=0, column=0, sticky=tk.W)
        self.elapsed_label.grid(row=0, column=1, sticky=tk.E)
        
        # Configure grid weights
        self.main_frame.columnconfigure(0, weight=1)
        self.info_frame.columnconfigure(1, weight=1)
    
    def update_progress(self, message: str, percentage: int = 0) -> None:
        """Update progress display."""
        self.progress_var.set(message)
        self.percentage_var.set(percentage)
        self.percentage_label.config(text=f"{percentage}%")
        
        # Update progress bar style based on status
        if "error" in message.lower() or "failed" in message.lower():
            self.progress_bar.config(style="Error.Horizontal.TProgressbar")
            self.status_label.config(style="Error.TLabel")
        elif "completed" in message.lower() or "success" in message.lower():
            self.progress_bar.config(style="Success.Horizontal.TProgressbar")
            self.status_label.config(style="Success.TLabel")
        else:
            self.progress_bar.config(style="TProgressbar")
            self.status_label.config(style="Title.TLabel")
    
    def start_timing(self) -> None:
        """Start the elapsed time counter."""
        import time
        self.start_time = time.time()
        self.update_elapsed_time()
    
    def stop_timing(self) -> None:
        """Stop the elapsed time counter."""
        if self.update_job:
            self.main_frame.after_cancel(self.update_job)
            self.update_job = None
    
    def update_elapsed_time(self) -> None:
        """Update elapsed time display."""
        if self.start_time:
            import time
            elapsed = time.time() - self.start_time
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            self.elapsed_var.set(f"{minutes:02d}:{seconds:02d}")
            
            # Schedule next update
            self.update_job = self.main_frame.after(1000, self.update_elapsed_time)
    
    def reset_progress(self) -> None:
        """Reset progress to initial state."""
        self.progress_var.set("Ready")
        self.percentage_var.set(0)
        self.elapsed_var.set("00:00")
        self.percentage_label.config(text="0%")
        self.stop_timing()
    
    def update_view(self, event_type: str, data: Dict[str, Any]) -> None:
        """Update view based on controller events."""
        if event_type == "crawl_started":
            self.start_timing()
            self.update_progress("Starting crawl...", 0)
        elif event_type == "crawl_completed":
            self.stop_timing()
            self.update_progress("Crawl completed successfully!", 100)
        elif event_type == "crawl_failed":
            self.stop_timing()
            self.update_progress(f"Crawl failed: {data.get('error', 'Unknown error')}", 0)
        elif event_type == "crawl_error":
            self.stop_timing()
            self.update_progress(f"Error: {data.get('error', 'Unknown error')}", 0)
        elif event_type == "progress_update":
            self.update_progress(data.get("message", ""), data.get("percentage", 0))


class ResultsView(BaseView):
    """
    View for displaying crawl results in tabbed interface.
    
    Contains:
    - Summary tab
    - Metadata tab
    - Links tab
    - Resources tab
    - AJAX/API tab
    """
    
    def __init__(self, parent: tk.Widget, controller: Optional[object] = None):
        """Initialize the results view."""
        super().__init__(parent, controller)
        
        # Current results
        self.current_results = {}
    
    def create_widgets(self) -> None:
        """Create results widgets."""
        # Main frame
        self.main_frame = ttk.LabelFrame(self.parent, text="Crawl Results", padding="10")
        self.widgets["main_frame"] = self.main_frame
        
        # Notebook for tabs
        self.notebook = ttk.Notebook(self.main_frame)
        self.widgets["notebook"] = self.notebook
        
        # Create tabs
        self.create_summary_tab()
        self.create_metadata_tab()
        self.create_links_tab()
        self.create_resources_tab()
        self.create_ajax_tab()
        
        # Export buttons
        self.export_frame = ttk.Frame(self.main_frame)
        self.export_json_button = ttk.Button(self.export_frame, text="Export JSON", command=self.export_json)
        self.export_csv_button = ttk.Button(self.export_frame, text="Export CSV", command=self.export_csv)
        self.clear_button = ttk.Button(self.export_frame, text="Clear Results", command=self.clear_results)
        
        self.widgets.update({
            "export_frame": self.export_frame,
            "export_json_button": self.export_json_button,
            "export_csv_button": self.export_csv_button,
            "clear_button": self.clear_button
        })
    
    def create_summary_tab(self) -> None:
        """Create summary tab."""
        self.summary_text = scrolledtext.ScrolledText(self.notebook, height=25, width=90)
        self.notebook.add(self.summary_text, text="Summary")
        self.widgets["summary_text"] = self.summary_text
    
    def create_metadata_tab(self) -> None:
        """Create metadata tab."""
        self.metadata_text = scrolledtext.ScrolledText(self.notebook, height=25, width=90)
        self.notebook.add(self.metadata_text, text="Metadata")
        self.widgets["metadata_text"] = self.metadata_text
    
    def create_links_tab(self) -> None:
        """Create links tab."""
        self.links_text = scrolledtext.ScrolledText(self.notebook, height=25, width=90)
        self.notebook.add(self.links_text, text="Links")
        self.widgets["links_text"] = self.links_text
    
    def create_resources_tab(self) -> None:
        """Create resources tab."""
        self.resources_text = scrolledtext.ScrolledText(self.notebook, height=25, width=90)
        self.notebook.add(self.resources_text, text="Resources")
        self.widgets["resources_text"] = self.resources_text
    
    def create_ajax_tab(self) -> None:
        """Create AJAX/API tab."""
        self.ajax_text = scrolledtext.ScrolledText(self.notebook, height=25, width=90)
        self.notebook.add(self.ajax_text, text="AJAX/API")
        self.widgets["ajax_text"] = self.ajax_text
    
    def layout_widgets(self) -> None:
        """Layout results widgets."""
        # Main frame
        self.main_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # Notebook
        self.notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Export frame
        self.export_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        self.export_json_button.grid(row=0, column=0, padx=5)
        self.export_csv_button.grid(row=0, column=1, padx=5)
        self.clear_button.grid(row=0, column=2, padx=5)
        
        # Configure grid weights
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(0, weight=1)
    
    def display_results(self, results: Dict[str, Any]) -> None:
        """Display crawl results."""
        self.current_results = results
        
        # Display summary
        self.display_summary(results)
        
        # Display metadata
        self.display_metadata(results)
        
        # Display links
        self.display_links(results)
        
        # Display resources
        self.display_resources(results)
        
        # Display AJAX data
        self.display_ajax(results)
    
    def display_summary(self, results: Dict[str, Any]) -> None:
        """Display summary information."""
        crawler_info = results.get("crawler_info", {})
        metadata = results.get("metadata", {})
        content_analysis = results.get("content_analysis", {})
        
        summary = f"""URL: {results.get('url', 'N/A')}
Timestamp: {results.get('timestamp', 'N/A')}
Strategy Used: {results.get('strategy_used', 'N/A')}
Crawl Time: {results.get('crawl_time', 0):.2f}s

Page Information:
- Title: {metadata.get('title', 'N/A')}
- Description: {metadata.get('description', 'N/A')}
- Language: {metadata.get('language', 'N/A')}
- Author: {metadata.get('author', 'N/A')}

Content Analysis:
- Word Count: {content_analysis.get('text_stats', {}).get('word_count', 0):,}
- Paragraphs: {content_analysis.get('text_stats', {}).get('paragraph_count', 0)}
- Tables: {len(content_analysis.get('tables', []))}
- Forms: {len(content_analysis.get('forms', []))}
- H1 Tags: {len(content_analysis.get('headings', {}).get('h1', []))}
- H2 Tags: {len(content_analysis.get('headings', {}).get('h2', []))}
- Interactive Elements: {content_analysis.get('interactive_elements', {}).get('buttons', 0)} buttons, {content_analysis.get('interactive_elements', {}).get('inputs', 0)} inputs

Links Summary:
- Internal: {len(results.get('links', {}).get('internal', []))}
- External: {len(results.get('links', {}).get('external', []))}
- Mailto: {len(results.get('links', {}).get('mailto', []))}

Resources:
- Images: {len(results.get('resources', {}).get('images', []))}
- Scripts: {len(results.get('resources', {}).get('scripts', []))}
- Stylesheets: {len(results.get('resources', {}).get('stylesheets', []))}
- Iframes: {len(results.get('resources', {}).get('iframes', []))}"""
        
        self.summary_text.delete(1.0, tk.END)
        self.summary_text.insert(1.0, summary)
    
    def display_metadata(self, results: Dict[str, Any]) -> None:
        """Display metadata information."""
        metadata = results.get("metadata", {})
        meta_display = json.dumps(metadata, indent=2, ensure_ascii=False)
        
        self.metadata_text.delete(1.0, tk.END)
        self.metadata_text.insert(1.0, meta_display)
    
    def display_links(self, results: Dict[str, Any]) -> None:
        """Display links information."""
        links = results.get("links", {})
        links_display = ""
        
        for category, urls in links.items():
            if isinstance(urls, dict):
                for subcat, suburls in urls.items():
                    if suburls:
                        links_display += f"\n{category.upper()} - {subcat.upper()} ({len(suburls)}):\n"
                        for url in suburls[:20]:  # Limit display
                            links_display += f"  {url}\n"
                        if len(suburls) > 20:
                            links_display += f"  ... and {len(suburls) - 20} more\n"
            elif urls:
                links_display += f"\n{category.upper()} ({len(urls)}):\n"
                for url in urls[:20]:  # Limit display
                    links_display += f"  {url}\n"
                if len(urls) > 20:
                    links_display += f"  ... and {len(urls) - 20} more\n"
        
        self.links_text.delete(1.0, tk.END)
        self.links_text.insert(1.0, links_display)
    
    def display_resources(self, results: Dict[str, Any]) -> None:
        """Display resources information."""
        resources = results.get("resources", {})
        resources_display = ""
        
        for category, urls in resources.items():
            if urls:
                resources_display += f"\n{category.upper()} ({len(urls)}):\n"
                for url in urls[:30]:  # Limit display
                    resources_display += f"  {url}\n"
                if len(urls) > 30:
                    resources_display += f"  ... and {len(urls) - 30} more\n"
        
        self.resources_text.delete(1.0, tk.END)
        self.resources_text.insert(1.0, resources_display)
    
    def display_ajax(self, results: Dict[str, Any]) -> None:
        """Display AJAX/API information."""
        ajax_data = results.get("ajax_data", {})
        ajax_display = json.dumps(ajax_data, indent=2, ensure_ascii=False)
        
        self.ajax_text.delete(1.0, tk.END)
        self.ajax_text.insert(1.0, ajax_display)
    
    def export_json(self) -> None:
        """Export results as JSON."""
        if not self.current_results:
            messagebox.showwarning("Warning", "No results to export")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(self.current_results, f, indent=2, ensure_ascii=False)
                messagebox.showinfo("Success", f"Results exported to {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export: {str(e)}")
    
    def export_csv(self) -> None:
        """Export results as CSV."""
        if not self.current_results:
            messagebox.showwarning("Warning", "No results to export")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                import csv
                with open(filename, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    
                    # Write basic information
                    writer.writerow(["Field", "Value"])
                    writer.writerow(["URL", self.current_results.get("url", "")])
                    writer.writerow(["Title", self.current_results.get("metadata", {}).get("title", "")])
                    writer.writerow(["Description", self.current_results.get("metadata", {}).get("description", "")])
                    writer.writerow(["Language", self.current_results.get("metadata", {}).get("language", "")])
                    writer.writerow(["Crawl Time", self.current_results.get("crawl_time", 0)])
                    writer.writerow(["Strategy Used", self.current_results.get("strategy_used", "")])
                    
                    # Add more fields as needed
                    content_analysis = self.current_results.get("content_analysis", {})
                    writer.writerow(["Word Count", content_analysis.get("text_stats", {}).get("word_count", 0)])
                    writer.writerow(["Paragraph Count", content_analysis.get("text_stats", {}).get("paragraph_count", 0)])
                    writer.writerow(["Internal Links", len(self.current_results.get("links", {}).get("internal", []))])
                    writer.writerow(["External Links", len(self.current_results.get("links", {}).get("external", []))])
                    writer.writerow(["Images", len(self.current_results.get("resources", {}).get("images", []))])
                    writer.writerow(["Scripts", len(self.current_results.get("resources", {}).get("scripts", []))])
                
                messagebox.showinfo("Success", f"Results exported to {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export: {str(e)}")
    
    def clear_results(self) -> None:
        """Clear all results."""
        result = messagebox.askyesno("Confirm", "Are you sure you want to clear all results?")
        if result:
            self.current_results = {}
            
            # Clear all tabs
            for text_widget in [self.summary_text, self.metadata_text, self.links_text, self.resources_text, self.ajax_text]:
                text_widget.delete(1.0, tk.END)
            
            self.notify_observers("results_cleared", {})
    
    def update_view(self, event_type: str, data: Dict[str, Any]) -> None:
        """Update view based on controller events."""
        if event_type == "crawl_completed":
            self.display_results(data.get("data", {}))
        elif event_type == "results_cleared":
            self.clear_results()


class MainView(BaseView):
    """
    Main view that coordinates all other views.
    
    Contains:
    - Input view
    - Progress view
    - Results view
    - Menu bar
    - Status bar
    """
    
    def __init__(self, parent: tk.Widget, controller: Optional[object] = None):
        """Initialize the main view."""
        self.controller = controller
        super().__init__(parent, controller)
        
        # Sub-views
        self.input_view = None
        self.progress_view = None
        self.results_view = None
    
    def create_widgets(self) -> None:
        """Create main widgets."""
        # Main frame
        self.main_frame = ttk.Frame(self.parent, padding="10")
        self.widgets["main_frame"] = self.main_frame
        
        # Create sub-views
        self.input_view = InputView(self.main_frame, self.controller)
        self.progress_view = ProgressView(self.main_frame, self.controller)
        self.results_view = ResultsView(self.main_frame, self.controller)
        
        # Menu bar
        self.create_menu_bar()
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        self.status_bar = ttk.Label(self.main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.widgets["status_bar"] = self.status_bar
    
    def create_menu_bar(self) -> None:
        """Create menu bar."""
        self.menu_bar = tk.Menu(self.parent)
        self.parent.config(menu=self.menu_bar)
        
        # File menu
        self.file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="File", menu=self.file_menu)
        self.file_menu.add_command(label="Export JSON", command=self.results_view.export_json)
        self.file_menu.add_command(label="Export CSV", command=self.results_view.export_csv)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self.parent.quit)
        
        # Edit menu
        self.edit_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Edit", menu=self.edit_menu)
        self.edit_menu.add_command(label="Clear Results", command=self.results_view.clear_results)
        
        # Help menu
        self.help_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Help", menu=self.help_menu)
        self.help_menu.add_command(label="About", command=self.show_about)
    
    def show_about(self) -> None:
        """Show about dialog."""
        about_text = """Advanced Crawler GUI
Version 2.0

A modular web crawler with JavaScript support and comprehensive content analysis.

Features:
- JavaScript and static crawling
- Content analysis and metadata extraction
- Link and resource discovery
- Export capabilities
- Observer pattern for real-time updates"""
        
        messagebox.showinfo("About", about_text)
    
    def layout_widgets(self) -> None:
        """Layout main widgets."""
        # Main frame
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Input view
        self.input_view.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # Progress view
        self.progress_view.main_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # Results view
        self.results_view.main_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # Status bar
        self.status_bar.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=2)
        
        # Configure grid weights
        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(2, weight=1)
    
    def bind_events(self) -> None:
        """Bind events to widgets."""
        # Connect sub-views to controller
        if self.controller:
            self.input_view.add_observer(self.controller_event_handler)
            self.progress_view.add_observer(self.controller_event_handler)
            self.results_view.add_observer(self.controller_event_handler)
    
    def controller_event_handler(self, event_type: str, data: Dict[str, Any]) -> None:
        """Handle events from sub-views and forward to controller."""
        if self.controller:
            # Forward events to controller
            if hasattr(self.controller, 'handle_view_event'):
                self.controller.handle_view_event(event_type, data)
    
    def update_status(self, message: str) -> None:
        """Update status bar."""
        self.status_var.set(message)
    
    def update_view(self, event_type: str, data: Dict[str, Any]) -> None:
        """Update view based on controller events."""
        # Forward events to sub-views
        if self.input_view:
            self.input_view.update_view(event_type, data)
        if self.progress_view:
            self.progress_view.update_view(event_type, data)
        if self.results_view:
            self.results_view.update_view(event_type, data)
        
        # Update status bar
        if event_type == "crawl_started":
            self.update_status("Crawling in progress...")
        elif event_type == "crawl_completed":
            self.update_status("Crawl completed successfully")
        elif event_type in ["crawl_failed", "crawl_error"]:
            self.update_status(f"Crawl failed: {data.get('error', 'Unknown error')}")
        else:
            self.update_status("Ready")
    
    def cleanup(self) -> None:
        """Cleanup resources."""
        if self.input_view:
            self.input_view.cleanup()
        if self.progress_view:
            self.progress_view.cleanup()
        if self.results_view:
            self.results_view.cleanup()
        
        super().cleanup()


# Factory functions for creating views

def create_input_view(parent: tk.Widget, controller: Optional[object] = None) -> InputView:
    """Create an input view."""
    return InputView(parent, controller)


def create_progress_view(parent: tk.Widget, controller: Optional[object] = None) -> ProgressView:
    """Create a progress view."""
    return ProgressView(parent, controller)


def create_results_view(parent: tk.Widget, controller: Optional[object] = None) -> ResultsView:
    """Create a results view."""
    return ResultsView(parent, controller)


def create_main_view(parent: tk.Widget, controller: Optional[object] = None) -> MainView:
    """Create a main view."""
    return MainView(parent, controller) 