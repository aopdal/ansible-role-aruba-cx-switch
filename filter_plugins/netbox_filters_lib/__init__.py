"""
NetBox filters package for Ansible

This package provides custom Ansible filters for transforming NetBox data
for use with Aruba AOS-CX switches.
"""

from .utils import _debug, collapse_vlan_list
from .vlan_filters import (
    extract_vlan_ids,
    filter_vlans_in_use,
    extract_evpn_vlans,
    extract_vxlan_mappings,
    get_vlans_in_use,
    get_vlans_needing_changes,
    get_vlan_interfaces,
)
from .vrf_filters import (
    extract_interface_vrfs,
    filter_vrfs_in_use,
    get_vrfs_in_use,
    filter_configurable_vrfs,
)
from .interface_categorization import (
    categorize_l2_interfaces,
    categorize_l3_interfaces,
)
from .interface_ip_processing import (
    get_interface_ip_addresses,
)
from .interface_change_detection import (
    get_interfaces_needing_config_changes,
)
from .comparison import (
    compare_interface_vlans,
    get_interfaces_needing_changes,
)

__all__ = [
    # Utilities
    "_debug",
    "collapse_vlan_list",
    # VLAN filters
    "extract_vlan_ids",
    "filter_vlans_in_use",
    "extract_evpn_vlans",
    "extract_vxlan_mappings",
    "get_vlans_in_use",
    "get_vlans_needing_changes",
    "get_vlan_interfaces",
    # VRF filters
    "extract_interface_vrfs",
    "filter_vrfs_in_use",
    "get_vrfs_in_use",
    "filter_configurable_vrfs",
    # Interface filters
    "categorize_l2_interfaces",
    "categorize_l3_interfaces",
    "get_interface_ip_addresses",
    "get_interfaces_needing_config_changes",
    # Comparison filters
    "compare_interface_vlans",
    "get_interfaces_needing_changes",
]
