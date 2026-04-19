"""
Unit tests for utility functions
"""
import pytest
from netbox_filters_lib.utils import (
    collapse_vlan_list,
    extract_ip_addresses,
    populate_ip_changes,
    select_interfaces_to_configure,
)


class TestCollapseVlanList:
    """Tests for collapse_vlan_list function"""

    def test_empty_list(self):
        """Test with empty list"""
        assert collapse_vlan_list([]) == ""

    def test_single_vlan(self):
        """Test with single VLAN"""
        assert collapse_vlan_list([10]) == "10"

    def test_consecutive_vlans(self):
        """Test with consecutive VLANs"""
        assert collapse_vlan_list([10, 11, 12, 13]) == "10-13"

    def test_non_consecutive_vlans(self):
        """Test with non-consecutive VLANs"""
        assert collapse_vlan_list([10, 15, 20]) == "10,15,20"

    def test_mixed_ranges_and_singles(self):
        """Test with mix of ranges and single VLANs"""
        assert collapse_vlan_list([10, 11, 12, 15, 20, 21]) == "10-12,15,20-21"

    def test_unsorted_input(self):
        """Test with unsorted input"""
        assert collapse_vlan_list([30, 10, 20, 11, 12]) == "10-12,20,30"

    def test_duplicate_vlans(self):
        """Test with duplicate VLANs"""
        assert collapse_vlan_list([10, 10, 11, 11, 12]) == "10-12"

    def test_complex_scenario(self):
        """Test with complex real-world scenario"""
        vlans = [1, 2, 3, 5, 7, 10, 11, 12, 20, 30, 31, 32, 100]
        result = collapse_vlan_list(vlans)
        assert result == "1-3,5,7,10-12,20,30-32,100"

    def test_all_consecutive(self):
        """Test with all consecutive VLANs"""
        assert collapse_vlan_list(list(range(1, 101))) == "1-100"

    def test_two_vlan_range(self):
        """Test with two consecutive VLANs"""
        assert collapse_vlan_list([10, 11]) == "10-11"


