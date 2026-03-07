"""
Unit tests for BGP filter functions
"""
import pytest
from netbox_filters_lib.bgp_filters import (
    get_bgp_session_vrf_info,
    collect_ebgp_vrf_policy_config,
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
