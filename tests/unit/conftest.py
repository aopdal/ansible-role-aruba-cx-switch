"""
Pytest configuration and fixtures for filter plugin tests
"""
import sys
import os
from pathlib import Path

# Add filter_plugins to Python path
filter_plugins_path = Path(__file__).parent.parent.parent / "filter_plugins"
sys.path.insert(0, str(filter_plugins_path))


def pytest_configure(config):
    """Configure pytest"""
    # Disable debug output during tests
    os.environ["DEBUG_ANSIBLE"] = "false"