class TestExtractIPAddresses:
    """Tests for extract_ip_addresses function"""

    def test_empty_interface(self):
        """Test interface with no IP addresses"""
        nb_intf = {}
        ipv4, ipv6 = extract_ip_addresses(nb_intf)
        assert ipv4 == []
        assert ipv6 == []

    def test_ipv4_only(self):
        """Test interface with only IPv4 addresses"""
        nb_intf = {
            "ip_addresses": [
                {"address": "192.168.1.1/24"},
                {"address": "10.0.0.1/24"},
            ]
        }
        ipv4, ipv6 = extract_ip_addresses(nb_intf)
        assert ipv4 == ["192.168.1.1/24", "10.0.0.1/24"]
        assert ipv6 == []

    def test_ipv6_only(self):
        """Test interface with only IPv6 addresses"""
        nb_intf = {
            "ip_addresses": [
                {"address": "2001:db8::1/64"},
                {"address": "fe80::1/64"},
            ]
        }
        ipv4, ipv6 = extract_ip_addresses(nb_intf)
        assert ipv4 == []
        assert ipv6 == ["2001:db8::1/64", "fe80::1/64"]

    def test_mixed_ip_versions(self):
        """Test interface with both IPv4 and IPv6"""
        nb_intf = {
            "ip_addresses": [
                {"address": "192.168.1.1/24"},
                {"address": "2001:db8::1/64"},
                {"address": "10.0.0.1/24"},
                {"address": "fe80::1/64"},
            ]
        }
        ipv4, ipv6 = extract_ip_addresses(nb_intf)
        assert ipv4 == ["192.168.1.1/24", "10.0.0.1/24"]
        assert ipv6 == ["2001:db8::1/64", "fe80::1/64"]

    def test_invalid_ip_objects(self):
        """Test handling of invalid IP objects"""
        nb_intf = {
            "ip_addresses": [
                {"address": "192.168.1.1/24"},
                "not-a-dict",  # Invalid object
                {"no-address-key": "value"},  # Missing address
                {"address": None},  # None address
                {"address": "2001:db8::1/64"},
            ]
        }
        ipv4, ipv6 = extract_ip_addresses(nb_intf)
        assert ipv4 == ["192.168.1.1/24"]
        assert ipv6 == ["2001:db8::1/64"]

    def test_exclude_anycast_skips_anycast_ips(self):
        """Test that exclude_anycast=True omits IPs with role 'anycast'"""
        nb_intf = {
            "ip_addresses": [
                {"address": "192.168.1.1/24", "role": None},
                {"address": "10.0.0.1/24", "role": {"value": "anycast"}},
                {"address": "2001:db8::1/64", "role": {"value": "anycast"}},
                {"address": "172.16.0.1/24"},  # no role key at all
            ]
        }
        ipv4, ipv6 = extract_ip_addresses(nb_intf, exclude_anycast=True)
        assert ipv4 == ["192.168.1.1/24", "172.16.0.1/24"]
        assert ipv6 == []

    def test_exclude_anycast_false_includes_all(self):
        """Test that exclude_anycast=False (default) includes anycast IPs"""
        nb_intf = {
            "ip_addresses": [
                {"address": "192.168.1.1/24"},
                {"address": "10.0.0.1/24", "role": {"value": "anycast"}},
            ]
        }
        ipv4, ipv6 = extract_ip_addresses(nb_intf, exclude_anycast=False)
        assert ipv4 == ["192.168.1.1/24", "10.0.0.1/24"]

    def test_exclude_anycast_string_role_value(self):
        """Test exclude_anycast with plain string role (non-dict)"""
        nb_intf = {
            "ip_addresses": [
                {"address": "10.0.0.1/24", "role": "anycast"},
                {"address": "192.168.1.1/24", "role": "regular"},
            ]
        }
        ipv4, ipv6 = extract_ip_addresses(nb_intf, exclude_anycast=True)
        assert "10.0.0.1/24" not in ipv4
        assert "192.168.1.1/24" in ipv4


class TestPopulateIPChanges:
    """Tests for populate_ip_changes function"""

    def test_basic_ip_population(self):
        """Test basic IP changes population"""
        nb_intf = {}
        nb_ipv4 = ["192.168.1.1/24", "10.0.0.1/24"]
        nb_ipv6 = ["2001:db8::1/64"]

        populate_ip_changes(nb_intf, nb_ipv4, nb_ipv6)

        assert "_ip_changes" in nb_intf
        assert nb_intf["_ip_changes"]["ipv4_to_add"] == nb_ipv4
        assert nb_intf["_ip_changes"]["ipv6_addresses"] == nb_ipv6

    def test_empty_ip_lists(self):
        """Test with empty IP address lists"""
        nb_intf = {}
        populate_ip_changes(nb_intf, [], [])

        # Note: Function doesn't create _ip_changes if no IPs to add
        assert "_ip_changes" not in nb_intf

    def test_overwrites_existing_ip_changes(self):
        """Test that it overwrites existing _ip_changes"""
        nb_intf = {
            "_ip_changes": {
                "ipv4_to_add": ["old-ip"],
                "ipv6_addresses": ["old-ipv6"],
            }
        }
        nb_ipv4 = ["192.168.1.1/24"]
        nb_ipv6 = ["2001:db8::1/64"]

        populate_ip_changes(nb_intf, nb_ipv4, nb_ipv6)

        assert nb_intf["_ip_changes"]["ipv4_to_add"] == nb_ipv4
        assert nb_intf["_ip_changes"]["ipv6_addresses"] == nb_ipv6

    def test_preserves_other_interface_data(self):
        """Test that other interface data is preserved"""
        nb_intf = {
            "name": "1/1/1",
            "type": "physical",
            "enabled": True,
        }
        populate_ip_changes(nb_intf, ["10.0.0.1/24"], [])

        assert nb_intf["name"] == "1/1/1"
        assert nb_intf["type"] == "physical"
        assert nb_intf["enabled"] is True
        assert "_ip_changes" in nb_intf


