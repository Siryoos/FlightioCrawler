"""
Compatibility wrapper for alibaba_adapter imports.
This file maintains backward compatibility while redirecting to the enhanced version.
"""

# Import the enhanced version and provide compatibility aliases
from .alibaba_adapter_enhanced import (
    EnhancedAlibabaAdapter as AlibabaAdapter,
    create_enhanced_alibaba_adapter as create_alibaba_adapter
)

# Re-export for backward compatibility
__all__ = ['AlibabaAdapter', 'create_alibaba_adapter']

# Maintain the same interface
def create_adapter(config=None):
    """Create Alibaba adapter instance (compatibility function)."""
    return AlibabaAdapter(config) 