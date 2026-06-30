"""
Pytest configuration and fixtures for filter plugin tests
"""
import sys
import os
from pathlib import Path

# Add role root (netbox_filters_lib) and filter_plugins (rest_api_transforms) to path
role_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(role_root))
sys.path.insert(0, str(role_root / "filter_plugins"))


def pytest_configure(config):
    """Configure pytest"""
    # Disable debug output during tests
    os.environ["DEBUG_ANSIBLE"] = "false"
