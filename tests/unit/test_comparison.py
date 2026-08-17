"""
Unit tests for comparison filter functions
"""
import pytest
from netbox_filters_lib.comparison import (
    compare_interface_vlans,
    get_interfaces_needing_changes,
)
from .fixtures import get_sample_interfaces, get_sample_ansible_facts


class TestCompareInterfaceVlans:
    """Tests for compare_interface_vlans function"""

    def test_compare_vlans_identical_access(self):
        """Test comparing identical access mode configurations"""
        netbox_config = {
            "name": "1/1/1",
            "mode": {"value": "access"},
            "untagged_vlan": {"vid": 10},
            "tagged_vlans": [],
        }
        device_config = {
            "vlan_mode": "access",
            "vlan_tag": {"10": "/rest/v10.09/system/vlans/10"},
            "vlan_trunks": {},
        }
        result = compare_interface_vlans(netbox_config, device_config)
        assert result["needs_change"] is False
        assert result["vlans_to_add"] == []
        assert result["vlans_to_remove"] == []

    def test_compare_vlans_untagged_different(self):
        """Test comparing when untagged VLAN is different"""
        netbox_config = {
            "name": "1/1/1",
            "mode": {"value": "access"},
            "untagged_vlan": {"vid": 10},
            "tagged_vlans": [],
        }
        device_config = {
            "vlan_mode": "access",
            "vlan_tag": {"20": "/rest/v10.09/system/vlans/20"},
            "vlan_trunks": {},
        }
        result = compare_interface_vlans(netbox_config, device_config)
        assert result["needs_change"] is True

    def test_compare_vlans_tagged_different(self):
        """Test comparing when tagged VLANs are different"""
        netbox_config = {
            "name": "1/1/1",
            "mode": {"value": "tagged"},
            "untagged_vlan": None,
            "tagged_vlans": [{"vid": 10}, {"vid": 20}, {"vid": 30}],
        }
        device_config = {
            "vlan_mode": "native-tagged",
            "vlan_tag": None,
            "vlan_trunks": {
                "10": "/rest/v10.09/system/vlans/10",
                "20": "/rest/v10.09/system/vlans/20",
                "40": "/rest/v10.09/system/vlans/40",
            },
        }
        result = compare_interface_vlans(netbox_config, device_config)
        assert result["needs_change"] is True
        assert 30 in result["vlans_to_add"]
        assert 40 in result["vlans_to_remove"]

    def test_compare_vlans_mode_different(self):
        """Test comparing when mode is different"""
        netbox_config = {
            "name": "1/1/1",
            "mode": {"value": "access"},
            "untagged_vlan": {"vid": 10},
            "tagged_vlans": [],
        }
        device_config = {
            "vlan_mode": "native-tagged",
            "vlan_tag": {"10": "/rest/v10.09/system/vlans/10"},
            "vlan_trunks": {},
        }
        result = compare_interface_vlans(netbox_config, device_config)
        assert result["needs_change"] is True
        assert result["mode_change"] is True

    def test_compare_vlans_device_not_configured(self):
        """Test when device has no configuration"""
        netbox_config = {
            "name": "1/1/1",
            "mode": {"value": "access"},
            "untagged_vlan": {"vid": 10},
            "tagged_vlans": [],
        }
        device_config = None
        result = compare_interface_vlans(netbox_config, device_config)
        assert result["needs_change"] is False  # Returns early

    def test_compare_vlans_tagged_all_with_native_identical(self):
        """Test comparing identical tagged-all with native VLAN"""
        netbox_config = {
            "name": "1/1/1",
            "mode": {"value": "tagged-all"},
            "untagged_vlan": {"vid": 100},
            "tagged_vlans": [],
        }
        device_config = {
            "vlan_mode": "native-tagged",
            "vlan_tag": {"100": "/rest/v10.09/system/vlans/100"},
            "vlan_trunks": {
                "10": "/rest/v10.09/system/vlans/10",
                "20": "/rest/v10.09/system/vlans/20",
                "100": "/rest/v10.09/system/vlans/100",
            },
        }
        result = compare_interface_vlans(netbox_config, device_config)
        assert result["needs_change"] is False
        assert result["vlans_to_add"] == []
        assert result["vlans_to_remove"] == []

    def test_compare_vlans_tagged_all_native_different(self):
        """Test comparing tagged-all when native VLAN differs"""
        netbox_config = {
            "name": "1/1/1",
            "mode": {"value": "tagged-all"},
            "untagged_vlan": {"vid": 100},
            "tagged_vlans": [],
        }
        device_config = {
            "vlan_mode": "native-tagged",
            "vlan_tag": {"200": "/rest/v10.09/system/vlans/200"},
            "vlan_trunks": {
                "10": "/rest/v10.09/system/vlans/10",
                "20": "/rest/v10.09/system/vlans/20",
            },
        }
        result = compare_interface_vlans(netbox_config, device_config)
        assert result["needs_change"] is True
        # For tagged-all, we only care about native VLAN, not trunk VLANs
        assert result["vlans_to_add"] == []
        assert result["vlans_to_remove"] == []

    def test_compare_vlans_tagged_all_no_native(self):
        """Test comparing tagged-all without native VLAN"""
        netbox_config = {
            "name": "1/1/1",
            "mode": {"value": "tagged-all"},
            "untagged_vlan": None,
            "tagged_vlans": [],
        }
        device_config = {
            "vlan_mode": "native-tagged",
            "vlan_tag": None,
            "vlan_trunks": {
                "10": "/rest/v10.09/system/vlans/10",
                "20": "/rest/v10.09/system/vlans/20",
                "30": "/rest/v10.09/system/vlans/30",
            },
        }
        result = compare_interface_vlans(netbox_config, device_config)
        assert result["needs_change"] is False
        # For tagged-all without native, trunk VLANs don't matter
        assert result["vlans_to_add"] == []
        assert result["vlans_to_remove"] == []

    def test_compare_vlans_tagged_all_ignores_trunk_vlans(self):
        """Test that tagged-all mode ignores trunk VLAN differences"""
        netbox_config = {
            "name": "1/1/1",
            "mode": {"value": "tagged-all"},
            "untagged_vlan": {"vid": 100},
            "tagged_vlans": [],  # Empty - should allow all VLANs
        }
        device_config = {
            "vlan_mode": "native-tagged",
            "vlan_tag": {"100": "/rest/v10.09/system/vlans/100"},
            "vlan_trunks": {
                # Device has many VLANs, but tagged-all doesn't care
                "10": "/rest/v10.09/system/vlans/10",
                "20": "/rest/v10.09/system/vlans/20",
                "30": "/rest/v10.09/system/vlans/30",
                "40": "/rest/v10.09/system/vlans/40",
                "50": "/rest/v10.09/system/vlans/50",
                "100": "/rest/v10.09/system/vlans/100",
            },
        }
        result = compare_interface_vlans(netbox_config, device_config)
        assert result["needs_change"] is False
        assert result["vlans_to_add"] == []
        assert result["vlans_to_remove"] == []

    def test_compare_vlans_mode_change_access_to_tagged_all(self):
        """Test mode change from access to tagged-all"""
        netbox_config = {
            "name": "1/1/1",
            "mode": {"value": "tagged-all"},
            "untagged_vlan": {"vid": 10},
            "tagged_vlans": [],
        }
        device_config = {
            "vlan_mode": "access",
            "vlan_tag": {"10": "/rest/v10.09/system/vlans/10"},
            "vlan_trunks": {},
        }
        result = compare_interface_vlans(netbox_config, device_config)
        assert result["needs_change"] is True
        assert result["mode_change"] is True

    def test_compare_vlans_mode_change_tagged_to_tagged_all(self):
        """Test mode change from tagged to tagged-all"""
        netbox_config = {
            "name": "1/1/1",
            "mode": {"value": "tagged-all"},
            "untagged_vlan": {"vid": 100},
            "tagged_vlans": [],
        }
        device_config = {
            "vlan_mode": "access",  # Wrong mode
            "vlan_tag": {"100": "/rest/v10.09/system/vlans/100"},
            "vlan_trunks": {},
        }
        result = compare_interface_vlans(netbox_config, device_config)
        assert result["needs_change"] is True
        assert result["mode_change"] is True


