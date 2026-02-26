"""
Unit tests for L3 configuration helper functions
"""
import pytest
from netbox_filters_lib.l3_config_helpers import (
    format_interface_name,
    is_ipv4_address,
    is_ipv6_address,
    get_interface_vrf,
    build_l3_config_lines,
)


class TestFormatInterfaceName:
    """Tests for format_interface_name function"""

    def test_physical_interface(self):
        """Test physical interface name formatting"""
        assert format_interface_name("1/1/1", "physical") == "1/1/1"
        assert format_interface_name("1/1/48", "physical") == "1/1/48"

    def test_lag_interface(self):
        """Test LAG interface name formatting (adds space)"""
        assert format_interface_name("lag1", "lag") == "lag 1"
        assert format_interface_name("lag10", "lag") == "lag 10"
        assert format_interface_name("lag256", "lag") == "lag 256"

    def test_vlan_interface(self):
        """Test VLAN interface name formatting"""
        assert format_interface_name("vlan10", "vlan") == "vlan10"
        assert format_interface_name("vlan100", "vlan") == "vlan100"

    def test_loopback_interface(self):
        """Test loopback interface name formatting"""
        assert format_interface_name("loopback0", "loopback") == "loopback0"
        assert format_interface_name("loopback1", "loopback") == "loopback1"

    def test_subinterface(self):
        """Test sub-interface name formatting (passed through unchanged)"""
        assert format_interface_name("1/1/3.2000", "subinterface") == "1/1/3.2000"
        assert format_interface_name("1/1/1.100", "subinterface") == "1/1/1.100"


class TestIsIPv4Address:
    """Tests for is_ipv4_address function"""

    def test_valid_ipv4_addresses(self):
        """Test valid IPv4 addresses"""
        assert is_ipv4_address("192.168.1.1/24") is True
        assert is_ipv4_address("10.0.0.1/8") is True
        assert is_ipv4_address("172.16.0.1/16") is True
        assert is_ipv4_address("1.1.1.1/32") is True

    def test_ipv6_addresses(self):
        """Test IPv6 addresses return False"""
        assert is_ipv4_address("2001:db8::1/64") is False
        assert is_ipv4_address("fe80::1/128") is False
        assert is_ipv4_address("::1/128") is False

    def test_invalid_formats(self):
        """Test invalid address formats - simple colon check"""
        # Note: is_ipv4_address uses simple ":" check, not full validation
        assert is_ipv4_address("192.168.1.1") is True  # No colon = IPv4
        assert is_ipv4_address("not-an-ip") is True  # No colon = treated as IPv4
        assert is_ipv4_address("") is True  # Empty string has no colon

    def test_none_value(self):
        """Test None value - expects TypeError"""
        # Note: Function doesn't handle None - would raise TypeError
        # This is acceptable as it's used in Jinja2 context with valid data
        with pytest.raises(TypeError):
            is_ipv4_address(None)


class TestIsIPv6Address:
    """Tests for is_ipv6_address function"""

    def test_valid_ipv6_addresses(self):
        """Test valid IPv6 addresses"""
        assert is_ipv6_address("2001:db8::1/64") is True
        assert is_ipv6_address("fe80::1/128") is True
        assert is_ipv6_address("::1/128") is True
        assert is_ipv6_address("2001:db8:85a3::8a2e:370:7334/128") is True

    def test_ipv4_addresses(self):
        """Test IPv4 addresses return False"""
        assert is_ipv6_address("192.168.1.1/24") is False
        assert is_ipv6_address("10.0.0.1/8") is False

    def test_invalid_formats(self):
        """Test invalid address formats - simple colon check"""
        # Note: is_ipv6_address uses simple ":" check, not full validation
        assert is_ipv6_address("2001:db8::1") is True  # Has colon = IPv6
        assert is_ipv6_address("not-an-ip") is False  # No colon = not IPv6
        assert is_ipv6_address("") is False  # Empty string has no colon

    def test_none_value(self):
        """Test None value - expects TypeError"""
        # Note: Function doesn't handle None - would raise TypeError
        # This is acceptable as it's used in Jinja2 context with valid data
        with pytest.raises(TypeError):
            is_ipv6_address(None)


