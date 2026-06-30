"""
NetBox filters package for Ansible

This package provides custom Ansible filters for transforming NetBox data
for use with Aruba AOS-CX switches.
"""

from .utils import (
    _debug,
    collapse_vlan_list,
    select_interfaces_to_configure,
    extract_ip_addresses,
    populate_ip_changes,
)
from .vlan_filters import (
    extract_vlan_ids,
    extract_port_access_vlan_ids,
    filter_vlans_in_use,
    extract_evpn_vlans,
    extract_vxlan_mappings,
    get_vlans_in_use,
    get_vlans_needing_changes,
    get_vlan_interfaces,
    parse_evpn_evi_output,
    parse_vlan_id_spec,
)
from .vrf_filters import (
    extract_interface_vrfs,
    filter_vrfs_in_use,
    get_vrfs_in_use,
    filter_configurable_vrfs,
    get_all_rt_names,
    build_vrf_rt_config,
)
from .bgp_filters import (
    get_bgp_session_vrf_info,
    collect_ebgp_vrf_policy_config,
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
from .ospf_filters import (
    select_ospf_interfaces,
    extract_ospf_areas,
    get_ospf_interfaces_by_area,
    validate_ospf_config,
)
from .l3_config_helpers import (
    format_interface_name,
    is_ipv4_address,
    is_ipv6_address,
    get_interface_vrf,
    group_interface_ips,
    build_l3_config_lines,
)
from .port_access import (
    port_access_diff,
    port_access_facts_from_device_profiles,
)

__all__ = [
    # Utilities
    "_debug",
    "collapse_vlan_list",
    "select_interfaces_to_configure",
    "extract_ip_addresses",
    "populate_ip_changes",
    # VLAN filters
    "extract_vlan_ids",
    "extract_port_access_vlan_ids",
    "filter_vlans_in_use",
    "extract_evpn_vlans",
    "extract_vxlan_mappings",
    "get_vlans_in_use",
    "get_vlans_needing_changes",
    "get_vlan_interfaces",
    "parse_evpn_evi_output",
    "parse_vlan_id_spec",
    # VRF filters
    "extract_interface_vrfs",
    "filter_vrfs_in_use",
    "get_vrfs_in_use",
    "filter_configurable_vrfs",
    "get_all_rt_names",
    "build_vrf_rt_config",
    # BGP filters
    "get_bgp_session_vrf_info",
    "collect_ebgp_vrf_policy_config",
    # Interface categorization
    "categorize_l2_interfaces",
    "categorize_l3_interfaces",
    # Interface IP processing
    "get_interface_ip_addresses",
    # Interface change detection
    "get_interfaces_needing_config_changes",
    # Comparison filters
    "compare_interface_vlans",
    "get_interfaces_needing_changes",
    # OSPF filters
    "select_ospf_interfaces",
    "extract_ospf_areas",
    "get_ospf_interfaces_by_area",
    "validate_ospf_config",
    # L3 config helpers
    "format_interface_name",
    "is_ipv4_address",
    "is_ipv6_address",
    "get_interface_vrf",
    "group_interface_ips",
    "build_l3_config_lines",
    # Port-access
    "port_access_diff",
    "port_access_facts_from_device_profiles",
]
