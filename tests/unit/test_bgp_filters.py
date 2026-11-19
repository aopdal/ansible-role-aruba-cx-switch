"""
Unit tests for BGP filter functions
"""
import pytest
from netbox_filters_lib.bgp_filters import (
    get_bgp_session_vrf_info,
    collect_ebgp_vrf_policy_config,
    get_bgp_redistribute_config,
    get_stale_bgp_redistribute,
    get_bgp_neighbor_options_config,
    get_stale_bgp_neighbor_options,
    get_bgp_bfd_enabled,
    get_stale_bgp_bfd,
    build_bgp_desired_neighbors,
    get_bgp_neighbor_changes,
    get_bgp_redistribute_changes,
    get_bgp_policy_changes,
    get_missing_bgp_neighbor_options,
    netbox_bgp_graphql_to_rest,
)
from rest_api_transforms import rest_api_to_aoscx_bgp


def _session(name, local_address):
    return {
        "name": name,
        "local_address": {"address": local_address},
        "remote_address": {"address": "10.0.0.0/31"},
        "remote_as": {"asn": 65001},
    }


def _interface(name, ip_addresses, vrf_name=None):
    intf = {"name": name, "ip_addresses": ip_addresses}
    if vrf_name:
        intf["vrf"] = {"name": vrf_name}
    return intf


class TestGetBgpSessionVrfInfo:
    """Tests for get_bgp_session_vrf_info function"""

    def test_empty_sessions_returns_empty(self):
        """Empty session list returns empty list"""
        result = get_bgp_session_vrf_info([], [])
        assert result == []

    def test_none_sessions_returns_empty(self):
        """None sessions returns empty list"""
        result = get_bgp_session_vrf_info(None, [])
        assert result == []

    def test_none_interfaces_defaults_to_default_vrf(self):
        """No interfaces → all sessions get _vrf='default'"""
        sessions = [_session("s1", "10.0.0.1/31")]
        result = get_bgp_session_vrf_info(sessions, None)
        assert len(result) == 1
        assert result[0]["_vrf"] == "default"
        assert result[0]["_af"] == "ipv4"

    def test_ipv4_session_matched_to_custom_vrf(self):
        """IPv4 session whose local address is on a custom-VRF interface"""
        sessions = [_session("s1", "10.0.0.1/31")]
        interfaces = [_interface("1/1/1", [{"address": "10.0.0.1/31"}], "customer-a")]
        result = get_bgp_session_vrf_info(sessions, interfaces)
        assert len(result) == 1
        assert result[0]["_vrf"] == "customer-a"
        assert result[0]["_af"] == "ipv4"

    def test_ipv4_session_interface_no_vrf_defaults_to_default(self):
        """Interface without VRF → session gets _vrf='default'"""
        sessions = [_session("s1", "10.0.0.1/31")]
        interfaces = [_interface("1/1/1", [{"address": "10.0.0.1/31"}])]
        result = get_bgp_session_vrf_info(sessions, interfaces)
        assert result[0]["_vrf"] == "default"

    def test_ipv6_session_detected_as_ipv6_af(self):
        """IPv6 local address produces _af='ipv6'"""
        sessions = [_session("s1", "2001:db8::1/64")]
        interfaces = [_interface("vlan10", [{"address": "2001:db8::1/64"}])]
        result = get_bgp_session_vrf_info(sessions, interfaces)
        assert result[0]["_af"] == "ipv6"

    def test_ipv6_session_custom_vrf(self):
        """IPv6 session on custom VRF interface"""
        sessions = [_session("s1", "2001:db8::1/64")]
        interfaces = [
            _interface("vlan10", [{"address": "2001:db8::1/64"}], "tenant-a")
        ]
        result = get_bgp_session_vrf_info(sessions, interfaces)
        assert result[0]["_vrf"] == "tenant-a"
        assert result[0]["_af"] == "ipv6"

    def test_session_local_address_not_found_defaults_to_default(self):
        """Session local address not in any interface → _vrf='default'"""
        sessions = [_session("s1", "10.99.99.1/31")]
        interfaces = [_interface("1/1/1", [{"address": "10.0.0.1/31"}])]
        result = get_bgp_session_vrf_info(sessions, interfaces)
        assert result[0]["_vrf"] == "default"

    def test_builtin_vrf_mgmt_normalised_to_default(self):
        """Interface in 'mgmt' VRF → session gets _vrf='default'"""
        sessions = [_session("s1", "10.0.0.1/31")]
        interfaces = [_interface("1/1/1", [{"address": "10.0.0.1/31"}], "mgmt")]
        result = get_bgp_session_vrf_info(sessions, interfaces)
        assert result[0]["_vrf"] == "default"

    def test_builtin_vrf_MGMT_normalised_to_default(self):
        """Interface in 'MGMT' VRF → session gets _vrf='default'"""
        sessions = [_session("s1", "10.0.0.1/31")]
        interfaces = [_interface("1/1/1", [{"address": "10.0.0.1/31"}], "MGMT")]
        result = get_bgp_session_vrf_info(sessions, interfaces)
        assert result[0]["_vrf"] == "default"

    def test_builtin_vrf_Global_normalised_to_default(self):
        """Interface in 'Global' VRF → session gets _vrf='default'"""
        sessions = [_session("s1", "10.0.0.1/31")]
        interfaces = [_interface("1/1/1", [{"address": "10.0.0.1/31"}], "Global")]
        result = get_bgp_session_vrf_info(sessions, interfaces)
        assert result[0]["_vrf"] == "default"

    def test_builtin_vrf_Default_normalised_to_default(self):
        """Interface in 'Default' VRF → session gets _vrf='default'"""
        sessions = [_session("s1", "10.0.0.1/31")]
        interfaces = [_interface("1/1/1", [{"address": "10.0.0.1/31"}], "Default")]
        result = get_bgp_session_vrf_info(sessions, interfaces)
        assert result[0]["_vrf"] == "default"

    def test_mgmt_only_interface_is_skipped(self):
        """mgmt_only interfaces are excluded from the IP→VRF map"""
        sessions = [_session("s1", "192.168.1.1/24")]
        interfaces = [
            {
                "name": "mgmt",
                "mgmt_only": True,
                "ip_addresses": [{"address": "192.168.1.1/24"}],
            }
        ]
        result = get_bgp_session_vrf_info(sessions, interfaces)
        # Address was on mgmt_only interface — falls back to default
        assert result[0]["_vrf"] == "default"

    def test_multiple_sessions_mixed_vrfs(self):
        """Multiple sessions matched to different VRFs"""
        sessions = [
            _session("global", "10.0.0.1/31"),
            _session("tenant-a", "192.168.1.1/30"),
            _session("unmatched", "172.16.0.1/30"),
        ]
        interfaces = [
            _interface("1/1/1", [{"address": "10.0.0.1/31"}]),
            _interface("1/1/2", [{"address": "192.168.1.1/30"}], "tenant-a"),
        ]
        result = get_bgp_session_vrf_info(sessions, interfaces)
        assert len(result) == 3
        by_name = {s["name"]: s for s in result}
        assert by_name["global"]["_vrf"] == "default"
        assert by_name["tenant-a"]["_vrf"] == "tenant-a"
        assert by_name["unmatched"]["_vrf"] == "default"

    def test_original_session_fields_preserved(self):
        """Enrichment does not mutate original session dict fields"""
        session = _session("s1", "10.0.0.1/31")
        original_keys = set(session.keys())
        interfaces = [_interface("1/1/1", [{"address": "10.0.0.1/31"}], "vrf-a")]
        result = get_bgp_session_vrf_info([session], interfaces)
        # Original dict untouched
        assert set(session.keys()) == original_keys
        # Enriched copy has extra fields
        assert "_vrf" in result[0]
        assert "_af" in result[0]
        assert result[0]["name"] == "s1"

    def test_interface_with_multiple_ips(self):
        """Interface with multiple IPs — all are indexed in the VRF map"""
        sessions = [
            _session("s1", "10.0.0.1/31"),
            _session("s2", "10.0.0.3/31"),
        ]
        interfaces = [
            _interface(
                "1/1/1",
                [{"address": "10.0.0.1/31"}, {"address": "10.0.0.3/31"}],
                "shared-vrf",
            )
        ]
        result = get_bgp_session_vrf_info(sessions, interfaces)
        assert result[0]["_vrf"] == "shared-vrf"
        assert result[1]["_vrf"] == "shared-vrf"

    def test_non_dict_session_is_skipped(self):
        """Non-dict entries in sessions list are silently skipped"""
        sessions = [None, "bad-entry", _session("s1", "10.0.0.1/31")]
        interfaces = [_interface("1/1/1", [{"address": "10.0.0.1/31"}])]
        result = get_bgp_session_vrf_info(sessions, interfaces)
        assert len(result) == 1

    def test_non_dict_interface_is_skipped(self):
        """Non-dict entries in interfaces list are silently skipped"""
        sessions = [_session("s1", "10.0.0.1/31")]
        interfaces = [None, "bad", _interface("1/1/1", [{"address": "10.0.0.1/31"}])]
        result = get_bgp_session_vrf_info(sessions, interfaces)
        assert result[0]["_vrf"] == "default"

    def test_session_without_local_address_key(self):
        """Session missing local_address → defaults to _vrf='default', _af='ipv4'"""
        sessions = [{"name": "s1", "remote_as": {"asn": 65001}}]
        result = get_bgp_session_vrf_info(sessions, [])
        assert result[0]["_vrf"] == "default"
        assert result[0]["_af"] == "ipv4"

    def test_interface_ip_as_plain_string(self):
        """ip_addresses entry as plain string (non-dict) is handled gracefully"""
        sessions = [_session("s1", "10.0.0.1/31")]
        interfaces = [
            {"name": "1/1/1", "ip_addresses": ["10.0.0.1/31"]}
        ]
        result = get_bgp_session_vrf_info(sessions, interfaces)
        # String IPs are indexed as-is; session matches
        assert result[0]["_vrf"] == "default"


# ---------------------------------------------------------------------------
# Helpers for collect_ebgp_vrf_policy_config
# ---------------------------------------------------------------------------

def _ebgp_session(name, import_policies=None, export_policies=None):
    """Build a minimal eBGP VRF session with optional routing policies."""
    return {
        "name": name,
        "local_as": {"asn": 65015},
        "remote_as": {"asn": 65020},
        "local_address": {"address": "172.27.4.1/30"},
        "remote_address": {"address": "172.27.250.32/30"},
        "_vrf": "lab-blue",
        "_af": "ipv4",
        "import_policies": import_policies or [],
        "export_policies": export_policies or [],
    }


def _policy_rule(
    policy_id,
    policy_name,
    index,
    action="permit",
    match_pfx_id=None,
    match_pfx_name=None,
    set_local_pref=None,
    set_prepend_asn=None,
):
    """Build a routing policy rule matching the real netbox-bgp API structure."""
    set_actions = {}
    if set_local_pref is not None:
        set_actions["local-preference"] = set_local_pref
    if set_prepend_asn is not None:
        set_actions["as-path prepend"] = [set_prepend_asn]

    rule = {
        "routing_policy": {"id": policy_id, "name": policy_name},
        "index": index,
        "action": action,  # plain string, not a dict
        "match_ip_address": (
            [{"id": match_pfx_id, "name": match_pfx_name}]
            if match_pfx_id is not None
            else []
        ),
        "set_actions": set_actions,
    }
    return rule