class TestSelectInterfacesToConfigure:
    """Tests for select_interfaces_to_configure function"""

    def test_standard_mode_returns_all(self):
        """Test that standard mode returns all interfaces"""
        interfaces = [
            {"name": "1/1/1", "type": {"value": "1000base-t"}},
            {"name": "1/1/2", "type": {"value": "1000base-t"}},
            {"name": "lag1", "type": {"value": "lag"}},
        ]
        result = select_interfaces_to_configure(interfaces, idempotent_mode=False)
        assert len(result) == 3
        assert result == interfaces

    def test_idempotent_mode_with_changes(self):
        """Test idempotent mode with interfaces needing changes"""
        interfaces = [
            {"name": "1/1/1", "type": {"value": "1000base-t"}},
            {"name": "1/1/2", "type": {"value": "1000base-t"}},
            {"name": "lag1", "type": {"value": "lag"}},
        ]
        interfaces_needing_changes = {
            "configure": [interfaces[0], interfaces[2]],  # Only 1/1/1 and lag1
        }
        result = select_interfaces_to_configure(
            interfaces, idempotent_mode=True, interfaces_needing_changes=interfaces_needing_changes
        )
        assert len(result) == 2
        assert result[0]["name"] == "1/1/1"
        assert result[1]["name"] == "lag1"

    def test_idempotent_mode_no_changes(self):
        """Test idempotent mode when no changes needed"""
        interfaces = [
            {"name": "1/1/1", "type": {"value": "1000base-t"}},
            {"name": "1/1/2", "type": {"value": "1000base-t"}},
        ]
        interfaces_needing_changes = {
            "configure": [],  # No interfaces need changes
        }
        result = select_interfaces_to_configure(
            interfaces, idempotent_mode=True, interfaces_needing_changes=interfaces_needing_changes
        )
        assert len(result) == 0

    def test_idempotent_mode_without_changes_dict(self):
        """Test idempotent mode when no changes dict provided returns all interfaces"""
        interfaces = [
            {"name": "1/1/1", "type": {"value": "1000base-t"}},
            {"name": "1/1/2", "type": {"value": "1000base-t"}},
        ]
        # When idempotent mode is True but no changes dict provided, return all interfaces
        result = select_interfaces_to_configure(interfaces, idempotent_mode=True)
        assert len(result) == 2

    def test_idempotent_mode_with_invalid_changes_dict(self):
        """Test idempotent mode with invalid changes dict returns all interfaces"""
        interfaces = [
            {"name": "1/1/1", "type": {"value": "1000base-t"}},
        ]
        # Invalid dict (not a dict)
        result = select_interfaces_to_configure(
            interfaces, idempotent_mode=True, interfaces_needing_changes="not-a-dict"
        )
        assert len(result) == 1

    def test_empty_interfaces(self):
        """Test with empty interface list"""
        result = select_interfaces_to_configure([], idempotent_mode=False)
        assert result == []

    def test_none_interfaces(self):
        """Test with None interfaces"""
        result = select_interfaces_to_configure(None, idempotent_mode=False)
        assert result == []

    def test_standard_mode_ignores_changes_dict(self):
        """Test that standard mode ignores the interfaces_needing_changes dict"""
        interfaces = [
            {"name": "1/1/1", "type": {"value": "1000base-t"}},
            {"name": "1/1/2", "type": {"value": "1000base-t"}},
        ]
        interfaces_needing_changes = {
            "configure": [interfaces[0]],  # Only 1/1/1
        }
        # In standard mode (idempotent_mode=False), all interfaces should be returned
        result = select_interfaces_to_configure(
            interfaces, idempotent_mode=False, interfaces_needing_changes=interfaces_needing_changes
        )
        assert len(result) == 2
