"""
Pipeline tests for L2 interface selection in tasks/configure_l2_interfaces.yml

The L2 task file runs two comparators in sequence:

1. get_interfaces_needing_config_changes() (identify_interface_changes.yml)
   builds interface_changes.l2 - the authoritative change detection.
2. get_interfaces_needing_changes() (comparison.py), idempotent mode only,
   builds the VLAN-removal `cleanup` list from interface_changes.l2.

The second comparator implements a narrower rule set (no native-tagged
handling, no native-VLAN-in-trunks handling). It used to also narrow the
list of interfaces to configure, silently dropping changes the first one
detected. These tests pin the contract the task file now relies on:
selection comes from interface_changes.l2, and the push that follows is
idempotent on re-run.
"""
import os

import yaml

from netbox_filters_lib.comparison import get_interfaces_needing_changes
from netbox_filters_lib.interface_categorization import categorize_l2_interfaces
from netbox_filters_lib.interface_change_detection import (
    get_interfaces_needing_config_changes,
)

_ROLE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _facts(name, device_intf):
    return {"network_resources": {"interfaces": {name: device_intf}}}


def _tagged_no_untagged():
    return {
        "name": "1/1/2",
        "type": {"value": "1000base-t"},
        "enabled": True,
        "mode": {"value": "tagged"},
        "untagged_vlan": None,
        "tagged_vlans": [{"vid": 10}, {"vid": 20}],
    }


def _tagged_all_no_untagged():
    return {
        "name": "1/1/1",
        "type": {"value": "1000base-t"},
        "enabled": True,
        "mode": {"value": "tagged-all"},
        "untagged_vlan": None,
        "tagged_vlans": [],
    }


class TestNativeTaggedChangesReachThePush:
    """Changes detected by stage 1 must be categorized for the push."""

    def test_tagged_all_no_untagged_vs_native_untagged_device(self):
        nb = _tagged_all_no_untagged()
        facts = _facts(
            nb["name"],
            {"vlan_mode": "native-untagged", "vlan_tag": {"1": "x"},
             "user_config": {"admin": "up"}},
        )
        l2 = get_interfaces_needing_config_changes([nb], facts)["l2"]
        assert [i["name"] for i in l2] == ["1/1/1"]
        assert [i["name"] for i in categorize_l2_interfaces(l2)["tagged_all_no_untagged"]] == ["1/1/1"]

    def test_tagged_no_untagged_vs_native_untagged_device(self):
        nb = _tagged_no_untagged()
        facts = _facts(
            nb["name"],
            {"vlan_mode": "native-untagged", "vlan_tag": {"1": "x"},
             "vlan_trunks": {"10": "x", "20": "x"},
             "user_config": {"admin": "up"}},
        )
        l2 = get_interfaces_needing_config_changes([nb], facts)["l2"]
        assert [i["name"] for i in l2] == ["1/1/2"]
        assert [i["name"] for i in categorize_l2_interfaces(l2)["tagged_no_untagged"]] == ["1/1/2"]


class TestNativeTaggedPushIsIdempotent:
    """Device state after configure_l2_physical.yml's push must compare clean."""

    def test_tagged_no_untagged_after_push(self):
        # Push: vlan_mode trunk, native_vlan_id = first tagged VID, native_vlan_tag
        nb = _tagged_no_untagged()
        facts = _facts(
            nb["name"],
            {"vlan_mode": "native-tagged", "vlan_tag": {"10": "x"},
             "vlan_trunks": {"10": "x", "20": "x"},
             "user_config": {"admin": "up"}},
        )
        result = get_interfaces_needing_config_changes([nb], facts)
        assert result["l2"] == []
        assert [i["name"] for i in result["no_changes"]] == ["1/1/2"]

    def test_tagged_all_no_untagged_after_push(self):
        # Push: trunk_allowed_all, native_vlan_id "1", native_vlan_tag
        nb = _tagged_all_no_untagged()
        facts = _facts(
            nb["name"],
            {"vlan_mode": "native-tagged", "vlan_tag": {"1": "x"},
             "user_config": {"admin": "up"}},
        )
        result = get_interfaces_needing_config_changes([nb], facts)
        assert result["l2"] == []
        assert [i["name"] for i in result["no_changes"]] == ["1/1/1"]


class TestCleanupListUnchanged:
    """Stage 2 still owns the VLAN-removal list; pin its shape."""

    def test_trunk_vlan_removal_on_lag(self):
        nb = {
            "name": "lag1",
            "type": {"value": "lag"},
            "enabled": True,
            "mode": {"value": "tagged"},
            "untagged_vlan": {"vid": 10},
            "tagged_vlans": [{"vid": 20}],
            "custom_fields": {"if_mclag": True},
        }
        facts = _facts(
            "lag1",
            {"vlan_mode": "native-untagged", "vlan_tag": {"10": "x"},
             "vlan_trunks": {"10": "x", "20": "x", "30": "x"},
             "user_config": {"admin": "up"}},
        )
        l2 = get_interfaces_needing_config_changes([nb], facts)["l2"]
        cleanup = get_interfaces_needing_changes(l2, facts)["cleanup"]
        assert cleanup == [
            {"interface": "lag1", "vlans_to_remove": [30], "is_lag": True, "is_mclag": True}
        ]


class TestTaskFileSelection:
    """Regression guard for the task-level selection expression."""

    def test_interfaces_to_configure_not_narrowed_by_stage_two(self):
        path = os.path.join(_ROLE_ROOT, "tasks", "configure_l2_interfaces.yml")
        with open(path, encoding="utf-8") as fh:
            tasks = yaml.safe_load(fh)
        exprs = [
            t["ansible.builtin.set_fact"]["interfaces_to_configure"]
            for t in tasks
            if isinstance(t.get("ansible.builtin.set_fact"), dict)
            and "interfaces_to_configure" in t["ansible.builtin.set_fact"]
        ]
        assert len(exprs) == 1
        assert "interfaces_needing_changes" not in exprs[0]
        assert "interface_changes.l2" in exprs[0]