def _prefix_list_rule(pl_id, pl_name, index, action, network):
    """Build a prefix list rule matching the real netbox-bgp API structure."""
    return {
        "prefix_list": {"id": pl_id, "name": pl_name},
        "index": index,
        "action": action,  # plain string
        "prefix": {"id": pl_id * 100, "prefix": network, "display": network},
    }


class TestCollectEbgpVrfPolicyConfig:
    """Tests for collect_ebgp_vrf_policy_config function"""

    def test_empty_sessions_returns_empty(self):
        result = collect_ebgp_vrf_policy_config([], [], [])
        assert result == {"prefix_lists": [], "route_map_rules": []}

    def test_none_inputs_returns_empty(self):
        result = collect_ebgp_vrf_policy_config(None, None, None)
        assert result == {"prefix_lists": [], "route_map_rules": []}

    def test_session_without_policies_returns_empty(self):
        session = _ebgp_session("s1")
        result = collect_ebgp_vrf_policy_config([session], [], [])
        assert result == {"prefix_lists": [], "route_map_rules": []}

    def test_export_policy_with_prefix_list(self):
        """Route-map rule with match prefix-list and set as-path prepend."""
        session = _ebgp_session(
            "s1",
            export_policies=[{"id": 1, "name": "LAB-BLUE-IPV4-OUT-01"}],
        )
        policy_rules = [
            _policy_rule(
                policy_id=1,
                policy_name="LAB-BLUE-IPV4-OUT-01",
                index=10,
                action="permit",
                match_pfx_id=10,
                match_pfx_name="LAB-BLUE-IPV4",
                set_prepend_asn=65015,
            )
        ]
        prefix_list_rules = [
            _prefix_list_rule(10, "LAB-BLUE-IPV4", 10, "permit", "172.27.4.0/24")
        ]

        result = collect_ebgp_vrf_policy_config([session], policy_rules, prefix_list_rules)

        assert len(result["route_map_rules"]) == 1
        rm = result["route_map_rules"][0]
        assert rm["name"] == "LAB-BLUE-IPV4-OUT-01"
        assert rm["index"] == 10
        assert rm["action"] == "permit"
        assert "route-map LAB-BLUE-IPV4-OUT-01 permit seq 10" in rm["commands"]
        assert "match ip address prefix-list LAB-BLUE-IPV4" in rm["commands"]
        assert "set as-path prepend 65015" in rm["commands"]

        assert len(result["prefix_lists"]) == 1
        pl = result["prefix_lists"][0]
        assert pl["name"] == "LAB-BLUE-IPV4"
        assert len(pl["rules"]) == 1
        assert pl["rules"][0] == {"index": 10, "action": "permit", "prefix": "172.27.4.0/24"}

    def test_import_policy_with_local_preference(self):
        """Route-map rule with match prefix-list and set local-preference."""
        session = _ebgp_session(
            "s1",
            import_policies=[{"id": 2, "name": "LAB-GW-IPV4-IN-01"}],
        )
        policy_rules = [
            _policy_rule(
                policy_id=2,
                policy_name="LAB-GW-IPV4-IN-01",
                index=10,
                action="permit",
                match_pfx_id=20,
                match_pfx_name="LAB-GW-IPV4",
                set_local_pref=300,
            )
        ]
        prefix_list_rules = [
            _prefix_list_rule(20, "LAB-GW-IPV4", 10, "permit", "0.0.0.0/0")
        ]

        result = collect_ebgp_vrf_policy_config([session], policy_rules, prefix_list_rules)

        rm = result["route_map_rules"][0]
        assert rm["name"] == "LAB-GW-IPV4-IN-01"
        assert "set local-preference 300" in rm["commands"]
        assert "match ip address prefix-list LAB-GW-IPV4" in rm["commands"]

        pl = result["prefix_lists"][0]
        assert pl["name"] == "LAB-GW-IPV4"
        assert pl["rules"][0]["prefix"] == "0.0.0.0/0"

    def test_multiple_sessions_deduplicate_policies(self):
        """Two sessions referencing the same export policy produce one route-map rule."""
        sessions = [
            _ebgp_session("s1", export_policies=[{"id": 1, "name": "OUT-01"}]),
            _ebgp_session("s2", export_policies=[{"id": 1, "name": "OUT-01"}]),
        ]
        policy_rules = [
            _policy_rule(1, "OUT-01", 10, match_pfx_id=10, match_pfx_name="PFX-A")
        ]
        prefix_list_rules = [
            _prefix_list_rule(10, "PFX-A", 10, "permit", "10.0.0.0/8")
        ]

        result = collect_ebgp_vrf_policy_config(sessions, policy_rules, prefix_list_rules)

        assert len(result["route_map_rules"]) == 1
        assert len(result["prefix_lists"]) == 1

    def test_route_map_without_match_or_set(self):
        """A rule with no match/set produces only the route-map entry line."""
        session = _ebgp_session("s1", export_policies=[{"id": 1, "name": "PLAIN"}])
        policy_rules = [_policy_rule(1, "PLAIN", 10)]
        result = collect_ebgp_vrf_policy_config([session], policy_rules, [])

        rm = result["route_map_rules"][0]
        assert rm["commands"] == ["route-map PLAIN permit seq 10"]
        assert result["prefix_lists"] == []

    def test_prefix_list_rules_sorted_by_index(self):
        """Prefix list rules are returned sorted by sequence number."""
        session = _ebgp_session("s1", export_policies=[{"id": 1, "name": "P"}])
        policy_rules = [
            _policy_rule(1, "P", 10, match_pfx_id=5, match_pfx_name="PFX")
        ]
        prefix_list_rules = [
            _prefix_list_rule(5, "PFX", 30, "permit", "10.3.0.0/24"),
            _prefix_list_rule(5, "PFX", 10, "permit", "10.1.0.0/24"),
            _prefix_list_rule(5, "PFX", 20, "permit", "10.2.0.0/24"),
        ]

        result = collect_ebgp_vrf_policy_config([session], policy_rules, prefix_list_rules)

        indexes = [r["index"] for r in result["prefix_lists"][0]["rules"]]
        assert indexes == [10, 20, 30]

    def test_action_as_plain_string(self):
        """action field as plain string (the real API format) is handled correctly."""
        session = _ebgp_session("s1", export_policies=[{"id": 1, "name": "P"}])
        policy_rules = [
            {
                "routing_policy": {"id": 1, "name": "P"},
                "index": 10,
                "action": "deny",
                "match_ip_address": [],
                "set_actions": {},
            }
        ]
        result = collect_ebgp_vrf_policy_config([session], policy_rules, [])
        assert result["route_map_rules"][0]["action"] == "deny"

    def test_prefix_as_ipam_object(self):
        """prefix field as IPAM FK object (the real API format) is handled correctly."""
        session = _ebgp_session("s1", export_policies=[{"id": 1, "name": "P"}])
        policy_rules = [
            _policy_rule(1, "P", 10, match_pfx_id=5, match_pfx_name="PFX")
        ]
        prefix_list_rules = [
            {
                "prefix_list": {"id": 5, "name": "PFX"},
                "index": 10,
                "action": "permit",
                "prefix": {"id": 999, "prefix": "192.168.0.0/16", "display": "192.168.0.0/16"},
            }
        ]
        result = collect_ebgp_vrf_policy_config([session], policy_rules, prefix_list_rules)
        assert result["prefix_lists"][0]["rules"][0]["prefix"] == "192.168.0.0/16"

    def test_unreferenced_policy_rules_are_ignored(self):
        """Rules for policies not referenced by any session are not included."""
        session = _ebgp_session("s1", export_policies=[{"id": 1, "name": "MINE"}])
        policy_rules = [
            _policy_rule(1, "MINE", 10),
            _policy_rule(99, "OTHER", 10),  # not referenced
        ]
        result = collect_ebgp_vrf_policy_config([session], policy_rules, [])
        names = [rm["name"] for rm in result["route_map_rules"]]
        assert "MINE" in names
        assert "OTHER" not in names

    def test_set_actions_as_path_prepend_list(self):
        """set_actions with as-path prepend list is handled correctly."""
        session = _ebgp_session("s1", export_policies=[{"id": 1, "name": "P"}])
        policy_rules = [
            {
                "routing_policy": {"id": 1, "name": "P"},
                "index": 10,
                "action": "permit",
                "match_ip_address": [],
                "set_actions": {"as-path prepend": [65100]},
            }
        ]
        result = collect_ebgp_vrf_policy_config([session], policy_rules, [])
        commands = result["route_map_rules"][0]["commands"]
        assert "set as-path prepend 65100" in commands

    def test_prefix_custom_field_used_when_ipam_prefix_is_none(self):
        """prefix_custom plain-string field is used when the IPAM prefix FK is null."""
        session = _ebgp_session("s1", import_policies=[{"id": 1, "name": "P"}])
        policy_rules = [
            _policy_rule(1, "P", 10, match_pfx_id=5, match_pfx_name="PFX")
        ]
        prefix_list_rules = [
            {
                "prefix_list": {"id": 5, "name": "PFX"},
                "index": 10,
                "action": "permit",
                "prefix": None,          # IPAM FK is null
                "prefix_custom": "0.0.0.0/0",  # free-text fallback
            }
        ]
        result = collect_ebgp_vrf_policy_config([session], policy_rules, prefix_list_rules)
        assert result["prefix_lists"][0]["rules"][0]["prefix"] == "0.0.0.0/0"

    def test_ipv4_prefix_list_has_af_ipv4(self):
        """Prefix lists referenced via match_ip_address carry af='ipv4'."""
        session = _ebgp_session("s1", export_policies=[{"id": 1, "name": "P"}])
        policy_rules = [
            _policy_rule(1, "P", 10, match_pfx_id=5, match_pfx_name="LAB-IPV4")
        ]
        prefix_list_rules = [
            _prefix_list_rule(5, "LAB-IPV4", 10, "permit", "172.27.4.0/24")
        ]
        result = collect_ebgp_vrf_policy_config([session], policy_rules, prefix_list_rules)
        assert result["prefix_lists"][0]["af"] == "ipv4"

    def test_ipv6_prefix_list_via_match_ipv6_address(self):
        """Prefix lists referenced via match_ipv6_address carry af='ipv6'."""
        session = _ebgp_session("s1", export_policies=[{"id": 1, "name": "P-V6-OUT"}])
        policy_rules = [
            {
                "routing_policy": {"id": 1, "name": "P-V6-OUT"},
                "index": 10,
                "action": "permit",
                "match_ip_address": [],
                "match_ipv6_address": [{"id": 6, "name": "LAB-BLUE-IPV6"}],
                "set_actions": {"as-path prepend": [65015]},
            }
        ]
        prefix_list_rules = [
            {
                "prefix_list": {"id": 6, "name": "LAB-BLUE-IPV6"},
                "index": 10,
                "action": "permit",
                "prefix": {"id": 600, "prefix": "2a02:20c8:5921:da10::/60", "display": "2a02:20c8:5921:da10::/60"},
            }
        ]

        result = collect_ebgp_vrf_policy_config([session], policy_rules, prefix_list_rules)

        assert len(result["prefix_lists"]) == 1
        pl = result["prefix_lists"][0]
        assert pl["name"] == "LAB-BLUE-IPV6"
        assert pl["af"] == "ipv6"
        assert pl["rules"][0]["prefix"] == "2a02:20c8:5921:da10::/60"

        rm = result["route_map_rules"][0]
        assert "match ipv6 address prefix-list LAB-BLUE-IPV6" in rm["commands"]
        assert "match ip address prefix-list LAB-BLUE-IPV6" not in rm["commands"]

    def test_mixed_ipv4_and_ipv6_prefix_lists_in_same_route_map(self):
        """A single route-map rule can match both IPv4 and IPv6 prefix lists."""
        session = _ebgp_session("s1", export_policies=[{"id": 1, "name": "MIXED-OUT"}])
        policy_rules = [
            {
                "routing_policy": {"id": 1, "name": "MIXED-OUT"},
                "index": 10,
                "action": "permit",
                "match_ip_address": [{"id": 4, "name": "LAB-IPV4"}],
                "match_ipv6_address": [{"id": 6, "name": "LAB-IPV6"}],
                "set_actions": {},
            }
        ]
        prefix_list_rules = [
            _prefix_list_rule(4, "LAB-IPV4", 10, "permit", "172.27.4.0/24"),
            {
                "prefix_list": {"id": 6, "name": "LAB-IPV6"},
                "index": 10,
                "action": "permit",
                "prefix": {"id": 600, "prefix": "2a02:20c8:5921:da20::/60", "display": "2a02:20c8:5921:da20::/60"},
            },
        ]

        result = collect_ebgp_vrf_policy_config([session], policy_rules, prefix_list_rules)

        af_map = {pl["name"]: pl["af"] for pl in result["prefix_lists"]}
        assert af_map["LAB-IPV4"] == "ipv4"
        assert af_map["LAB-IPV6"] == "ipv6"

        commands = result["route_map_rules"][0]["commands"]
        assert "match ip address prefix-list LAB-IPV4" in commands
        assert "match ipv6 address prefix-list LAB-IPV6" in commands

    def test_address_family_on_prefix_list_object_overrides_field_detection(self):
        """address_family on the prefix_list FK object takes precedence."""
        session = _ebgp_session("s1", export_policies=[{"id": 1, "name": "P"}])
        # Deliberately reference via match_ip_address but the PL object says ipv6
        policy_rules = [
            _policy_rule(1, "P", 10, match_pfx_id=5, match_pfx_name="TRICKY")
        ]
        prefix_list_rules = [
            {
                "prefix_list": {"id": 5, "name": "TRICKY", "address_family": {"value": "ipv6", "label": "IPv6"}},
                "index": 10,
                "action": "permit",
                "prefix": {"id": 500, "prefix": "2a02:20c8::/32", "display": "2a02:20c8::/32"},
            }
        ]

        result = collect_ebgp_vrf_policy_config([session], policy_rules, prefix_list_rules)
        assert result["prefix_lists"][0]["af"] == "ipv6"

    def test_ipv6_default_route_in_prefix_list(self):
        """The IPv6 default route ::/0 is stored correctly."""
        session = _ebgp_session("s1", import_policies=[{"id": 1, "name": "GW-V6-IN"}])
        policy_rules = [
            {
                "routing_policy": {"id": 1, "name": "GW-V6-IN"},
                "index": 10,
                "action": "permit",
                "match_ip_address": [],
                "match_ipv6_address": [{"id": 7, "name": "LAB-GW-IPV6"}],
                "set_actions": {"local-preference": 300},
            }
        ]
        prefix_list_rules = [
            {
                "prefix_list": {"id": 7, "name": "LAB-GW-IPV6"},
                "index": 10,
                "action": "permit",
                "prefix": {"id": 700, "prefix": "::/0", "display": "::/0"},
            }
        ]

        result = collect_ebgp_vrf_policy_config([session], policy_rules, prefix_list_rules)

        pl = result["prefix_lists"][0]
        assert pl["name"] == "LAB-GW-IPV6"
        assert pl["af"] == "ipv6"
        assert pl["rules"][0]["prefix"] == "::/0"

        commands = result["route_map_rules"][0]["commands"]
        assert "match ipv6 address prefix-list LAB-GW-IPV6" in commands
        assert "set local-preference 300" in commands

    def test_ipv6_session_export_policy_collected(self):
        """Policies on an IPv6 BGP session are collected regardless of _af."""
        session = {
            "name": "gw-v6",
            "local_as": {"asn": 65015},
            "remote_as": {"asn": 65020},
            "local_address": {"address": "2a02:20c8:5921:da10::1/64"},
            "remote_address": {"address": "2a02:20c8:5921:da10::2/64"},
            "_vrf": "lab-blue",
            "_af": "ipv6",
            "import_policies": [],
            "export_policies": [{"id": 1, "name": "LAB-BLUE-IPV6-OUT-01"}],
        }
        policy_rules = [
            {
                "routing_policy": {"id": 1, "name": "LAB-BLUE-IPV6-OUT-01"},
                "index": 10,
                "action": "permit",
                "match_ip_address": [],
                "match_ipv6_address": [{"id": 6, "name": "LAB-BLUE-IPV6"}],
                "set_actions": {"as-path prepend": [65015]},
            }
        ]
        prefix_list_rules = [
            {
                "prefix_list": {"id": 6, "name": "LAB-BLUE-IPV6"},
                "index": 10,
                "action": "permit",
                "prefix": {"id": 600, "prefix": "2a02:20c8:5921:da10::/60", "display": "2a02:20c8:5921:da10::/60"},
            }
        ]

        result = collect_ebgp_vrf_policy_config([session], policy_rules, prefix_list_rules)

        assert len(result["route_map_rules"]) == 1
        rm = result["route_map_rules"][0]
        assert rm["name"] == "LAB-BLUE-IPV6-OUT-01"
        assert "route-map LAB-BLUE-IPV6-OUT-01 permit seq 10" in rm["commands"]
        assert "match ipv6 address prefix-list LAB-BLUE-IPV6" in rm["commands"]
        assert "set as-path prepend 65015" in rm["commands"]

        assert len(result["prefix_lists"]) == 1
        pl = result["prefix_lists"][0]
        assert pl["af"] == "ipv6"
        assert pl["rules"][0]["prefix"] == "2a02:20c8:5921:da10::/60"

    def test_ipv6_session_import_policy_collected(self):
        """Import policies on an IPv6 session produce correct route-map commands."""
        session = {
            "name": "gw-v6",
            "local_as": {"asn": 65015},
            "remote_as": {"asn": 65020},
            "local_address": {"address": "2a02:20c8:5921:da10::1/64"},
            "remote_address": {"address": "2a02:20c8:5921:da10::2/64"},
            "_vrf": "lab-blue",
            "_af": "ipv6",
            "import_policies": [{"id": 2, "name": "LAB-GW-IPV6-IN-01"}],
            "export_policies": [],
        }
        policy_rules = [
            {
                "routing_policy": {"id": 2, "name": "LAB-GW-IPV6-IN-01"},
                "index": 10,
                "action": "permit",
                "match_ip_address": [],
                "match_ipv6_address": [{"id": 7, "name": "LAB-GW-IPV6"}],
                "set_actions": {"local-preference": 300},
            }
        ]
        prefix_list_rules = [
            {
                "prefix_list": {"id": 7, "name": "LAB-GW-IPV6"},
                "index": 10,
                "action": "permit",
                "prefix": {"id": 700, "prefix": "::/0", "display": "::/0"},
            }
        ]

        result = collect_ebgp_vrf_policy_config([session], policy_rules, prefix_list_rules)

        rm = result["route_map_rules"][0]
        assert rm["name"] == "LAB-GW-IPV6-IN-01"
        assert "match ipv6 address prefix-list LAB-GW-IPV6" in rm["commands"]
        assert "set local-preference 300" in rm["commands"]

        pl = result["prefix_lists"][0]
        assert pl["af"] == "ipv6"
        assert pl["rules"][0]["prefix"] == "::/0"

    def test_mixed_ipv4_and_ipv6_sessions_collect_all_policies(self):
        """Both IPv4 and IPv6 sessions have their policies collected in one pass."""
        sessions = [
            _ebgp_session("v4-peer", export_policies=[{"id": 1, "name": "V4-OUT"}]),
            {
                "name": "v6-peer",
                "local_as": {"asn": 65015},
                "remote_as": {"asn": 65020},
                "local_address": {"address": "2a02:20c8::1/64"},
                "remote_address": {"address": "2a02:20c8::2/64"},
                "_vrf": "lab-blue",
                "_af": "ipv6",
                "import_policies": [],
                "export_policies": [{"id": 2, "name": "V6-OUT"}],
            },
        ]
        policy_rules = [
            _policy_rule(1, "V4-OUT", 10, match_pfx_id=4, match_pfx_name="PFX-V4"),
            {
                "routing_policy": {"id": 2, "name": "V6-OUT"},
                "index": 10,
                "action": "permit",
                "match_ip_address": [],
                "match_ipv6_address": [{"id": 6, "name": "PFX-V6"}],
                "set_actions": {},
            },
        ]
        prefix_list_rules = [
            _prefix_list_rule(4, "PFX-V4", 10, "permit", "172.27.4.0/24"),
            {
                "prefix_list": {"id": 6, "name": "PFX-V6"},
                "index": 10,
                "action": "permit",
                "prefix": {"id": 600, "prefix": "2a02:20c8::/32", "display": "2a02:20c8::/32"},
            },
        ]

        result = collect_ebgp_vrf_policy_config(sessions, policy_rules, prefix_list_rules)

        rm_names = [rm["name"] for rm in result["route_map_rules"]]
        assert "V4-OUT" in rm_names
        assert "V6-OUT" in rm_names

        af_map = {pl["name"]: pl["af"] for pl in result["prefix_lists"]}
        assert af_map["PFX-V4"] == "ipv4"
        assert af_map["PFX-V6"] == "ipv6"


