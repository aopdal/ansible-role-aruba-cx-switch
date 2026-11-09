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
            "match": [{"seq": 10, "sysname": "lab-sw01"}],
        }
    ],
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
                "10": {"match_type": "sys-name", "system_name": "lab-sw01"}
            },
        }
    },
}


# ---------------------------------------------------------------------------
# Steady-state: nothing to do
# ---------------------------------------------------------------------------


class TestSteadyState:
    def test_all_match_returns_empty_lists(self):
        result = port_access_diff(DESIRED_FULL, CURRENT_MATCHING)
        assert result == {
            "lldp_groups": [],
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
# LLDP group diffs
# ---------------------------------------------------------------------------


class TestLldpGroupDiff:
    def test_match_value_changed(self):
        current = {
            **CURRENT_MATCHING,
            "lldp_groups": {
                "AP-group": {
                    "name": "AP-group",
                    "entries": {
                        "10": {"match_type": "sys-name", "system_name": "different"}
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
                        "100": {"match_type": "sys-name", "system_name": "lab-sw01"}
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
                        "10": {"match_type": "sys-name", "system_name": "lab-sw01"},
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


# ---------------------------------------------------------------------------
# extra_lines: roles with arbitrary CLI lines are always pushed
# ---------------------------------------------------------------------------


class TestRoleExtraLines:
    def test_extra_lines_forces_push_even_when_structured_fields_match(self):
        desired = {
            **DESIRED_FULL,
            "roles": [
                {
                    **DESIRED_FULL["roles"][0],
                    "extra_lines": ["reauth-period 3600"],
                }
            ],
        }
        result = port_access_diff(desired, CURRENT_MATCHING)
        assert [r["name"] for r in result["roles"]] == ["LAB-SW01"]

    def test_empty_extra_lines_does_not_force_push(self):
        desired = {
            **DESIRED_FULL,
            "roles": [
                {
                    **DESIRED_FULL["roles"][0],
                    "extra_lines": [],
                }
            ],
        }
        result = port_access_diff(desired, CURRENT_MATCHING)
        assert result["roles"] == []

    def test_multiple_extra_lines_all_force_push(self):
        desired = {
            **DESIRED_FULL,
            "roles": [
                {
                    **DESIRED_FULL["roles"][0],
                    "extra_lines": [
                        "reauth-period 3600",
                        "cached-reauth-period 86400",
                    ],
                }
            ],
        }
        result = port_access_diff(desired, CURRENT_MATCHING)
        assert [r["name"] for r in result["roles"]] == ["LAB-SW01"]


# ---------------------------------------------------------------------------
# Role associate_policy (optional, REST: in_policy)
# ---------------------------------------------------------------------------


def _with_policy(desired_policy, current_in_policy):
    desired = {
        **DESIRED_FULL,
        "roles": [{**DESIRED_FULL["roles"][0], "associate_policy": desired_policy}],
    }
    current_role = dict(CURRENT_MATCHING["roles"]["LAB-SW01"])
    if current_in_policy is not None:
        current_role["in_policy"] = current_in_policy
    current = {**CURRENT_MATCHING, "roles": {"LAB-SW01": current_role}}
    return port_access_diff(desired, current)


class TestRoleAssociatePolicy:
    @pytest.mark.parametrize(
        "in_policy",
        [
            "/rest/v10.16/system/port_access_policies/sys_policy_pap_AP-Device-Role",
            {"name": "sys_policy_pap_AP-Device-Role", "cfg_entries": {}},
            {
                "sys_policy_pap_AP-Device-Role": (
                    "/rest/v10.16/system/port_access_policies/"
                    "sys_policy_pap_AP-Device-Role"
                )
            },
        ],
        ids=["uri", "expanded", "keyed"],
    )
    def test_policy_match_in_any_rest_shape(self, in_policy):
        result = _with_policy("sys_policy_pap_AP-Device-Role", in_policy)
        assert result["roles"] == []

    def test_policy_missing_on_device_pushes_role(self):
        result = _with_policy("sys_policy_pap_AP-Device-Role", None)
        assert [r["name"] for r in result["roles"]] == ["LAB-SW01"]

    def test_policy_differs_pushes_role(self):
        result = _with_policy(
            "new-policy", "/rest/v10.16/system/port_access_policies/old-policy"
        )
        assert [r["name"] for r in result["roles"]] == ["LAB-SW01"]

    def test_url_encoded_policy_name(self):
        result = _with_policy(
            "my policy", "/rest/v10.16/system/port_access_policies/my%20policy"
        )
        assert result["roles"] == []

    def test_no_policy_in_netbox_ignores_device_policy(self):
        """Roles without associate_policy stay idempotent (backward compatible)."""
        current_role = {
            **CURRENT_MATCHING["roles"]["LAB-SW01"],
            "in_policy": "/rest/v10.16/system/port_access_policies/legacy",
        }
        current = {**CURRENT_MATCHING, "roles": {"LAB-SW01": current_role}}
        result = port_access_diff(DESIRED_FULL, current)
        assert result["roles"] == []


# ---------------------------------------------------------------------------
# Role auth_mode (optional, REST: auth_mode)
# ---------------------------------------------------------------------------


def _with_auth_mode(desired_fields, current_auth_mode):
    desired = {
        **DESIRED_FULL,
        "roles": [{**DESIRED_FULL["roles"][0], **desired_fields}],
    }
    current_role = dict(CURRENT_MATCHING["roles"]["LAB-SW01"])
    if current_auth_mode is not None:
        current_role["auth_mode"] = current_auth_mode
    current = {**CURRENT_MATCHING, "roles": {"LAB-SW01": current_role}}
    return port_access_diff(desired, current)


class TestRoleAuthMode:
    @pytest.mark.parametrize("key", ["auth_mode", "auth-mode"])
    def test_auth_mode_matches(self, key):
        result = _with_auth_mode({key: "client-mode"}, "client-mode")
        assert result["roles"] == []

    @pytest.mark.parametrize("key", ["auth_mode", "auth-mode"])
    def test_auth_mode_missing_on_device_pushes_role(self, key):
        result = _with_auth_mode({key: "client-mode"}, None)
        assert [r["name"] for r in result["roles"]] == ["LAB-SW01"]

    def test_auth_mode_differs_pushes_role(self):
        result = _with_auth_mode({"auth_mode": "client-mode"}, "device-mode")
        assert [r["name"] for r in result["roles"]] == ["LAB-SW01"]

    def test_underscore_key_wins_over_alias(self):
        result = _with_auth_mode(
            {"auth_mode": "client-mode", "auth-mode": "device-mode"}, "client-mode"
        )
        assert result["roles"] == []

    def test_no_auth_mode_in_netbox_ignores_device_value(self):
        """Roles without auth_mode stay idempotent (backward compatible)."""
        result = _with_auth_mode({}, "device-mode")
        assert result["roles"] == []


# ---------------------------------------------------------------------------
# Role gateway_zone / gateway_role (UBT)
# ---------------------------------------------------------------------------


def _with_gateway(desired_fields, current_fields):
    desired = {
        **DESIRED_FULL,
        "roles": [{**DESIRED_FULL["roles"][0], **desired_fields}],
    }
    current_role = {**CURRENT_MATCHING["roles"]["LAB-SW01"], **current_fields}
    current = {**CURRENT_MATCHING, "roles": {"LAB-SW01": current_role}}
    return port_access_diff(desired, current)


class TestRoleGatewayZone:
    @pytest.mark.parametrize(
        "gateway_zone",
        [
            "UBT-Zone",
            "/rest/v10.16/system/ubt_zones/UBT-Zone,default",
            {"UBT-Zone,default": "/rest/v10.16/system/ubt_zones/UBT-Zone,default"},
            {"name": "UBT-Zone", "vrf": "default"},
        ],
        ids=["name", "uri-with-vrf", "keyed", "expanded"],
    )
    def test_gateway_matches_in_any_rest_shape(self, gateway_zone):
        result = _with_gateway(
            {"gateway_zone": "UBT-Zone", "gateway_role": "Pod5-IoT"},
            {"gateway_zone": gateway_zone, "ubt_gateway_role": "Pod5-IoT"},
        )
        assert result["roles"] == []

    def test_gateway_role_defaults_to_role_name(self):
        result = _with_gateway(
            {"gateway_zone": "UBT-Zone"},
            {"gateway_zone": "UBT-Zone", "ubt_gateway_role": "LAB-SW01"},
        )
        assert result["roles"] == []

    def test_gateway_missing_on_device_pushes_role(self):
        result = _with_gateway(
            {"gateway_zone": "UBT-Zone"},
            {"gateway_zone": None, "ubt_gateway_role": None},
        )
        assert [r["name"] for r in result["roles"]] == ["LAB-SW01"]

    def test_gateway_role_differs_pushes_role(self):
        result = _with_gateway(
            {"gateway_zone": "UBT-Zone", "gateway_role": "new"},
            {"gateway_zone": "UBT-Zone", "ubt_gateway_role": "old"},
        )
        assert [r["name"] for r in result["roles"]] == ["LAB-SW01"]

    def test_gateway_zone_differs_pushes_role(self):
        result = _with_gateway(
            {"gateway_zone": "Zone-B"},
            {"gateway_zone": "UBT-Zone", "ubt_gateway_role": "LAB-SW01"},
        )
        assert [r["name"] for r in result["roles"]] == ["LAB-SW01"]

    def test_no_gateway_in_netbox_ignores_device_value(self):
        result = _with_gateway(
            {}, {"gateway_zone": "UBT-Zone", "ubt_gateway_role": "x"}
        )
        assert result["roles"] == []
