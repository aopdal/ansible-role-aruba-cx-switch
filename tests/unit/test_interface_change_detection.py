"""
Unit tests for interface change detection functions
"""
import pytest
from netbox_filters_lib.interface_change_detection import (
    get_interfaces_needing_config_changes,
)


class TestGetInterfacesNeedingConfigChanges:
    """Tests for get_interfaces_needing_config_changes function"""

    def test_empty_interfaces(self):
        """Test with empty interface list"""
        result = get_interfaces_needing_config_changes([], {})
        assert result["physical"] == []
        assert result["lag"] == []
        assert result["l2"] == []
        assert result["l3"] == []
        assert result["no_changes"] == []

    def test_no_device_facts_all_need_changes(self):
        """Test that all interfaces need changes when no device facts provided"""
        interfaces = [
            {
                "name": "1/1/1",
                "type": {"value": "1000base-t"},
                "enabled": True,
                "mode": {"value": "access"},
                "untagged_vlan": {"vid": 10},
            },
            {
                "name": "1/1/2",
                "type": {"value": "1000base-t"},
                "enabled": True,
                "mode": {"value": "tagged"},
                "tagged_vlans": [{"vid": 20}],
            },
        ]
        result = get_interfaces_needing_config_changes(interfaces, None)
        # All interfaces should need changes when no facts available
        assert len(result["physical"]) == 2
        assert len(result["l2"]) == 2

    def test_interface_not_on_device_needs_changes(self):
        """Test that interface not found in device facts needs changes"""
        interfaces = [
            {
                "name": "1/1/1",
                "type": {"value": "1000base-t"},
                "enabled": True,
                "mode": {"value": "access"},
                "untagged_vlan": {"vid": 10},
            },
        ]
        device_facts = {
            "network_resources": {
                "interfaces": {
                    # 1/1/1 is not present
                    "1/1/2": {"admin": "up"},
                }
            }
        }
        result = get_interfaces_needing_config_changes(interfaces, device_facts)
        assert len(result["physical"]) == 1
        assert result["physical"][0]["name"] == "1/1/1"

    def test_interface_no_changes_needed(self):
        """Test interface that matches device facts needs no changes"""
        interfaces = [
            {
                "name": "1/1/1",
                "type": {"value": "1000base-t"},
                "enabled": True,
                "description": "",
            },
        ]
        device_facts = {
            "network_resources": {
                "interfaces": {
                    "1/1/1": {
                        "admin": "up",
                        "admin_state": "up",
                        "description": "",
                    }
                }
            }
        }
        result = get_interfaces_needing_config_changes(interfaces, device_facts)
        assert len(result["no_changes"]) == 1
        assert result["no_changes"][0]["name"] == "1/1/1"

    def test_enabled_state_mismatch(self):
        """Test detection of enabled state mismatch"""
        interfaces = [
            {
                "name": "1/1/1",
                "type": {"value": "1000base-t"},
                "enabled": False,  # Should be disabled
            },
        ]
        device_facts = {
            "network_resources": {
                "interfaces": {
                    "1/1/1": {
                        "admin": "up",  # Currently enabled
                        "admin_state": "up",
                    }
                }
            }
        }
        result = get_interfaces_needing_config_changes(interfaces, device_facts)
        assert len(result["physical"]) == 1

    def test_description_mismatch(self):
        """Test detection of description mismatch"""
        interfaces = [
            {
                "name": "1/1/1",
                "type": {"value": "1000base-t"},
                "enabled": True,
                "description": "New Description",
            },
        ]
        device_facts = {
            "network_resources": {
                "interfaces": {
                    "1/1/1": {
                        "admin": "up",
                        "description": "Old Description",
                    }
                }
            }
        }
        result = get_interfaces_needing_config_changes(interfaces, device_facts)
        assert len(result["physical"]) == 1

    def test_mtu_mismatch(self):
        """Test detection of MTU mismatch"""
        interfaces = [
            {
                "name": "1/1/1",
                "type": {"value": "1000base-t"},
                "enabled": True,
                "mtu": 9198,
            },
        ]
        device_facts = {
            "network_resources": {
                "interfaces": {
                    "1/1/1": {
                        "admin": "up",
                        "mtu": 1500,
                    }
                }
            }
        }
        result = get_interfaces_needing_config_changes(interfaces, device_facts)
        assert len(result["physical"]) == 1

    def test_vlan_interface_not_on_device(self):
        """Test VLAN interface (SVI) not on device needs L3 changes"""
        interfaces = [
            {
                "name": "vlan100",
                "type": {"value": "virtual"},
                "ip_addresses": [{"address": "10.1.100.1/24"}],
            },
        ]
        device_facts = {
            "network_resources": {
                "interfaces": {}  # VLAN interface doesn't exist
            }
        }
        result = get_interfaces_needing_config_changes(interfaces, device_facts)
        assert len(result["l3"]) == 1
        assert result["l3"][0]["name"] == "vlan100"

    def test_lag_interface_categorization(self):
        """Test LAG interface is categorized correctly"""
        interfaces = [
            {
                "name": "lag1",
                "type": {"value": "lag"},
                "enabled": True,
                "mode": {"value": "access"},
                "untagged_vlan": {"vid": 10},
            },
        ]
        device_facts = {
            "network_resources": {
                "interfaces": {}  # LAG doesn't exist
            }
        }
        result = get_interfaces_needing_config_changes(interfaces, device_facts)
        assert len(result["lag"]) == 1
        assert result["lag"][0]["name"] == "lag1"

    def test_lag_member_categorization(self):
        """Test LAG member interface is categorized correctly"""
        interfaces = [
            {
                "name": "1/1/10",
                "type": {"value": "1000base-t"},
                "enabled": True,
                "lag": {"name": "lag1"},  # This is a LAG member
            },
        ]
        device_facts = {
            "network_resources": {
                "interfaces": {
                    "1/1/10": {"admin": "up"},
                    "lag1": {
                        "type": "lag",
                        "interfaces": {},  # 1/1/10 not in LAG yet
                    },
                }
            }
        }
        result = get_interfaces_needing_config_changes(interfaces, device_facts)
        # Should be in both lag_members and physical
        assert len(result["lag_members"]) == 1
        assert len(result["physical"]) == 1

    def test_access_vlan_mismatch(self):
        """Test detection of access VLAN mismatch"""
        interfaces = [
            {
                "name": "1/1/1",
                "type": {"value": "1000base-t"},
                "enabled": True,
                "mode": {"value": "access"},
                "untagged_vlan": {"vid": 20},  # Should be VLAN 20
            },
        ]
        device_facts = {
            "network_resources": {
                "interfaces": {
                    "1/1/1": {
                        "admin": "up",
                        "vlan_mode": "access",
                        "vlan_tag": {"10": {}},  # Currently VLAN 10
                    }
                }
            }
        }
        result = get_interfaces_needing_config_changes(interfaces, device_facts)
        assert len(result["l2"]) == 1

    def test_ip_address_changes(self):
        """Test detection of IP address changes"""
        interfaces = [
            {
                "name": "vlan100",
                "type": {"value": "virtual"},
                "ip_addresses": [
                    {"address": "10.1.100.1/24"},
                    {"address": "10.1.100.2/24"},  # Additional IP
                ],
            },
        ]
        device_facts = {
            "network_resources": {
                "interfaces": {
                    "vlan100": {
                        "admin": "up",
                        "ip4_address": "10.1.100.1/24",  # Only one IP configured
                    }
                }
            }
        }
        result = get_interfaces_needing_config_changes(interfaces, device_facts)
        assert len(result["l3"]) == 1
        # Check that _ip_changes is populated
        assert "_ip_changes" in result["l3"][0]
        assert "ipv4_to_add" in result["l3"][0]["_ip_changes"]

    def test_skip_management_interface(self):
        """Test that management interfaces are skipped"""
        interfaces = [
            {
                "name": "mgmt",
                "type": {"value": "1000base-t"},
                "enabled": True,
            },
        ]
        device_facts = {
            "network_resources": {
                "interfaces": {
                    "mgmt": {"admin": "up"},
                }
            }
        }
        result = get_interfaces_needing_config_changes(interfaces, device_facts)
        assert len(result["no_changes"]) == 1
        assert result["no_changes"][0]["name"] == "mgmt"

    def test_skip_mgmt_only_interface(self):
        """Test that interfaces marked mgmt_only are skipped"""
        interfaces = [
            {
                "name": "1/1/1",
                "type": {"value": "1000base-t"},
                "enabled": True,
                "mgmt_only": True,
            },
        ]
        device_facts = {
            "network_resources": {
                "interfaces": {
                    "1/1/1": {"admin": "up"},
                }
            }
        }
        result = get_interfaces_needing_config_changes(interfaces, device_facts)
        assert len(result["no_changes"]) == 1

    def test_mclag_interface_categorization(self):
        """Test MCLAG interface is categorized correctly"""
        interfaces = [
            {
                "name": "lag1",
                "type": {"value": "lag"},
                "enabled": True,
                "mode": {"value": "access"},
                "untagged_vlan": {"vid": 10},
                "custom_fields": {"if_mclag": True},
            },
        ]
        device_facts = {
            "network_resources": {
                "interfaces": {}  # LAG doesn't exist
            }
        }
        result = get_interfaces_needing_config_changes(interfaces, device_facts)
        assert len(result["mclag"]) == 1
        assert result["mclag"][0]["name"] == "lag1"

    def test_trunk_vlan_changes(self):
        """Test detection of trunk VLAN changes"""
        interfaces = [
            {
                "name": "1/1/1",
                "type": {"value": "1000base-t"},
                "enabled": True,
                "mode": {"value": "tagged"},
                "untagged_vlan": {"vid": 100},
                "tagged_vlans": [{"vid": 200}, {"vid": 300}],
            },
        ]
        device_facts = {
            "network_resources": {
                "interfaces": {
                    "1/1/1": {
                        "admin": "up",
                        "vlan_mode": "native-untagged",
                        "vlan_tag": {"100": {}},
                        "vlan_trunks": {"200": {}},  # Missing VLAN 300
                    }
                }
            }
        }
        result = get_interfaces_needing_config_changes(interfaces, device_facts)
        assert len(result["l2"]) == 1

    def test_loopback_interface(self):
        """Test loopback interface categorization"""
        interfaces = [
            {
                "name": "loopback0",
                "type": {"value": "virtual"},
                "ip_addresses": [{"address": "10.255.255.1/32"}],
            },
        ]
        device_facts = {
            "network_resources": {
                "interfaces": {}  # Loopback doesn't exist
            }
        }
        result = get_interfaces_needing_config_changes(interfaces, device_facts)
        assert len(result["l3"]) == 1
        assert result["l3"][0]["name"] == "loopback0"
