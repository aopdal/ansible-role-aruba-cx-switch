"""
Unit tests for BGP filter functions
"""
import pytest
from netbox_filters_lib.bgp_filters import (
    get_bgp_session_vrf_info,
    normalize_routing_plugin_peers,
    collect_ebgp_vrf_policy_config,
    collect_ebgp_vrf_policy_config_routing,
)


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


# ===========================================================================
# Helpers for normalize_routing_plugin_peers
# ===========================================================================

def _router(router_id, asn, device_name):
    """Build a minimal bgp/router object."""
    return {
        "id": router_id,
        "display": f"{device_name}:AS{asn}",
        "name": None,
        "asn": {"id": 1, "asn": asn},
        "assigned_object": {
            "id": router_id * 100,
            "name": device_name,
        },
    }


def _scope(scope_id, router_id, asn, device_name, vrf=None):
    """Build a minimal bgp/scope object."""
    vrf_obj = {"id": 1, "name": vrf} if vrf else None
    return {
        "id": scope_id,
        "display": f"{device_name}:AS{asn}: {'Global VRF' if not vrf else vrf}",
        "router": {
            "id": router_id,
            "asn": {"id": 1, "asn": asn},
            "assigned_object": {"id": router_id * 100, "name": device_name},
        },
        "vrf": vrf_obj,
    }


def _peer(peer_id, scope_id, src_addr, peer_addr, local_asn, remote_asn,
          name="peer", enabled=True):
    """Build a minimal bgp/peer object."""
    return {
        "id": peer_id,
        "name": name,
        "scope": {"id": scope_id},
        "source": {"address": src_addr},
        "peer": {"address": peer_addr},
        "local_as": {"asn": local_asn},
        "remote_as": {"asn": remote_asn},
        "status": None,
        "enabled": enabled,
    }


def _peer_af(paf_id, peer_id, af_id, rm_in=None, rm_out=None):
    """Build a minimal bgp/peer-address-family object."""
    return {
        "id": paf_id,
        "assigned_object_type": "netbox_routing.bgppeer",
        "assigned_object_id": peer_id,
        "address_family": af_id,
        "routemap_in": rm_in,
        "routemap_out": rm_out,
    }


def _route_map(rm_id, name):
    """Build a minimal objects/route-map object."""
    return {"id": rm_id, "name": name, "display": name}


