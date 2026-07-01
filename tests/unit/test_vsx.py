"""Unit tests for VSX configuration comparison filter."""
import pytest
from netbox_filters_lib.vsx import vsx_config_diff


class TestVsxConfigDiff:
    """Tests for vsx_config_diff function."""

    _DESIRED = {
        "vsx_role": "primary",
        "vsx_system_mac": "02:00:00:00:01:00",
        "vsx_isl_lag": "lag256",
        "vsx_keepalive_vrf": "keepalive",
        "vsx_keepalive_src": "192.168.255.1",
        "vsx_keepalive_peer": "192.168.255.2",
    }

    _FACTS_MATCH = {
        "device_role": "primary",
        "system_mac": "02:00:00:00:01:00",
        "isl_port": {"lag256": "/rest/v10.16/system/interfaces/lag256"},
        "keepalive_vrf": {"keepalive": "/rest/v10.16/system/vrfs/keepalive"},
        "keepalive_src_ip": "192.168.255.1",
        "keepalive_peer_ip": "192.168.255.2",
    }

    def test_no_changes_when_matching(self):
        result = vsx_config_diff(self._DESIRED, self._FACTS_MATCH)
        assert result["changed"] is False
        assert result["changes"] == []

    def test_detect_role_change(self):
        facts = {**self._FACTS_MATCH, "device_role": "secondary"}
        result = vsx_config_diff(self._DESIRED, facts)
        assert result["changed"] is True
        assert any(c["field"] == "device_role" for c in result["changes"])

    def test_detect_system_mac_change(self):
        facts = {**self._FACTS_MATCH, "system_mac": "02:00:00:00:02:00"}
        result = vsx_config_diff(self._DESIRED, facts)
        assert result["changed"] is True
        fields = [c["field"] for c in result["changes"]]
        assert "system_mac" in fields

    def test_detect_isl_port_change(self):
        facts = {
            **self._FACTS_MATCH,
            "isl_port": {"lag100": "/rest/v10.16/system/interfaces/lag100"},
        }
        result = vsx_config_diff(self._DESIRED, facts)
        assert result["changed"] is True
        change = next(c for c in result["changes"] if c["field"] == "isl_port")
        assert change["expected"] == "lag256"
        assert change["actual"] == "lag100"

    def test_detect_keepalive_vrf_change(self):
        facts = {
            **self._FACTS_MATCH,
            "keepalive_vrf": {"mgmt": "/rest/v10.16/system/vrfs/mgmt"},
        }
        result = vsx_config_diff(self._DESIRED, facts)
        assert result["changed"] is True
        change = next(
            c for c in result["changes"] if c["field"] == "keepalive_vrf"
        )
        assert change["expected"] == "keepalive"
        assert change["actual"] == "mgmt"

    def test_detect_keepalive_src_change(self):
        facts = {**self._FACTS_MATCH, "keepalive_src_ip": "10.0.0.1"}
        result = vsx_config_diff(self._DESIRED, facts)
        assert result["changed"] is True
        fields = [c["field"] for c in result["changes"]]
        assert "keepalive_src_ip" in fields

    def test_detect_keepalive_peer_change(self):
        facts = {**self._FACTS_MATCH, "keepalive_peer_ip": "10.0.0.2"}
        result = vsx_config_diff(self._DESIRED, facts)
        assert result["changed"] is True
        fields = [c["field"] for c in result["changes"]]
        assert "keepalive_peer_ip" in fields

    def test_multiple_changes(self):
        facts = {
            **self._FACTS_MATCH,
            "device_role": "secondary",
            "keepalive_peer_ip": "10.0.0.99",
        }
        result = vsx_config_diff(self._DESIRED, facts)
        assert result["changed"] is True
        assert len(result["changes"]) == 2

    def test_empty_facts_all_changed(self):
        result = vsx_config_diff(self._DESIRED, {})
        assert result["changed"] is True
        assert len(result["changes"]) == 6

    def test_none_facts(self):
        result = vsx_config_diff(self._DESIRED, None)
        assert result["changed"] is True

    def test_none_desired(self):
        result = vsx_config_diff(None, self._FACTS_MATCH)
        assert result["changed"] is False
        assert result["changes"] == []

    def test_empty_desired(self):
        result = vsx_config_diff({}, self._FACTS_MATCH)
        assert result["changed"] is False

    def test_case_insensitive_mac_comparison(self):
        facts = {
            **self._FACTS_MATCH,
            "system_mac": "02:00:00:00:01:00",
        }
        desired = {**self._DESIRED, "vsx_system_mac": "02:00:00:00:01:00"}
        result = vsx_config_diff(desired, facts)
        assert result["changed"] is False

    def test_case_insensitive_mac_upper_lower(self):
        facts = {
            **self._FACTS_MATCH,
            "system_mac": "02:00:00:00:01:AA",
        }
        desired = {**self._DESIRED, "vsx_system_mac": "02:00:00:00:01:aa"}
        result = vsx_config_diff(desired, facts)
        assert result["changed"] is False

    def test_vsx_isl_port_fallback(self):
        """vsx_isl_port is used when vsx_isl_lag is absent."""
        desired = {
            "vsx_role": "primary",
            "vsx_system_mac": "02:00:00:00:01:00",
            "vsx_isl_port": "lag256",
        }
        result = vsx_config_diff(desired, self._FACTS_MATCH)
        assert result["changed"] is False

    def test_skip_undefined_desired_fields(self):
        """Fields not in desired dict are not compared."""
        desired = {"vsx_role": "primary"}
        facts = {
            "device_role": "primary",
            "system_mac": "ff:ff:ff:ff:ff:ff",
        }
        result = vsx_config_diff(desired, facts)
        assert result["changed"] is False

    def test_isl_port_plain_string_in_facts(self):
        """Handle isl_port as plain string (non-dict) in facts."""
        facts = {**self._FACTS_MATCH, "isl_port": "lag256"}
        result = vsx_config_diff(self._DESIRED, facts)
        assert result["changed"] is False

    def test_keepalive_vrf_plain_string_in_facts(self):
        """Handle keepalive_vrf as plain string in facts."""
        facts = {**self._FACTS_MATCH, "keepalive_vrf": "keepalive"}
        result = vsx_config_diff(self._DESIRED, facts)
        assert result["changed"] is False