class TestGetInterfacesNeedingChanges:
    """Tests for get_interfaces_needing_changes function"""

    def test_interfaces_needing_changes_new_interface(self):
        """Test identifying interfaces that need to be configured"""
        interfaces = [
            {
                "name": "1/1/1",
                "type": {"value": "1000base-t"},
                "mode": {"value": "access"},
                "untagged_vlan": {"vid": 10},
                "tagged_vlans": [],
                "mgmt_only": False,
            }
        ]
        # Interface exists in device facts but has no VLAN config - needs configuration
        ansible_facts = {
            "network_resources": {
                "interfaces": {
                    "1/1/1": {
                        # No VLAN configuration
                    }
                }
            }
        }
        result = get_interfaces_needing_changes(interfaces, ansible_facts)
        assert len(result["configure"]) == 1
        assert result["configure"][0]["name"] == "1/1/1"

    def test_interfaces_needing_changes_existing_correct(self):
        """Test that correctly configured interfaces are not included"""
        interfaces = [
            {
                "name": "1/1/1",
                "type": {"value": "1000base-t"},
                "mode": {"value": "access"},
                "untagged_vlan": {"vid": 10},
                "tagged_vlans": [],
                "mgmt_only": False,
            }
        ]
        ansible_facts = {
            "network_resources": {
                "interfaces": {
                    "1/1/1": {
                        "vlan_mode": "access",
                        "vlan_tag": {"10": "/rest/v10.09/system/vlans/10"},
                        "vlan_trunks": {},
                    }
                }
            }
        }
        result = get_interfaces_needing_changes(interfaces, ansible_facts)
        assert len(result["configure"]) == 0

    def test_interfaces_needing_changes_needs_update(self):
        """Test identifying interfaces that need updates"""
        interfaces = [
            {
                "name": "1/1/1",
                "type": {"value": "1000base-t"},
                "mode": {"value": "access"},
                "untagged_vlan": {"vid": 10},
                "tagged_vlans": [],
                "mgmt_only": False,
            }
        ]
        ansible_facts = {
            "network_resources": {
                "interfaces": {
                    "1/1/1": {
                        "vlan_mode": "access",
                        "vlan_tag": {"20": "/rest/v10.09/system/vlans/20"},
                        "vlan_trunks": {},
                    }
                }
            }
        }
        result = get_interfaces_needing_changes(interfaces, ansible_facts)
        assert len(result["configure"]) == 1

    def test_empty_interfaces_returns_empty_result(self):
        """Empty interfaces list short-circuits before touching device_facts"""
        result = get_interfaces_needing_changes([], {"network_resources": {}})
        assert result == {"cleanup": [], "configure": []}

    def test_none_interfaces_returns_empty_result(self):
        """None interfaces short-circuits the same as an empty list"""
        result = get_interfaces_needing_changes(None, {"network_resources": {}})
        assert result == {"cleanup": [], "configure": []}

    def test_empty_device_facts_returns_empty_result(self):
        """Empty device_facts short-circuits before any comparison"""
        interfaces = [{"name": "1/1/1", "mode": {"value": "access"}}]
        result = get_interfaces_needing_changes(interfaces, {})
        assert result == {"cleanup": [], "configure": []}

    def test_none_device_facts_returns_empty_result(self):
        """None device_facts short-circuits the same as empty device_facts"""
        interfaces = [{"name": "1/1/1", "mode": {"value": "access"}}]
        result = get_interfaces_needing_changes(interfaces, None)
        assert result == {"cleanup": [], "configure": []}

    def test_unrecognized_fact_format_returns_empty_result(self):
        """device_facts present but matching none of the known shapes yields
        an empty facts_by_interface, so every interface is silently skipped
        rather than treated as needing configuration"""
        interfaces = [{"name": "1/1/1", "mode": {"value": "access"}}]
        ansible_facts = {"some_other_key": {"interfaces": {}}}
        result = get_interfaces_needing_changes(interfaces, ansible_facts)
        assert result == {"cleanup": [], "configure": []}

    def test_ansible_network_resources_fact_path(self):
        """Interface facts found under the primary
        ansible_network_resources.interfaces path (not the alternate
        network_resources path used by other tests in this file)"""
        interfaces = [
            {
                "name": "1/1/1",
                "type": {"value": "1000base-t"},
                "mode": {"value": "access"},
                "untagged_vlan": {"vid": 10},
                "tagged_vlans": [],
                "mgmt_only": False,
            }
        ]
        ansible_facts = {
            "ansible_network_resources": {
                "interfaces": {
                    "1/1/1": {
                        "vlan_mode": "access",
                        "vlan_tag": {"20": "/rest/v10.09/system/vlans/20"},
                        "vlan_trunks": {},
                    }
                }
            }
        }
        result = get_interfaces_needing_changes(interfaces, ansible_facts)
        assert len(result["configure"]) == 1
        assert result["configure"][0]["name"] == "1/1/1"

    def test_ansible_net_interfaces_line_card_fact_path(self):
        """Interface facts found under the raw ansible_net_interfaces
        line-card format (Aruba aoscx_facts, not the resource-module path)"""
        interfaces = [
            {
                "name": "1/1/1",
                "type": {"value": "1000base-t"},
                "mode": {"value": "access"},
                "untagged_vlan": {"vid": 10},
                "tagged_vlans": [],
                "mgmt_only": False,
            }
        ]
        ansible_facts = {
            "ansible_net_interfaces": {
                "line_card,1/1": {
                    "1/1/1": {
                        "vlan_mode": "access",
                        "vlan_tag": {"20": "/rest/v10.09/system/vlans/20"},
                        "vlan_trunks": {},
                    }
                },
                # Non line-card entries must be ignored, not merged in
                "chassis_info": {"not": "an interface"},
            }
        }
        result = get_interfaces_needing_changes(interfaces, ansible_facts)
        assert len(result["configure"]) == 1
        assert result["configure"][0]["name"] == "1/1/1"

    def test_none_interface_entry_is_skipped(self):
        """A None entry in the interfaces list is skipped, not dereferenced"""
        interfaces = [
            None,
            {
                "name": "1/1/1",
                "mode": {"value": "access"},
                "untagged_vlan": {"vid": 20},
                "tagged_vlans": [],
            },
        ]
        # Non-empty facts_by_interface so the function doesn't short-circuit
        # before reaching the per-interface loop; VLAN 10 vs. desired 20
        # forces a real diff so we know iteration actually happened.
        ansible_facts = {
            "network_resources": {
                "interfaces": {
                    "1/1/1": {
                        "vlan_mode": "access",
                        "vlan_tag": {"10": "/rest/v10.09/system/vlans/10"},
                        "vlan_trunks": {},
                    }
                }
            }
        }
        result = get_interfaces_needing_changes(interfaces, ansible_facts)
        # The None entry must not have raised, and the real interface's
        # VLAN mismatch is still detected
        assert len(result["configure"]) == 1
        assert result["configure"][0]["name"] == "1/1/1"

    def test_interface_without_name_is_skipped(self):
        """An interface with no name cannot be matched against device facts
        and must be skipped rather than added to configure"""
        interfaces = [{"mode": {"value": "access"}}]
        # Non-empty facts so the function reaches the per-interface loop
        # instead of short-circuiting on an empty facts_by_interface.
        ansible_facts = {
            "network_resources": {"interfaces": {"1/1/1": {"vlan_mode": "access"}}}
        }
        result = get_interfaces_needing_changes(interfaces, ansible_facts)
        assert result == {"cleanup": [], "configure": []}

    def test_mgmt_only_interface_is_skipped(self):
        """mgmt_only interfaces are not L2 and must not be evaluated, even
        when device facts exist for them"""
        interfaces = [
            {"name": "mgmt", "mode": {"value": "access"}, "mgmt_only": True}
        ]
        ansible_facts = {
            "network_resources": {
                "interfaces": {
                    "mgmt": {
                        "vlan_mode": "access",
                        "vlan_tag": {"999": "/rest/v10.09/system/vlans/999"},
                    }
                }
            }
        }
        result = get_interfaces_needing_changes(interfaces, ansible_facts)
        assert result == {"cleanup": [], "configure": []}

    def test_interface_without_mode_is_skipped(self):
        """An interface with no (or non-dict) mode has nothing to compare
        and must be skipped rather than flagged for configuration"""
        interfaces = [{"name": "1/1/1", "mode": None}]
        ansible_facts = {
            "network_resources": {"interfaces": {"1/1/1": {"vlan_mode": "access"}}}
        }
        result = get_interfaces_needing_changes(interfaces, ansible_facts)
        assert result == {"cleanup": [], "configure": []}

    def test_comparison_error_defaults_to_configure(self):
        """If compare_interface_vlans blows up on malformed device facts,
        get_interfaces_needing_changes must not propagate the exception -
        it should log and fall back to treating the interface as needing
        configuration"""
        interfaces = [
            {
                "name": "1/1/1",
                "mode": {"value": "access"},
                "untagged_vlan": {"vid": 10},
                "tagged_vlans": [],
            }
        ]
        ansible_facts = {
            "network_resources": {
                "interfaces": {
                    # Malformed: a list instead of a dict of device facts,
                    # so device_facts_interface.get(...) raises AttributeError
                    "1/1/1": ["not", "a", "dict"]
                }
            }
        }
        result = get_interfaces_needing_changes(interfaces, ansible_facts)
        assert len(result["configure"]) == 1
        assert result["configure"][0]["name"] == "1/1/1"