class TestNormalizeRoutingPluginPeers:
    """Tests for normalize_routing_plugin_peers"""

    def _call(self, routers, scopes, peers, afs=None, peer_afs=None,
              route_maps=None, device="ao-01"):
        return normalize_routing_plugin_peers(
            routers, scopes, peers,
            afs or [],
            peer_afs or [],
            route_maps or [],
            device,
        )

    def test_empty_inputs_returns_empty(self):
        result = self._call([], [], [])
        assert result == []

    def test_none_inputs_returns_empty(self):
        result = self._call(None, None, None)
        assert result == []

    def test_unknown_device_returns_empty(self):
        routers = [_router(1, 65015, "other-device")]
        scopes = [_scope(1, 1, 65015, "other-device")]
        peers = [_peer(1, 1, "10.0.0.1/32", "10.0.0.2/32", 65015, 65015)]
        result = self._call(routers, scopes, peers, device="ao-01")
        assert result == []

    def test_basic_peer_normalised_correctly(self):
        """Single global-VRF peer produces correct compat shape."""
        routers = [_router(1, 65015, "ao-01")]
        scopes = [_scope(1, 1, 65015, "ao-01")]
        peers = [_peer(1, 1, "172.27.252.0/32", "172.27.252.1/32", 65015, 65015,
                       name="ao-01-ao-02")]
        result = self._call(routers, scopes, peers)

        assert len(result) == 1
        p = result[0]
        assert p["name"] == "ao-01-ao-02"
        assert p["local_address"]["address"] == "172.27.252.0/32"
        assert p["remote_address"]["address"] == "172.27.252.1/32"
        assert p["local_as"]["asn"] == 65015
        assert p["remote_as"]["asn"] == 65015
        assert p["_vrf"] == "default"
        assert p["_af"] == "ipv4"
        assert p["status"]["value"] == "active"

    def test_ipv6_peer_gets_af_ipv6(self):
        """Peer with IPv6 remote address gets _af='ipv6'."""
        routers = [_router(1, 65015, "ao-01")]
        scopes = [_scope(1, 1, 65015, "ao-01")]
        peers = [_peer(1, 1, "2a02::/64", "2a02::1/64", 65015, 65020)]
        result = self._call(routers, scopes, peers)
        assert result[0]["_af"] == "ipv6"

    def test_vrf_scope_sets_vrf_name(self):
        """Scope with explicit VRF sets _vrf to the VRF name."""
        routers = [_router(1, 65015, "ao-01")]
        scopes = [_scope(1, 1, 65015, "ao-01", vrf="lab-blue")]
        peers = [_peer(1, 1, "172.27.4.1/27", "172.27.4.2/27", 65015, 65020)]
        result = self._call(routers, scopes, peers)
        assert result[0]["_vrf"] == "lab-blue"

    def test_builtin_vrf_normalised_to_default(self):
        """Scope with 'mgmt' VRF is normalised to 'default'."""
        routers = [_router(1, 65015, "ao-01")]
        scopes = [_scope(1, 1, 65015, "ao-01", vrf="mgmt")]
        peers = [_peer(1, 1, "10.0.0.1/32", "10.0.0.2/32", 65015, 65015)]
        result = self._call(routers, scopes, peers)
        assert result[0]["_vrf"] == "default"

    def test_disabled_peer_is_excluded(self):
        """Peer with enabled=False is not included in the result."""
        routers = [_router(1, 65015, "ao-01")]
        scopes = [_scope(1, 1, 65015, "ao-01")]
        peers = [
            _peer(1, 1, "10.0.0.1/32", "10.0.0.2/32", 65015, 65015, enabled=False),
            _peer(2, 1, "10.0.0.3/32", "10.0.0.4/32", 65015, 65015, enabled=True),
        ]
        result = self._call(routers, scopes, peers)
        assert len(result) == 1
        assert result[0]["local_address"]["address"] == "10.0.0.3/32"

    def test_routemaps_resolved_from_peer_af(self):
        """routemap_in / routemap_out are resolved to names via route_maps list."""
        routers = [_router(1, 65015, "ao-01")]
        scopes = [_scope(1, 1, 65015, "ao-01")]
        peers = [_peer(1, 1, "10.0.0.1/27", "10.0.0.2/27", 65015, 65020)]
        peer_afs = [_peer_af(1, 1, af_id=77, rm_in=19, rm_out=20)]
        rms = [_route_map(19, "LAB-GW-IPV4-IN-01"), _route_map(20, "LAB-BLUE-IPV4-OUT-01")]

        result = self._call(routers, scopes, peers, peer_afs=peer_afs, route_maps=rms)
        p = result[0]
        assert len(p["import_policies"]) == 1
        assert p["import_policies"][0]["name"] == "LAB-GW-IPV4-IN-01"
        assert len(p["export_policies"]) == 1
        assert p["export_policies"][0]["name"] == "LAB-BLUE-IPV4-OUT-01"

    def test_peer_without_routemaps_has_empty_policies(self):
        """Peer with no peer-address-family entries gets empty policy lists."""
        routers = [_router(1, 65015, "ao-01")]
        scopes = [_scope(1, 1, 65015, "ao-01")]
        peers = [_peer(1, 1, "10.0.0.1/32", "10.0.0.2/32", 65015, 65015)]
        result = self._call(routers, scopes, peers)
        assert result[0]["import_policies"] == []
        assert result[0]["export_policies"] == []

    def test_multiple_peers_for_same_device(self):
        """All peers in the same scope are included."""
        routers = [_router(1, 65015, "ao-01")]
        scopes = [_scope(1, 1, 65015, "ao-01")]
        peers = [
            _peer(1, 1, "10.0.0.1/32", "10.0.0.2/32", 65015, 65015, name="p1"),
            _peer(2, 1, "10.0.0.3/32", "10.0.0.4/32", 65015, 65020, name="p2"),
        ]
        result = self._call(routers, scopes, peers)
        assert len(result) == 2
        names = {p["name"] for p in result}
        assert names == {"p1", "p2"}

    def test_peer_af_for_other_device_not_applied(self):
        """peer-address-family belonging to a different peer is ignored."""
        routers = [_router(1, 65015, "ao-01")]
        scopes = [_scope(1, 1, 65015, "ao-01")]
        peers = [_peer(1, 1, "10.0.0.1/27", "10.0.0.2/27", 65015, 65020)]
        # peer_id=99 does not belong to this device
        peer_afs = [_peer_af(1, 99, af_id=77, rm_in=19, rm_out=20)]
        rms = [_route_map(19, "OTHER-IN"), _route_map(20, "OTHER-OUT")]
        result = self._call(routers, scopes, peers, peer_afs=peer_afs, route_maps=rms)
        assert result[0]["import_policies"] == []
        assert result[0]["export_policies"] == []

    def test_non_bgppeer_paf_is_ignored(self):
        """peer-address-family with type bgppeertemplate is not applied to peers."""
        routers = [_router(1, 65015, "ao-01")]
        scopes = [_scope(1, 1, 65015, "ao-01")]
        peers = [_peer(1, 1, "10.0.0.1/27", "10.0.0.2/27", 65015, 65020)]
        peer_afs = [
            {
                "id": 1,
                "assigned_object_type": "netbox_routing.bgppeertemplate",
                "assigned_object_id": 1,
                "address_family": 75,
                "routemap_in": 19,
                "routemap_out": 20,
            }
        ]
        rms = [_route_map(19, "TMPL-IN"), _route_map(20, "TMPL-OUT")]
        result = self._call(routers, scopes, peers, peer_afs=peer_afs, route_maps=rms)
        assert result[0]["import_policies"] == []

    def test_global_vrf_peers_default_vrf(self):
        """Scope with null VRF produces _vrf='default' (EVPN/underlay)."""
        routers = [_router(1, 65005, "z13-cx1")]
        scopes = [_scope(1, 1, 65005, "z13-cx1")]  # vrf=None
        peers = [_peer(1, 1, "172.20.1.1/32", "172.20.1.3/32", 65005, 65005)]
        result = self._call(routers, scopes, peers, device="z13-cx1")
        assert result[0]["_vrf"] == "default"

    def test_multiple_scopes_different_vrfs(self):
        """Device with two scopes (global + VRF) yields correct _vrf per peer."""
        routers = [_router(1, 65015, "ao-01")]
        scopes = [
            _scope(1, 1, 65015, "ao-01"),           # global, vrf=None
            _scope(2, 1, 65015, "ao-01", vrf="blue"),  # VRF blue
        ]
        peers = [
            _peer(1, 1, "172.27.252.0/32", "172.27.252.1/32", 65015, 65015,
                  name="evpn-peer"),
            _peer(2, 2, "172.27.4.1/27", "172.27.4.2/27", 65015, 65020,
                  name="vrf-peer"),
        ]
        result = self._call(routers, scopes, peers)
        by_name = {p["name"]: p for p in result}
        assert by_name["evpn-peer"]["_vrf"] == "default"
        assert by_name["vrf-peer"]["_vrf"] == "blue"


