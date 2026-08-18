"""
Unit tests for the filter_plugins/netbox_filters.py FilterModule.

This is a smoke test for the public Jinja2 filter registration layer
itself. Every other test in this suite imports straight from
netbox_filters_lib, bypassing this file entirely, so a typo in an import,
a rename in netbox_filters_lib not mirrored here, or a filter that was
implemented but never added to FilterModule.filters() would pass the rest
of the unit suite and only surface when Ansible actually loads the plugin.
"""
import pytest
from netbox_filters import FilterModule

# The exact set of filter names FilterModule.filters() is expected to
# register, mirrored from filter_plugins/netbox_filters.py. Keep this in
# sync when adding/removing/renaming a filter there.
EXPECTED_FILTER_NAMES = {
    "collapse_vlan_list",
    "select_interfaces_to_configure",
    "extract_vlan_ids",
    "extract_port_access_vlan_ids",
    "parse_vlan_id_spec",
    "filter_vlans_in_use",
    "filter_out_vlan_groups",
    "extract_evpn_vlans",
    "extract_vxlan_mappings",
    "get_vlans_in_use",
    "get_vlans_needing_changes",
    "get_vlans_needing_igmp_update",
    "get_vlans_needing_voice_update",
    "get_vlans_needing_name_update",
    "get_vlan_interfaces",
    "parse_evpn_evi_output",
    "extract_interface_vrfs",
    "filter_vrfs_in_use",
    "get_vrfs_in_use",
    "filter_configurable_vrfs",
    "get_all_rt_names",
    "build_vrf_rt_config",
    "get_vrf_rt_removals",
    "get_vrf_changes",
    "categorize_l2_interfaces",
    "categorize_l3_interfaces",
    "get_interface_ip_addresses",
    "get_interfaces_needing_config_changes",
    "compare_interface_vlans",
    "get_interfaces_needing_changes",
    "get_virtual_interfaces_to_delete",
    "select_ospf_interfaces",
    "extract_ospf_areas",
    "get_ospf_interfaces_by_area",
    "normalize_ospf_vrfs",
    "filter_ospf_vrfs_in_use",
    "validate_ospf_config",
    "get_ospf_router_changes",
    "get_ospf_interface_changes",
    "format_interface_name",
    "is_ipv4_address",
    "is_ipv6_address",
    "get_interface_vrf",
    "group_interface_ips",
    "build_l3_config_lines",
    "should_add_interface_ip",
    "build_l3_config_preview",
    "get_bgp_session_vrf_info",
    "collect_ebgp_vrf_policy_config",
    "get_bgp_redistribute_config",
    "get_stale_bgp_redistribute",
    "get_bgp_neighbor_options_config",
    "get_stale_bgp_neighbor_options",
    "get_bgp_bfd_enabled",
    "get_stale_bgp_bfd",
    "port_access_diff",
    "port_access_facts_from_device_profiles",
    "port_access_orphans",
    "stp_global_config_diff",
    "stp_interface_changes",
    "vsx_config_diff",
    "get_static_route_changes",
}


class TestFilterModule:
    """Tests for the FilterModule Jinja2 filter registration"""

    def test_filters_returns_dict(self):
        """filters() must return a dict, as required by Ansible's filter
        plugin loader"""
        result = FilterModule().filters()
        assert isinstance(result, dict)

    def test_registered_filter_names_match_expected(self):
        """Every filter netbox_filters.py imports must be registered under
        exactly the expected name - catches a typo'd import, a rename in
        netbox_filters_lib left stale here, or a filter that was written
        but never wired up to FilterModule.filters()"""
        result = FilterModule().filters()
        assert set(result.keys()) == EXPECTED_FILTER_NAMES

    def test_all_registered_filters_are_callable(self):
        """Every registered filter must actually be a callable, not e.g. a
        module or None from a broken import"""
        result = FilterModule().filters()
        for name, func in result.items():
            assert callable(func), f"filter '{name}' is not callable"

    @pytest.mark.parametrize(
        "name",
        [
            # One filter per netbox_filters_lib module imported by
            # netbox_filters.py, so a broken import anywhere in the file
            # fails loudly here instead of only at Ansible runtime.
            "collapse_vlan_list",  # utils
            "get_vlans_in_use",  # vlan_filters
            "get_vrf_changes",  # vrf_filters
            "categorize_l2_interfaces",  # interface_categorization
            "get_interface_ip_addresses",  # interface_ip_processing
            "get_interfaces_needing_config_changes",  # interface_change_detection
            "compare_interface_vlans",  # comparison
            "get_ospf_router_changes",  # ospf_filters
            "is_ipv4_address",  # l3_config_helpers
            "get_bgp_session_vrf_info",  # bgp_filters
            "port_access_diff",  # port_access
            "port_access_orphans",  # port_access_orphans
            "get_virtual_interfaces_to_delete",  # interface_orphans
            "stp_global_config_diff",  # stp
            "vsx_config_diff",  # vsx
            "get_static_route_changes",  # static_route_filters
        ],
    )
    def test_filter_resolves_to_a_real_function(self, name):
        """Each sampled filter must resolve to a function with the expected
        name, proving the import binding actually points at the intended
        netbox_filters_lib function rather than e.g. a shadowed local"""
        result = FilterModule().filters()
        assert result[name].__name__ == name