class TestGetInterfacesNeedingChangesCleanup:
    """Tests for cleanup functionality in get_interfaces_needing_changes"""

    def test_interfaces_needing_cleanup_extra_vlans(self):
        """Test identifying interfaces with extra VLANs to remove"""
        interfaces = [
            {
                "name": "1/1/1",
                "type": {"value": "1000base-t"},
                "mode": {"value": "tagged"},
                "untagged_vlan": None,
                "tagged_vlans": [{"vid": 10}, {"vid": 20}],
            }
        ]
        ansible_facts = {
            "network_resources": {
                "interfaces": {
                    "1/1/1": {
                        "vlan_mode": "native-tagged",
                        "vlan_tag": None,
                        "vlan_trunks": {
                            "10": "/rest/v10.09/system/vlans/10",
                            "20": "/rest/v10.09/system/vlans/20",
                            "30": "/rest/v10.09/system/vlans/30",
                            "40": "/rest/v10.09/system/vlans/40",
                        },
                    }
                }
            }
        }
        result = get_interfaces_needing_changes(interfaces, ansible_facts)
        cleanup = result["cleanup"]
        assert len(cleanup) == 1
        assert cleanup[0]["interface"] == "1/1/1"
        assert 30 in cleanup[0]["vlans_to_remove"]
        assert 40 in cleanup[0]["vlans_to_remove"]

    def test_interfaces_needing_cleanup_none_needed(self):
        """Test when no cleanup is needed"""
        interfaces = [
            {
                "name": "1/1/1",
                "type": {"value": "1000base-t"},
                "mode": {"value": "tagged"},
                "untagged_vlan": None,
                "tagged_vlans": [{"vid": 10}, {"vid": 20}],
            }
        ]
        ansible_facts = {
            "network_resources": {
                "interfaces": {
                    "1/1/1": {
                        "vlan_mode": "native-tagged",
                        "vlan_tag": None,
                        "vlan_trunks": {
                            "10": "/rest/v10.09/system/vlans/10",
                            "20": "/rest/v10.09/system/vlans/20",
                        },
                    }
                }
            }
        }
        result = get_interfaces_needing_changes(interfaces, ansible_facts)
        assert len(result["cleanup"]) == 0

    def test_interfaces_needing_cleanup_interface_not_on_device(self):
        """Test when interface doesn't exist on device yet"""
        interfaces = [
            {
                "name": "1/1/1",
                "mode": {"value": "access"},
                "untagged_vlan": {"vid": 10},
                "tagged_vlans": [],
            }
        ]
        ansible_facts = {"network_resources": {"interfaces": {}}}
        result = get_interfaces_needing_changes(interfaces, ansible_facts)
        assert len(result["cleanup"]) == 0  # Can't cleanup what doesn't exist

    def test_cleanup_entry_marks_lag_and_mclag(self):
        """Cleanup entries must flag is_lag/is_mclag from the NetBox
        interface's type and custom_fields.if_mclag, not just the VLAN diff"""
        interfaces = [
            {
                "name": "lag1",
                "type": {"value": "lag"},
                "mode": {"value": "tagged"},
                "untagged_vlan": None,
                "tagged_vlans": [{"vid": 10}],
                "custom_fields": {"if_mclag": True},
            }
        ]
        ansible_facts = {
            "network_resources": {
                "interfaces": {
                    "lag1": {
                        "vlan_mode": "native-tagged",
                        "vlan_tag": None,
                        "vlan_trunks": {
                            "10": "/rest/v10.09/system/vlans/10",
                            "99": "/rest/v10.09/system/vlans/99",
                        },
                    }
                }
            }
        }
        result = get_interfaces_needing_changes(interfaces, ansible_facts)
        assert len(result["cleanup"]) == 1
        entry = result["cleanup"][0]
        assert entry["is_lag"] is True
        assert entry["is_mclag"] is True
        assert 99 in entry["vlans_to_remove"]

    def test_cleanup_entry_non_mclag_physical_interface(self):
        """A plain physical interface's cleanup entry reports is_lag/is_mclag
        as False rather than leaving them unset or truthy by accident"""
        interfaces = [
            {
                "name": "1/1/1",
                "type": {"value": "1000base-t"},
                "mode": {"value": "tagged"},
                "untagged_vlan": None,
                "tagged_vlans": [{"vid": 10}],
                "custom_fields": {"if_mclag": False},
            }
        ]
        ansible_facts = {
            "network_resources": {
                "interfaces": {
                    "1/1/1": {
                        "vlan_mode": "native-tagged",
                        "vlan_tag": None,
                        "vlan_trunks": {
                            "10": "/rest/v10.09/system/vlans/10",
                            "99": "/rest/v10.09/system/vlans/99",
                        },
                    }
                }
            }
        }
        result = get_interfaces_needing_changes(interfaces, ansible_facts)
        assert len(result["cleanup"]) == 1
        entry = result["cleanup"][0]
        assert entry["is_lag"] is False
        assert entry["is_mclag"] is False
