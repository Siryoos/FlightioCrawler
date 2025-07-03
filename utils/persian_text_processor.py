"""
Utility module for Persian text processing.
This module provides a unified interface for Persian text processing
by importing from the main persian_text module.
"""

from persian_text import PersianTextProcessor

# Re-export the processor class for backward compatibility
__all__ = ['PersianTextProcessor'] 