# ===========================================================================
# Helpers for collect_ebgp_vrf_policy_config_routing
# ===========================================================================

def _routing_session(name, import_rms=None, export_rms=None, vrf="lab-blue", af="ipv4"):
    """Build a minimal normalized peer (output of normalize_routing_plugin_peers)."""
    return {
        "name": name,
        "local_as": {"asn": 65015},
        "remote_as": {"asn": 65020},
        "local_address": {"address": "10.0.0.1/30"},
        "remote_address": {"address": "10.0.0.2/30"},
        "_vrf": vrf,
        "_af": af,
        "import_policies": [{"id": None, "name": n} for n in (import_rms or [])],
        "export_policies": [{"id": None, "name": n} for n in (export_rms or [])],
    }


def _rm_entry(rm_id, rm_name, sequence, action="permit",
              match_pls=None, set_prepend=None, set_local_pref=None):
    """Build a route-map-entry object (netbox-routing format)."""
    set_dict = {}
    if set_prepend is not None:
        set_dict["as-path prepend"] = set_prepend if isinstance(set_prepend, list) else [set_prepend]
    if set_local_pref is not None:
        set_dict["local-preference"] = set_local_pref

    return {
        "id": rm_id,
        "route_map": {"id": rm_id, "display": rm_name, "name": rm_name},
        "sequence": sequence,
        "action": action,
        "match_prefix_list": [
            {"id": i + 1, "display": pl, "name": pl}
            for i, pl in enumerate(match_pls or [])
        ],
        "set": set_dict,
    }