# ---------------------------------------------------------------------------
# Tests for get_bgp_redistribute_config
# ---------------------------------------------------------------------------


class TestGetBgpRedistributeConfig:
    """Tests for get_bgp_redistribute_config function"""

    def test_none_returns_empty(self):
        assert get_bgp_redistribute_config(None) == []

    def test_empty_dict_returns_empty(self):
        assert get_bgp_redistribute_config({}) == []

    def test_non_dict_input_returns_empty(self):
        assert get_bgp_redistribute_config("not-a-dict") == []

    def test_global_default_vrf(self):
        result = get_bgp_redistribute_config(
            {"default": {"ipv4": ["connected", "static"]}}
        )
        assert result == [
            {"vrf": "default", "af": "ipv4", "protocol": "connected"},
            {"vrf": "default", "af": "ipv4", "protocol": "static"},
        ]

    def test_multiple_vrfs_and_address_families(self):
        result = get_bgp_redistribute_config(
            {
                "lab-blue": {"ipv4": ["static"], "ipv6": ["static"]},
                "lab-green": {"ipv4": ["static"]},
            }
        )
        assert result == [
            {"vrf": "lab-blue", "af": "ipv4", "protocol": "static"},
            {"vrf": "lab-blue", "af": "ipv6", "protocol": "static"},
            {"vrf": "lab-green", "af": "ipv4", "protocol": "static"},
        ]

    def test_unknown_address_family_skipped(self):
        result = get_bgp_redistribute_config({"default": {"l2vpn": ["static"]}})
        assert result == []

    def test_unsupported_protocol_skipped(self):
        result = get_bgp_redistribute_config({"default": {"ipv4": ["bgp", "static"]}})
        assert result == [{"vrf": "default", "af": "ipv4", "protocol": "static"}]

    def test_non_dict_af_map_skipped(self):
        result = get_bgp_redistribute_config({"default": "not-a-dict"})
        assert result == []

    def test_non_list_protocols_skipped(self):
        result = get_bgp_redistribute_config({"default": {"ipv4": "static"}})
        assert result == []

    def test_result_is_sorted(self):
        result = get_bgp_redistribute_config(
            {
                "lab-green": {"ipv4": ["static"]},
                "default": {"ipv6": ["static"], "ipv4": ["static", "connected"]},
            }
        )
        assert result == [
            {"vrf": "default", "af": "ipv4", "protocol": "connected"},
            {"vrf": "default", "af": "ipv4", "protocol": "static"},
            {"vrf": "default", "af": "ipv6", "protocol": "static"},
            {"vrf": "lab-green", "af": "ipv4", "protocol": "static"},
        ]


