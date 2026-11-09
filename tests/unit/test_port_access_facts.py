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
            "match": [{"seq": 10, "vendor-oui": "000b86"}],
        }
    ],
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
    assert set(facts.keys()) == {"device_profiles", "roles", "lldp_groups"}
    assert set(facts["device_profiles"].keys()) == {"LAB-SW", "Lab-IAP-prof"}
    assert set(facts["roles"].keys()) == {"LAB-SW01", "Lab-IAP-role"}
    assert set(facts["lldp_groups"].keys()) == {"AP-group", "Lab-IAP-group"}


def test_flatten_handles_none():
    assert port_access_facts_from_device_profiles(None) == {
        "device_profiles": {},
        "roles": {},
        "lldp_groups": {},
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
        "roles": [],
        "device_profiles": [],
    }


def test_diff_lldp_sysname_match_via_system_name_key():
    """REST returns 'system_name'; desired uses 'sysname'. Should match."""
    desired = {
        "lldp_groups": [
            {"name": "AP-group",
             "match": [{"seq": 10, "sysname": "lab-sw01"}]}
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
        {"name": "G1", "match": [{"seq": 10, "sys-desc": "ArubaOS"}]}]}
    facts = port_access_facts_from_device_profiles(payload)
    diff = port_access_diff(desired, facts)
    assert diff["lldp_groups"] == []


# ---------------------------------------------------------------------------
# User roles from /system/port_access_roles (no device-profile reference)
# ---------------------------------------------------------------------------

# Trimmed /system/port_access_roles?depth=2 response: one profile role,
# one local user role, one ClearPass-downloaded and one RADIUS role.
ROLES_PAYLOAD = {
    "Lab-IAP-role": {
        "name": "Lab-IAP-role",
        "origin": "local",
        "description": "Aruba IAP",
        "qos_trust_mode": "dscp",
        "vlan_mode": "native-untagged",
        "vlan_tag": "/rest/v10.09/system/vlans/11",
        "vlan_trunks": [
            "/rest/v10.09/system/vlans/11",
            "/rest/v10.09/system/vlans/12",
            "/rest/v10.09/system/vlans/13",
        ],
    },
    "Pod5-Ansatt": {
        "name": "Pod5-Ansatt",
        "origin": "local",
        "description": "Pod5-Ansatt",
        "auth_mode": "client-mode",
        "in_policy": "/rest/v10.09/system/port_access_policies/sys_policy_pap_Pod5-Ansatt",
        "vlan_mode": "access",
        "vlan_tag": {"id": 10, "name": "VLAN10"},
        "vlan_trunks": [],
    },
    "cppm-guest-3001-1": {"name": "cppm-guest-3001-1", "origin": "downloaded"},
    "radius-Ansatt": {"name": "radius-Ansatt", "origin": "radius"},
}

USER_ROLE_DESIRED = {
    "roles": [
        {
            "name": "Pod5-Ansatt",
            "description": "Pod5-Ansatt",
            "associate_policy": "sys_policy_pap_Pod5-Ansatt",
            "auth_mode": "client-mode",
            "vlan_access": 10,
        }
    ],
}


def test_roles_payload_adds_user_roles():
    facts = port_access_facts_from_device_profiles(DEPTH5_PAYLOAD, ROLES_PAYLOAD)
    assert "Pod5-Ansatt" in facts["roles"]
    # Profile roles are still present.
    assert {"LAB-SW01", "Lab-IAP-role"} <= set(facts["roles"])


def test_roles_payload_skips_downloaded_and_radius_roles():
    facts = port_access_facts_from_device_profiles(DEPTH5_PAYLOAD, ROLES_PAYLOAD)
    assert "cppm-guest-3001-1" not in facts["roles"]
    assert "radius-Ansatt" not in facts["roles"]


def test_roles_payload_without_origin_is_kept():
    facts = port_access_facts_from_device_profiles({}, {"r1": {"name": "r1"}})
    assert set(facts["roles"]) == {"r1"}


