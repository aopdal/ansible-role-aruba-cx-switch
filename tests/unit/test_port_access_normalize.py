"""Unit tests for port_access_normalize and port_access_missing_ubt_zones."""
from netbox_filters_lib.port_access import port_access_diff
from netbox_filters_lib.port_access_normalize import (
    port_access_missing_ubt_zones,
    port_access_normalize,
)
from netbox_filters_lib.port_access_orphans import port_access_orphans
from netbox_filters_lib.vlan_filters import extract_port_access_vlan_ids

# What NetBox renders for a 6200F after merging three name-keyed contexts:
# the AP profile, the Ansatt profile and the UBT overlay for the Ansatt role.
MERGED_KEYED = {
    "classes": {
        "AO-AP-ip-allow": {"type": "ip", "entries": [{"seq": 10, "match": "any any any"}]},
        "AO-Ansatt-ip-allow": {"type": "ip", "entries": [{"seq": 10, "match": "any any any"}]},
    },
    "policies": {
        "AO-AP-policy": {"entries": [{"seq": 10, "class": "AO-AP-ip-allow"}]},
        "AO-Ansatt-policy": {"entries": [{"seq": 10, "class": "AO-Ansatt-ip-allow"}]},
    },
    "lldp_groups": {
        "AO-AP-group": {"match": [{"seq": 10, "vendor-oui": "000b86"}]},
    },
    "roles": {
        "AO-AP-role": {
            "associate_policy": "AO-AP-policy",
            "trust_mode": "dscp",
            "vlan_trunk_native": 1,
            "vlan_trunk_allowed": "1,101,102,201,202",
        },
        "AO-Ansatt-role": {
            "associate_policy": "AO-Ansatt-policy",
            "auth-mode": "client-mode",
            "vlan_access": 102,
            "gateway_zone": "LAB-UBT-Zone",
            "gateway_role": "Ansatt",
        },
    },
    "device_profiles": {
        "AO-AP-profile": {
            "enable": True,
            "associate_role": "AO-AP-role",
            "associate_lldp_group": "AO-AP-group",
        },
    },
}


class TestPortAccessNormalize:
    def test_none_and_non_dict(self):
        assert port_access_normalize(None) == {}
        assert port_access_normalize([]) == {}
        assert port_access_normalize("x") == {}

    def test_empty(self):
        assert port_access_normalize({}) == {}

    def test_keyed_form_becomes_sorted_list(self):
        out = port_access_normalize(MERGED_KEYED)
        assert [r["name"] for r in out["roles"]] == ["AO-AP-role", "AO-Ansatt-role"]
        assert [c["name"] for c in out["classes"]] == [
            "AO-AP-ip-allow",
            "AO-Ansatt-ip-allow",
        ]
        ansatt = out["roles"][1]
        assert ansatt["gateway_zone"] == "LAB-UBT-Zone"
        assert ansatt["vlan_access"] == 102

    def test_list_form_passes_through(self):
        legacy = {"roles": [{"name": "r1", "vlan_access": 10}]}
        assert port_access_normalize(legacy) == legacy

    def test_mixed_forms(self):
        out = port_access_normalize(
            {"roles": {"r1": {}}, "lldp_groups": [{"name": "g1"}]}
        )
        assert out["roles"] == [{"name": "r1"}]
        assert out["lldp_groups"] == [{"name": "g1"}]

    def test_null_drops_object(self):
        out = port_access_normalize({"roles": {"keep": {"x": 1}, "drop": None}})
        assert out["roles"] == [{"x": 1, "name": "keep"}]

    def test_non_dict_body_skipped(self):
        out = port_access_normalize({"roles": {"bad": "string", "ok": {}}})
        assert out["roles"] == [{"name": "ok"}]

    def test_key_wins_over_name_field(self):
        out = port_access_normalize({"roles": {"real": {"name": "other"}}})
        assert out["roles"] == [{"name": "real"}]

    def test_unknown_keys_untouched(self):
        out = port_access_normalize({"custom": {"a": 1}, "roles": {}})
        assert out == {"custom": {"a": 1}, "roles": []}

    def test_wrong_collection_type_becomes_empty(self):
        assert port_access_normalize({"roles": 5}) == {"roles": []}

    def test_input_not_mutated(self):
        src = {"roles": {"r1": {"vlan_access": 1}}}
        port_access_normalize(src)
        assert src == {"roles": {"r1": {"vlan_access": 1}}}

    def test_idempotent(self):
        once = port_access_normalize(MERGED_KEYED)
        assert port_access_normalize(once) == once


class TestConsumersAcceptKeyedForm:
    def test_diff_without_facts_returns_all(self):
        diff = port_access_diff(MERGED_KEYED, {})
        assert [r["name"] for r in diff["roles"]] == ["AO-AP-role", "AO-Ansatt-role"]
        assert [p["name"] for p in diff["device_profiles"]] == ["AO-AP-profile"]

    def test_orphans_use_keyed_names(self):
        current = {"roles": {"AO-AP-role": {}, "AO-Ansatt-role": {}, "old": {}}}
        assert port_access_orphans(MERGED_KEYED, current)["roles"] == ["old"]

    def test_vlan_ids_from_keyed_roles(self):
        assert extract_port_access_vlan_ids(MERGED_KEYED) == [1, 101, 102, 201, 202]


class TestPortAccessMissingUbtZones:
    UBT = {"zones": [{"name": "LAB-UBT-Zone", "vrf": "default"}]}

    def test_zone_defined(self):
        assert port_access_missing_ubt_zones(MERGED_KEYED, self.UBT) == []

    def test_no_ubt_context(self):
        # e.g. a CX 6000 that still received a gateway_zone
        assert port_access_missing_ubt_zones(MERGED_KEYED, None) == [
            "AO-Ansatt-role -> LAB-UBT-Zone"
        ]

    def test_unknown_zone(self):
        ubt = {"zones": [{"name": "Other-Zone"}]}
        assert port_access_missing_ubt_zones(MERGED_KEYED, ubt) == [
            "AO-Ansatt-role -> LAB-UBT-Zone"
        ]

    def test_list_form_and_no_gateway_zone(self):
        pa = {"roles": [{"name": "r1"}, {"name": "r2", "gateway_zone": ""}]}
        assert port_access_missing_ubt_zones(pa, {}) == []

    def test_none_inputs(self):
        assert port_access_missing_ubt_zones(None, None) == []
