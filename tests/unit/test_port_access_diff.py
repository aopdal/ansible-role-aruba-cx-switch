"""Unit tests for the port_access_diff filter."""
import pytest

from netbox_filters_lib.port_access import port_access_diff


# ---------------------------------------------------------------------------
# Fixtures: mirror the example from the user (LAB-SW / LAB-SW01 / AP-group)
# ---------------------------------------------------------------------------

DESIRED_FULL = {
    "lldp_groups": [
        {
            "name": "AP-group",
            "match": [{"seq": 10, "sys_name": "lab-sw01"}],
        }
    ],
    "mac_groups": [],
    "roles": [
        {
            "name": "LAB-SW01",
            "description": "LAB SW01",
            "vlan_trunk_allowed": "101-108,201-208",
        }
    ],
    "device_profiles": [
        {
            "name": "LAB-SW",
            "enable": True,
            "associate_role": "LAB-SW01",
            "associate_lldp_group": "AP-group",
        }
    ],
}

CURRENT_MATCHING = {
    "device_profiles": {
        "LAB-SW": {
            "name": "LAB-SW",
            "enable": True,
            "lldp_groups": {"AP-group": {"name": "AP-group"}},
            "mac_groups": {},
            "role": {"LAB-SW01": {"name": "LAB-SW01"}},
        }
    },
    "roles": {
        "LAB-SW01": {
            "name": "LAB-SW01",
            "description": "LAB SW01",
            "vlan_mode": "native-tagged",
            "vlan_tag": None,
            "vlan_trunks": [
                101, 102, 103, 104, 105, 106, 107, 108,
                201, 202, 203, 204, 205, 206, 207, 208,
            ],
            "poe_priority": None,
            "qos_trust_mode": None,
        }
    },
    "lldp_groups": {
        "AP-group": {
            "name": "AP-group",
            "entries": {
                "10": {"match_type": "sys-name", "sys_name": "lab-sw01"}
            },
        }
    },
    "mac_groups": {},
}


# ---------------------------------------------------------------------------
# Steady-state: nothing to do
# ---------------------------------------------------------------------------


class TestSteadyState:
    def test_all_match_returns_empty_lists(self):
        result = port_access_diff(DESIRED_FULL, CURRENT_MATCHING)
        assert result == {
            "lldp_groups": [],
            "mac_groups": [],
            "roles": [],
            "device_profiles": [],
        }


# ---------------------------------------------------------------------------
# Role diffs
# ---------------------------------------------------------------------------


class TestRoleDiff:
    def test_description_change(self):
        current = {**CURRENT_MATCHING}
        current["roles"] = {
            "LAB-SW01": {**CURRENT_MATCHING["roles"]["LAB-SW01"], "description": "OLD"}
        }
        result = port_access_diff(DESIRED_FULL, current)
        assert [r["name"] for r in result["roles"]] == ["LAB-SW01"]

    def test_trunk_allowed_range_dedupes_to_match(self):
        # Range expansion equivalence: "101-108,201-208" == [101..108, 201..208]
        result = port_access_diff(DESIRED_FULL, CURRENT_MATCHING)
        assert result["roles"] == []

    def test_trunk_allowed_missing_vlan_diff(self):
        current = {
            **CURRENT_MATCHING,
            "roles": {
                "LAB-SW01": {
                    **CURRENT_MATCHING["roles"]["LAB-SW01"],
                    "vlan_trunks": [101, 102],  # missing the rest
                }
            },
        }
        result = port_access_diff(DESIRED_FULL, current)
        assert [r["name"] for r in result["roles"]] == ["LAB-SW01"]

    def test_role_missing_on_device(self):
        current = {**CURRENT_MATCHING, "roles": {"OTHER": {}}}
        result = port_access_diff(DESIRED_FULL, current)
        assert [r["name"] for r in result["roles"]] == ["LAB-SW01"]

    def test_native_vlan_mismatch(self):
        desired = {
            **DESIRED_FULL,
            "roles": [
                {
                    **DESIRED_FULL["roles"][0],
                    "vlan_trunk_native": 100,
                }
            ],
        }
        result = port_access_diff(desired, CURRENT_MATCHING)
        assert [r["name"] for r in result["roles"]] == ["LAB-SW01"]

    def test_native_vlan_match(self):
        desired = {
            **DESIRED_FULL,
            "roles": [
                {
                    **DESIRED_FULL["roles"][0],
                    "vlan_trunk_native": 100,
                }
            ],
        }
        current = {
            **CURRENT_MATCHING,
            "roles": {
                "LAB-SW01": {
                    **CURRENT_MATCHING["roles"]["LAB-SW01"],
                    "vlan_tag": 100,
                }
            },
        }
        result = port_access_diff(desired, current)
        assert result["roles"] == []

    def test_poe_and_trust_mode(self):
        desired = {
            **DESIRED_FULL,
            "roles": [
                {
                    **DESIRED_FULL["roles"][0],
                    "poe_priority": "high",
                    "trust_mode": "dscp",
                }
            ],
        }
        current = {
            **CURRENT_MATCHING,
            "roles": {
                "LAB-SW01": {
                    **CURRENT_MATCHING["roles"]["LAB-SW01"],
                    "poe_priority": "high",
                    "qos_trust_mode": "dscp",
                }
            },
        }
        result = port_access_diff(desired, current)
        assert result["roles"] == []