def test_roles_payload_only():
    facts = port_access_facts_from_device_profiles(None, ROLES_PAYLOAD)
    assert facts["device_profiles"] == {}
    assert set(facts["roles"]) == {"Lab-IAP-role", "Pod5-Ansatt"}


def test_roles_payload_bad_shapes_ignored():
    facts = port_access_facts_from_device_profiles(
        DEPTH5_PAYLOAD, {"bad": "string", "also": None}
    )
    assert set(facts["roles"]) == {"LAB-SW01", "Lab-IAP-role"}
    assert port_access_facts_from_device_profiles(DEPTH5_PAYLOAD, "nope")[
        "roles"
    ] == port_access_facts_from_device_profiles(DEPTH5_PAYLOAD)["roles"]


def test_user_role_steady_state_is_idempotent():
    facts = port_access_facts_from_device_profiles({}, ROLES_PAYLOAD)
    assert port_access_diff(USER_ROLE_DESIRED, facts)["roles"] == []


def test_user_role_vlan_change_detected():
    facts = port_access_facts_from_device_profiles({}, ROLES_PAYLOAD)
    desired = {"roles": [{**USER_ROLE_DESIRED["roles"][0], "vlan_access": 20}]}
    assert [r["name"] for r in port_access_diff(desired, facts)["roles"]] == [
        "Pod5-Ansatt"
    ]


def test_uri_vlan_references_compare_equal():
    """vlan_tag / vlan_trunks as REST URIs compare like plain ints."""
    facts = port_access_facts_from_device_profiles({}, ROLES_PAYLOAD)
    desired = {
        "roles": [
            {
                "name": "Lab-IAP-role",
                "description": "Aruba IAP",
                "trust_mode": "dscp",
                "vlan_trunk_native": 11,
                "vlan_trunk_allowed": "11-13",
            }
        ]
    }
    assert port_access_diff(desired, facts)["roles"] == []


def test_keyed_vlan_trunks_compare_equal():
    """vlan_trunks expanded as a dict keyed by VLAN ID."""
    role = {
        **ROLES_PAYLOAD["Lab-IAP-role"],
        "vlan_tag": 11,
        "vlan_trunks": {"11": {"id": 11}, "12": {"id": 12}, "13": {"id": 13}},
    }
    facts = port_access_facts_from_device_profiles({}, {"Lab-IAP-role": role})
    desired = {
        "roles": [
            {
                "name": "Lab-IAP-role",
                "description": "Aruba IAP",
                "trust_mode": "dscp",
                "vlan_trunk_native": 11,
                "vlan_trunk_allowed": "11-13",
            }
        ]
    }
    assert port_access_diff(desired, facts)["roles"] == []


def test_lab_stack_user_role_real_payload_is_idempotent():
    """Real lab-stack (6200F, 10.16) /system/port_access_roles?depth=2 shape.

    in_policy comes back as a single-entry dict keyed by policy name,
    vlan_tag as a plain int; the role is referenced by no device-profile.
    """
    roles_payload = {
        "AO-Ansatt-role": {
            "auth_mode": "client-mode",
            "description": None,
            "in_policy": {
                "AO-Ansatt-policy": (
                    "/rest/v10.16/system/port_access_policies/AO-Ansatt-policy"
                )
            },
            "name": "AO-Ansatt-role",
            "origin": "local",
            "poe_priority": None,
            "qos_trust_mode": None,
            "vlan_mode": "access",
            "vlan_tag": 102,
            "vlan_trunks": [],
        }
    }
    desired = {
        "roles": [
            {
                "associate_policy": "AO-Ansatt-policy",
                "auth-mode": "client-mode",
                "name": "AO-Ansatt-role",
                "vlan_access": 102,
            }
        ]
    }
    facts = port_access_facts_from_device_profiles({}, roles_payload)
    assert port_access_diff(desired, facts)["roles"] == []
