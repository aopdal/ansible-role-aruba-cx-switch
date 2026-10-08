"""Unit tests for interface split (breakout) filters."""
from netbox_filters_lib.interface_split import (
    get_interfaces_to_split,
    parse_interface_splits,
    parse_rest_interface_splits,
)

RUNNING_CONFIG = """\
hostname ao-03
interface 1/1/17
    no shutdown
    mtu 9198
interface 1/1/18
    no shutdown
    split 4
    mtu 9198
interface 1/1/18:1
    no shutdown
    lag 101
interface 1/1/19
    split
interface lag 101
    no shutdown
"""


def _phys(name, channels=None, **extra):
    intf = {"name": name, "type": {"value": "100gbase-x-qsfp28"}, **extra}
    if channels is not None or "channels_key" in extra:
        intf["channels"] = channels
    intf.pop("channels_key", None)
    return intf


class TestParseInterfaceSplits:
    def test_parses_split_count(self):
        assert parse_interface_splits(RUNNING_CONFIG) == {"1/1/18": 4, "1/1/19": 0}

    def test_empty_or_invalid_input(self):
        assert parse_interface_splits("") == {}
        assert parse_interface_splits(None) == {}
        assert parse_interface_splits(["split 4"]) == {}

    def test_split_outside_interface_ignored(self):
        assert parse_interface_splits("split 4\nvlan 10\n    split 2\n") == {}


class TestGetInterfacesToSplit:
    def test_already_split_is_idempotent(self):
        interfaces = [_phys("1/1/18", 4)]
        assert get_interfaces_to_split(interfaces, RUNNING_CONFIG) == []

    def test_unsplit_port_needs_split(self):
        interfaces = [_phys("1/1/17", 4)]
        assert get_interfaces_to_split(interfaces, RUNNING_CONFIG) == [
            {"name": "1/1/17", "channels": 4, "current": None, "supported": True}
        ]

    def test_different_count_needs_split(self):
        interfaces = [_phys("1/1/18", 2)]
        assert get_interfaces_to_split(interfaces, RUNNING_CONFIG) == [
            {"name": "1/1/18", "channels": 2, "current": 4, "supported": True}
        ]

    def test_bare_split_left_alone(self):
        interfaces = [_phys("1/1/19", 4)]
        assert get_interfaces_to_split(interfaces, RUNNING_CONFIG) == []

    def test_netbox_46_without_channels_field(self):
        """NetBox < 4.7 has no channels key at all."""
        interfaces = [{"name": "1/1/17", "type": {"value": "100gbase-x-qsfp28"}}]
        assert get_interfaces_to_split(interfaces, RUNNING_CONFIG) == []

    def test_null_and_single_channel_ignored(self):
        interfaces = [
            {"name": "1/1/17", "type": {"value": "x"}, "channels": None},
            {"name": "1/1/20", "type": {"value": "x"}, "channels": 1},
            {"name": "1/1/21", "type": {"value": "x"}, "channels": 0},
            {"name": "1/1/22", "type": {"value": "x"}, "channels": True},
        ]
        assert get_interfaces_to_split(interfaces, RUNNING_CONFIG) == []

    def test_never_unsplits(self):
        """Device split but NetBox has no channels -> no change (no 'no split')."""
        interfaces = [{"name": "1/1/18", "type": {"value": "x"}, "channels": None}]
        assert get_interfaces_to_split(interfaces, RUNNING_CONFIG) == []

    def test_virtual_and_lag_ignored(self):
        interfaces = [
            {"name": "lag1", "type": {"value": "lag"}, "channels": 4},
            {"name": "vlan10", "type": {"value": "virtual"}, "channels": 4},
        ]
        assert get_interfaces_to_split(interfaces, "") == []

    def test_no_running_config_returns_all_desired(self):
        interfaces = [_phys("1/1/18", 4), _phys("1/1/17", "2")]
        assert get_interfaces_to_split(interfaces, None) == [
            {"name": "1/1/17", "channels": 2, "current": None, "supported": True},
            {"name": "1/1/18", "channels": 4, "current": None, "supported": True},
        ]

    def test_invalid_input(self):
        assert get_interfaces_to_split(None, RUNNING_CONFIG) == []
        assert get_interfaces_to_split([None, {"channels": 4}], RUNNING_CONFIG) == []


