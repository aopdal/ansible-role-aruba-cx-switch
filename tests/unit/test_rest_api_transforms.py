"""
Unit tests for REST API transform filter functions
"""
import pytest
from rest_api_transforms import (
    rest_api_to_aoscx_interfaces,
    rest_api_to_aoscx_vlans,
    rest_api_to_aoscx_evpn_vlans,
    rest_api_to_aoscx_vnis,
)


class TestRestApiToAoscxInterfaces:
    """Tests for rest_api_to_aoscx_interfaces function"""

    def test_basic_interface_conversion(self):
        """Test basic interface data conversion"""
        rest_data = {
            "1/1/1": {
                "admin_state": "up",
                "description": "Uplink",
                "mtu": 9198,
                "type": "physical",
            }
        }
        result = rest_api_to_aoscx_interfaces(rest_data)
        assert "1/1/1" in result
        assert result["1/1/1"]["name"] == "1/1/1"
        assert result["1/1/1"]["admin"] == "up"
        assert result["1/1/1"]["description"] == "Uplink"
        assert result["1/1/1"]["mtu"] == 9198

    def test_ipv6_addresses_conversion(self):
        """Test IPv6 addresses are properly decoded from URL-encoded keys"""
        rest_data = {
            "vlan10": {
                "admin_state": "up",
                "ip6_addresses": {
                    "2001%3Adb8%3A%3A1%2F64": {
                        "address": "2001:db8::1/64"
                    }
                },
            }
        }
        result = rest_api_to_aoscx_interfaces(rest_data)
        assert "vlan10" in result
        ip6 = result["vlan10"]["ip6_addresses"]
        assert isinstance(ip6, dict)
        assert "2001:db8::1/64" in ip6

    def test_vsx_virtual_ips(self):
        """Test VSX virtual IPs are included"""
        rest_data = {
            "vlan100": {
                "admin_state": "up",
                "vsx_virtual_ip4": "10.1.100.254/24",
                "vsx_virtual_ip6": "2001:db8:100::fe/64",
                "vsx_virtual_gw_mac_v4": "00:00:5e:00:01:01",
            }
        }
        result = rest_api_to_aoscx_interfaces(rest_data)
        assert result["vlan100"]["vsx_virtual_ip4"] == "10.1.100.254/24"
        assert result["vlan100"]["vsx_virtual_ip6"] == "2001:db8:100::fe/64"
        assert result["vlan100"]["vsx_virtual_gw_mac_v4"] == "00:00:5e:00:01:01"

    def test_empty_input(self):
        """Test with empty input"""
        result = rest_api_to_aoscx_interfaces({})
        assert result == {}

    def test_non_dict_input(self):
        """Test with non-dict input"""
        result = rest_api_to_aoscx_interfaces(None)
        assert result == {}
        result = rest_api_to_aoscx_interfaces([])
        assert result == {}
        result = rest_api_to_aoscx_interfaces("string")
        assert result == {}

    def test_admin_field_fallback(self):
        """Test admin field fallback when admin_state is not present"""
        rest_data = {
            "1/1/1": {
                "admin": "down",
                "description": "Test",
            }
        }
        result = rest_api_to_aoscx_interfaces(rest_data)
        assert result["1/1/1"]["admin"] == "down"

    def test_ipv6_as_url_string(self):
        """Test handling of IPv6 as URL string (older API versions)"""
        rest_data = {
            "vlan10": {
                "admin_state": "up",
                "ip6_addresses": "/rest/v10.09/system/interfaces/vlan10/ip6_addresses",
            }
        }
        result = rest_api_to_aoscx_interfaces(rest_data)
        # Should keep the URL string as-is
        assert result["vlan10"]["ip6_addresses"] == \
            "/rest/v10.09/system/interfaces/vlan10/ip6_addresses"

    def test_multiple_interfaces(self):
        """Test conversion of multiple interfaces"""
        rest_data = {
            "1/1/1": {"admin_state": "up", "description": "Port 1"},
            "1/1/2": {"admin_state": "down", "description": "Port 2"},
            "vlan10": {"admin_state": "up", "description": "VLAN 10"},
        }
        result = rest_api_to_aoscx_interfaces(rest_data)
        assert len(result) == 3
        assert "1/1/1" in result
        assert "1/1/2" in result
        assert "vlan10" in result


