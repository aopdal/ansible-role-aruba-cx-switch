"""
Unit tests for L3 configuration helper functions
"""
import pytest
from netbox_filters_lib.l3_config_helpers import (
    format_interface_name,
    is_ipv4_address,
    is_ipv6_address,
    get_interface_vrf,
    group_interface_ips,
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
        """Test loopback interface name formatting (adds space)"""
        assert format_interface_name("loopback0", "loopback") == "loopback 0"
        assert format_interface_name("loopback1", "loopback") == "loopback 1"

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
        assert is_ipv4_address("fe80::1/64") is False
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
        assert is_ipv6_address("fe80::1/64") is True
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


def _make_item(interface, addresses):
    """Helper: build a grouped interface item as returned by group_interface_ips()."""
    return {
        "interface_name": interface.get("_name", "1/1/1"),
        "interface": interface,
        "addresses": addresses,
    }


class TestGroupInterfaceIps:
    """Tests for group_interface_ips function"""

    def test_empty_list(self):
        assert group_interface_ips([]) == []

    def test_single_ip(self):
        items = [{"interface_name": "1/1/1", "interface": {}, "address": "10.0.0.1/24",
                  "ip_role": None, "anycast_mac": None, "_needs_add": True}]
        result = group_interface_ips(items)
        assert len(result) == 1
        assert result[0]["interface_name"] == "1/1/1"
        assert len(result[0]["addresses"]) == 1
        assert result[0]["addresses"][0]["address"] == "10.0.0.1/24"

    def test_filters_needs_add_false(self):
        items = [
            {"interface_name": "1/1/1", "interface": {}, "address": "10.0.0.1/24",
             "ip_role": None, "anycast_mac": None, "_needs_add": True},
            {"interface_name": "1/1/1", "interface": {}, "address": "10.0.0.2/24",
             "ip_role": None, "anycast_mac": None, "_needs_add": False},
        ]
        result = group_interface_ips(items)
        assert len(result) == 1
        assert len(result[0]["addresses"]) == 1
        assert result[0]["addresses"][0]["address"] == "10.0.0.1/24"

    def test_groups_multiple_ips_on_same_interface(self):
        items = [
            {"interface_name": "vlan10", "interface": {}, "address": "10.0.0.1/24",
             "ip_role": None, "anycast_mac": None, "_needs_add": True},
            {"interface_name": "vlan10", "interface": {}, "address": "2001:db8::1/64",
             "ip_role": None, "anycast_mac": None, "_needs_add": True},
        ]
        result = group_interface_ips(items)
        assert len(result) == 1
        assert len(result[0]["addresses"]) == 2

    def test_sorts_regular_before_anycast(self):
        items = [
            {"interface_name": "vlan10", "interface": {}, "address": "10.0.0.1/24",
             "ip_role": "anycast", "anycast_mac": "00:00:00:01:00:01", "_needs_add": True},
            {"interface_name": "vlan10", "interface": {}, "address": "10.0.0.2/24",
             "ip_role": None, "anycast_mac": None, "_needs_add": True},
        ]
        result = group_interface_ips(items)
        addrs = result[0]["addresses"]
        assert addrs[0]["ip_role"] is None       # regular first
        assert addrs[1]["ip_role"] == "anycast"  # anycast second

    def test_sorts_ipv4_before_ipv6(self):
        items = [
            {"interface_name": "vlan10", "interface": {}, "address": "2001:db8::1/64",
             "ip_role": None, "anycast_mac": None, "_needs_add": True},
            {"interface_name": "vlan10", "interface": {}, "address": "10.0.0.1/24",
             "ip_role": None, "anycast_mac": None, "_needs_add": True},
        ]
        result = group_interface_ips(items)
        addrs = result[0]["addresses"]
        assert ":" not in addrs[0]["address"]  # IPv4 first
        assert ":" in addrs[1]["address"]       # IPv6 second

    def test_omits_interfaces_with_no_needs_add(self):
        items = [{"interface_name": "1/1/1", "interface": {}, "address": "10.0.0.1/24",
                  "ip_role": None, "anycast_mac": None, "_needs_add": False}]
        assert group_interface_ips(items) == []

    def test_includes_ospf_interface_when_no_ips_need_add_no_facts(self):
        """Without ospf_facts, OSPF interfaces are always included (conservative fallback)"""
        items = [{"interface_name": "1/1/1",
                  "interface": {"custom_fields": {"if_ip_ospf_1_area": "0.0.0.0"}},
                  "address": "10.0.0.1/24", "ip_role": None, "anycast_mac": None,
                  "_needs_add": False}]
        result = group_interface_ips(items)
        assert len(result) == 1
        assert result[0]["interface_name"] == "1/1/1"
        assert result[0]["addresses"] == []

    def test_omits_non_ospf_interface_when_no_ips_need_add(self):
        """Interfaces without OSPF and no IPs needing addition must still be omitted"""
        items = [{"interface_name": "1/1/1",
                  "interface": {"custom_fields": {"if_ip_ospf_1_area": None}},
                  "address": "10.0.0.1/24", "ip_role": None, "anycast_mac": None,
                  "_needs_add": False}]
        assert group_interface_ips(items) == []

    def test_skips_ospf_interface_already_in_correct_area(self):
        """With ospf_facts, skip interface already in the correct OSPF area"""
        items = [{"interface_name": "1/1/18",
                  "interface": {"custom_fields": {"if_ip_ospf_1_area": "0.0.0.0"}},
                  "address": "10.0.0.1/24", "ip_role": None, "anycast_mac": None,
                  "_needs_add": False}]
        ospf_facts = {"default": {"1": {"0.0.0.0": {
            "1/1/18": {"ospf_if_type": None},
            "1/1/13": {"ospf_if_type": None},
        }}}}
        result = group_interface_ips(items, ospf_facts=ospf_facts)
        assert result == []  # already in correct area, no IPs to add → skip

    def test_includes_ospf_interface_not_yet_in_area(self):
        """With ospf_facts, include interface not yet registered in the OSPF area"""
        items = [{"interface_name": "1/1/5",
                  "interface": {"custom_fields": {"if_ip_ospf_1_area": "0.0.0.0"}},
                  "address": "10.0.0.1/24", "ip_role": None, "anycast_mac": None,
                  "_needs_add": False}]
        ospf_facts = {"default": {"1": {"0.0.0.0": {
            "1/1/18": {"ospf_if_type": None},
            "1/1/13": {"ospf_if_type": None},
        }}}}
        result = group_interface_ips(items, ospf_facts=ospf_facts)
        assert len(result) == 1  # 1/1/5 not in area yet → include

    def test_includes_ospf_interface_in_wrong_area(self):
        """With ospf_facts, include interface that is in a different area than intended"""
        items = [{"interface_name": "1/1/18",
                  "interface": {"custom_fields": {"if_ip_ospf_1_area": "0.0.0.1"}},
                  "address": "10.0.0.1/24", "ip_role": None, "anycast_mac": None,
                  "_needs_add": False}]
        # Device has 1/1/18 in area 0.0.0.0 but NetBox wants 0.0.0.1
        ospf_facts = {"default": {"1": {"0.0.0.0": {"1/1/18": {"ospf_if_type": None}}}}}
        result = group_interface_ips(items, ospf_facts=ospf_facts)
        assert len(result) == 1  # wrong area → include for reconfiguration

    def test_ospf_facts_with_custom_vrf(self):
        """OSPF interface check uses interface VRF, not default"""
        items = [{"interface_name": "1/1/5",
                  "interface": {"vrf": {"name": "BLUE"},
                                "custom_fields": {"if_ip_ospf_1_area": "0.0.0.0"}},
                  "address": "10.0.0.1/24", "ip_role": None, "anycast_mac": None,
                  "_needs_add": False}]
        ospf_facts = {"BLUE": {"1": {"0.0.0.0": {"1/1/5": {"ospf_if_type": None}}}}}
        result = group_interface_ips(items, ospf_facts=ospf_facts)
        assert result == []  # already in correct area under BLUE VRF

    def test_skips_ospf_interface_when_network_type_matches_p2p(self):
        """Skip interface when both device and NetBox have point-to-point"""
        items = [{"interface_name": "1/1/18",
                  "interface": {"custom_fields": {
                      "if_ip_ospf_1_area": "0.0.0.0",
                      "if_ip_ospf_network": "point-to-point",
                  }},
                  "address": "10.0.0.1/31", "ip_role": None, "anycast_mac": None,
                  "_needs_add": False}]
        ospf_facts = {"default": {"1": {"0.0.0.0": {
            "1/1/18": {"ospf_if_type": "ospf_iftype_pointopoint"},
        }}}}
        result = group_interface_ips(items, ospf_facts=ospf_facts)
        assert result == []  # P2P matches → skip

    def test_includes_ospf_interface_when_network_type_changes_to_p2p(self):
        """Include interface when device is broadcast but NetBox wants point-to-point"""
        items = [{"interface_name": "1/1/18",
                  "interface": {"custom_fields": {
                      "if_ip_ospf_1_area": "0.0.0.0",
                      "if_ip_ospf_network": "point-to-point",
                  }},
                  "address": "10.0.0.1/31", "ip_role": None, "anycast_mac": None,
                  "_needs_add": False}]
        ospf_facts = {"default": {"1": {"0.0.0.0": {
            "1/1/18": {"ospf_if_type": None},  # broadcast (null)
        }}}}
        result = group_interface_ips(items, ospf_facts=ospf_facts)
        assert len(result) == 1  # type mismatch → include for reconfiguration

    def test_includes_ospf_interface_when_network_type_changes_to_broadcast(self):
        """Include interface when device is P2P but NetBox wants broadcast (no network type)"""
        items = [{"interface_name": "1/1/18",
                  "interface": {"custom_fields": {
                      "if_ip_ospf_1_area": "0.0.0.0",
                      "if_ip_ospf_network": None,
                  }},
                  "address": "10.0.0.1/24", "ip_role": None, "anycast_mac": None,
                  "_needs_add": False}]
        ospf_facts = {"default": {"1": {"0.0.0.0": {
            "1/1/18": {"ospf_if_type": "ospf_iftype_pointopoint"},
        }}}}
        result = group_interface_ips(items, ospf_facts=ospf_facts)
        assert len(result) == 1  # type mismatch → include for reconfiguration


class TestBuildL3ConfigLines:
    """Tests for build_l3_config_lines function (interface-level, grouped addresses)"""

    def test_physical_ipv4_default_vrf(self):
        """Physical interface with single IPv4 in default VRF"""
        item = _make_item(
            {"mtu": 9000},
            [{"address": "10.0.0.1/24", "ip_role": None, "anycast_mac": None}],
        )
        lines = build_l3_config_lines(item, "physical", "default", True)

        assert "ip address 10.0.0.1/24" in lines
        assert "ip mtu 9000" in lines
        assert "l3-counters" in lines
        assert not any("vrf attach" in line for line in lines)

    def test_physical_ipv4_custom_vrf(self):
        """Physical interface with IPv4 in custom VRF"""
        item = _make_item(
            {"vrf": {"name": "CUSTOMER-A"}, "mtu": 1500},
            [{"address": "192.168.1.1/24", "ip_role": None, "anycast_mac": None}],
        )
        lines = build_l3_config_lines(item, "physical", "custom", True)

        assert "vrf attach CUSTOMER-A" in lines
        assert "ip address 192.168.1.1/24" in lines
        assert "ip mtu 1500" in lines
        assert "l3-counters" in lines

    def test_physical_ipv6_default_vrf(self):
        """Physical interface with single IPv6 in default VRF"""
        item = _make_item(
            {"mtu": 9000},
            [{"address": "2001:db8::1/64", "ip_role": None, "anycast_mac": None}],
        )
        lines = build_l3_config_lines(item, "physical", "default", True)

        assert "ipv6 address 2001:db8::1/64" in lines
        assert "ip mtu 9000" in lines
        assert "l3-counters" in lines

    def test_vlan_dual_stack_with_active_gateway(self):
        """VLAN interface with IPv4 + IPv6 anycast gateways and regular addresses"""
        item = _make_item(
            {"vrf": {"name": "lab-blue"}, "mtu": 9198},
            [
                {"address": "172.27.4.225/27",      "ip_role": "anycast", "anycast_mac": "00:00:00:01:00:01"},
                {"address": "172.27.4.226/27",      "ip_role": None,      "anycast_mac": None},
                {"address": "2001:db8:1000:17::1",   "ip_role": "anycast", "anycast_mac": "00:00:00:01:00:01"},
                {"address": "2001:db8:1000:17::2/64","ip_role": None,      "anycast_mac": None},
            ],
        )
        lines = build_l3_config_lines(item, "vlan", "custom", True)

        # VRF once
        assert lines.count("vrf attach lab-blue") == 1
        # MTU once
        assert lines.count("ip mtu 9198") == 1
        # L3 counters once
        assert lines.count("l3-counters") == 1
        # IPv4 anycast
        assert "active-gateway ip mac 00:00:00:01:00:01" in lines
        assert "active-gateway ip 172.27.4.225" in lines
        # IPv4 regular
        assert "ip address 172.27.4.226/27" in lines
        # IPv6 anycast
        assert "active-gateway ipv6 mac 00:00:00:01:00:01" in lines
        assert "active-gateway ipv6 2001:db8:1000:17::1" in lines
        # IPv6 regular
        assert "ipv6 address 2001:db8:1000:17::2/64" in lines
        # Order: vrf -> regular IPv4 -> anycast IPv4 -> regular IPv6 -> anycast IPv6 -> mtu -> l3-counters
        assert lines.index("vrf attach lab-blue") < lines.index("ip address 172.27.4.226/27")
        assert lines.index("ip address 172.27.4.226/27") < lines.index("active-gateway ip mac 00:00:00:01:00:01")
        assert lines.index("ipv6 address 2001:db8:1000:17::2/64") < lines.index("active-gateway ipv6 mac 00:00:00:01:00:01")
        assert lines.index("active-gateway ipv6 2001:db8:1000:17::1") < lines.index("ip mtu 9198")
        assert lines.index("ip mtu 9198") < lines.index("l3-counters")

    def test_vlan_link_local_anycast_gateway(self):
        """Link-local IPv6 anycast generates 'ipv6 address link-local' before active-gateway"""
        item = _make_item(
            {"vrf": {"name": "lab-blue"}},
            [
                {"address": "172.27.4.2/27",          "ip_role": None,      "anycast_mac": None},
                {"address": "172.27.4.1/27",          "ip_role": "anycast", "anycast_mac": "00:00:00:01:00:01"},
                {"address": "2001:db8:1000:10::2/64", "ip_role": None,      "anycast_mac": None},
                {"address": "fe80::1/64",             "ip_role": "anycast", "anycast_mac": "00:00:00:01:00:01"},
            ],
        )
        lines = build_l3_config_lines(item, "vlan", "custom", True)

        # Link-local address must be explicitly configured
        assert "ipv6 address link-local fe80::1/64" in lines
        # Active-gateway commands must follow
        assert "active-gateway ipv6 mac 00:00:00:01:00:01" in lines
        assert "active-gateway ipv6 fe80::1" in lines
        # link-local address command must appear before active-gateway commands
        assert lines.index("ipv6 address link-local fe80::1/64") < lines.index("active-gateway ipv6 mac 00:00:00:01:00:01")
        # Global-unicast anycast does NOT get an extra 'ipv6 address link-local' line
        assert "ipv6 address link-local 2001:db8" not in " ".join(lines)

    def test_vlan_global_unicast_anycast_no_link_local_command(self):
        """Global-unicast IPv6 anycast does NOT add 'ipv6 address link-local'"""
        item = _make_item(
            {},
            [
                {"address": "2001:db8:1000:17::1",    "ip_role": "anycast", "anycast_mac": "00:00:00:01:00:01"},
                {"address": "2001:db8:1000:17::2/64", "ip_role": None,      "anycast_mac": None},
            ],
        )
        lines = build_l3_config_lines(item, "vlan", "default", False)

        assert "active-gateway ipv6 mac 00:00:00:01:00:01" in lines
        assert "active-gateway ipv6 2001:db8:1000:17::1" in lines
        assert not any(l.startswith("ipv6 address link-local") for l in lines)

    def test_no_redundant_lines_multiple_addresses(self):
        """vrf attach, ip mtu, and l3-counters appear exactly once with multiple IPs"""
        item = _make_item(
            {"vrf": {"name": "BLUE"}, "mtu": 9000},
            [
                {"address": "10.0.0.1/24", "ip_role": None, "anycast_mac": None},
                {"address": "10.0.0.2/24", "ip_role": None, "anycast_mac": None},
                {"address": "2001:db8::1/64", "ip_role": None, "anycast_mac": None},
            ],
        )
        lines = build_l3_config_lines(item, "vlan", "custom", True)

        assert lines.count("vrf attach BLUE") == 1
        assert lines.count("ip mtu 9000") == 1
        assert lines.count("l3-counters") == 1

    def test_interface_without_mtu(self):
        """Interface without MTU defined emits no ip mtu line"""
        item = _make_item(
            {},
            [{"address": "10.0.0.1/24", "ip_role": None, "anycast_mac": None}],
        )
        lines = build_l3_config_lines(item, "physical", "default", True)

        assert "ip address 10.0.0.1/24" in lines
        assert not any("mtu" in line for line in lines)
        assert "l3-counters" in lines

    def test_l3_counters_disabled(self):
        """l3-counters omitted when disabled"""
        item = _make_item(
            {},
            [{"address": "10.0.0.1/24", "ip_role": None, "anycast_mac": None}],
        )
        lines = build_l3_config_lines(item, "physical", "default", False)

        assert "ip address 10.0.0.1/24" in lines
        assert "l3-counters" not in lines

    def test_anycast_without_mac_falls_back_to_regular(self):
        """Anycast IP without MAC is treated as a regular address"""
        item = _make_item(
            {},
            [{"address": "10.1.1.1/24", "ip_role": "anycast", "anycast_mac": None}],
        )
        lines = build_l3_config_lines(item, "vlan", "default", True)

        assert "ip address 10.1.1.1/24" in lines
        assert not any("active-gateway" in line for line in lines)

    def test_lag_custom_vrf(self):
        """LAG interface with custom VRF"""
        item = _make_item(
            {"mtu": 9000, "vrf": {"name": "PROD"}},
            [{"address": "172.16.0.1/24", "ip_role": None, "anycast_mac": None}],
        )
        lines = build_l3_config_lines(item, "lag", "custom", True)

        assert "vrf attach PROD" in lines
        assert "ip address 172.16.0.1/24" in lines
        assert "ip mtu 9000" in lines
        assert "l3-counters" in lines

    def test_command_order_custom_vrf(self):
        """VRF first, then IPs, then MTU, then l3-counters"""
        item = _make_item(
            {"vrf": {"name": "TEST"}, "mtu": 9000},
            [{"address": "10.0.0.1/24", "ip_role": None, "anycast_mac": None}],
        )
        lines = build_l3_config_lines(item, "physical", "custom", True)

        assert lines[0] == "vrf attach TEST"
        assert lines.index("ip address 10.0.0.1/24") < lines.index("ip mtu 9000")
        assert lines[-1] == "l3-counters"

    def test_subinterface_with_encapsulation(self):
        """Sub-interface generates dot1q encapsulation before other lines"""
        item = _make_item(
            {"tagged_vlans": [{"vid": 100}], "mtu": None, "_name": "1/1/3.100"},
            [{"address": "10.0.0.1/30", "ip_role": None, "anycast_mac": None}],
        )
        lines = build_l3_config_lines(item, "subinterface", "default", True)

        assert "encapsulation dot1q 100" in lines
        assert "ip address 10.0.0.1/30" in lines
        assert lines.index("encapsulation dot1q 100") < lines.index("ip address 10.0.0.1/30")

    def test_subinterface_without_tagged_vlans(self):
        """Sub-interface without tagged VLANs has no encapsulation"""
        item = _make_item(
            {"tagged_vlans": [], "mtu": None},
            [{"address": "10.0.0.1/30", "ip_role": None, "anycast_mac": None}],
        )
        lines = build_l3_config_lines(item, "subinterface", "default", True)

        assert not any("encapsulation" in line for line in lines)
        assert "ip address 10.0.0.1/30" in lines

    def test_subinterface_with_custom_vrf(self):
        """Sub-interface: encapsulation comes before vrf attach"""
        item = _make_item(
            {"tagged_vlans": [{"vid": 200}], "vrf": {"name": "CUST-A"}, "mtu": None},
            [{"address": "192.168.1.1/30", "ip_role": None, "anycast_mac": None}],
        )
        lines = build_l3_config_lines(item, "subinterface", "custom", False)

        assert "encapsulation dot1q 200" in lines
        assert "vrf attach CUST-A" in lines
        assert lines.index("encapsulation dot1q 200") < lines.index("vrf attach CUST-A")

    def test_ospf_interface_config(self):
        """OSPF area and network type emitted after l3-counters"""
        item = _make_item(
            {"custom_fields": {"if_ip_ospf_1_area": "0.0.0.0", "if_ip_ospf_network": "point-to-point"}, "mtu": 9198},
            [{"address": "172.27.250.2/31", "ip_role": None, "anycast_mac": None}],
        )
        lines = build_l3_config_lines(item, "physical", "default", True)

        assert "ip ospf 1 area 0.0.0.0" in lines
        assert "ip ospf network point-to-point" in lines
        assert lines.index("l3-counters") < lines.index("ip ospf 1 area 0.0.0.0")

    def test_ospf_custom_process_id(self):
        """OSPF process ID is configurable"""
        item = _make_item(
            {"custom_fields": {"if_ip_ospf_1_area": "0.0.0.1", "if_ip_ospf_network": None}},
            [{"address": "10.0.0.1/30", "ip_role": None, "anycast_mac": None}],
        )
        lines = build_l3_config_lines(item, "physical", "default", True, ospf_process_id=2)

        assert "ip ospf 2 area 0.0.0.1" in lines

    def test_no_ospf_without_custom_fields(self):
        """No OSPF lines emitted when custom_fields is absent"""
        item = _make_item(
            {"mtu": 1500},
            [{"address": "10.0.0.1/24", "ip_role": None, "anycast_mac": None}],
        )
        lines = build_l3_config_lines(item, "physical", "default", True)

        assert not any("ospf" in line for line in lines)

    def test_loopback_skips_l3_counters(self):
        """Loopback interfaces never emit l3-counters even when enabled"""
        item = _make_item(
            {},
            [{"address": "10.0.0.1/32", "ip_role": None, "anycast_mac": None}],
        )
        lines = build_l3_config_lines(item, "loopback", "default", True)

        assert "ip address 10.0.0.1/32" in lines
        assert "l3-counters" not in lines

    def test_loopback_skips_ospf_network_type(self):
        """Loopback interfaces never emit ip ospf network even when set in NetBox"""
        item = _make_item(
            {"custom_fields": {"if_ip_ospf_1_area": "0.0.0.0", "if_ip_ospf_network": "loopback"}},
            [{"address": "172.27.252.0/32", "ip_role": None, "anycast_mac": None}],
        )
        lines = build_l3_config_lines(item, "loopback", "default", True)

        assert "ip ospf 1 area 0.0.0.0" in lines
        assert not any("ospf network" in line for line in lines)

    def test_vlan_ipv6_anycast_strips_prefix(self):
        """IPv6 anycast gateway command strips prefix length"""
        item = _make_item(
            {},
            [{"address": "2001:db8:cafe::1/128", "ip_role": "anycast", "anycast_mac": "02:01:00:00:02:00"}],
        )
        lines = build_l3_config_lines(item, "vlan", "default", False)

        assert "active-gateway ipv6 mac 02:01:00:00:02:00" in lines
        assert "active-gateway ipv6 2001:db8:cafe::1" in lines
        assert not any("/128" in line for line in lines)
