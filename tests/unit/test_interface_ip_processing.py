"""
Unit tests for get_interface_ip_addresses (interface_ip_processing.py).
"""
from netbox_filters_lib.interface_ip_processing import get_interface_ip_addresses


def _intf(intf_id, name, **overrides):
    """Build a minimal NetBox-shaped interface dict for a test."""
    intf = {
        "id": intf_id,
        "name": name,
        "type": {"value": "1000base-t"},
        "enabled": True,
        "description": "",
        "mgmt_only": False,
        "custom_fields": {},
    }
    intf.update(overrides)
    return intf


def _ip(address, assigned_id, **overrides):
    """Build a minimal NetBox-shaped IP address dict for a test."""
    ip = {
        "address": address,
        "assigned_object": {"id": assigned_id},
        "vrf": None,
        "role": None,
    }
    ip.update(overrides)
    return ip


class TestGetInterfaceIpAddressesEmpty:
    def test_empty_interfaces(self):
        assert get_interface_ip_addresses([], [_ip("10.0.0.1/24", 1)]) == []

    def test_empty_ip_addresses(self):
        assert get_interface_ip_addresses([_intf(1, "1/1/1")], []) == []

    def test_none_inputs(self):
        assert get_interface_ip_addresses(None, None) == []
        assert get_interface_ip_addresses(None, []) == []
        assert get_interface_ip_addresses([], None) == []


class TestGetInterfaceIpAddressesMatching:
    def test_single_match(self):
        interfaces = [_intf(1, "1/1/1")]
        ips = [_ip("10.0.0.1/24", 1)]

        result = get_interface_ip_addresses(interfaces, ips)

        assert len(result) == 1
        entry = result[0]
        assert entry["interface_name"] == "1/1/1"
        assert entry["address"] == "10.0.0.1/24"
        assert entry["vrf"] == "default"
        assert entry["interface_type"] == "1000base-t"
        assert entry["enabled"] is True
        assert entry["ip_role"] is None
        assert entry["anycast_mac"] is None
        assert entry["interface"] is interfaces[0]

    def test_multiple_ips_on_same_interface(self):
        interfaces = [_intf(1, "1/1/1")]
        ips = [
            _ip("10.0.0.1/24", 1),
            _ip("10.0.1.1/24", 1),
            _ip("2001:db8::1/64", 1),
        ]

        result = get_interface_ip_addresses(interfaces, ips)

        assert [r["address"] for r in result] == [
            "10.0.0.1/24",
            "10.0.1.1/24",
            "2001:db8::1/64",
        ]
        assert all(r["interface_name"] == "1/1/1" for r in result)

    def test_multiple_interfaces_matched_by_id(self):
        interfaces = [_intf(1, "1/1/1"), _intf(2, "1/1/2")]
        ips = [_ip("10.0.0.1/24", 2), _ip("10.0.1.1/24", 1)]

        result = get_interface_ip_addresses(interfaces, ips)

        by_addr = {r["address"]: r["interface_name"] for r in result}
        assert by_addr == {"10.0.0.1/24": "1/1/2", "10.0.1.1/24": "1/1/1"}

    def test_unassigned_ip_ignored(self):
        interfaces = [_intf(1, "1/1/1")]
        ips = [_ip("10.0.0.1/24", 999)]

        assert get_interface_ip_addresses(interfaces, ips) == []


class TestGetInterfaceIpAddressesSkipping:
    def test_mgmt_only_interface_skipped(self):
        interfaces = [_intf(1, "mgmt", mgmt_only=True)]
        ips = [_ip("10.0.0.1/24", 1)]

        assert get_interface_ip_addresses(interfaces, ips) == []

    def test_ip_without_address_skipped(self):
        interfaces = [_intf(1, "1/1/1")]
        ips = [_ip("", 1)]

        assert get_interface_ip_addresses(interfaces, ips) == []

    def test_ip_without_assigned_object_skipped(self):
        interfaces = [_intf(1, "1/1/1")]
        ips = [{"address": "10.0.0.1/24", "assigned_object": None}]

        assert get_interface_ip_addresses(interfaces, ips) == []

    def test_ip_with_non_dict_assigned_object_skipped(self):
        interfaces = [_intf(1, "1/1/1")]
        ips = [{"address": "10.0.0.1/24", "assigned_object": 42}]

        assert get_interface_ip_addresses(interfaces, ips) == []

    def test_ip_with_missing_assigned_object_id_skipped(self):
        interfaces = [_intf(1, "1/1/1")]
        ips = [{"address": "10.0.0.1/24", "assigned_object": {"name": "1/1/1"}}]

        assert get_interface_ip_addresses(interfaces, ips) == []

    def test_non_dict_interface_ignored(self):
        interfaces = [None, "bogus", _intf(1, "1/1/1")]
        ips = [_ip("10.0.0.1/24", 1)]

        result = get_interface_ip_addresses(interfaces, ips)

        assert len(result) == 1
        assert result[0]["interface_name"] == "1/1/1"

    def test_interface_without_id_ignored(self):
        interfaces = [_intf(None, "unnamed")]
        ips = [_ip("10.0.0.1/24", None)]

        assert get_interface_ip_addresses(interfaces, ips) == []

    def test_non_dict_ip_ignored(self):
        interfaces = [_intf(1, "1/1/1")]
        ips = [None, "bogus", _ip("10.0.0.1/24", 1)]

        result = get_interface_ip_addresses(interfaces, ips)

        assert len(result) == 1
        assert result[0]["address"] == "10.0.0.1/24"