# ---------------------------------------------------------------------------
# Tests for get_stale_bgp_redistribute
# ---------------------------------------------------------------------------


class TestGetStaleBgpRedistribute:
    """Tests for get_stale_bgp_redistribute function"""

    _RUNNING_CONFIG = """
!
router bgp 65015
    bgp router-id 10.255.255.11
    neighbor 10.255.255.1 remote-as 65015
    address-family ipv4 unicast
        redistribute connected
    exit-address-family
    vrf lab-blue
        address-family ipv4 unicast
            redistribute static
        exit-address-family
        address-family ipv6 unicast
            redistribute static
        exit-address-family
    exit-vrf
    vrf lab-green
        address-family ipv4 unicast
            redistribute static
            redistribute connected
        exit-address-family
    exit-vrf
!
vlan 10
    name TEST
!
"""

    def test_no_stale_entries_when_config_matches(self):
        desired = {
            "default": {"ipv4": ["connected"]},
            "lab-blue": {"ipv4": ["static"], "ipv6": ["static"]},
            "lab-green": {"ipv4": ["static", "connected"]},
        }
        result = get_stale_bgp_redistribute(desired, self._RUNNING_CONFIG, 65015)
        assert result == []

    def test_removed_from_config_context_is_stale(self):
        # lab-green's 'redistribute connected' removed from desired state
        desired = {
            "default": {"ipv4": ["connected"]},
            "lab-blue": {"ipv4": ["static"], "ipv6": ["static"]},
            "lab-green": {"ipv4": ["static"]},
        }
        result = get_stale_bgp_redistribute(desired, self._RUNNING_CONFIG, 65015)
        assert result == [{"vrf": "lab-green", "af": "ipv4", "protocol": "connected"}]

    def test_entire_vrf_removed_from_config_context(self):
        desired = {"default": {"ipv4": ["connected"]}}
        result = get_stale_bgp_redistribute(desired, self._RUNNING_CONFIG, 65015)
        keys = {(e["vrf"], e["af"], e["protocol"]) for e in result}
        assert ("lab-blue", "ipv4", "static") in keys
        assert ("lab-blue", "ipv6", "static") in keys
        assert ("lab-green", "ipv4", "static") in keys
        assert ("lab-green", "ipv4", "connected") in keys
        assert len(result) == 4

    def test_empty_config_context_removes_everything(self):
        result = get_stale_bgp_redistribute({}, self._RUNNING_CONFIG, 65015)
        assert len(result) == 5

    def test_wrong_asn_scopes_out_everything(self):
        """ASN not matching the running-config's 'router bgp' line finds nothing."""
        result = get_stale_bgp_redistribute({}, self._RUNNING_CONFIG, 65099)
        assert result == []

    def test_empty_running_config_returns_empty(self):
        result = get_stale_bgp_redistribute(
            {"default": {"ipv4": ["static"]}}, "", 65015
        )
        assert result == []

    def test_none_running_config_returns_empty(self):
        result = get_stale_bgp_redistribute(
            {"default": {"ipv4": ["static"]}}, None, 65015
        )
        assert result == []

    def test_redistribute_outside_address_family_is_ignored(self):
        """A 'redistribute' line outside any address-family block is not parsed."""
        running_config = """
router bgp 65015
    redistribute connected
"""
        result = get_stale_bgp_redistribute({}, running_config, 65015)
        assert result == []

    def test_l2vpn_evpn_address_family_is_ignored(self):
        """redistribute isn't valid under l2vpn evpn; must not be parsed as ipv4/ipv6."""
        running_config = """
router bgp 65015
    address-family l2vpn evpn
        redistribute connected
    exit-address-family
"""
        result = get_stale_bgp_redistribute({}, running_config, 65015)
        assert result == []


# ---------------------------------------------------------------------------
# Tests for get_bgp_neighbor_options_config
# ---------------------------------------------------------------------------


def _enriched_session(remote_ip, vrf="default", af="ipv4"):
    return {
        "name": f"session-{remote_ip}",
        "remote_address": {"address": f"{remote_ip}/31"},
        "_vrf": vrf,
        "_af": af,
    }


class TestGetBgpNeighborOptionsConfig:
    """Tests for get_bgp_neighbor_options_config function"""

    def test_none_returns_empty(self):
        assert get_bgp_neighbor_options_config(None, []) == []

    def test_empty_dict_returns_empty(self):
        assert get_bgp_neighbor_options_config({}, []) == []

    def test_non_dict_input_returns_empty(self):
        assert get_bgp_neighbor_options_config("not-a-dict", []) == []

    def test_basic_single_neighbor(self):
        sessions = [_enriched_session("172.27.250.32")]
        result = get_bgp_neighbor_options_config(
            {"172.27.250.32": {"ipv4": ["soft-reconfiguration inbound"]}}, sessions
        )
        assert result == [
            {
                "vrf": "default",
                "af": "ipv4",
                "neighbor_ip": "172.27.250.32",
                "command": "soft-reconfiguration inbound",
            }
        ]

    def test_multiple_commands_same_neighbor(self):
        sessions = [_enriched_session("172.27.250.32")]
        result = get_bgp_neighbor_options_config(
            {
                "172.27.250.32": {
                    "ipv4": ["soft-reconfiguration inbound", "weight 100"]
                }
            },
            sessions,
        )
        assert result == [
            {
                "vrf": "default",
                "af": "ipv4",
                "neighbor_ip": "172.27.250.32",
                "command": "soft-reconfiguration inbound",
            },
            {
                "vrf": "default",
                "af": "ipv4",
                "neighbor_ip": "172.27.250.32",
                "command": "weight 100",
            },
        ]

    def test_unmatched_neighbor_ip_skipped(self):
        sessions = [_enriched_session("172.27.250.32")]
        result = get_bgp_neighbor_options_config(
            {"10.0.0.99": {"ipv4": ["soft-reconfiguration inbound"]}}, sessions
        )
        assert result == []

    def test_unknown_address_family_skipped(self):
        sessions = [_enriched_session("172.27.250.32")]
        result = get_bgp_neighbor_options_config(
            {"172.27.250.32": {"l2vpn": ["soft-reconfiguration inbound"]}}, sessions
        )
        assert result == []

    def test_af_not_matching_session_skipped(self):
        # Session is ipv4 only; requesting an ipv6 option for the same IP finds no context.
        sessions = [_enriched_session("172.27.250.32", af="ipv4")]
        result = get_bgp_neighbor_options_config(
            {"172.27.250.32": {"ipv6": ["soft-reconfiguration inbound"]}}, sessions
        )
        assert result == []

    def test_reserved_keyword_skipped(self):
        sessions = [_enriched_session("172.27.250.32")]
        result = get_bgp_neighbor_options_config(
            {
                "172.27.250.32": {
                    "ipv4": [
                        "remote-as 65001",
                        "route-map FOO out",
                        "activate",
                        "next-hop-self",
                        "route-reflector-client",
                        "send-community extended",
                        "update-source 10.0.0.1",
                        "soft-reconfiguration inbound",
                    ]
                }
            },
            sessions,
        )
        assert result == [
            {
                "vrf": "default",
                "af": "ipv4",
                "neighbor_ip": "172.27.250.32",
                "command": "soft-reconfiguration inbound",
            }
        ]

    def test_non_list_commands_skipped(self):
        sessions = [_enriched_session("172.27.250.32")]
        result = get_bgp_neighbor_options_config(
            {"172.27.250.32": {"ipv4": "soft-reconfiguration inbound"}}, sessions
        )
        assert result == []

    def test_non_dict_af_map_skipped(self):
        sessions = [_enriched_session("172.27.250.32")]
        result = get_bgp_neighbor_options_config(
            {"172.27.250.32": "not-a-dict"}, sessions
        )
        assert result == []

    def test_multiple_vrfs_same_ip_and_af(self):
        # Unlikely in practice, but the same neighbor IP could be peered
        # under more than one VRF; the option must be pushed to each.
        sessions = [
            _enriched_session("172.27.250.32", vrf="lab-blue"),
            _enriched_session("172.27.250.32", vrf="lab-green"),
        ]
        result = get_bgp_neighbor_options_config(
            {"172.27.250.32": {"ipv4": ["soft-reconfiguration inbound"]}}, sessions
        )
        assert result == [
            {
                "vrf": "lab-blue",
                "af": "ipv4",
                "neighbor_ip": "172.27.250.32",
                "command": "soft-reconfiguration inbound",
            },
            {
                "vrf": "lab-green",
                "af": "ipv4",
                "neighbor_ip": "172.27.250.32",
                "command": "soft-reconfiguration inbound",
            },
        ]

    def test_result_is_sorted(self):
        sessions = [
            _enriched_session("172.27.250.99"),
            _enriched_session("172.27.250.32"),
        ]
        result = get_bgp_neighbor_options_config(
            {
                "172.27.250.99": {"ipv4": ["weight 100"]},
                "172.27.250.32": {"ipv4": ["soft-reconfiguration inbound"]},
            },
            sessions,
        )
        assert result == [
            {
                "vrf": "default",
                "af": "ipv4",
                "neighbor_ip": "172.27.250.32",
                "command": "soft-reconfiguration inbound",
            },
            {
                "vrf": "default",
                "af": "ipv4",
                "neighbor_ip": "172.27.250.99",
                "command": "weight 100",
            },
        ]

    def test_general_scope_basic(self):
        """'general' scope commands (e.g. fall-over bfd) are pushed with af=None."""
        sessions = [_enriched_session("172.27.250.32")]
        result = get_bgp_neighbor_options_config(
            {"172.27.250.32": {"general": ["fall-over bfd"]}}, sessions
        )
        assert result == [
            {
                "vrf": "default",
                "af": None,
                "neighbor_ip": "172.27.250.32",
                "command": "fall-over bfd",
            }
        ]

    def test_general_scope_matches_regardless_of_af(self):
        """'general' options aren't tied to a specific address family, so
        they resolve against every VRF the neighbor is peered under."""
        sessions = [
            _enriched_session("172.27.250.32", vrf="lab-blue", af="ipv4"),
            _enriched_session("172.27.250.32", vrf="lab-blue", af="ipv6"),
        ]
        result = get_bgp_neighbor_options_config(
            {"172.27.250.32": {"general": ["fall-over bfd"]}}, sessions
        )
        assert result == [
            {
                "vrf": "lab-blue",
                "af": None,
                "neighbor_ip": "172.27.250.32",
                "command": "fall-over bfd",
            }
        ]

    def test_general_and_af_scopes_combined(self):
        sessions = [_enriched_session("172.27.250.32", af="ipv4")]
        result = get_bgp_neighbor_options_config(
            {
                "172.27.250.32": {
                    "general": ["fall-over bfd"],
                    "ipv4": ["soft-reconfiguration inbound"],
                }
            },
            sessions,
        )
        assert result == [
            {
                "vrf": "default",
                "af": None,
                "neighbor_ip": "172.27.250.32",
                "command": "fall-over bfd",
            },
            {
                "vrf": "default",
                "af": "ipv4",
                "neighbor_ip": "172.27.250.32",
                "command": "soft-reconfiguration inbound",
            },
        ]

    def test_general_scope_reserved_keyword_skipped(self):
        sessions = [_enriched_session("172.27.250.32")]
        result = get_bgp_neighbor_options_config(
            {"172.27.250.32": {"general": ["remote-as 65001", "fall-over bfd"]}},
            sessions,
        )
        assert result == [
            {
                "vrf": "default",
                "af": None,
                "neighbor_ip": "172.27.250.32",
                "command": "fall-over bfd",
            }
        ]


