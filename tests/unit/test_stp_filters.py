"""
Unit tests for STP (Spanning Tree Protocol) filter functions.
"""
import pytest
from netbox_filters_lib.stp import stp_interface_changes


class TestStpInterfaceChanges:
    """Tests for stp_interface_changes filter function."""

    def _l2_intf(self, name, cf=None, mode="access"):
        """Build a minimal NetBox L2 interface dict."""
        return {
            "name": name,
            "mode": {"value": mode, "label": mode.capitalize()},
            "custom_fields": cf or {},
        }

    def _enhanced(self, name, **stp_fields):
        """Build a minimal aoscx_enhanced_interface_facts entry."""
        return {name: {"stp_config": stp_fields}}

    # ------------------------------------------------------------------
    # Guard: invalid / degenerate inputs
    # ------------------------------------------------------------------

    def test_non_list_interfaces_returns_empty(self):
        assert stp_interface_changes(None, {}) == []
        assert stp_interface_changes({}, {}) == []
        assert stp_interface_changes("bad", {}) == []

    def test_non_dict_enhanced_facts_is_tolerated(self):
        intfs = [self._l2_intf("1/1/1", {"if_stp_bpdu_guard": True})]
        result = stp_interface_changes(intfs, None)
        # No device facts → desired True vs current False (default) → change needed
        assert len(result) == 1
        assert "spanning-tree bpdu-guard" in result[0]["lines"]

    def test_empty_interfaces_returns_empty(self):
        assert stp_interface_changes([], {}) == []

    # ------------------------------------------------------------------
    # L3 / routed interfaces must be ignored
    # ------------------------------------------------------------------

    def test_routed_interface_skipped(self):
        intf = {
            "name": "1/1/1",
            "mode": None,
            "custom_fields": {"if_stp_bpdu_guard": True},
        }
        assert stp_interface_changes([intf], {}) == []

    def test_interface_without_mode_key_skipped(self):
        intf = {"name": "1/1/1", "custom_fields": {"if_stp_bpdu_guard": True}}
        assert stp_interface_changes([intf], {}) == []

    # ------------------------------------------------------------------
    # No changes needed (device already matches NetBox)
    # ------------------------------------------------------------------

    def test_no_change_when_device_matches_netbox(self):
        intfs = [
            self._l2_intf(
                "1/1/1",
                cf={
                    "if_stp_bpdu_filter": True,
                    "if_stp_bpdu_guard": False,
                    "if_stp_edge_port": True,
                    "if_stp_root_guard": False,
                },
            )
        ]
        facts = self._enhanced(
            "1/1/1",
            bpdu_filter_enable=True,
            bpdu_guard_enable=False,
            admin_edge_port_enable=True,
            root_guard_enable=False,
        )
        assert stp_interface_changes(intfs, facts) == []

    def test_no_change_when_no_stp_custom_fields_set(self):
        intfs = [self._l2_intf("1/1/1", cf={"if_stp_bpdu_guard": None})]
        facts = self._enhanced("1/1/1", bpdu_guard_enable=True)
        assert stp_interface_changes(intfs, facts) == []

    def test_no_change_when_custom_fields_absent(self):
        intfs = [self._l2_intf("1/1/1", cf={})]
        facts = self._enhanced("1/1/1", bpdu_guard_enable=True)
        assert stp_interface_changes(intfs, facts) == []

    # ------------------------------------------------------------------
    # Enable commands (desired True, device False)
    # ------------------------------------------------------------------

    def test_bpdu_guard_enable(self):
        intfs = [self._l2_intf("1/1/1", cf={"if_stp_bpdu_guard": True})]
        facts = self._enhanced("1/1/1", bpdu_guard_enable=False)
        result = stp_interface_changes(intfs, facts)
        assert len(result) == 1
        assert result[0]["name"] == "1/1/1"
        assert result[0]["lines"] == ["spanning-tree bpdu-guard"]

    def test_bpdu_filter_enable(self):
        intfs = [self._l2_intf("1/1/1", cf={"if_stp_bpdu_filter": True})]
        facts = self._enhanced("1/1/1", bpdu_filter_enable=False)
        result = stp_interface_changes(intfs, facts)
        assert result[0]["lines"] == ["spanning-tree bpdu-filter"]

    def test_edge_port_enable(self):
        intfs = [self._l2_intf("1/1/1", cf={"if_stp_edge_port": True})]
        facts = self._enhanced("1/1/1", admin_edge_port_enable=False)
        result = stp_interface_changes(intfs, facts)
        assert result[0]["lines"] == ["spanning-tree port-type admin-edge"]

    def test_root_guard_enable(self):
        intfs = [self._l2_intf("1/1/1", cf={"if_stp_root_guard": True})]
        facts = self._enhanced("1/1/1", root_guard_enable=False)
        result = stp_interface_changes(intfs, facts)
        assert result[0]["lines"] == ["spanning-tree root-guard"]

    # ------------------------------------------------------------------
    # Disable commands (desired False, device True)
    # ------------------------------------------------------------------

    def test_bpdu_guard_disable(self):
        intfs = [self._l2_intf("1/1/1", cf={"if_stp_bpdu_guard": False})]
        facts = self._enhanced("1/1/1", bpdu_guard_enable=True)
        result = stp_interface_changes(intfs, facts)
        assert result[0]["lines"] == ["no spanning-tree bpdu-guard"]

    def test_bpdu_filter_disable(self):
        intfs = [self._l2_intf("1/1/1", cf={"if_stp_bpdu_filter": False})]
        facts = self._enhanced("1/1/1", bpdu_filter_enable=True)
        result = stp_interface_changes(intfs, facts)
        assert result[0]["lines"] == ["no spanning-tree bpdu-filter"]

    def test_edge_port_disable(self):
        intfs = [self._l2_intf("1/1/1", cf={"if_stp_edge_port": False})]
        facts = self._enhanced("1/1/1", admin_edge_port_enable=True)
        result = stp_interface_changes(intfs, facts)
        assert result[0]["lines"] == ["no spanning-tree port-type admin-edge"]

    def test_root_guard_disable(self):
        intfs = [self._l2_intf("1/1/1", cf={"if_stp_root_guard": False})]
        facts = self._enhanced("1/1/1", root_guard_enable=True)
        result = stp_interface_changes(intfs, facts)
        assert result[0]["lines"] == ["no spanning-tree root-guard"]

    # ------------------------------------------------------------------
    # Multiple fields on one interface
    # ------------------------------------------------------------------

    def test_multiple_fields_produce_ordered_lines(self):
        intfs = [
            self._l2_intf(
                "1/1/2",
                cf={
                    "if_stp_bpdu_filter": True,
                    "if_stp_bpdu_guard": True,
                    "if_stp_edge_port": False,
                    "if_stp_root_guard": True,
                },
            )
        ]
        facts = self._enhanced(
            "1/1/2",
            bpdu_filter_enable=False,
            bpdu_guard_enable=False,
            admin_edge_port_enable=True,
            root_guard_enable=False,
        )
        result = stp_interface_changes(intfs, facts)
        assert len(result) == 1
        assert result[0]["lines"] == [
            "spanning-tree bpdu-filter",
            "spanning-tree bpdu-guard",
            "no spanning-tree port-type admin-edge",
            "spanning-tree root-guard",
        ]

    # ------------------------------------------------------------------
    # Multiple interfaces — only changed ones returned
    # ------------------------------------------------------------------

    def test_only_interfaces_with_changes_returned(self):
        intfs = [
            self._l2_intf("1/1/1", cf={"if_stp_bpdu_guard": True}),
            self._l2_intf("1/1/2", cf={"if_stp_bpdu_guard": True}),
            self._l2_intf("1/1/3", cf={"if_stp_bpdu_guard": True}),
        ]
        facts = {
            "1/1/1": {"stp_config": {"bpdu_guard_enable": True}},   # already correct
            "1/1/2": {"stp_config": {"bpdu_guard_enable": False}},  # needs change
            "1/1/3": {"stp_config": {}},                             # needs change (missing = False)
        }
        result = stp_interface_changes(intfs, facts)
        names = [r["name"] for r in result]
        assert "1/1/1" not in names
        assert "1/1/2" in names
        assert "1/1/3" in names

    # ------------------------------------------------------------------
    # No device facts available (fresh/unqueried switch)
    # ------------------------------------------------------------------

    def test_no_device_facts_treats_all_as_false(self):
        """Without REST API facts all device fields default to False."""
        intfs = [
            self._l2_intf(
                "1/1/1",
                cf={"if_stp_bpdu_guard": True, "if_stp_bpdu_filter": False},
            )
        ]
        result = stp_interface_changes(intfs, {})
        # True != False → add enable cmd
        # False == False → no change for bpdu-filter
        assert len(result) == 1
        assert result[0]["lines"] == ["spanning-tree bpdu-guard"]

    def test_interface_not_in_enhanced_facts(self):
        """Interface missing from facts dict is treated the same as all-false."""
        intfs = [self._l2_intf("1/1/5", cf={"if_stp_root_guard": True})]
        facts = {"1/1/1": {"stp_config": {}}}  # different interface
        result = stp_interface_changes(intfs, facts)
        assert len(result) == 1
        assert result[0]["lines"] == ["spanning-tree root-guard"]

    # ------------------------------------------------------------------
    # Tagged and tagged-all L2 modes are treated identically
    # ------------------------------------------------------------------

    def test_tagged_interface_receives_stp(self):
        intf = {
            "name": "1/1/10",
            "mode": {"value": "tagged", "label": "Tagged"},
            "custom_fields": {"if_stp_edge_port": True},
        }
        result = stp_interface_changes([intf], {})
        assert len(result) == 1

    def test_tagged_all_interface_receives_stp(self):
        intf = {
            "name": "1/1/11",
            "mode": {"value": "tagged-all", "label": "Tagged All"},
            "custom_fields": {"if_stp_root_guard": True},
        }
        result = stp_interface_changes([intf], {})
        assert len(result) == 1