class TestGetInterfaceIpAddressesVrf:
    def test_named_vrf(self):
        interfaces = [_intf(1, "1/1/1")]
        ips = [_ip("10.0.0.1/24", 1, vrf={"name": "MGMT"})]

        result = get_interface_ip_addresses(interfaces, ips)

        assert result[0]["vrf"] == "MGMT"

    def test_vrf_dict_without_name_falls_back_to_default(self):
        interfaces = [_intf(1, "1/1/1")]
        ips = [_ip("10.0.0.1/24", 1, vrf={"id": 5})]

        result = get_interface_ip_addresses(interfaces, ips)

        assert result[0]["vrf"] == "default"

    def test_non_dict_vrf_falls_back_to_default(self):
        interfaces = [_intf(1, "1/1/1")]
        ips = [_ip("10.0.0.1/24", 1, vrf="MGMT")]

        result = get_interface_ip_addresses(interfaces, ips)

        assert result[0]["vrf"] == "default"


class TestGetInterfaceIpAddressesRoleAndAnycast:
    def test_role_as_dict(self):
        interfaces = [_intf(1, "vlan10")]
        ips = [
            _ip("10.0.0.1/24", 1, role={"value": "anycast", "label": "Anycast"})]

        result = get_interface_ip_addresses(interfaces, ips)

        assert result[0]["ip_role"] == "anycast"

    def test_role_as_string(self):
        interfaces = [_intf(1, "vlan10")]
        ips = [_ip("10.0.0.1/24", 1, role="anycast")]

        result = get_interface_ip_addresses(interfaces, ips)

        assert result[0]["ip_role"] == "anycast"

    def test_anycast_mac_from_custom_fields(self):
        interfaces = [
            _intf(
                1,
                "vlan10",
                custom_fields={"if_anycast_gateway_mac": "02:00:00:00:00:01"},
            )
        ]
        ips = [_ip("10.0.0.1/24", 1, role={"value": "anycast"})]

        result = get_interface_ip_addresses(interfaces, ips)

        assert result[0]["anycast_mac"] == "02:00:00:00:00:01"

    def test_missing_custom_fields(self):
        intf = _intf(1, "1/1/1")
        del intf["custom_fields"]
        interfaces = [intf]
        ips = [_ip("10.0.0.1/24", 1)]

        result = get_interface_ip_addresses(interfaces, ips)

        assert result[0]["anycast_mac"] is None


class TestGetInterfaceIpAddressesInterfaceType:
    def test_type_as_dict(self):
        interfaces = [_intf(1, "vlan10", type={"value": "virtual"})]
        ips = [_ip("10.0.0.1/24", 1)]

        result = get_interface_ip_addresses(interfaces, ips)

        assert result[0]["interface_type"] == "virtual"

    def test_type_as_string_returns_string(self):
        interfaces = [_intf(1, "1/1/1", type="1000base-t")]
        ips = [_ip("10.0.0.1/24", 1)]

        result = get_interface_ip_addresses(interfaces, ips)

        assert result[0]["interface_type"] == "1000base-t"

    def test_missing_type_yields_none(self):
        intf = _intf(1, "1/1/1")
        del intf["type"]
        interfaces = [intf]
        ips = [_ip("10.0.0.1/24", 1)]

        result = get_interface_ip_addresses(interfaces, ips)

        assert result[0]["interface_type"] is None