# ---------------------------------------------------------------------------
# Tests for get_stale_bgp_neighbor_options
# ---------------------------------------------------------------------------


class TestGetStaleBgpNeighborOptions:
    """Tests for get_stale_bgp_neighbor_options function"""

    _RUNNING_CONFIG = """
!
router bgp 65015
    bgp router-id 10.255.255.11
    neighbor 172.27.250.32 remote-as 65001
    neighbor 172.27.250.32 update-source 10.255.255.11
    neighbor 172.27.250.32 fall-over bfd
    address-family ipv4 unicast
        neighbor 172.27.250.32 activate
        neighbor 172.27.250.32 soft-reconfiguration inbound
        neighbor 172.27.250.32 weight 100
    exit-address-family
    vrf lab-blue
        neighbor 172.27.100.1 remote-as 65010
        address-family ipv4 unicast
            neighbor 172.27.100.1 activate
            neighbor 172.27.100.1 route-map LAB-BLUE-OUT out
            neighbor 172.27.100.1 soft-reconfiguration inbound
        exit-address-family
    exit-vrf
!
vlan 10
    name TEST
!
"""

    _SESSIONS = [
        _enriched_session("172.27.250.32", vrf="default", af="ipv4"),
        _enriched_session("172.27.100.1", vrf="lab-blue", af="ipv4"),
    ]

    def test_no_stale_entries_when_config_matches(self):
        desired = {
            "172.27.250.32": {
                "general": ["fall-over bfd"],
                "ipv4": ["soft-reconfiguration inbound", "weight 100"],
            },
            "172.27.100.1": {"ipv4": ["soft-reconfiguration inbound"]},
        }
        result = get_stale_bgp_neighbor_options(
            desired, self._SESSIONS, self._RUNNING_CONFIG, 65015
        )
        assert result == []

    def test_removed_option_is_stale(self):
        desired = {
            "172.27.250.32": {
                "general": ["fall-over bfd"],
                "ipv4": ["soft-reconfiguration inbound"],
            },
            "172.27.100.1": {"ipv4": ["soft-reconfiguration inbound"]},
        }
        result = get_stale_bgp_neighbor_options(
            desired, self._SESSIONS, self._RUNNING_CONFIG, 65015
        )
        assert result == [
            {
                "vrf": "default",
                "af": "ipv4",
                "neighbor_ip": "172.27.250.32",
                "command": "weight 100",
            }
        ]

    def test_removed_general_option_is_stale(self):
        desired = {
            "172.27.250.32": {
                "ipv4": ["soft-reconfiguration inbound", "weight 100"],
            },
            "172.27.100.1": {"ipv4": ["soft-reconfiguration inbound"]},
        }
        result = get_stale_bgp_neighbor_options(
            desired, self._SESSIONS, self._RUNNING_CONFIG, 65015
        )
        assert result == [
            {
                "vrf": "default",
                "af": None,
                "neighbor_ip": "172.27.250.32",
                "command": "fall-over bfd",
            }
        ]

    def test_reserved_keywords_never_considered_stale(self):
        """Even with an empty config_context, lines owned by other tasks
        (remote-as, update-source, activate, route-map) must never appear
        as removal candidates."""
        result = get_stale_bgp_neighbor_options(
            {}, self._SESSIONS, self._RUNNING_CONFIG, 65015
        )
        commands = {entry["command"] for entry in result}
        assert "soft-reconfiguration inbound" in commands
        assert "weight 100" in commands
        assert "fall-over bfd" in commands
        assert not any(
            cmd.startswith(
                ("remote-as", "update-source", "activate", "route-map")
            )
            for cmd in commands
        )
        assert len(result) == 4

    def test_wrong_asn_scopes_out_everything(self):
        result = get_stale_bgp_neighbor_options(
            {}, self._SESSIONS, self._RUNNING_CONFIG, 65099
        )
        assert result == []

    def test_empty_running_config_returns_empty(self):
        result = get_stale_bgp_neighbor_options(
            {"172.27.250.32": {"ipv4": ["weight 100"]}}, self._SESSIONS, "", 65015
        )
        assert result == []

    def test_none_running_config_returns_empty(self):
        result = get_stale_bgp_neighbor_options(
            {"172.27.250.32": {"ipv4": ["weight 100"]}}, self._SESSIONS, None, 65015
        )
        assert result == []


class TestGetBgpBfdEnabled:
    """Tests for get_bgp_bfd_enabled function"""

    def test_fall_over_bfd_requires_bfd_enabled(self):
        sessions = [_enriched_session("172.27.250.32")]
        result = get_bgp_bfd_enabled(
            {"172.27.250.32": {"general": ["fall-over bfd"]}}, sessions
        )
        assert result is True

    def test_fall_over_bfd_on_non_default_vrf_also_enables(self):
        """'bfd' is global, so a fall-over bfd neighbor on any VRF counts."""
        sessions = [_enriched_session("172.27.100.1", vrf="lab-blue")]
        result = get_bgp_bfd_enabled(
            {"172.27.100.1": {"general": ["fall-over bfd"]}}, sessions
        )
        assert result is True

    def test_no_fall_over_bfd_returns_false(self):
        sessions = [_enriched_session("172.27.250.32")]
        result = get_bgp_bfd_enabled(
            {"172.27.250.32": {"ipv4": ["soft-reconfiguration inbound"]}}, sessions
        )
        assert result is False

    def test_other_general_options_do_not_trigger_bfd(self):
        sessions = [_enriched_session("172.27.250.32")]
        result = get_bgp_bfd_enabled(
            {"172.27.250.32": {"general": ["timers 3 9"]}}, sessions
        )
        assert result is False

    def test_empty_config_returns_false(self):
        assert get_bgp_bfd_enabled({}, [_enriched_session("172.27.250.32")]) is False


class TestGetStaleBgpBfd:
    """Tests for get_stale_bgp_bfd function"""

    _RUNNING_CONFIG = """
!
clock timezone europe/oslo
bfd
no ip icmp redirect
router bgp 65015
    bgp router-id 10.255.255.11
    neighbor 172.27.250.32 remote-as 65001
    neighbor 172.27.250.32 fall-over bfd
    vrf lab-blue
        neighbor 172.27.100.1 remote-as 65010
        address-family ipv4 unicast
            neighbor 172.27.100.1 activate
        exit-address-family
    exit-vrf
!
"""

    _SESSIONS = [
        _enriched_session("172.27.250.32", vrf="default", af="ipv4"),
        _enriched_session("172.27.100.1", vrf="lab-blue", af="ipv4"),
    ]

    def test_no_stale_when_still_desired(self):
        desired = {"172.27.250.32": {"general": ["fall-over bfd"]}}
        result = get_stale_bgp_bfd(desired, self._SESSIONS, self._RUNNING_CONFIG)
        assert result is False

    def test_removed_fall_over_bfd_makes_bfd_stale(self):
        result = get_stale_bgp_bfd({}, self._SESSIONS, self._RUNNING_CONFIG)
        assert result is True

    def test_bfd_not_configured_is_never_stale(self):
        running_config = "!\nclock timezone europe/oslo\nno ip icmp redirect\n!\n"
        result = get_stale_bgp_bfd({}, self._SESSIONS, running_config)
        assert result is False

    def test_bfd_inside_router_bgp_is_not_the_global_line(self):
        """A 'bfd' line nested under router bgp/vrf must not be mistaken for
        the global toggle - only an unindented top-level 'bfd' counts."""
        running_config = (
            "!\nrouter bgp 65015\n    vrf lab-blue\n        bfd\n    exit-vrf\n!\n"
        )
        result = get_stale_bgp_bfd({}, self._SESSIONS, running_config)
        assert result is False

    def test_empty_running_config_returns_false(self):
        result = get_stale_bgp_bfd(
            {"172.27.250.32": {"general": ["fall-over bfd"]}}, self._SESSIONS, ""
        )
        assert result is False

    def test_none_running_config_returns_false(self):
        result = get_stale_bgp_bfd(
            {"172.27.250.32": {"general": ["fall-over bfd"]}}, self._SESSIONS, None
        )
        assert result is False