def _pl_entry(pl_id, pl_name, sequence, action, prefix):
    """Build a prefix-list-entry object (netbox-routing format)."""
    return {
        "id": pl_id,
        "prefix_list": {"id": pl_id, "name": pl_name, "display": pl_name},
        "sequence": sequence,
        "action": action,
        "assigned_prefix_type": "ipam.prefix",
        "assigned_prefix": {"id": pl_id * 100, "prefix": prefix, "display": prefix},
        "le": None,
        "ge": None,
    }


class TestCollectEbgpVrfPolicyConfigRouting:
    """Tests for collect_ebgp_vrf_policy_config_routing"""

    def test_empty_inputs_returns_empty(self):
        result = collect_ebgp_vrf_policy_config_routing([], [], [])
        assert result == {"prefix_lists": [], "route_map_rules": []}

    def test_none_inputs_returns_empty(self):
        result = collect_ebgp_vrf_policy_config_routing(None, None, None)
        assert result == {"prefix_lists": [], "route_map_rules": []}

    def test_session_without_policies_returns_empty(self):
        session = _routing_session("s1")
        result = collect_ebgp_vrf_policy_config_routing([session], [], [])
        assert result == {"prefix_lists": [], "route_map_rules": []}

    def test_export_policy_with_ipv4_prefix_list(self):
        """IPv4 route-map with prefix-list match and as-path prepend."""
        session = _routing_session("s1", export_rms=["LAB-BLUE-IPV4-OUT-01"])
        rm_entries = [
            _rm_entry(20, "LAB-BLUE-IPV4-OUT-01", 10,
                      match_pls=["LAB-BLUE-IPV4"], set_prepend=65015)
        ]
        pl_entries = [_pl_entry(25, "LAB-BLUE-IPV4", 10, "permit", "172.27.4.0/24")]

        result = collect_ebgp_vrf_policy_config_routing([session], rm_entries, pl_entries)

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
        assert pl["af"] == "ipv4"
        assert pl["rules"][0] == {"index": 10, "action": "permit", "prefix": "172.27.4.0/24"}

    def test_import_policy_with_ipv4_default_route(self):
        """Import route-map with 0.0.0.0/0 via custom prefix."""
        session = _routing_session("s1", import_rms=["LAB-GW-IPV4-IN-01"])
        rm_entries = [
            _rm_entry(19, "LAB-GW-IPV4-IN-01", 10,
                      match_pls=["LAB-GW-IPV4"], set_local_pref=300)
        ]
        pl_entries = [
            {
                "id": 12,
                "prefix_list": {"id": 29, "name": "LAB-GW-IPV4"},
                "sequence": 10,
                "action": "permit",
                "assigned_prefix_type": "netbox_routing.customprefix",
                "assigned_prefix": {"prefix": "0.0.0.0/0"},
                "le": None,
                "ge": None,
            }
        ]

        result = collect_ebgp_vrf_policy_config_routing([session], rm_entries, pl_entries)

        rm = result["route_map_rules"][0]
        assert rm["name"] == "LAB-GW-IPV4-IN-01"
        assert "match ip address prefix-list LAB-GW-IPV4" in rm["commands"]
        assert "set local-preference 300" in rm["commands"]

        pl = result["prefix_lists"][0]
        assert pl["af"] == "ipv4"
        assert pl["rules"][0]["prefix"] == "0.0.0.0/0"

    def test_ipv6_prefix_list_gets_ipv6_match_command(self):
        """Prefix-list with IPv6 entries uses 'match ipv6 address prefix-list'."""
        session = _routing_session("s1", export_rms=["LAB-BLUE-IPV6-OUT-01"], af="ipv6")
        rm_entries = [
            _rm_entry(28, "LAB-BLUE-IPV6-OUT-01", 10,
                      match_pls=["LAB-BLUE-IPV6"], set_prepend=65015)
        ]
        pl_entries = [
            _pl_entry(26, "LAB-BLUE-IPV6", 10, "permit", "2a02:20c8:5921:da10::/60")
        ]

        result = collect_ebgp_vrf_policy_config_routing([session], rm_entries, pl_entries)

        rm = result["route_map_rules"][0]
        assert "match ipv6 address prefix-list LAB-BLUE-IPV6" in rm["commands"]
        assert "match ip address prefix-list LAB-BLUE-IPV6" not in rm["commands"]

        pl = result["prefix_lists"][0]
        assert pl["af"] == "ipv6"
        assert pl["rules"][0]["prefix"] == "2a02:20c8:5921:da10::/60"

    def test_ipv6_default_route(self):
        """IPv6 default route '::/0' is recognised as IPv6."""
        session = _routing_session("s1", import_rms=["LAB-GW-IPV6-IN-01"])
        rm_entries = [
            _rm_entry(31, "LAB-GW-IPV6-IN-01", 10,
                      match_pls=["LAB-GW-IPV6"], set_local_pref=300)
        ]
        pl_entries = [_pl_entry(30, "LAB-GW-IPV6", 10, "permit", "::/0")]

        result = collect_ebgp_vrf_policy_config_routing([session], rm_entries, pl_entries)

        pl = result["prefix_lists"][0]
        assert pl["af"] == "ipv6"
        assert pl["rules"][0]["prefix"] == "::/0"
        commands = result["route_map_rules"][0]["commands"]
        assert "match ipv6 address prefix-list LAB-GW-IPV6" in commands

    def test_multiple_sequence_entries_in_same_route_map(self):
        """Multiple entries for one route-map produce separate rule items."""
        session = _routing_session("s1", export_rms=["OUT"])
        rm_entries = [
            _rm_entry(1, "OUT", 10, match_pls=["PFX"], set_prepend=65015),
            _rm_entry(1, "OUT", 20, match_pls=["PFX"], set_prepend=[65015, 65015]),
        ]
        pl_entries = [_pl_entry(5, "PFX", 10, "permit", "10.0.0.0/8")]

        result = collect_ebgp_vrf_policy_config_routing([session], rm_entries, pl_entries)

        assert len(result["route_map_rules"]) == 2
        indexes = [r["index"] for r in result["route_map_rules"]]
        assert sorted(indexes) == [10, 20]
        # Double prepend
        cmd20 = next(r["commands"] for r in result["route_map_rules"] if r["index"] == 20)
        assert "set as-path prepend 65015 65015" in cmd20

    def test_route_map_without_match_or_set(self):
        """Entry with no match/set produces only the route-map header command."""
        session = _routing_session("s1", export_rms=["PLAIN"])
        rm_entries = [_rm_entry(1, "PLAIN", 10)]

        result = collect_ebgp_vrf_policy_config_routing([session], rm_entries, [])

        rm = result["route_map_rules"][0]
        assert rm["commands"] == ["route-map PLAIN permit seq 10"]
        assert result["prefix_lists"] == []

    def test_unreferenced_route_map_entries_ignored(self):
        """Entries for route-maps not referenced by any session are skipped."""
        session = _routing_session("s1", export_rms=["MINE"])
        rm_entries = [
            _rm_entry(1, "MINE", 10),
            _rm_entry(2, "OTHER", 10),  # not referenced
        ]

        result = collect_ebgp_vrf_policy_config_routing([session], rm_entries, [])

        names = [r["name"] for r in result["route_map_rules"]]
        assert "MINE" in names
        assert "OTHER" not in names

    def test_two_sessions_sharing_same_route_map_deduplicated(self):
        """Two sessions referencing the same route-map produce one rule set."""
        sessions = [
            _routing_session("s1", export_rms=["OUT"]),
            _routing_session("s2", export_rms=["OUT"]),
        ]
        rm_entries = [_rm_entry(1, "OUT", 10, match_pls=["PFX"])]
        pl_entries = [_pl_entry(5, "PFX", 10, "permit", "10.0.0.0/8")]

        result = collect_ebgp_vrf_policy_config_routing(sessions, rm_entries, pl_entries)

        assert len(result["route_map_rules"]) == 1
        assert len(result["prefix_lists"]) == 1

    def test_prefix_list_rules_sorted_by_sequence(self):
        """Prefix list rules are sorted by sequence number."""
        session = _routing_session("s1", export_rms=["P"])
        rm_entries = [_rm_entry(1, "P", 10, match_pls=["PFX"])]
        pl_entries = [
            _pl_entry(5, "PFX", 30, "permit", "10.3.0.0/24"),
            _pl_entry(5, "PFX", 10, "permit", "10.1.0.0/24"),
            _pl_entry(5, "PFX", 20, "permit", "10.2.0.0/24"),
        ]

        result = collect_ebgp_vrf_policy_config_routing([session], rm_entries, pl_entries)

        indexes = [r["index"] for r in result["prefix_lists"][0]["rules"]]
        assert indexes == [10, 20, 30]

    def test_route_map_rules_sorted_by_name_then_sequence(self):
        """Route-map rules are sorted by name then sequence."""
        sessions = [
            _routing_session("s1", export_rms=["B-OUT", "A-OUT"]),
        ]
        rm_entries = [
            _rm_entry(2, "B-OUT", 20),
            _rm_entry(1, "A-OUT", 10),
            _rm_entry(2, "B-OUT", 10),
        ]

        result = collect_ebgp_vrf_policy_config_routing(sessions, rm_entries, [])

        names_seqs = [(r["name"], r["index"]) for r in result["route_map_rules"]]
        assert names_seqs == [("A-OUT", 10), ("B-OUT", 10), ("B-OUT", 20)]

    def test_le_ge_included_in_prefix_list_rule(self):
        """le/ge values from prefix-list entry are passed through."""
        session = _routing_session("s1", export_rms=["P"])
        rm_entries = [_rm_entry(1, "P", 10, match_pls=["PFX"])]
        pl_entries = [
            {
                "id": 5,
                "prefix_list": {"id": 5, "name": "PFX"},
                "sequence": 10,
                "action": "permit",
                "assigned_prefix": {"prefix": "10.0.0.0/8"},
                "le": 32,
                "ge": 24,
            }
        ]

        result = collect_ebgp_vrf_policy_config_routing([session], rm_entries, pl_entries)

        rule = result["prefix_lists"][0]["rules"][0]
        assert rule["le"] == 32
        assert rule["ge"] == 24

    def test_prefix_list_entry_without_le_ge_has_no_keys(self):
        """Entries without le/ge don't include those keys in the rule dict."""
        session = _routing_session("s1", export_rms=["P"])
        rm_entries = [_rm_entry(1, "P", 10, match_pls=["PFX"])]
        pl_entries = [_pl_entry(5, "PFX", 10, "permit", "10.0.0.0/8")]

        result = collect_ebgp_vrf_policy_config_routing([session], rm_entries, pl_entries)

        rule = result["prefix_lists"][0]["rules"][0]
        assert "le" not in rule
        assert "ge" not in rule

    def test_mixed_ipv4_and_ipv6_prefix_lists(self):
        """A single route-map matching both IPv4 and IPv6 prefix-lists."""
        session = _routing_session("s1", export_rms=["MIXED-OUT"])
        rm_entries = [
            _rm_entry(1, "MIXED-OUT", 10, match_pls=["PFX-V4", "PFX-V6"])
        ]
        pl_entries = [
            _pl_entry(4, "PFX-V4", 10, "permit", "172.27.4.0/24"),
            _pl_entry(6, "PFX-V6", 10, "permit", "2a02:20c8::/32"),
        ]

        result = collect_ebgp_vrf_policy_config_routing([session], rm_entries, pl_entries)

        af_map = {pl["name"]: pl["af"] for pl in result["prefix_lists"]}
        assert af_map["PFX-V4"] == "ipv4"
        assert af_map["PFX-V6"] == "ipv6"

        commands = result["route_map_rules"][0]["commands"]
        assert "match ip address prefix-list PFX-V4" in commands
        assert "match ipv6 address prefix-list PFX-V6" in commands