class TestRestApiToAoscxVlans:
    """Tests for rest_api_to_aoscx_vlans function"""

    def test_basic_vlan_conversion(self):
        """Test basic VLAN data conversion"""
        rest_data = {
            "10": {
                "id": 10,
                "name": "DATA",
                "description": "Data VLAN",
                "admin": "up",
                "voice": False,
                "type": "static",
            }
        }
        result = rest_api_to_aoscx_vlans(rest_data)
        assert "10" in result
        assert result["10"]["id"] == 10
        assert result["10"]["name"] == "DATA"
        assert result["10"]["description"] == "Data VLAN"
        assert result["10"]["admin"] == "up"

    def test_vlan_id_as_int_key(self):
        """Test VLAN with integer key"""
        rest_data = {
            10: {
                "id": 10,
                "name": "VLAN10",
            }
        }
        result = rest_api_to_aoscx_vlans(rest_data)
        # Key should be string
        assert "10" in result
        assert result["10"]["id"] == 10

    def test_skip_uri_strings(self):
        """Test that URI strings are skipped (depth=1 behavior)"""
        rest_data = {
            "10": "/rest/v10.17/system/vlans/10",
            "20": {"id": 20, "name": "VLAN20"},
        }
        result = rest_api_to_aoscx_vlans(rest_data)
        # Only the dict entry should be included
        assert len(result) == 1
        assert "20" in result
        assert "10" not in result

    def test_empty_input(self):
        """Test with empty input"""
        result = rest_api_to_aoscx_vlans({})
        assert result == {}

    def test_non_dict_input(self):
        """Test with non-dict input"""
        result = rest_api_to_aoscx_vlans(None)
        assert result == {}

    def test_default_values(self):
        """Test default values for missing fields"""
        rest_data = {
            "100": {
                "id": 100,
            }
        }
        result = rest_api_to_aoscx_vlans(rest_data)
        assert result["100"]["name"] == "VLAN100"
        assert result["100"]["description"] == ""
        assert result["100"]["admin"] == "up"
        assert result["100"]["voice"] is False

    def test_multiple_vlans(self):
        """Test conversion of multiple VLANs"""
        rest_data = {
            "1": {"id": 1, "name": "default", "admin": "up"},
            "10": {"id": 10, "name": "DATA", "admin": "up"},
            "20": {"id": 20, "name": "VOICE", "admin": "up", "voice": True},
        }
        result = rest_api_to_aoscx_vlans(rest_data)
        assert len(result) == 3
        assert result["20"]["voice"] is True


class TestRestApiToAoscxEvpnVlans:
    """Tests for rest_api_to_aoscx_evpn_vlans function"""

    def test_basic_evpn_vlan_conversion(self):
        """Test basic EVPN VLAN data conversion"""
        rest_data = {
            "10": {
                "vlan": 10,
                "rd": "auto",
                "export_route_targets": ["auto"],
                "import_route_targets": ["auto"],
            }
        }
        result = rest_api_to_aoscx_evpn_vlans(rest_data)
        assert "10" in result
        assert result["10"]["vlan"] == 10
        assert result["10"]["rd"] == "auto"
        assert "auto" in result["10"]["export_route_targets"]

    def test_empty_input(self):
        """Test with empty input"""
        result = rest_api_to_aoscx_evpn_vlans({})
        assert result == {}

    def test_non_dict_input(self):
        """Test with non-dict input"""
        result = rest_api_to_aoscx_evpn_vlans(None)
        assert result == {}

    def test_redistribute_options(self):
        """Test redistribute options"""
        rest_data = {
            "100": {
                "vlan": 100,
                "redistribute": {"host-route": True},
            }
        }
        result = rest_api_to_aoscx_evpn_vlans(rest_data)
        assert result["100"]["redistribute"]["host-route"] is True


class TestRestApiToAoscxVnis:
    """Tests for rest_api_to_aoscx_vnis function"""

    def test_basic_vni_conversion(self):
        """Test basic VNI data conversion"""
        rest_data = {
            "vxlan,10100": {
                "type": "vxlan",
                "id": 10100,
                "vlan": "/rest/v10.17/system/vlans/100",
                "vrf": None,
            }
        }
        result = rest_api_to_aoscx_vnis(rest_data)
        assert "10100" in result
        assert result["10100"]["id"] == 10100
        assert result["10100"]["type"] == "vxlan"

    def test_l3_vni(self):
        """Test L3 VNI with VRF"""
        rest_data = {
            "vxlan,50000": {
                "type": "vxlan",
                "id": 50000,
                "vlan": None,
                "vrf": "/rest/v10.17/system/vrfs/CUSTOMER_A",
                "routing": True,
            }
        }
        result = rest_api_to_aoscx_vnis(rest_data)
        assert "50000" in result
        assert result["50000"]["routing"] is True

    def test_empty_input(self):
        """Test with empty input"""
        result = rest_api_to_aoscx_vnis({})
        assert result == {}

    def test_non_dict_input(self):
        """Test with non-dict input"""
        result = rest_api_to_aoscx_vnis(None)
        assert result == {}

    def test_skip_entries_without_id(self):
        """Test that entries without id are skipped"""
        rest_data = {
            "vxlan,invalid": {
                "type": "vxlan",
                # No id field
            }
        }
        result = rest_api_to_aoscx_vnis(rest_data)
        assert len(result) == 0

    def test_multiple_vnis(self):
        """Test conversion of multiple VNIs"""
        rest_data = {
            "vxlan,10100": {"type": "vxlan", "id": 10100},
            "vxlan,10200": {"type": "vxlan", "id": 10200},
            "vxlan,50000": {"type": "vxlan", "id": 50000, "routing": True},
        }
        result = rest_api_to_aoscx_vnis(rest_data)
        assert len(result) == 3