class TestBgpRunningConfigDeviceFormat:
    """The parsers against 'show running-config' as AOS-CX 10.16 prints it
    (8360 lab switch): no 'exit-vrf', and a column-0 '!' between the global
    section and each 'vrf' section. The '!' must not end 'router bgp'."""

    _RUNNING_CONFIG = """
bfd
router bgp 65015
    bgp router-id 172.27.252.0
    neighbor 172.27.252.1 remote-as 65015
    neighbor 172.27.252.1 password ciphertext AQBapWeH
    neighbor 172.27.252.1 update-source 172.27.252.0
    address-family l2vpn evpn
        neighbor 172.27.252.1 send-community extended
        neighbor 172.27.252.1 activate
    exit-address-family
!
    vrf lab-blue
        neighbor 172.27.250.32 remote-as 65020
        neighbor 172.27.250.32 fall-over bfd
        address-family ipv4 unicast
            neighbor 172.27.250.32 route-map LAB-GW-IPV4-IN-01 in
            neighbor 172.27.250.32 soft-reconfiguration inbound
            neighbor 172.27.250.32 activate
            redistribute static
        exit-address-family
!
    vrf lab-green
        neighbor 172.27.250.38 remote-as 65020
        address-family ipv4 unicast
            redistribute connected
        exit-address-family
!
https-server vrf mgmt
"""

    _SESSIONS = [
        _enriched_session("172.27.252.1", vrf="default", af="ipv4"),
        _enriched_session("172.27.250.32", vrf="lab-blue", af="ipv4"),
        _enriched_session("172.27.250.38", vrf="lab-green", af="ipv4"),
    ]

    def test_redistribute_after_bang_is_parsed(self):
        desired = {"lab-blue": {"ipv4": ["static"]}}
        result = get_stale_bgp_redistribute(desired, self._RUNNING_CONFIG, 65015)
        assert result == [{"vrf": "lab-green", "af": "ipv4", "protocol": "connected"}]

    def test_vrf_neighbor_options_after_bang_are_parsed(self):
        result = get_stale_bgp_neighbor_options(
            {}, self._SESSIONS, self._RUNNING_CONFIG, 65015)
        assert result == [
            {"vrf": "default", "af": None, "neighbor_ip": "172.27.252.1",
             "command": "password ciphertext AQBapWeH"},
            {"vrf": "lab-blue", "af": None, "neighbor_ip": "172.27.250.32",
             "command": "fall-over bfd"},
            {"vrf": "lab-blue", "af": "ipv4", "neighbor_ip": "172.27.250.32",
             "command": "soft-reconfiguration inbound"},
        ]

    def test_no_stale_options_when_config_matches(self):
        desired = {
            "172.27.252.1": {"general": ["password ciphertext AQBapWeH"]},
            "172.27.250.32": {
                "general": ["fall-over bfd"],
                "ipv4": ["soft-reconfiguration inbound"],
            },
        }
        result = get_stale_bgp_neighbor_options(
            desired, self._SESSIONS, self._RUNNING_CONFIG, 65015)
        assert result == []

    def test_next_top_level_statement_ends_router_bgp(self):
        config = self._RUNNING_CONFIG + "router ospf 1\n    redistribute static\n"
        result = get_stale_bgp_redistribute(
            {"lab-blue": {"ipv4": ["static"]}, "lab-green": {"ipv4": ["connected"]}},
            config, 65015)
        assert result == []


def _nb_session(name, local, remote, vrf, af, local_as=65015, remote_as=65015,
                import_policy=None, export_policy=None):
    return {
        "name": name,
        "local_address": {"address": local},
        "remote_address": {"address": remote},
        "local_as": {"asn": local_as},
        "remote_as": {"asn": remote_as},
        "import_policies": [{"name": import_policy}] if import_policy else [],
        "export_policies": [{"name": export_policy}] if export_policy else [],
        "_vrf": vrf,
        "_af": af,
    }


_LAB_SESSIONS = [
    _nb_session("ao-01-ao-02", "172.27.252.0/32", "172.27.252.1/32", "default", "ipv4"),
    _nb_session("ao-01-ao-02-blue", "172.27.4.2/27", "172.27.4.3/27", "lab-blue", "ipv4"),
    _nb_session("ao-01-ao-02-blue", "2a02:20c8:5921:da10::2/64",
                "2a02:20c8:5921:da10:0:0:0:3/64", "lab-blue", "ipv6"),
    _nb_session("ao-01-lab-gw-blue", "172.27.250.33/31", "172.27.250.32/31", "lab-blue",
                "ipv4", remote_as=65020, import_policy="GW-IN", export_policy="BLUE-OUT"),
]


def _have(**kwargs):
    """A neighbor as rest_api_to_aoscx_bgp returns it."""
    n = {
        "remote_as": None, "update_source": None, "shutdown": False,
        "activate": [], "next_hop_self": [], "route_reflector_client": [],
        "soft_reconfiguration_inbound": [], "send_community": {},
        "route_maps": {}, "bfd": False, "fall_over": False,
        "password": None, "state": "Established",
    }
    n.update(kwargs)
    return n


def _converged_facts():
    return {
        "asn": 65015,
        "bfd_enable": True,
        "vrfs": {
            "default": {"router_id": "172.27.252.0", "redistribute": {}, "neighbors": {
                "172.27.252.1": _have(remote_as=65015, update_source="172.27.252.0",
                                      activate=["evpn"], send_community={"evpn": "extended"}),
            }},
            "lab-blue": {"router_id": None, "redistribute": {"ipv4": ["static"]}, "neighbors": {
                "172.27.4.3": _have(remote_as=65015, update_source="172.27.4.2",
                                    activate=["ipv4"], next_hop_self=["ipv4"]),
                "2a02:20c8:5921:da10::3": _have(
                    remote_as=65015, update_source="2a02:20c8:5921:da10::2",
                    activate=["ipv6"], next_hop_self=["ipv6"],
                    send_community={"ipv6": "extended"}),
                "172.27.250.32": _have(remote_as=65020, activate=["ipv4"],
                                       route_maps={"ipv4": {"in": "GW-IN", "out": "BLUE-OUT"}}),
            }},
        },
    }


class TestBuildBgpDesiredNeighbors:
    """Tests for build_bgp_desired_neighbors"""

    def test_evpn_neighbor_with_vxlan(self):
        result = build_bgp_desired_neighbors(_LAB_SESSIONS, device_vxlan=True)
        n = result["default"]["172.27.252.1"]
        assert n["update_source"] == "172.27.252.0"
        assert list(n["afs"]) == ["evpn"]
        assert n["afs"]["evpn"]["send_community"] == "extended"
        assert n["afs"]["evpn"]["route_reflector_client"] is False

    def test_default_vrf_without_vxlan_is_address_family_neighbor(self):
        n = build_bgp_desired_neighbors(_LAB_SESSIONS)["default"]["172.27.252.1"]
        assert list(n["afs"]) == ["ipv4"]
        assert n["afs"]["ipv4"]["next_hop_self"] is True

    def test_evpn_ipv4_unicast(self):
        n = build_bgp_desired_neighbors(
            _LAB_SESSIONS, device_vxlan=True, evpn_ipv4_unicast=True)["default"]["172.27.252.1"]
        assert sorted(n["afs"]) == ["evpn", "ipv4"]

    def test_vrf_ibgp_ipv4_and_ipv6(self):
        vrf = build_bgp_desired_neighbors(_LAB_SESSIONS, device_vxlan=True)["lab-blue"]
        v4 = vrf["172.27.4.3"]
        assert v4["ibgp"] is True and v4["update_source"] == "172.27.4.2"
        assert v4["afs"]["ipv4"]["next_hop_self"] is True
        assert v4["afs"]["ipv4"]["send_community"] is None
        # NetBox address written uncompressed is normalised
        v6 = vrf["2a02:20c8:5921:da10::3"]
        assert v6["afs"]["ipv6"]["send_community"] == "extended"

    def test_vrf_ebgp_route_maps(self):
        n = build_bgp_desired_neighbors(_LAB_SESSIONS)["lab-blue"]["172.27.250.32"]
        assert n["ibgp"] is False
        assert n["update_source"] is None
        assert n["afs"]["ipv4"]["route_map_in"] == "GW-IN"
        assert n["afs"]["ipv4"]["route_map_out"] == "BLUE-OUT"
        assert n["afs"]["ipv4"]["next_hop_self"] is False

    def test_route_reflector_only_on_ibgp(self):
        vrf = build_bgp_desired_neighbors(_LAB_SESSIONS, route_reflector=True)["lab-blue"]
        assert vrf["172.27.4.3"]["afs"]["ipv4"]["route_reflector_client"] is True
        assert vrf["172.27.250.32"]["afs"]["ipv4"]["route_reflector_client"] is False

    def test_session_without_remote_address_skipped(self):
        bad = dict(_LAB_SESSIONS[0], remote_address=None)
        assert build_bgp_desired_neighbors([bad, None]) == {}

    def test_empty(self):
        assert build_bgp_desired_neighbors(None) == {}


class TestGetBgpNeighborChanges:
    """Tests for get_bgp_neighbor_changes"""

    _DESIRED = build_bgp_desired_neighbors(_LAB_SESSIONS, device_vxlan=True)

    def test_converged_device_needs_nothing(self):
        result = get_bgp_neighbor_changes(self._DESIRED, _converged_facts(), 65015, True)
        assert result == {"push": [], "remove": [], "source": "rest"}

    def test_without_facts_everything_pushed_nothing_removed(self):
        result = get_bgp_neighbor_changes(self._DESIRED, None, 65015, True)
        assert result["source"] == "none"
        assert len(result["push"]) == 4
        assert result["remove"] == []
        evpn = [p for p in result["push"] if p["vrf"] == "default"][0]
        assert evpn["commands"] == [
            "configure terminal", "router bgp 65015",
            "neighbor 172.27.252.1 remote-as 65015",
            "neighbor 172.27.252.1 update-source 172.27.252.0",
            "address-family l2vpn evpn",
            "neighbor 172.27.252.1 activate",
            "neighbor 172.27.252.1 send-community extended",
            "exit-address-family", "end",
        ]

    def test_only_missing_lines_pushed_in_vrf_context(self):
        facts = _converged_facts()
        facts["vrfs"]["lab-blue"]["neighbors"]["172.27.4.3"]["next_hop_self"] = []
        result = get_bgp_neighbor_changes(self._DESIRED, facts, 65015)
        assert result["push"] == [{
            "vrf": "lab-blue", "ip": "172.27.4.3", "name": "ao-01-ao-02-blue",
            "commands": [
                "configure terminal", "router bgp 65015", "vrf lab-blue",
                "address-family ipv4 unicast",
                "neighbor 172.27.4.3 next-hop-self",
                "exit-address-family", "exit-vrf", "end",
            ],
        }]

    def test_missing_route_map_is_pushed(self):
        facts = _converged_facts()
        facts["vrfs"]["lab-blue"]["neighbors"]["172.27.250.32"]["route_maps"] = {
            "ipv4": {"out": "BLUE-OUT"}}
        result = get_bgp_neighbor_changes(self._DESIRED, facts, 65015)
        assert "neighbor 172.27.250.32 route-map GW-IN in" in result["push"][0]["commands"]

    def test_send_community_both_satisfies_extended(self):
        facts = _converged_facts()
        facts["vrfs"]["default"]["neighbors"]["172.27.252.1"]["send_community"] = {"evpn": "both"}
        assert get_bgp_neighbor_changes(self._DESIRED, facts, 65015)["push"] == []

    def test_stale_route_map_removed_only_when_idempotent(self):
        sessions = [dict(_LAB_SESSIONS[3], import_policies=[])]
        desired = build_bgp_desired_neighbors(sessions)
        facts = {"vrfs": {"lab-blue": {"neighbors": {
            "172.27.250.32": _converged_facts()["vrfs"]["lab-blue"]["neighbors"]["172.27.250.32"]}}}}
        assert get_bgp_neighbor_changes(desired, facts, 65015)["push"] == []
        result = get_bgp_neighbor_changes(desired, facts, 65015, idempotent=True)
        assert "no neighbor 172.27.250.32 route-map GW-IN in" in result["push"][0]["commands"]

    def test_stale_route_reflector_client_removed(self):
        facts = _converged_facts()
        facts["vrfs"]["lab-blue"]["neighbors"]["172.27.4.3"]["route_reflector_client"] = ["ipv4"]
        result = get_bgp_neighbor_changes(self._DESIRED, facts, 65015, idempotent=True)
        assert "no neighbor 172.27.4.3 route-reflector-client" in result["push"][0]["commands"]

    def test_remote_as_change_pushed(self):
        facts = _converged_facts()
        facts["vrfs"]["lab-blue"]["neighbors"]["172.27.250.32"]["remote_as"] = 65099
        result = get_bgp_neighbor_changes(self._DESIRED, facts, 65015)
        assert "neighbor 172.27.250.32 remote-as 65020" in result["push"][0]["commands"]

    def test_stale_neighbors_removed_in_any_vrf(self):
        facts = _converged_facts()
        facts["vrfs"]["lab-blue"]["neighbors"]["10.9.9.9"] = _have(remote_as=65099)
        facts["vrfs"]["lab-red"] = {"neighbors": {
            "10.8.8.8": _have(remote_as=65015), "PEER-GROUP": _have()}}
        result = get_bgp_neighbor_changes(self._DESIRED, facts, 65015, idempotent=True)
        assert [(r["vrf"], r["ip"]) for r in result["remove"]] == [
            ("lab-blue", "10.9.9.9"), ("lab-red", "10.8.8.8")]
        assert result["remove"][1]["commands"] == [
            "configure terminal", "router bgp 65015", "vrf lab-red",
            "no neighbor 10.8.8.8", "exit-vrf", "end"]

    def test_stale_neighbors_kept_when_not_idempotent(self):
        facts = _converged_facts()
        facts["vrfs"]["lab-blue"]["neighbors"]["10.9.9.9"] = _have(remote_as=65099)
        assert get_bgp_neighbor_changes(self._DESIRED, facts, 65015)["remove"] == []


