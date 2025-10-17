"""
Unit tests for interface filter functions
"""
import pytest
from netbox_filters_lib.interface_filters import (
    categorize_l2_interfaces,
    categorize_l3_interfaces,
    get_interface_ip_addresses,
)
from .fixtures import get_sample_interfaces, get_sample_ip_addresses


class TestCategorizeL2Interfaces:
    """Tests for categorize_l2_interfaces function"""

    def test_categorize_physical_access(self):
        """Test categorizing physical access ports"""
        interfaces = [
            {
                "name": "1/1/1",
                "type": {"value": "1000base-t"},
                "mode": {"value": "access"},
                "untagged_vlan": {"vid": 10},
                "tagged_vlans": [],
                "lag": None,
            }
        ]
        result = categorize_l2_interfaces(interfaces)
        assert len(result["access"]) == 1
        assert result["access"][0]["name"] == "1/1/1"
        assert len(result["tagged_with_untagged"]) == 0
        assert len(result["tagged_no_untagged"]) == 0

    def test_categorize_physical_trunk_with_native(self):
        """Test categorizing trunk ports with native VLAN"""
        interfaces = [
            {
                "name": "1/1/2",
                "type": {"value": "1000base-t"},
                "mode": {"value": "tagged"},
                "untagged_vlan": {"vid": 100},
                "tagged_vlans": [{"vid": 200}],
                "lag": None,
            }
        ]
        result = categorize_l2_interfaces(interfaces)
        assert len(result["tagged_with_untagged"]) == 1
        assert result["tagged_with_untagged"][0]["name"] == "1/1/2"

    def test_categorize_physical_trunk_no_native(self):
        """Test categorizing trunk ports without native VLAN"""
        interfaces = [
            {
                "name": "1/1/3",
                "type": {"value": "1000base-t"},
                "mode": {"value": "tagged"},
                "untagged_vlan": None,
                "tagged_vlans": [{"vid": 20}, {"vid": 30}],
                "lag": None,
            }
        ]
        result = categorize_l2_interfaces(interfaces)
        assert len(result["tagged_no_untagged"]) == 1
        assert result["tagged_no_untagged"][0]["name"] == "1/1/3"

    def test_categorize_lag_access(self):
        """Test categorizing LAG access ports"""
        interfaces = [
            {
                "name": "lag1",
                "type": {"value": "lag"},
                "mode": {"value": "access"},
                "untagged_vlan": {"vid": 50},
                "tagged_vlans": [],
            }
        ]
        result = categorize_l2_interfaces(interfaces)
        assert len(result["lag_access"]) == 1
        assert result["lag_access"][0]["name"] == "lag1"

    def test_categorize_mclag(self):
        """Test categorizing MCLAG interfaces"""
        interfaces = [
            {
                "name": "lag1",
                "type": {"value": "lag"},
                "mode": {"value": "access"},
                "untagged_vlan": {"vid": 50},
                "custom_fields": {"if_mclag": True},
            }
        ]
        result = categorize_l2_interfaces(interfaces)
        assert len(result["mclag_access"]) == 1
        assert result["mclag_access"][0]["name"] == "lag1"

    def test_categorize_mixed_interfaces(self):
        """Test categorizing mixed interface types"""
        interfaces = get_sample_interfaces()
        result = categorize_l2_interfaces(interfaces)
        # Should have at least one of each type
        assert len(result["access"]) > 0
        assert len(result["tagged_no_untagged"]) > 0

    def test_categorize_skips_no_mode(self):
        """Test that interfaces without mode are skipped"""
        interfaces = [
            {
                "name": "1/1/1",
                "type": {"value": "1000base-t"},
            }
        ]
        result = categorize_l2_interfaces(interfaces)
        # All categories should be empty
        assert len(result["access"]) == 0
        assert len(result["tagged_with_untagged"]) == 0
        assert len(result["tagged_no_untagged"]) == 0


