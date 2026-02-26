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


class TestEnhancedFacts:
    """Tests for get_interfaces_needing_config_changes with enhanced_facts parameter"""

    def _vlan_interface(self, ipv6_address):
        """Helper: NetBox VLAN interface with one IPv6 address"""
        return {
            "name": "vlan10",
            "type": {"value": "virtual"},
            "ip_addresses": [
                {
                    "address": ipv6_address,
                    "vrf": {"name": "default"},
                }
            ],
        }

    def _device_facts_with_url_ref(self):
        """Helper: device facts where ip6_addresses is a URL reference (standard aoscx_facts)"""
        return {
            "network_resources": {
                "interfaces": {
                    "vlan10": {
                        "admin": "up",
                        "ip6_addresses": (
                            "/rest/v10.09/system/interfaces/vlan10/ip6_addresses"
                        ),
                    }
                }
            }
        }

    def test_enhanced_facts_ipv6_already_configured_no_change(self):
        """IPv6 already on device via enhanced facts → no change needed"""
        interfaces = [self._vlan_interface("2001:db8::1/64")]
        device_facts = self._device_facts_with_url_ref()
        enhanced_facts = {
            "vlan10": {
                "ip6_addresses": {"2001:db8::1/64": {}}
            }
        }

        result = get_interfaces_needing_config_changes(
            interfaces, device_facts, enhanced_facts
        )

        assert len(result["l3"]) == 0
        assert len(result["no_changes"]) == 1

    def test_enhanced_facts_ipv6_missing_needs_adding(self):
        """IPv6 not on device via enhanced facts → interface needs change"""
        interfaces = [self._vlan_interface("2001:db8::1/64")]
        device_facts = self._device_facts_with_url_ref()
        enhanced_facts = {
            "vlan10": {
                "ip6_addresses": {}  # Empty — address not configured
            }
        }

        result = get_interfaces_needing_config_changes(
            interfaces, device_facts, enhanced_facts
        )

        assert len(result["l3"]) == 1
        assert result["l3"][0]["name"] == "vlan10"

    def test_enhanced_facts_ipv6_url_encoded_key(self):
        """Enhanced facts with URL-encoded IPv6 key is decoded and matched correctly"""
        interfaces = [self._vlan_interface("2001:db8::1/64")]
        device_facts = self._device_facts_with_url_ref()
        # REST API returns URL-encoded colons and slashes
        enhanced_facts = {
            "vlan10": {
                "ip6_addresses": {
                    "2001%3Adb8%3A%3A1%2F64": {}  # URL-encoded "2001:db8::1/64"
                }
            }
        }

        result = get_interfaces_needing_config_changes(
            interfaces, device_facts, enhanced_facts
        )

        assert len(result["l3"]) == 0
        assert len(result["no_changes"]) == 1

    def test_no_enhanced_facts_ipv6_always_marks_for_config(self):
        """Without enhanced facts, any IPv6 address triggers a change (fallback behaviour)"""
        interfaces = [self._vlan_interface("2001:db8::1/64")]
        device_facts = self._device_facts_with_url_ref()

        # No enhanced facts passed
        result = get_interfaces_needing_config_changes(interfaces, device_facts)

        assert len(result["l3"]) == 1

    def test_enhanced_facts_interface_not_in_enhanced_data(self):
        """Interface missing from enhanced_facts falls back to URL-reference behaviour"""
        interfaces = [self._vlan_interface("2001:db8::1/64")]
        device_facts = self._device_facts_with_url_ref()
        enhanced_facts = {}  # vlan10 not present

        result = get_interfaces_needing_config_changes(
            interfaces, device_facts, enhanced_facts
        )

        # Falls back: IPv6 present in NetBox → marks as needing config
        assert len(result["l3"]) == 1

    def test_enhanced_facts_vsx_virtual_ip_already_configured(self):
        """VSX virtual IP in enhanced facts does not trigger spurious change"""
        interfaces = [
            {
                "name": "vlan10",
                "type": {"value": "virtual"},
                "ip_addresses": [
                    {"address": "10.1.1.1/24", "vrf": {"name": "default"}}
                ],
                "custom_fields": {"if_anycast_gateway_mac": "02:01:00:00:01:00"},
            }
        ]
        device_facts = {
            "network_resources": {
                "interfaces": {
                    "vlan10": {
                        "admin": "up",
                        "ip4_address": "10.1.1.1/24",
                    }
                }
            }
        }
        enhanced_facts = {
            "vlan10": {
                "vsx_virtual_ip4": "10.1.1.1",
                "ip6_addresses": {},
            }
        }

        result = get_interfaces_needing_config_changes(
            interfaces, device_facts, enhanced_facts
        )
        # IPv4 already on device — no changes expected
        assert len(result["l3"]) == 0
