"""
Unit tests for utility functions
"""
import pytest
from netbox_filters_lib.utils import (
    collapse_vlan_list,
    extract_ip_addresses,
    populate_ip_changes,
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
                {"address": "fe80::1/128"},
            ]
        }
        ipv4, ipv6 = extract_ip_addresses(nb_intf)
        assert ipv4 == []
        assert ipv6 == ["2001:db8::1/64", "fe80::1/128"]

    def test_mixed_ip_versions(self):
        """Test interface with both IPv4 and IPv6"""
        nb_intf = {
            "ip_addresses": [
                {"address": "192.168.1.1/24"},
                {"address": "2001:db8::1/64"},
                {"address": "10.0.0.1/24"},
                {"address": "fe80::1/128"},
            ]
        }
        ipv4, ipv6 = extract_ip_addresses(nb_intf)
        assert ipv4 == ["192.168.1.1/24", "10.0.0.1/24"]
        assert ipv6 == ["2001:db8::1/64", "fe80::1/128"]

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