class TestCategorizeL3Interfaces:
    """Tests for categorize_l3_interfaces function"""

    def test_categorize_physical_default_vrf(self):
        """Test categorizing physical L3 interfaces in default VRF"""
        interface_ips = [
            {
                "interface_name": "1/1/1",
                "interface_type": "1000base-t",
                "address": "10.1.1.1/30",
                "vrf": "default",
            }
        ]
        result = categorize_l3_interfaces(interface_ips)
        assert len(result["physical_default_vrf"]) == 1
        assert result["physical_default_vrf"][0]["interface_name"] == "1/1/1"

    def test_categorize_physical_custom_vrf(self):
        """Test categorizing physical L3 interfaces in custom VRF"""
        interface_ips = [
            {
                "interface": {"vrf": {"name": "customer_a"}},
                "interface_name": "1/1/2",
                "interface_type": "1000base-t",
                "address": "192.168.1.1/24",
                "vrf": "customer_a",
            }
        ]
        result = categorize_l3_interfaces(interface_ips)
        assert len(result["physical_custom_vrf"]) == 1
        assert result["physical_custom_vrf"][0]["vrf"] == "customer_a"

    def test_categorize_vlan_interface(self):
        """Test categorizing VLAN (SVI) interfaces"""
        interface_ips = [
            {
                "interface_name": "vlan100",
                "interface_type": "virtual",
                "address": "10.1.100.1/24",
                "vrf": "default",
            }
        ]
        result = categorize_l3_interfaces(interface_ips)
        assert len(result["vlan_default_vrf"]) == 1
        assert result["vlan_default_vrf"][0]["interface_name"] == "vlan100"

    def test_categorize_loopback(self):
        """Test categorizing loopback interfaces"""
        interface_ips = [
            {
                "interface_name": "loopback0",
                "interface_type": "virtual",
                "address": "10.255.255.1/32",
                "vrf": "default",
            }
        ]
        result = categorize_l3_interfaces(interface_ips)
        assert len(result["loopback"]) == 1
        assert result["loopback"][0]["interface_name"] == "loopback0"

    def test_categorize_lag_interface(self):
        """Test categorizing LAG L3 interfaces"""
        interface_ips = [
            {
                "interface_name": "lag1",
                "interface_type": "lag",
                "address": "10.1.1.1/30",
                "vrf": "default",
            }
        ]
        result = categorize_l3_interfaces(interface_ips)
        assert len(result["lag_default_vrf"]) == 1
        assert result["lag_default_vrf"][0]["interface_name"] == "lag1"

    def test_categorize_mixed_l3_interfaces(self):
        """Test categorizing mixed L3 interface types"""
        interface_ips = [
            {
                "interface_name": "1/1/1",
                "interface_type": "1000base-t",
                "address": "10.1.1.1/30",
                "vrf": "default",
            },
            {
                "interface": {"vrf": {"name": "customer_a"}},
                "interface_name": "1/1/2",
                "interface_type": "1000base-t",
                "address": "192.168.1.1/24",
                "vrf": "customer_a",
            },
            {
                "interface_name": "vlan100",
                "interface_type": "virtual",
                "address": "10.1.100.1/24",
                "vrf": "default",
            },
            {
                "interface_name": "loopback0",
                "interface_type": "virtual",
                "address": "10.255.255.1/32",
                "vrf": "default",
            },
        ]
        result = categorize_l3_interfaces(interface_ips)
        assert len(result["physical_default_vrf"]) == 1
        assert len(result["physical_custom_vrf"]) == 1
        assert len(result["vlan_default_vrf"]) == 1
        assert len(result["loopback"]) == 1

    def test_categorize_empty_list(self):
        """Test with empty interface list"""
        result = categorize_l3_interfaces([])
        # All categories should be empty lists
        assert result["physical_default_vrf"] == []
        assert result["physical_custom_vrf"] == []
        assert result["vlan_default_vrf"] == []
        assert result["loopback"] == []


class TestGetInterfaceIpAddresses:
    """Tests for get_interface_ip_addresses function"""

    def test_get_interface_ip_addresses(self):
        """Test matching IP addresses to interfaces"""
        interfaces = [
            {
                "id": 1,
                "name": "1/1/1",
                "type": {"value": "1000base-t"},
            },
            {
                "id": 2,
                "name": "1/1/2",
                "type": {"value": "1000base-t"},
            },
        ]
        ip_addresses = [
            {
                "address": "10.1.1.1/30",
                "vrf": {"name": "default"},
                "assigned_object": {"id": 1},
            },
            {
                "address": "192.168.1.1/24",
                "vrf": {"name": "customer_a"},
                "assigned_object": {"id": 2},
            },
        ]
        result = get_interface_ip_addresses(interfaces, ip_addresses)
        assert len(result) == 2
        assert result[0]["address"] == "10.1.1.1/30"
        assert result[1]["address"] == "192.168.1.1/24"

    def test_get_interface_multiple_ips(self):
        """Test interface with multiple IP addresses"""
        interfaces = [
            {
                "id": 1,
                "name": "1/1/1",
                "type": {"value": "1000base-t"},
            },
        ]
        ip_addresses = [
            {
                "address": "10.1.1.1/30",
                "vrf": {"name": "default"},
                "assigned_object": {"id": 1},
            },
            {
                "address": "2001:db8::1/64",
                "vrf": {"name": "default"},
                "assigned_object": {"id": 1},
            },
        ]
        result = get_interface_ip_addresses(interfaces, ip_addresses)
        assert len(result) == 2

    def test_get_interface_no_ips(self):
        """Test with no IP addresses"""
        interfaces = [{"id": 1, "name": "1/1/1", "type": {"value": "1000base-t"}}]
        ip_addresses = []
        result = get_interface_ip_addresses(interfaces, ip_addresses)
        assert result == []

    def test_get_interface_no_match(self):
        """Test when IP addresses don't match any interfaces"""
        interfaces = [{"id": 1, "name": "1/1/1", "type": {"value": "1000base-t"}}]
        ip_addresses = [
            {
                "address": "10.1.1.1/30",
                "vrf": {"name": "default"},
                "assigned_object": {"id": 999},  # No matching interface
            }
        ]
        result = get_interface_ip_addresses(interfaces, ip_addresses)
        assert result == []
