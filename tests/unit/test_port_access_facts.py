"""Unit tests for port_access_facts_from_device_profiles + depth=5 diff."""
from netbox_filters_lib.port_access import (
    port_access_diff,
    port_access_facts_from_device_profiles,
)


# Real depth=5 response from /system/device_profiles?depth=5 (trimmed to
# the fields the diff filter actually consumes).
DEPTH5_PAYLOAD = {
    "LAB-SW": {
        "enable": True,
        "name": "LAB-SW",
        "lldp_groups": {
            "AP-group": {
                "name": "AP-group",
                "entries": {
                    "10": {
                        "action": "match",
                        "sequence_number": 10,
                        "system_name": "lab-sw01",
                        "system_description": None,
                        "vendor_oui": None,
                    }
                },
            }
        },
        "mac_groups": {},
        "role": {
            "LAB-SW01": {
                "name": "LAB-SW01",
                "description": "LAB SW01",
                "poe_priority": None,
                "qos_trust_mode": None,
                "vlan_mode": "native-tagged",
                "vlan_tag": None,
                "vlan_trunks": [101, 102, 103, 104, 105, 106, 107, 108,
                                201, 202, 203, 204, 205, 206, 207, 208],
            }
        },
    },
    "Lab-IAP-prof": {
        "enable": True,
        "name": "Lab-IAP-prof",
        "lldp_groups": {
            "Lab-IAP-group": {
                "name": "Lab-IAP-group",
                "entries": {
                    "10": {
                        "action": "match",
                        "sequence_number": 10,
                        "system_name": None,
                        "system_description": None,
                        "vendor_oui": "000b86",
                    }
                },
            }
        },
        "mac_groups": {},
        "role": {
            "Lab-IAP-role": {
                "name": "Lab-IAP-role",
                "description": "Aruba IAP",
                "poe_priority": None,
                "qos_trust_mode": "dscp",
                "vlan_mode": "native-untagged",
                "vlan_tag": 11,
                "vlan_trunks": [11, 12, 13],
            }
        },
    },
}


# Desired NetBox config_context for the IAP profile (matches the device
# except for poe_priority which is "high" in NetBox but null on device).
DESIRED = {
    "lldp_groups": [
        {
            "name": "Lab-IAP-group",
            "match": [{"seq": 10, "vendor_oui": "000b86"}],
        }
    ],
    "mac_groups": [],
    "roles": [
        {
            "name": "Lab-IAP-role",
            "description": "Aruba IAP",
            "poe_priority": "high",
            "trust_mode": "dscp",
            "vlan_trunk_native": 11,
            "vlan_trunk_allowed": "11-13",
        }
    ],
    "device_profiles": [
        {
            "name": "Lab-IAP-prof",
            "enable": True,
            "associate_role": "Lab-IAP-role",
            "associate_lldp_group": "Lab-IAP-group",
        }
    ],
}


# ---------------------------------------------------------------------------
# port_access_facts_from_device_profiles
# ---------------------------------------------------------------------------


def test_flatten_basic():
    facts = port_access_facts_from_device_profiles(DEPTH5_PAYLOAD)
    assert set(facts.keys()) == {
        "device_profiles",
        "roles",
        "lldp_groups",
        "mac_groups",
    }
    assert set(facts["device_profiles"].keys()) == {"LAB-SW", "Lab-IAP-prof"}
    assert set(facts["roles"].keys()) == {"LAB-SW01", "Lab-IAP-role"}
    assert set(facts["lldp_groups"].keys()) == {"AP-group", "Lab-IAP-group"}
    assert facts["mac_groups"] == {}


def test_flatten_handles_none():
    assert port_access_facts_from_device_profiles(None) == {
        "device_profiles": {},
        "roles": {},
        "lldp_groups": {},
        "mac_groups": {},
    }


def test_flatten_handles_empty():
    assert port_access_facts_from_device_profiles({})["device_profiles"] == {}


def test_flatten_skips_non_dict_profile():
    facts = port_access_facts_from_device_profiles({"bad": "string"})
    assert facts["roles"] == {}
    assert facts["lldp_groups"] == {}


# ---------------------------------------------------------------------------
# End-to-end: real depth=5 payload through diff
# ---------------------------------------------------------------------------


def test_diff_with_depth5_payload_only_flags_poe_priority():
    """Device matches NetBox except poe_priority -> only role differs."""
    facts = port_access_facts_from_device_profiles(DEPTH5_PAYLOAD)
    diff = port_access_diff(DESIRED, facts)
    assert diff["lldp_groups"] == []  # vendor_oui matches
    assert diff["mac_groups"] == []
    assert diff["device_profiles"] == []  # associations match
    assert len(diff["roles"]) == 1
    assert diff["roles"][0]["name"] == "Lab-IAP-role"


def test_diff_with_depth5_steady_state():
    """Aligning poe_priority on the device side -> empty diff."""
    facts = port_access_facts_from_device_profiles(DEPTH5_PAYLOAD)
    facts["roles"]["Lab-IAP-role"]["poe_priority"] = "high"
    diff = port_access_diff(DESIRED, facts)
    assert diff == {
        "lldp_groups": [],
        "mac_groups": [],
        "roles": [],
        "device_profiles": [],
    }


def test_diff_lldp_sys_name_match_via_system_name_key():
    """REST returns 'system_name'; desired uses 'sys_name'. Should match."""
    desired = {
        "lldp_groups": [
            {"name": "AP-group",
             "match": [{"seq": 10, "sys_name": "lab-sw01"}]}
        ],
    }
    facts = port_access_facts_from_device_profiles(DEPTH5_PAYLOAD)
    diff = port_access_diff(desired, facts)
    assert diff["lldp_groups"] == []


def test_diff_lldp_sys_desc_match_via_system_description_key():
    payload = {
        "P1": {"name": "P1", "lldp_groups": {
            "G1": {"name": "G1", "entries": {
                "10": {"system_description": "ArubaOS"}}}}}}
    desired = {"lldp_groups": [
        {"name": "G1", "match": [{"seq": 10, "sys_desc": "ArubaOS"}]}]}
    facts = port_access_facts_from_device_profiles(payload)
    diff = port_access_diff(desired, facts)
    assert diff["lldp_groups"] == []
