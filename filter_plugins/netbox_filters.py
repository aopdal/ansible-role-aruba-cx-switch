#!/usr/bin/env python3
"""
Custom Ansible filters for NetBox data transformation
"""

import sys
import os

# Add the filter_plugins directory to Python path to enable imports
# This allows the submodule imports to work when installed as a role
_filter_dir = os.path.dirname(os.path.abspath(__file__))
if _filter_dir not in sys.path:
    sys.path.insert(0, _filter_dir)

# Import from the netbox_filters_lib package (subdirectory)
# pylint: disable=wrong-import-position
# flake8: noqa: E402
from netbox_filters_lib.utils import collapse_vlan_list
from netbox_filters_lib.vlan_filters import (
    extract_vlan_ids,
    filter_vlans_in_use,
    extract_evpn_vlans,
    extract_vxlan_mappings,
    get_vlans_in_use,
    get_vlans_needing_changes,
    get_vlan_interfaces,
)
from netbox_filters_lib.vrf_filters import (
    extract_interface_vrfs,
    filter_vrfs_in_use,
    get_vrfs_in_use,
    filter_configurable_vrfs,
)
from netbox_filters_lib.interface_filters import (
    categorize_l2_interfaces,
    categorize_l3_interfaces,
    get_interface_ip_addresses,
)
from netbox_filters_lib.comparison import (
    compare_interface_vlans,
    get_interfaces_needing_changes,
    get_interfaces_needing_vlan_cleanup,
)


class FilterModule:
    """Ansible filter plugin class"""

    def filters(self):
        """Return dict of all available filters"""
        return {
            "collapse_vlan_list": collapse_vlan_list,
            "extract_vlan_ids": extract_vlan_ids,
            "filter_vlans_in_use": filter_vlans_in_use,
            "extract_evpn_vlans": extract_evpn_vlans,
            "extract_vxlan_mappings": extract_vxlan_mappings,
            "get_vlans_in_use": get_vlans_in_use,
            "get_vlans_needing_changes": get_vlans_needing_changes,
            "get_vlan_interfaces": get_vlan_interfaces,
            "extract_interface_vrfs": extract_interface_vrfs,
            "filter_vrfs_in_use": filter_vrfs_in_use,
            "get_vrfs_in_use": get_vrfs_in_use,
            "filter_configurable_vrfs": filter_configurable_vrfs,
            "categorize_l2_interfaces": categorize_l2_interfaces,
            "categorize_l3_interfaces": categorize_l3_interfaces,
            "get_interface_ip_addresses": get_interface_ip_addresses,
            "compare_interface_vlans": compare_interface_vlans,
            "get_interfaces_needing_vlan_cleanup": get_interfaces_needing_vlan_cleanup,
            "get_interfaces_needing_changes": get_interfaces_needing_changes,
        }