class TestGetBgpRedistributeChanges:
    """Tests for get_bgp_redistribute_changes"""

    _CTX = {"lab-blue": {"ipv4": ["static"], "ipv6": ["static"]}}

    def test_without_facts_all_added(self):
        result = get_bgp_redistribute_changes(self._CTX, None, True)
        assert result["source"] == "none"
        assert len(result["add"]) == 2 and result["remove"] == []

    def test_only_missing_added(self):
        facts = {"vrfs": {"lab-blue": {"redistribute": {"ipv4": ["static"]}}}}
        result = get_bgp_redistribute_changes(self._CTX, facts)
        assert result["add"] == [{"vrf": "lab-blue", "af": "ipv6", "protocol": "static"}]
        assert result["remove"] == []

    def test_stale_removed_when_idempotent(self):
        facts = {"vrfs": {
            "lab-blue": {"redistribute": {"ipv4": ["connected", "static"], "ipv6": ["static"]}},
            "default": {"redistribute": {"ipv4": ["local-loopback"]}},
        }}
        result = get_bgp_redistribute_changes(self._CTX, facts, True)
        assert result["add"] == []
        assert result["remove"] == [
            {"vrf": "default", "af": "ipv4", "protocol": "local-loopback"},
            {"vrf": "lab-blue", "af": "ipv4", "protocol": "connected"},
        ]
        assert get_bgp_redistribute_changes(self._CTX, facts, False)["remove"] == []


# ---------------------------------------------------------------------------
# Running-config based change detection (prefix lists, route-maps, options)
# ---------------------------------------------------------------------------

# Trimmed from ao-02 'show running-config' (AOS-CX 10.16).
_POLICY_RUNNING_CONFIG = """bfd
ip prefix-list LAB-BLUE-IPV4 seq 10 permit 172.27.4.0/24
ipv6 prefix-list LAB-BLUE-IPV6 seq 10 permit 2a02:20c8:5921:da10::/60
ip prefix-list LAB-GW-IPV4 seq 10 permit 0.0.0.0/0
ip prefix-list LAB-GW-IPV4 seq 15 permit 172.16.3.0/24
route-map LAB-BLUE-IPV4-OUT-02 permit seq 10
     match ip address prefix-list LAB-BLUE-IPV4
     set as-path prepend 65015 65015
route-map LAB-GW-IPV6-IN-02 permit seq 10
     match ipv6 address prefix-list LAB-GW-IPV6
     set local-preference 200
router bgp 65015
    bgp router-id 172.27.252.1
!
    vrf lab-blue
        neighbor 172.27.250.34 remote-as 65020
        neighbor 172.27.250.34 fall-over bfd
        neighbor 2a02:20c8:5921:da1f::2 remote-as 65020
        address-family ipv4 unicast
            neighbor 172.27.250.34 soft-reconfiguration inbound
            neighbor 172.27.250.34 activate
        exit-address-family
!
"""

_POLICY_DATA = {
    "prefix_lists": [
        {"name": "LAB-BLUE-IPV4", "af": "ipv4",
         "rules": [{"index": 10, "action": "permit", "prefix": "172.27.4.0/24"}]},
        {"name": "LAB-BLUE-IPV6", "af": "ipv6",
         "rules": [{"index": 10, "action": "permit",
                    "prefix": "2a02:20c8:5921:da10:0::/60"}]},
        {"name": "LAB-GW-IPV4", "af": "ipv4",
         "rules": [{"index": 10, "action": "permit", "prefix": "0.0.0.0/0"},
                   {"index": 15, "action": "permit", "prefix": "172.16.3.0/24"}]},
    ],
    "route_map_rules": [
        {"name": "LAB-BLUE-IPV4-OUT-02", "index": 10, "action": "permit",
         "commands": ["route-map LAB-BLUE-IPV4-OUT-02 permit seq 10",
                      "match ip address prefix-list LAB-BLUE-IPV4",
                      "set as-path prepend 65015 65015"]},
        {"name": "LAB-GW-IPV6-IN-02", "index": 10, "action": "permit",
         "commands": ["route-map LAB-GW-IPV6-IN-02 permit seq 10",
                      "match ipv6 address prefix-list LAB-GW-IPV6",
                      "set local-preference 200"]},
    ],
}


def _policy_facts(**overrides):
    """aoscx_bgp_facts policy part built from trimmed ao-02 REST payloads."""
    prefix_lists = {
        "LAB-BLUE-IPV4": {"address_family": "ipv4", "name": "LAB-BLUE-IPV4",
                          "prefix_list_entries": {"10": {
                              "action": "permit", "ge": None, "le": None,
                              "preference": 10, "prefix": "172.27.4.0/24"}}},
        "LAB-BLUE-IPV6": {"address_family": "ipv6", "name": "LAB-BLUE-IPV6",
                          "prefix_list_entries": {"10": {
                              "action": "permit", "ge": None, "le": None,
                              "preference": 10,
                              "prefix": "2a02:20c8:5921:da10::/60"}}},
        "LAB-GW-IPV4": {"address_family": "ipv4", "name": "LAB-GW-IPV4",
                        "prefix_list_entries": {
                            "10": {"action": "permit", "ge": None, "le": None,
                                   "preference": 10, "prefix": "0.0.0.0/0"},
                            "15": {"action": "permit", "ge": None, "le": None,
                                   "preference": 15, "prefix": "172.16.3.0/24"}}},
    }
    route_maps = {
        "LAB-BLUE-IPV4-OUT-02": {"name": "LAB-BLUE-IPV4-OUT-02",
                                 "route_map_entries": {"10": {
                                     "action": "permit", "preference": 10,
                                     "match_ipv4_prefix_list": {
                                         "LAB-BLUE-IPV4": "/rest/v10.16/x"},
                                     "match_ipv6_prefix_list": None,
                                     "set": {"as_path_prepend": "65015 65015"}}}},
        "LAB-GW-IPV6-IN-02": {"name": "LAB-GW-IPV6-IN-02",
                              "route_map_entries": {"10": {
                                  "action": "permit", "preference": 10,
                                  "match_ipv4_prefix_list": None,
                                  "match_ipv6_prefix_list": {
                                      "LAB-GW-IPV6": "/rest/v10.16/x"},
                                  "set": {"local_preference": 200}}}},
    }
    prefix_lists.update(overrides.get("prefix_lists", {}))
    route_maps.update(overrides.get("route_maps", {}))
    return rest_api_to_aoscx_bgp({}, None, None, prefix_lists, route_maps)


class TestGetBgpPolicyChanges:
    """Tests for get_bgp_policy_changes"""

    def test_converged_device_needs_nothing(self):
        result = get_bgp_policy_changes(_POLICY_DATA, _policy_facts())
        assert result == {"prefix_lists": [], "route_map_rules": [],
                          "source": "rest"}

    def test_no_facts_returns_everything(self):
        for facts in (None, {}, {"prefix_lists": None, "route_maps": None}):
            result = get_bgp_policy_changes(_POLICY_DATA, facts)
            assert result["source"] == "none"
            assert result["prefix_lists"] == _POLICY_DATA["prefix_lists"]
            assert result["route_map_rules"] == _POLICY_DATA["route_map_rules"]

    def test_none_inputs(self):
        assert get_bgp_policy_changes(None, None) == {
            "prefix_lists": [], "route_map_rules": [], "source": "none"}

    def test_missing_prefix_list_entry_only(self):
        facts = _policy_facts()
        del facts["prefix_lists"]["LAB-GW-IPV4"]["entries"][15]
        result = get_bgp_policy_changes(_POLICY_DATA, facts)
        assert result["prefix_lists"] == [
            {"name": "LAB-GW-IPV4", "af": "ipv4",
             "rules": [{"index": 15, "action": "permit",
                        "prefix": "172.16.3.0/24"}]}]
        assert result["route_map_rules"] == []

    def test_missing_prefix_list(self):
        facts = _policy_facts()
        del facts["prefix_lists"]["LAB-BLUE-IPV4"]
        result = get_bgp_policy_changes(_POLICY_DATA, facts)
        assert [p["name"] for p in result["prefix_lists"]] == ["LAB-BLUE-IPV4"]

    def test_changed_action_is_pushed(self):
        facts = _policy_facts()
        facts["prefix_lists"]["LAB-BLUE-IPV4"]["entries"][10]["action"] = "deny"
        result = get_bgp_policy_changes(_POLICY_DATA, facts)
        assert [p["name"] for p in result["prefix_lists"]] == ["LAB-BLUE-IPV4"]

    def test_ge_le_on_device_is_not_in_sync(self):
        facts = _policy_facts()
        facts["prefix_lists"]["LAB-GW-IPV4"]["entries"][10]["le"] = 32
        result = get_bgp_policy_changes(_POLICY_DATA, facts)
        assert result["prefix_lists"][0]["rules"] == [
            {"index": 10, "action": "permit", "prefix": "0.0.0.0/0"}]

    def test_ipv6_prefix_is_normalised(self):
        # NetBox side is written '2a02:20c8:5921:da10:0::/60'.
        result = get_bgp_policy_changes(_POLICY_DATA, _policy_facts())
        assert not any(p["name"] == "LAB-BLUE-IPV6"
                       for p in result["prefix_lists"])

    def test_same_name_other_af_does_not_match(self):
        facts = _policy_facts()
        facts["prefix_lists"]["LAB-BLUE-IPV6"]["af"] = "ipv4"
        result = get_bgp_policy_changes(_POLICY_DATA, facts)
        assert [p["name"] for p in result["prefix_lists"]] == ["LAB-BLUE-IPV6"]

    def test_missing_route_map_set_line(self):
        facts = _policy_facts()
        facts["route_maps"]["LAB-GW-IPV6-IN-02"][10]["lines"].remove(
            "set local-preference 200")
        result = get_bgp_policy_changes(_POLICY_DATA, facts)
        assert [r["name"] for r in result["route_map_rules"]] == [
            "LAB-GW-IPV6-IN-02"]

    def test_wrong_set_value_is_pushed(self):
        facts = _policy_facts(route_maps={"LAB-GW-IPV6-IN-02": {
            "route_map_entries": {"10": {
                "action": "permit",
                "match_ipv6_prefix_list": {"LAB-GW-IPV6": "/x"},
                "set": {"local_preference": 300}}}}})
        result = get_bgp_policy_changes(_POLICY_DATA, facts)
        assert [r["name"] for r in result["route_map_rules"]] == [
            "LAB-GW-IPV6-IN-02"]

    def test_missing_route_map_sequence(self):
        facts = _policy_facts()
        facts["route_maps"]["LAB-BLUE-IPV4-OUT-02"] = {
            20: facts["route_maps"]["LAB-BLUE-IPV4-OUT-02"][10]}
        result = get_bgp_policy_changes(_POLICY_DATA, facts)
        assert [r["name"] for r in result["route_map_rules"]] == [
            "LAB-BLUE-IPV4-OUT-02"]

    def test_extra_route_map_line_is_ignored(self):
        facts = _policy_facts()
        facts["route_maps"]["LAB-GW-IPV6-IN-02"][10]["lines"].append(
            "set metric 5")
        result = get_bgp_policy_changes(_POLICY_DATA, facts)
        assert result["route_map_rules"] == []


