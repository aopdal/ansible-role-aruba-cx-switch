"""
Unit tests for BGP filter functions
"""
import pytest
from netbox_filters_lib.bgp_filters import get_bgp_session_vrf_info


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
