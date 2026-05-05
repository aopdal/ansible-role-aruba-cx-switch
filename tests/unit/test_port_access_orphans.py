import pytest
from netbox_filters_lib.port_access_orphans import port_access_orphans

def test_port_access_orphans_basic():
    desired = {
        "device_profiles": [
            {"name": "A"},
            {"name": "B"},
        ],
        "roles": [
            {"name": "R1"},
        ],
        "lldp_groups": [
            {"name": "L1"},
        ],
        "mac_groups": [
            {"name": "M1"},
        ],
    }
    current = {
        "device_profiles": {"A": {}, "C": {}},
        "roles": {"R1": {}, "R2": {}},
        "lldp_groups": {"L1": {}, "L2": {}},
        "mac_groups": {"M1": {}, "M2": {}},
    }
    out = port_access_orphans(desired, current)
    assert out["device_profiles"] == ["C"]
    assert out["roles"] == ["R2"]
    assert out["lldp_groups"] == ["L2"]
    assert out["mac_groups"] == ["M2"]

def test_port_access_orphans_empty():
    assert port_access_orphans({}, {}) == {
        "device_profiles": [],
        "roles": [],
        "lldp_groups": [],
        "mac_groups": [],
    }
    # No desired, current has objects
    current = {"device_profiles": {"A": {}}, "roles": {"R": {}}, "lldp_groups": {"L": {}}, "mac_groups": {"M": {}}}
    out = port_access_orphans(None, current)
    assert out["device_profiles"] == ["A"]
    assert out["roles"] == ["R"]
    assert out["lldp_groups"] == ["L"]
    assert out["mac_groups"] == ["M"]

def test_port_access_orphans_missing_keys():
    # Missing keys in desired
    desired = {"device_profiles": [{"name": "A"}]}
    current = {"device_profiles": {"A": {}, "B": {}}, "roles": {"R": {}}}
    out = port_access_orphans(desired, current)
    assert out["device_profiles"] == ["B"]
    assert out["roles"] == ["R"]
    assert out["lldp_groups"] == []
    assert out["mac_groups"] == []