class TestGetMissingBgpNeighborOptions:
    """Tests for get_missing_bgp_neighbor_options"""

    _SESSIONS = [
        _enriched_session("172.27.250.34", vrf="lab-blue", af="ipv4"),
        _enriched_session("2a02:20c8:5921:da1f::2", vrf="lab-blue", af="ipv6"),
    ]
    _OPTIONS = {
        "172.27.250.34": {"general": ["fall-over bfd"],
                          "ipv4": ["soft-reconfiguration inbound"]},
        "2a02:20c8:5921:da1f::2": {"general": ["fall-over bfd"]},
    }

    def test_only_missing_options_returned(self):
        result = get_missing_bgp_neighbor_options(
            self._OPTIONS, self._SESSIONS, _POLICY_RUNNING_CONFIG, 65015)
        assert result == [{"vrf": "lab-blue", "af": None,
                           "neighbor_ip": "2a02:20c8:5921:da1f::2",
                           "command": "fall-over bfd"}]

    def test_everything_present(self):
        options = {"172.27.250.34": self._OPTIONS["172.27.250.34"]}
        assert get_missing_bgp_neighbor_options(
            options, self._SESSIONS, _POLICY_RUNNING_CONFIG, 65015) == []

    def test_no_running_config_returns_all_desired(self):
        result = get_missing_bgp_neighbor_options(
            self._OPTIONS, self._SESSIONS, "", 65015)
        assert len(result) == 3

    def test_af_scope_must_match(self):
        options = {"172.27.250.34": {"general": ["soft-reconfiguration inbound"]}}
        result = get_missing_bgp_neighbor_options(
            options, self._SESSIONS, _POLICY_RUNNING_CONFIG, 65015)
        assert len(result) == 1

    def test_empty_options(self):
        assert get_missing_bgp_neighbor_options(
            {}, self._SESSIONS, _POLICY_RUNNING_CONFIG, 65015) == []


# ---------------------------------------------------------------------------
# netbox_bgp_graphql_to_rest
# ---------------------------------------------------------------------------

def _gql_prefix_list(pl_id, name, rules):
    return {"id": str(pl_id), "name": name, "prefrules": rules}


def _gql_session(sid, name, status="active", import_policies=None, export_policies=None):
    """A session as netbox-bgp's GraphQL returns it: ids and ASNs as strings."""
    return {
        "id": str(sid),
        "name": name,
        "description": "",
        "status": status,
        "device": {"id": "444", "name": "ao-01"},
        "local_address": {"id": "1832", "address": "172.27.250.33/31"},
        "remote_address": {"id": "1831", "address": "172.27.250.32/31"},
        "local_as": {"id": "11", "asn": "65015"},
        "remote_as": {"id": "12", "asn": "65020"},
        "import_policies": import_policies or [],
        "export_policies": export_policies or [],
    }


_GQL_PL_BLUE = _gql_prefix_list(2, "LAB-BLUE-IPV4", [
    {"id": "3", "index": "20", "action": "deny",
     "prefix": None, "prefix_custom": "10.0.0.0/8"},
    {"id": "2", "index": "10", "action": "permit",
     "prefix": {"id": "756", "prefix": "172.27.4.0/24"}, "prefix_custom": None},
])
_GQL_PL_BLUE6 = _gql_prefix_list(5, "LAB-BLUE-IPV6", [
    {"id": "9", "index": "10", "action": "permit",
     "prefix": {"id": "900", "prefix": "2001:db8::/48"}, "prefix_custom": None},
])
_GQL_POLICY_OUT = {
    "id": "2", "name": "LAB-BLUE-OUT-01",
    "rules": [
        {"id": "21", "index": "20", "action": "deny", "set_actions": None,
         "match_ip_address": [], "match_ipv6_address": [_GQL_PL_BLUE6]},
        {"id": "20", "index": "10", "action": "permit",
         "set_actions": {"as-path prepend": [65015]},
         "match_ip_address": [_GQL_PL_BLUE], "match_ipv6_address": []},
    ],
}
_GQL_POLICY_IN = {
    "id": "4", "name": "LAB-BLUE-IN-01",
    "rules": [
        {"id": "40", "index": "10", "action": "permit",
         "set_actions": {"local-preference": 300},
         "match_ip_address": [_GQL_PL_BLUE], "match_ipv6_address": []},
    ],
}


def _gql_response(*sessions):
    return {"data": {"netbox_bgp_session_list": list(sessions)}}


class TestNetboxBgpGraphqlToRest:
    """Tests for netbox_bgp_graphql_to_rest"""

    def test_session_in_rest_shape(self):
        result = netbox_bgp_graphql_to_rest(_gql_response(
            _gql_session(13, "ao-01-ao-02", export_policies=[_GQL_POLICY_OUT])))
        assert result["available"] is True
        assert result["errors"] == []
        assert result["sessions"] == [{
            "id": 13,
            "name": "ao-01-ao-02",
            "description": "",
            "status": {"value": "active"},
            "device": {"id": 444, "name": "ao-01"},
            "local_address": {"id": 1832, "address": "172.27.250.33/31"},
            "remote_address": {"id": 1831, "address": "172.27.250.32/31"},
            "local_as": {"id": 11, "asn": 65015},
            "remote_as": {"id": 12, "asn": 65020},
            "import_policies": [],
            "export_policies": [{"id": 2, "name": "LAB-BLUE-OUT-01"}],
        }]

    def test_rules_flattened_deduplicated_and_ordered(self):
        """Policies and prefix lists shared by sessions appear once, in name
        order, with rules in index order (the REST endpoints' ordering)."""
        result = netbox_bgp_graphql_to_rest(_gql_response(
            _gql_session(13, "s1", import_policies=[_GQL_POLICY_IN],
                         export_policies=[_GQL_POLICY_OUT]),
            _gql_session(14, "s2", export_policies=[_GQL_POLICY_OUT])))
        assert [(r["routing_policy"]["name"], r["index"]) for r in result["policy_rules"]] == [
            ("LAB-BLUE-IN-01", 10), ("LAB-BLUE-OUT-01", 10), ("LAB-BLUE-OUT-01", 20)]
        assert result["policy_rules"][1] == {
            "id": 20, "index": 10, "action": "permit",
            "routing_policy": {"id": 2, "name": "LAB-BLUE-OUT-01"},
            "set_actions": {"as-path prepend": [65015]},
            "match_ip_address": [{"id": 2, "name": "LAB-BLUE-IPV4"}],
            "match_ipv6_address": [],
        }
        assert [(r["prefix_list"]["name"], r["index"]) for r in result["prefix_list_rules"]] == [
            ("LAB-BLUE-IPV4", 10), ("LAB-BLUE-IPV4", 20), ("LAB-BLUE-IPV6", 10)]
        assert result["prefix_list_rules"][0]["prefix"] == {"id": 756, "prefix": "172.27.4.0/24"}
        assert result["prefix_list_rules"][1]["prefix"] is None
        assert result["prefix_list_rules"][1]["prefix_custom"] == "10.0.0.0/8"

    def test_output_feeds_collect_ebgp_vrf_policy_config(self):
        result = netbox_bgp_graphql_to_rest(_gql_response(
            _gql_session(13, "s1", import_policies=[_GQL_POLICY_IN],
                         export_policies=[_GQL_POLICY_OUT])))
        sessions = [dict(s, _vrf="lab-blue", _af="ipv4") for s in result["sessions"]]
        policy = collect_ebgp_vrf_policy_config(
            sessions, result["policy_rules"], result["prefix_list_rules"])
        assert {pl["name"]: (pl["af"], [r["prefix"] for r in pl["rules"]])
                for pl in policy["prefix_lists"]} == {
            "LAB-BLUE-IPV4": ("ipv4", ["172.27.4.0/24", "10.0.0.0/8"]),
            "LAB-BLUE-IPV6": ("ipv6", ["2001:db8::/48"]),
        }
        assert [r["commands"] for r in policy["route_map_rules"]] == [
            ["route-map LAB-BLUE-IN-01 permit seq 10",
             "match ip address prefix-list LAB-BLUE-IPV4",
             "set local-preference 300"],
            ["route-map LAB-BLUE-OUT-01 permit seq 10",
             "match ip address prefix-list LAB-BLUE-IPV4",
             "set as-path prepend 65015"],
            ["route-map LAB-BLUE-OUT-01 deny seq 20",
             "match ipv6 address prefix-list LAB-BLUE-IPV6"],
        ]

    def test_no_sessions(self):
        result = netbox_bgp_graphql_to_rest(_gql_response())
        assert result == {"available": True, "errors": [], "sessions": [],
                          "policy_rules": [], "prefix_list_rules": []}

    def test_plugin_not_installed(self):
        """NetBox without netbox-bgp has no netbox_bgp_session_list field."""
        result = netbox_bgp_graphql_to_rest({"data": None, "errors": [{
            "message": "Cannot query field 'netbox_bgp_session_list' on type 'Query'."}]})
        assert result["available"] is False
        assert result["errors"] == []
        assert result["sessions"] == []

    def test_other_graphql_errors_are_returned(self):
        """GraphQL errors arrive with HTTP 200; they must not read as 'no BGP'."""
        result = netbox_bgp_graphql_to_rest({"data": None, "errors": [{
            "message": "Cannot query field 'bogus' on type 'BGPSessionType'."}]})
        assert result["available"] is True
        assert result["errors"] == ["Cannot query field 'bogus' on type 'BGPSessionType'."]
        assert result["sessions"] == []

    @pytest.mark.parametrize("response", [None, "", []])
    def test_non_json_response_is_an_error(self, response):
        result = netbox_bgp_graphql_to_rest(response)
        assert result["errors"]
        assert result["sessions"] == []
