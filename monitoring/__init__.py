"""
Monitoring package for flight crawler system.
"""

# Import the class directly without causing circular import
try:
    from .production_memory_monitor import ProductionMemoryMonitor
    # Import the main Monitoring class from monitoring.py
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from monitoring import Monitoring
    __all__ = ['ProductionMemoryMonitor', 'Monitoring']
except ImportError:
    # If there's an import error, create dummy classes
    class ProductionMemoryMonitor:
        def __init__(self, *args, **kwargs):
            pass
    
    class Monitoring:
        def __init__(self, *args, **kwargs):
            pass
        
        def record_success(self):
            pass
        
        def record_error(self):
            pass
    
    __all__ = ['ProductionMemoryMonitor', 'Monitoring'] 