class TestGetInterfaceVRF:
    """Tests for get_interface_vrf function"""

    def test_interface_with_vrf(self):
        """Test interface with VRF defined"""
        interface = {"vrf": {"name": "CUSTOMER-A"}}
        assert get_interface_vrf(interface) == "CUSTOMER-A"

    def test_interface_with_nested_vrf(self):
        """Test interface with deeply nested VRF"""
        interface = {"vrf": {"name": "MGMT", "id": 1}}
        assert get_interface_vrf(interface) == "MGMT"

    def test_interface_without_vrf(self):
        """Test interface without VRF (returns default)"""
        interface = {}
        assert get_interface_vrf(interface) == "default"

    def test_interface_with_empty_vrf(self):
        """Test interface with empty VRF dict"""
        interface = {"vrf": {}}
        assert get_interface_vrf(interface) == "default"

    def test_interface_with_none_vrf(self):
        """Test interface with None VRF"""
        interface = {"vrf": None}
        assert get_interface_vrf(interface) == "default"

    def test_none_interface(self):
        """Test None interface"""
        assert get_interface_vrf(None) == "default"


class TestBuildL3ConfigLines:
    """Tests for build_l3_config_lines function"""

    def test_physical_ipv4_default_vrf(self):
        """Test physical interface IPv4 in default VRF"""
        item = {
            "interface": {"mtu": 9000},
            "address": "10.0.0.1/24",
            "ip_role": None,
        }
        lines = build_l3_config_lines(item, "physical", "ipv4", "default", True)

        assert "ip address 10.0.0.1/24" in lines
        assert "ip mtu 9000" in lines
        assert "l3-counters" in lines
        assert not any("vrf attach" in line for line in lines)

    def test_physical_ipv4_custom_vrf(self):
        """Test physical interface IPv4 in custom VRF"""
        item = {
            "interface": {"vrf": {"name": "CUSTOMER-A"}, "mtu": 1500},
            "address": "192.168.1.1/24",
            "ip_role": None,
        }
        lines = build_l3_config_lines(item, "physical", "ipv4", "custom", True)

        assert "vrf attach CUSTOMER-A" in lines
        assert "ip address 192.168.1.1/24" in lines
        assert "ip mtu 1500" in lines
        assert "l3-counters" in lines

    def test_physical_ipv6_default_vrf(self):
        """Test physical interface IPv6 in default VRF"""
        item = {
            "interface": {"mtu": 9000},
            "address": "2001:db8::1/64",
            "ip_role": None,
        }
        lines = build_l3_config_lines(item, "physical", "ipv6", "default", True)

        assert "ipv6 address 2001:db8::1/64" in lines
        assert "ip mtu 9000" in lines  # Note: Uses "ip mtu" even for IPv6
        assert "l3-counters" in lines

    def test_vlan_anycast_gateway(self):
        """Test VLAN interface with anycast gateway"""
        item = {
            "interface": {"mtu": 9000},
            "address": "10.1.1.1/24",
            "ip_role": "anycast",
            "anycast_mac": "02:01:00:00:01:00",
        }
        lines = build_l3_config_lines(item, "vlan", "ipv4", "default", True)

        assert "active-gateway ip mac 02:01:00:00:01:00" in lines
        assert "active-gateway ip 10.1.1.1" in lines  # Note: Prefix stripped for anycast
        assert "ip mtu 9000" in lines
        assert "l3-counters" in lines

    def test_vlan_regular_ip(self):
        """Test VLAN interface with regular IP (not anycast)"""
        item = {
            "interface": {"mtu": 9000},
            "address": "10.1.1.1/24",
            "ip_role": None,
        }
        lines = build_l3_config_lines(item, "vlan", "ipv4", "default", True)

        assert "ip address 10.1.1.1/24" in lines
        assert not any("active-gateway" in line for line in lines)

    def test_interface_without_mtu(self):
        """Test interface without MTU defined"""
        item = {
            "interface": {},
            "address": "10.0.0.1/24",
            "ip_role": None,
        }
        lines = build_l3_config_lines(item, "physical", "ipv4", "default", True)

        assert "ip address 10.0.0.1/24" in lines
        assert not any("mtu" in line for line in lines)
        assert "l3-counters" in lines

    def test_l3_counters_disabled(self):
        """Test with L3 counters disabled"""
        item = {
            "interface": {},
            "address": "10.0.0.1/24",
            "ip_role": None,
        }
        lines = build_l3_config_lines(item, "physical", "ipv4", "default", False)

        assert "ip address 10.0.0.1/24" in lines
        assert "l3-counters" not in lines

    def test_lag_interface(self):
        """Test LAG interface configuration"""
        item = {
            "interface": {"mtu": 9000, "vrf": {"name": "PROD"}},
            "address": "172.16.0.1/24",
            "ip_role": None,
        }
        lines = build_l3_config_lines(item, "lag", "ipv4", "custom", True)

        assert "vrf attach PROD" in lines
        assert "ip address 172.16.0.1/24" in lines
        assert "ip mtu 9000" in lines
        assert "l3-counters" in lines

    def test_anycast_without_mac(self):
        """Test anycast IP without MAC (fallback to regular IP)"""
        item = {
            "interface": {},
            "address": "10.1.1.1/24",
            "ip_role": "anycast",
            "anycast_mac": None,
        }
        lines = build_l3_config_lines(item, "vlan", "ipv4", "default", True)

        assert "ip address 10.1.1.1/24" in lines
        assert not any("active-gateway" in line for line in lines)

    def test_command_order(self):
        """Test that commands are in correct order"""
        item = {
            "interface": {"vrf": {"name": "TEST"}, "mtu": 9000},
            "address": "10.0.0.1/24",
            "ip_role": None,
        }
        lines = build_l3_config_lines(item, "physical", "ipv4", "custom", True)

        # VRF should be first
        assert lines[0] == "vrf attach TEST"
        # IP address should come before MTU
        assert lines.index("ip address 10.0.0.1/24") < lines.index("ip mtu 9000")
        # L3 counters should be last
        assert lines[-1] == "l3-counters"

    def test_subinterface_with_encapsulation(self):
        """Test sub-interface with tagged VLANs generates dot1q encapsulation"""
        item = {
            "interface": {"tagged_vlans": [{"vid": 100}], "mtu": None},
            "interface_name": "1/1/3.100",
            "address": "10.0.0.1/30",
            "ip_role": None,
        }
        lines = build_l3_config_lines(item, "subinterface", "ipv4", "default", True)

        assert "encapsulation dot1q 100" in lines
        assert "ip address 10.0.0.1/30" in lines
        # encapsulation must come before the IP address
        assert lines.index("encapsulation dot1q 100") < lines.index("ip address 10.0.0.1/30")

    def test_subinterface_without_tagged_vlans(self):
        """Test sub-interface without tagged VLANs generates no encapsulation"""
        item = {
            "interface": {"tagged_vlans": [], "mtu": None},
            "interface_name": "1/1/3.100",
            "address": "10.0.0.1/30",
            "ip_role": None,
        }
        lines = build_l3_config_lines(item, "subinterface", "ipv4", "default", True)

        assert not any("encapsulation" in line for line in lines)
        assert "ip address 10.0.0.1/30" in lines

    def test_subinterface_tagged_vlan_without_vid(self):
        """Test sub-interface with tagged VLAN entry missing vid generates no encapsulation"""
        item = {
            "interface": {"tagged_vlans": [{}], "mtu": None},  # No vid key
            "interface_name": "1/1/3.100",
            "address": "10.0.0.1/30",
            "ip_role": None,
        }
        lines = build_l3_config_lines(item, "subinterface", "ipv4", "default", True)

        assert not any("encapsulation" in line for line in lines)
        assert "ip address 10.0.0.1/30" in lines

    def test_subinterface_with_custom_vrf(self):
        """Test sub-interface with encapsulation and custom VRF"""
        item = {
            "interface": {
                "tagged_vlans": [{"vid": 200}],
                "vrf": {"name": "CUST-A"},
                "mtu": None,
            },
            "interface_name": "1/1/1.200",
            "address": "192.168.1.1/30",
            "ip_role": None,
        }
        lines = build_l3_config_lines(item, "subinterface", "ipv4", "custom", False)

        assert "encapsulation dot1q 200" in lines
        assert "vrf attach CUST-A" in lines
        assert "ip address 192.168.1.1/30" in lines
        # encapsulation before vrf
        assert lines.index("encapsulation dot1q 200") < lines.index("vrf attach CUST-A")

    def test_vlan_ipv6_anycast_gateway(self):
        """Test VLAN interface with IPv6 anycast gateway"""
        item = {
            "interface": {"mtu": 9000},
            "interface_name": "vlan100",
            "address": "2001:db8::1/64",
            "ip_role": "anycast",
            "anycast_mac": "02:01:00:00:01:00",
        }
        lines = build_l3_config_lines(item, "vlan", "ipv6", "default", True)

        assert "active-gateway ipv6 mac 02:01:00:00:01:00" in lines
        # Address without prefix length
        assert "active-gateway ipv6 2001:db8::1" in lines
        # Should not have a plain ipv6 address command
        assert not any("ipv6 address" in line for line in lines)
        assert not any("ip address" in line for line in lines)

    def test_vlan_ipv6_anycast_no_prefix(self):
        """Test IPv6 anycast gateway strips prefix from address"""
        item = {
            "interface": {},
            "interface_name": "vlan200",
            "address": "2001:db8:cafe::1/128",
            "ip_role": "anycast",
            "anycast_mac": "02:01:00:00:02:00",
        }
        lines = build_l3_config_lines(item, "vlan", "ipv6", "default", False)

        assert "active-gateway ipv6 mac 02:01:00:00:02:00" in lines
        assert "active-gateway ipv6 2001:db8:cafe::1" in lines
        assert not any("/128" in line for line in lines)
