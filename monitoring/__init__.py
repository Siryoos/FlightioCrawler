"""
Monitoring package for flight crawler system.
"""

# Import the class directly without causing circular import
try:
    from .production_memory_monitor import ProductionMemoryMonitor
    from .unified_monitoring import UnifiedMonitor
    # Import the main CrawlerMonitor class from the parent monitoring.py
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from monitoring import CrawlerMonitor, Monitoring
    __all__ = ['ProductionMemoryMonitor', 'CrawlerMonitor', 'Monitoring', 'UnifiedMonitor']
except ImportError:
    # If there's an import error, create dummy classes
    class ProductionMemoryMonitor:
        def __init__(self, *args, **kwargs):
            pass
    
    class CrawlerMonitor:
        def __init__(self, *args, **kwargs):
            pass
        
        def record_success(self):
            pass
        
        def record_error(self):
            pass
        
        def get_all_metrics(self):
            return {}
        
        def get_health_status(self):
            return {"status": "unknown"}
        
        def track_request(self, domain, start_time):
            pass
    
    class Monitoring:
        def __init__(self, *args, **kwargs):
            pass
        
        def record_success(self):
            pass
        
        def record_error(self):
            pass
    
    class UnifiedMonitor:
        def __init__(self, *args, **kwargs):
            pass

    __all__ = ['ProductionMemoryMonitor', 'CrawlerMonitor', 'Monitoring', 'UnifiedMonitor']
