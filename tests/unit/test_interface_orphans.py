from netbox_filters_lib.interface_orphans import get_virtual_interfaces_to_delete


def test_finds_orphaned_vlan_loopback_and_subinterface():
    desired = [
        {"name": "vlan10"},
        {"name": "loopback0"},
        {"name": "1/1/3.100"},
    ]
    device = {
        "vlan10": {},
        "vlan20": {},  # orphan: renamed away in NetBox
        "loopback0": {},
        "loopback1": {},  # orphan
        "1/1/3.100": {},
        "1/1/3.200": {},  # orphan
        "1/1/1": {},  # physical, never an orphan candidate
        "lag1": {},  # LAG, never an orphan candidate
    }
    out = get_virtual_interfaces_to_delete(desired, device)
    assert out == ["1/1/3.200", "loopback1", "vlan20"]


def test_no_orphans_when_netbox_matches_device():
    desired = [{"name": "vlan10"}, {"name": "loopback0"}]
    device = {"vlan10": {}, "loopback0": {}}
    assert get_virtual_interfaces_to_delete(desired, device) == []


def test_empty_device_facts_returns_empty():
    assert get_virtual_interfaces_to_delete([{"name": "vlan10"}], {}) == []
    assert get_virtual_interfaces_to_delete([{"name": "vlan10"}], None) == []


def test_missing_or_empty_desired_treats_all_virtual_as_orphans():
    device = {"vlan10": {}, "loopback0": {}, "1/1/1": {}}
    assert get_virtual_interfaces_to_delete(None, device) == ["loopback0", "vlan10"]
    assert get_virtual_interfaces_to_delete([], device) == ["loopback0", "vlan10"]


def test_ignores_physical_and_lag_interfaces():
    desired = []
    device = {"1/1/1": {}, "1/1/2": {}, "lag1": {}, "lag100": {}}
    assert get_virtual_interfaces_to_delete(desired, device) == []