# ---------------------------------------------------------------------------
# Device-profile diffs
# ---------------------------------------------------------------------------


class TestDeviceProfileDiff:
    def test_associate_role_changed(self):
        current = {
            **CURRENT_MATCHING,
            "device_profiles": {
                "LAB-SW": {
                    **CURRENT_MATCHING["device_profiles"]["LAB-SW"],
                    "role": {"OTHER-ROLE": {}},
                }
            },
        }
        result = port_access_diff(DESIRED_FULL, current)
        assert [p["name"] for p in result["device_profiles"]] == ["LAB-SW"]

    def test_associate_lldp_group_changed(self):
        current = {
            **CURRENT_MATCHING,
            "device_profiles": {
                "LAB-SW": {
                    **CURRENT_MATCHING["device_profiles"]["LAB-SW"],
                    "lldp_groups": {"OTHER-GRP": {}},
                }
            },
        }
        result = port_access_diff(DESIRED_FULL, current)
        assert [p["name"] for p in result["device_profiles"]] == ["LAB-SW"]

    def test_enable_flipped(self):
        current = {
            **CURRENT_MATCHING,
            "device_profiles": {
                "LAB-SW": {
                    **CURRENT_MATCHING["device_profiles"]["LAB-SW"],
                    "enable": False,
                }
            },
        }
        result = port_access_diff(DESIRED_FULL, current)
        assert [p["name"] for p in result["device_profiles"]] == ["LAB-SW"]

    def test_profile_missing(self):
        current = {**CURRENT_MATCHING, "device_profiles": {"OTHER": {}}}
        result = port_access_diff(DESIRED_FULL, current)
        assert [p["name"] for p in result["device_profiles"]] == ["LAB-SW"]


# ---------------------------------------------------------------------------
# LLDP / MAC group diffs
# ---------------------------------------------------------------------------


class TestLldpGroupDiff:
    def test_match_value_changed(self):
        current = {
            **CURRENT_MATCHING,
            "lldp_groups": {
                "AP-group": {
                    "name": "AP-group",
                    "entries": {
                        "10": {"match_type": "sys-name", "sys_name": "different"}
                    },
                }
            },
        }
        result = port_access_diff(DESIRED_FULL, current)
        assert [g["name"] for g in result["lldp_groups"]] == ["AP-group"]

    def test_seq_renumber_ignored(self):
        # Same match content under a different seq -> no diff.
        current = {
            **CURRENT_MATCHING,
            "lldp_groups": {
                "AP-group": {
                    "name": "AP-group",
                    "entries": {
                        "100": {"match_type": "sys-name", "sys_name": "lab-sw01"}
                    },
                }
            },
        }
        result = port_access_diff(DESIRED_FULL, current)
        assert result["lldp_groups"] == []

    def test_extra_entry_on_device(self):
        current = {
            **CURRENT_MATCHING,
            "lldp_groups": {
                "AP-group": {
                    "name": "AP-group",
                    "entries": {
                        "10": {"match_type": "sys-name", "sys_name": "lab-sw01"},
                        "20": {"match_type": "vendor-oui", "vendor_oui": "001122"},
                    },
                }
            },
        }
        result = port_access_diff(DESIRED_FULL, current)
        assert [g["name"] for g in result["lldp_groups"]] == ["AP-group"]


# ---------------------------------------------------------------------------
# Safety / fallback
# ---------------------------------------------------------------------------


class TestSafeFallback:
    def test_no_current_pushes_everything(self):
        result = port_access_diff(DESIRED_FULL, {})
        assert [r["name"] for r in result["roles"]] == ["LAB-SW01"]
        assert [g["name"] for g in result["lldp_groups"]] == ["AP-group"]
        assert [p["name"] for p in result["device_profiles"]] == ["LAB-SW"]

    def test_none_current_pushes_everything(self):
        result = port_access_diff(DESIRED_FULL, None)
        assert [r["name"] for r in result["roles"]] == ["LAB-SW01"]

    def test_none_desired_returns_empty(self):
        result = port_access_diff(None, CURRENT_MATCHING)
        assert result == {
            "lldp_groups": [],
            "mac_groups": [],
            "roles": [],
            "device_profiles": [],
        }

    def test_partial_current_falls_back_per_kind(self):
        # Only roles is populated on the device; lldp/profile have no facts -> push.
        partial = {"roles": CURRENT_MATCHING["roles"]}
        result = port_access_diff(DESIRED_FULL, partial)
        assert result["roles"] == []
        assert [g["name"] for g in result["lldp_groups"]] == ["AP-group"]
        assert [p["name"] for p in result["device_profiles"]] == ["LAB-SW"]

    def test_unnamed_item_is_pushed(self):
        desired = {"roles": [{"description": "no name"}]}
        result = port_access_diff(desired, {"roles": {"X": {}}})
        assert len(result["roles"]) == 1
