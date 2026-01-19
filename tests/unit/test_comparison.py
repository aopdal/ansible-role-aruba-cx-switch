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