def _split_entry(admin, children=None, parent=None):
    return {
        "split_admin_status": admin,
        "split_children": children,
        "split_oper_status": admin,
        "split_parent": parent,
    }


def _children(port, n=4):
    return {
        f"{port}:{i}": f"/rest/v10.18/system/interfaces/{port}:{i}"
        for i in range(1, n + 1)
    }


# Shape from a CX 8325 (ao-03), REST v10.18: 1/1/17 splittable but not
# split, 1/1/18 split 4, 1/1/1 not splittable, LAGs return null.
REST_SPLIT_FACTS = {
    "1/1/1": _split_entry("none", {}),
    "1/1/17": _split_entry("active", _children("1/1/17")),
    **{
        f"1/1/17:{i}": _split_entry("inactive", {}, {"1/1/17": "/rest"})
        for i in range(1, 5)
    },
    "1/1/18": _split_entry("inactive", _children("1/1/18")),
    **{
        f"1/1/18:{i}": _split_entry("active", {}, {"1/1/18": "/rest"})
        for i in range(1, 5)
    },
    "lag101": _split_entry(None, None),
    "loopback0": _split_entry("none", {}),
}


class TestParseRestInterfaceSplits:
    def test_parses_device_state(self):
        assert parse_rest_interface_splits(REST_SPLIT_FACTS) == {
            "1/1/17": None,
            "1/1/18": 4,
        }

    def test_split_two_counts_active_children(self):
        facts = {
            "1/1/18": _split_entry("inactive", _children("1/1/18")),
            "1/1/18:1": _split_entry("active", {}),
            "1/1/18:2": _split_entry("active", {}),
            "1/1/18:3": _split_entry("inactive", {}),
            "1/1/18:4": _split_entry("inactive", {}),
        }
        assert parse_rest_interface_splits(facts) == {"1/1/18": 2}

    def test_children_missing_from_response(self):
        facts = {"1/1/18": _split_entry("inactive", _children("1/1/18"))}
        assert parse_rest_interface_splits(facts) == {"1/1/18": 0}

    def test_invalid_input(self):
        assert parse_rest_interface_splits(None) == {}
        assert parse_rest_interface_splits({"1/1/1": None}) == {}


class TestGetInterfacesToSplitRest:
    def test_already_split_is_idempotent(self):
        interfaces = [_phys("1/1/18", 4)]
        assert get_interfaces_to_split(interfaces, None, REST_SPLIT_FACTS) == []

    def test_unsplit_port_needs_split(self):
        interfaces = [_phys("1/1/17", 4)]
        assert get_interfaces_to_split(interfaces, None, REST_SPLIT_FACTS) == [
            {"name": "1/1/17", "channels": 4, "current": None, "supported": True}
        ]

    def test_unsupported_port_flagged(self):
        interfaces = [_phys("1/1/1", 4), _phys("1/1/99", 4)]
        assert get_interfaces_to_split(interfaces, None, REST_SPLIT_FACTS) == [
            {"name": "1/1/1", "channels": 4, "current": None, "supported": False},
            {"name": "1/1/99", "channels": 4, "current": None, "supported": False},
        ]

    def test_rest_facts_take_precedence_over_running_config(self):
        """Running-config says 1/1/17 unsplit too, but REST is used."""
        interfaces = [_phys("1/1/18", 4)]
        assert get_interfaces_to_split(interfaces, "", REST_SPLIT_FACTS) == []

    def test_empty_rest_facts_fall_back_to_running_config(self):
        interfaces = [_phys("1/1/18", 4)]
        assert get_interfaces_to_split(interfaces, RUNNING_CONFIG, {}) == []

    def test_rest_facts_without_split_attributes_fall_back(self):
        """Firmware that ignores unknown attributes returns bare entries."""
        facts = {"1/1/17": {}, "1/1/18": {}}
        interfaces = [_phys("1/1/17", 4), _phys("1/1/18", 4)]
        assert get_interfaces_to_split(interfaces, RUNNING_CONFIG, facts) == [
            {"name": "1/1/17", "channels": 4, "current": None, "supported": True}
        ]
