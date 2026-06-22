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
        result = get_interfaces_needing_config_changes(
            interfaces, device_facts)
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
        result = get_interfaces_needing_config_changes(
            interfaces, device_facts)
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
        result = get_interfaces_needing_config_changes(
            interfaces, device_facts)
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
        result = get_interfaces_needing_config_changes(
            interfaces, device_facts)
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
        result = get_interfaces_needing_config_changes(
            interfaces, device_facts)
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
        result = get_interfaces_needing_config_changes(
            interfaces, device_facts)
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
        result = get_interfaces_needing_config_changes(
            interfaces, device_facts)
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
        result = get_interfaces_needing_config_changes(
            interfaces, device_facts)
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
        result = get_interfaces_needing_config_changes(
            interfaces, device_facts)
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
        result = get_interfaces_needing_config_changes(
            interfaces, device_facts)
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
        result = get_interfaces_needing_config_changes(
            interfaces, device_facts)
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
        result = get_interfaces_needing_config_changes(
            interfaces, device_facts)
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
        result = get_interfaces_needing_config_changes(
            interfaces, device_facts)
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
        result = get_interfaces_needing_config_changes(
            interfaces, device_facts)
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
        result = get_interfaces_needing_config_changes(
            interfaces, device_facts)
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
        result = get_interfaces_needing_config_changes(
            interfaces, device_facts)

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

    def test_stale_anycast_ipv6_removed_from_netbox(self):
        """Stale active-gateway ipv6 on device (not in NetBox) is detected for removal"""
        interfaces = [
            {
                "name": "vlan101",
                "type": {"value": "virtual"},
                "vrf": {"name": "lab-blue"},
                "custom_fields": {"if_anycast_gateway_mac": "00:00:00:01:00:01"},
                "ip_addresses": [
                    {"address": "172.27.4.2/27", "role": None,
                        "vrf": {"name": "lab-blue"}},
                    {"address": "172.27.4.1/27", "role": {"value": "anycast"},
                        "vrf": {"name": "lab-blue"}},
                    {"address": "2001:db8:1000:10::2/64",
                        "role": None, "vrf": {"name": "lab-blue"}},
                    # Only fe80::1 in NetBox — 2001:db8:1000:10::1 was replaced with link-local
                    {"address": "fe80::1/64", "role": {"value": "anycast"},
                        "vrf": {"name": "lab-blue"}},
                ],
            }
        ]
        device_facts = {
            "network_resources": {
                "interfaces": {
                    "vlan101": {
                        "ip4_address": "172.27.4.2/27",
                        "ip6_addresses": {},
                    }
                }
            }
        }
        enhanced_facts = {
            "vlan101": {
                "ip4_address": "172.27.4.2/27",
                "ip4_address_secondary": [],
                "ip6_addresses": {"2001:db8:1000:10::2/64": "/rest/..."},
                # Device still has both active-gateway ipv6 entries
                "vsx_virtual_ip4": ["172.27.4.1"],
                "vsx_virtual_ip6": ["2001:db8:1000:10::1", "fe80::1"],
                "vsx_virtual_gw_mac_v4": "00:00:00:01:00:01",
                "vsx_virtual_gw_mac_v6": "00:00:00:01:00:01",
            }
        }

        result = get_interfaces_needing_config_changes(
            interfaces, device_facts, enhanced_facts
        )
        # Interface must be flagged for change (stale anycast to remove)
        assert len(result["l3"]) == 1
        intf = result["l3"][0]
        ip_changes = intf.get("_ip_changes", {})
        # Stale global-unicast anycast must be marked for removal
        assert "anycast_ipv6_to_remove" in ip_changes
        assert "2001:db8:1000:10::1" in ip_changes["anycast_ipv6_to_remove"]
        # fe80::1 is in NetBox — must NOT be in removal list
        assert "fe80::1" not in ip_changes["anycast_ipv6_to_remove"]
        # IPv4 anycast matches NetBox — must NOT be in removal list
        assert ip_changes.get("anycast_ipv4_to_remove", []) == []

    def test_no_stale_anycast_when_device_matches_netbox(self):
        """No removal triggered when device active-gateway matches NetBox exactly"""
        interfaces = [
            {
                "name": "vlan101",
                "type": {"value": "virtual"},
                "vrf": {"name": "lab-blue"},
                "custom_fields": {"if_anycast_gateway_mac": "00:00:00:01:00:01"},
                "ip_addresses": [
                    {"address": "172.27.4.2/27", "role": None,
                        "vrf": {"name": "lab-blue"}},
                    {"address": "172.27.4.1/27", "role": {"value": "anycast"},
                        "vrf": {"name": "lab-blue"}},
                    {"address": "2001:db8:1000:10::2/64",
                        "role": None, "vrf": {"name": "lab-blue"}},
                    {"address": "fe80::1/64", "role": {"value": "anycast"},
                        "vrf": {"name": "lab-blue"}},
                ],
            }
        ]
        device_facts = {
            "network_resources": {
                "interfaces": {
                    "vlan101": {
                        "ip4_address": "172.27.4.2/27",
                        "ip6_addresses": {},
                    }
                }
            }
        }
        enhanced_facts = {
            "vlan101": {
                "ip4_address": "172.27.4.2/27",
                "ip4_address_secondary": [],
                "ip6_addresses": {"2001:db8:1000:10::2/64": "/rest/...", "fe80::1/64": "/rest/..."},
                # Device matches NetBox — only fe80::1 as active-gateway ipv6
                "vsx_virtual_ip4": ["172.27.4.1"],
                "vsx_virtual_ip6": ["fe80::1"],
                "vsx_virtual_gw_mac_v4": "00:00:00:01:00:01",
                "vsx_virtual_gw_mac_v6": "00:00:00:01:00:01",
            }
        }

        result = get_interfaces_needing_config_changes(
            interfaces, device_facts, enhanced_facts
        )
        # Everything matches — interface must NOT need any IP changes
        for intf in result.get("l3", []):
            ip_changes = intf.get("_ip_changes", {})
            assert ip_changes.get("anycast_ipv6_to_remove", []) == []
            assert ip_changes.get("anycast_ipv4_to_remove", []) == []

    def test_link_local_anycast_missing_link_local_address_detected(self):
        """When active-gateway ipv6 fe80::1 is configured but 'ipv6 address link-local'
        is missing, link_local_ipv6_to_add must contain the full address with prefix"""
        interfaces = [
            {
                "name": "vlan102",
                "type": {"value": "virtual"},
                "vrf": {"name": "lab-blue"},
                "custom_fields": {"if_anycast_gateway_mac": "00:00:00:01:00:01"},
                "ip_addresses": [
                    {"address": "172.27.4.34/27", "role": None,
                        "vrf": {"name": "lab-blue"}},
                    {"address": "172.27.4.33/27", "role": {"value": "anycast"},
                        "vrf": {"name": "lab-blue"}},
                    {"address": "2001:db8:1000:11::2/64",
                        "role": None, "vrf": {"name": "lab-blue"}},
                    {"address": "fe80::1/64", "role": {"value": "anycast"},
                        "vrf": {"name": "lab-blue"}},
                ],
            }
        ]
        device_facts = {
            "network_resources": {"interfaces": {"vlan102": {"ip4_address": "172.27.4.34/27", "ip6_addresses": {}}}}
        }
        enhanced_facts = {
            "vlan102": {
                "ip4_address": "172.27.4.34/27",
                "ip4_address_secondary": [],
                "ip6_addresses": {"2001:db8:1000:11::2/64": "/rest/..."},
                "vsx_virtual_ip4": ["172.27.4.33"],
                "vsx_virtual_ip6": ["fe80::1"],
                "vsx_virtual_gw_mac_v4": "00:00:00:01:00:01",
                "vsx_virtual_gw_mac_v6": "00:00:00:01:00:01",
                # Auto-generated link-local (NOT the custom fe80::1)
                "ip6_address_link_local": {"fe80::3810:f080:668c:f880/64": "/rest/.../ip6_autoconfigured_addresses/..."},
            }
        }

        result = get_interfaces_needing_config_changes(
            interfaces, device_facts, enhanced_facts)
        l3_intfs = result.get("l3", [])
        vlan102 = next((i for i in l3_intfs if i["name"] == "vlan102"), None)
        assert vlan102 is not None, "vlan102 should need changes"
        ip_changes = vlan102.get("_ip_changes", {})
        assert "link_local_ipv6_to_add" in ip_changes
        assert "fe80::1/64" in ip_changes["link_local_ipv6_to_add"]

    def test_link_local_anycast_already_configured_no_change(self):
        """When 'ipv6 address link-local fe80::1/64' is correctly configured,
        link_local_ipv6_to_add must be absent (no change needed)"""
        interfaces = [
            {
                "name": "vlan101",
                "type": {"value": "virtual"},
                "vrf": {"name": "lab-blue"},
                "custom_fields": {"if_anycast_gateway_mac": "00:00:00:01:00:01"},
                "ip_addresses": [
                    {"address": "172.27.4.2/27", "role": None,
                        "vrf": {"name": "lab-blue"}},
                    {"address": "172.27.4.1/27", "role": {"value": "anycast"},
                        "vrf": {"name": "lab-blue"}},
                    {"address": "2001:db8:1000:10::2/64",
                        "role": None, "vrf": {"name": "lab-blue"}},
                    {"address": "fe80::1/64", "role": {"value": "anycast"},
                        "vrf": {"name": "lab-blue"}},
                ],
            }
        ]
        device_facts = {
            "network_resources": {"interfaces": {"vlan101": {"ip4_address": "172.27.4.2/27", "ip6_addresses": {}}}}
        }
        enhanced_facts = {
            "vlan101": {
                "ip4_address": "172.27.4.2/27",
                "ip4_address_secondary": [],
                "ip6_addresses": {"2001:db8:1000:10::2/64": "/rest/..."},
                "vsx_virtual_ip4": ["172.27.4.1"],
                "vsx_virtual_ip6": ["fe80::1"],
                "vsx_virtual_gw_mac_v4": "00:00:00:01:00:01",
                "vsx_virtual_gw_mac_v6": "00:00:00:01:00:01",
                # Custom link-local configured correctly
                "ip6_address_link_local": {"fe80::1/64": "/rest/.../ip6_address_custom_link_local/fe80::1%2F64"},
            }
        }

        result = get_interfaces_needing_config_changes(
            interfaces, device_facts, enhanced_facts)
        # Interface may still be in l3 for other reasons, but link_local_ipv6_to_add must be absent
        for intf in result.get("l3", []) + result.get("no_changes", []):
            if intf["name"] == "vlan101":
                ip_changes = intf.get("_ip_changes", {})
                assert ip_changes.get("link_local_ipv6_to_add", []) == []

    def test_global_unicast_anycast_no_link_local_check(self):
        """Global-unicast anycast (non-fe80) must never trigger link_local_ipv6_to_add"""
        interfaces = [
            {
                "name": "vlan103",
                "type": {"value": "virtual"},
                "custom_fields": {"if_anycast_gateway_mac": "00:00:00:01:00:01"},
                "ip_addresses": [
                    {"address": "2001:db8:1000:12::2/64", "role": None},
                    {"address": "2001:db8:1000:12::1/64",
                        "role": {"value": "anycast"}},
                ],
            }
        ]
        device_facts = {
            "network_resources": {"interfaces": {"vlan103": {"ip4_address": None, "ip6_addresses": {}}}}
        }
        enhanced_facts = {
            "vlan103": {
                "ip4_address": None,
                "ip4_address_secondary": [],
                "ip6_addresses": {"2001:db8:1000:12::2/64": "/rest/..."},
                "vsx_virtual_ip4": [],
                "vsx_virtual_ip6": ["2001:db8:1000:12::1"],
                "vsx_virtual_gw_mac_v6": "00:00:00:01:00:01",
                "ip6_address_link_local": {"fe80::abc:def/64": "/rest/.../ip6_autoconfigured_addresses/..."},
            }
        }

        result = get_interfaces_needing_config_changes(
            interfaces, device_facts, enhanced_facts)
        for intf in result.get("l3", []) + result.get("no_changes", []):
            if intf["name"] == "vlan103":
                ip_changes = intf.get("_ip_changes", {})
                assert ip_changes.get("link_local_ipv6_to_add", []) == []

    def test_stale_ipv6_address_detected_for_removal(self):
        """Device has an IPv6 address that was removed from NetBox → ipv6_to_remove populated"""
        interfaces = [self._vlan_interface("2001:db8::2/64")]
        device_facts = self._device_facts_with_url_ref()
        enhanced_facts = {
            "vlan10": {
                # Device has the old address (::1) and does NOT have the new one (::2)
                "ip6_addresses": {"2001:db8::1/64": {}}
            }
        }

        result = get_interfaces_needing_config_changes(
            interfaces, device_facts, enhanced_facts
        )

        assert len(result["l3"]) == 1, "Interface should need changes"
        ip_changes = result["l3"][0].get("_ip_changes", {})
        assert "2001:db8::1/64" in ip_changes.get("ipv6_to_remove", [])
        assert "2001:db8::2/64" in ip_changes.get("ipv6_to_add", [])

    def test_stale_ipv6_no_removal_when_address_unchanged(self):
        """When NetBox and device IPv6 match exactly, ipv6_to_remove is empty"""
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

        assert len(result["no_changes"]) == 1
        # Interface needs no changes so _ip_changes may not even be set
        for intf in result.get("l3", []) + result.get("no_changes", []):
            if intf["name"] == "vlan10":
                assert intf.get("_ip_changes", {}).get(
                    "ipv6_to_remove", []) == []

    def test_stale_ipv6_all_ipv6_removed_interface_still_has_ipv4(self):
        """All IPv6 removed from NetBox but device still has them; interface retains IPv4.
        The stale IPv6 address must be marked for removal."""
        interfaces = [
            {
                "name": "vlan10",
                "type": {"value": "virtual"},
                "ip_addresses": [
                    {"address": "10.0.0.1/24", "vrf": {"name": "default"}}
                ],  # Only IPv4 remains in NetBox
            }
        ]
        device_facts = {
            "network_resources": {
                "interfaces": {
                    "vlan10": {
                        "admin": "up",
                        "ip4_address": "10.0.0.1/24",
                        "ip6_addresses": (
                            "/rest/v10.09/system/interfaces/vlan10/ip6_addresses"
                        ),
                    }
                }
            }
        }
        enhanced_facts = {
            "vlan10": {
                "ip4_address": "10.0.0.1/24",
                "ip6_addresses": {"2001:db8::1/64": {}}
            }
        }

        result = get_interfaces_needing_config_changes(
            interfaces, device_facts, enhanced_facts
        )

        assert len(
            result["l3"]) == 1, "Interface should need changes (stale IPv6 to remove)"
        ip_changes = result["l3"][0].get("_ip_changes", {})
        assert "2001:db8::1/64" in ip_changes.get("ipv6_to_remove", [])


# ──────────────────────────────────────────────────────────────────────────────
# DHCP relay / ip helper-address change detection
# ──────────────────────────────────────────────────────────────────────────────

def _vlan_intf_with_helper(name, vrf_name, if_ip_helper=True):
    """Helper: minimal NetBox VLAN interface with ip_helper custom field."""
    return {
        "name": name,
        "type": {"value": "virtual", "label": "Virtual"},
        "enabled": True,
        "description": "",
        "mtu": None,
        "lag": None,
        "mode": None,
        "mgmt_only": False,
        "custom_fields": {"if_ip_helper": if_ip_helper},
        "vrf": {"name": vrf_name, "id": 1},
        "ip_addresses": [
            {"address": "10.0.0.1/24", "role": None, "family": {"value": 4}},
        ],
        "tagged_vlans": [],
        "untagged_vlan": {"vid": 100},
    }


def _device_facts_for(intf_name, ip="10.0.0.1/24"):
    return {
        "network_resources": {
            "interfaces": {
                intf_name: {
                    "admin": "up",
                    "ip4_address": ip,
                    "ip6_addresses": {},
                }
            }
        }
    }


_IP_HELPER_ADDRESSES = {
    "lab-blue": {"0": "172.16.3.10", "1": "172.16.3.11"},
    "lab-green": {"0": "172.16.3.12", "1": "172.16.3.13"},
}


class TestDhcpRelayChangeDetection:
    """Tests for DHCP relay / ip helper-address change detection."""

    def test_no_change_when_helpers_match(self):
        """Interface skips L3 push when device relay servers match NetBox config."""
        iface = _vlan_intf_with_helper("vlan101", "lab-blue")
        device_facts = _device_facts_for("vlan101")
        dhcp_relay_facts = {"vlan101": ["172.16.3.10", "172.16.3.11"]}

        result = get_interfaces_needing_config_changes(
            [iface], device_facts,
            dhcp_relay_facts=dhcp_relay_facts,
            ip_helper_addresses=_IP_HELPER_ADDRESSES,
        )

        assert len(result["no_changes"]) == 1
        assert len(result["l3"]) == 0

    def test_change_when_helpers_differ(self):
        """Interface is pushed when device relay servers differ from NetBox config."""
        iface = _vlan_intf_with_helper("vlan101", "lab-blue")
        device_facts = _device_facts_for("vlan101")
        dhcp_relay_facts = {"vlan101": ["172.16.3.99"]}  # wrong server

        result = get_interfaces_needing_config_changes(
            [iface], device_facts,
            dhcp_relay_facts=dhcp_relay_facts,
            ip_helper_addresses=_IP_HELPER_ADDRESSES,
        )

        assert len(result["l3"]) == 1

    def test_change_when_helpers_missing_from_device(self):
        """Interface is pushed when device has no relays but NetBox wants some."""
        iface = _vlan_intf_with_helper("vlan101", "lab-blue")
        device_facts = _device_facts_for("vlan101")
        dhcp_relay_facts = {}  # no relays on device

        result = get_interfaces_needing_config_changes(
            [iface], device_facts,
            dhcp_relay_facts=dhcp_relay_facts,
            ip_helper_addresses=_IP_HELPER_ADDRESSES,
        )

        assert len(result["l3"]) == 1

    def test_change_when_no_relay_facts_available(self):
        """Conservative: interface always pushed when dhcp_relay_facts is None."""
        iface = _vlan_intf_with_helper("vlan101", "lab-blue")
        device_facts = _device_facts_for("vlan101")

        result = get_interfaces_needing_config_changes(
            [iface], device_facts,
            dhcp_relay_facts=None,
            ip_helper_addresses=_IP_HELPER_ADDRESSES,
        )

        assert len(result["l3"]) == 1

    def test_no_helper_flag_and_no_device_relays_no_change(self):
        """No change when if_ip_helper=False and device has no relays."""
        iface = _vlan_intf_with_helper(
            "vlan101", "lab-blue", if_ip_helper=False)
        device_facts = _device_facts_for("vlan101")
        dhcp_relay_facts = {}

        result = get_interfaces_needing_config_changes(
            [iface], device_facts,
            dhcp_relay_facts=dhcp_relay_facts,
            ip_helper_addresses=_IP_HELPER_ADDRESSES,
        )

        assert len(result["no_changes"]) == 1
        assert len(result["l3"]) == 0

    def test_stale_relay_triggers_change(self):
        """Interface is pushed when if_ip_helper=False but device has stale relays."""
        iface = _vlan_intf_with_helper(
            "vlan101", "lab-blue", if_ip_helper=False)
        device_facts = _device_facts_for("vlan101")
        dhcp_relay_facts = {"vlan101": ["172.16.3.10"]}  # stale

        result = get_interfaces_needing_config_changes(
            [iface], device_facts,
            dhcp_relay_facts=dhcp_relay_facts,
            ip_helper_addresses=_IP_HELPER_ADDRESSES,
        )

        assert len(result["l3"]) == 1

    def test_uses_interface_vrf_not_ip_vrf(self):
        """Relay comparison uses the interface VRF, not the IP address VRF."""
        iface = _vlan_intf_with_helper("vlan201", "lab-green")
        device_facts = _device_facts_for("vlan201")
        # Device has the lab-green helpers, not lab-blue ones
        dhcp_relay_facts = {"vlan201": ["172.16.3.12", "172.16.3.13"]}

        result = get_interfaces_needing_config_changes(
            [iface], device_facts,
            dhcp_relay_facts=dhcp_relay_facts,
            ip_helper_addresses=_IP_HELPER_ADDRESSES,
        )

        assert len(result["no_changes"]) == 1
        assert len(result["l3"]) == 0

    def test_dhcp_relay_change_flag_set_on_mismatch(self):
        """_ip_changes['dhcp_relay_change'] is True when relay servers differ."""
        iface = _vlan_intf_with_helper("vlan101", "lab-blue")
        device_facts = _device_facts_for("vlan101")
        dhcp_relay_facts = {"vlan101": ["172.16.3.99"]}

        result = get_interfaces_needing_config_changes(
            [iface], device_facts,
            dhcp_relay_facts=dhcp_relay_facts,
            ip_helper_addresses=_IP_HELPER_ADDRESSES,
        )

        assert len(result["l3"]) == 1
        assert result["l3"][0].get("_ip_changes", {}).get(
            "dhcp_relay_change") is True

    def test_dhcp_relay_change_flag_set_when_no_facts(self):
        """_ip_changes['dhcp_relay_change'] is True when dhcp_relay_facts is None."""
        iface = _vlan_intf_with_helper("vlan101", "lab-blue")
        device_facts = _device_facts_for("vlan101")

        result = get_interfaces_needing_config_changes(
            [iface], device_facts,
            dhcp_relay_facts=None,
            ip_helper_addresses=_IP_HELPER_ADDRESSES,
        )

        assert len(result["l3"]) == 1
        assert result["l3"][0].get("_ip_changes", {}).get(
            "dhcp_relay_change") is True

    def test_dhcp_relay_change_flag_set_on_stale_relay(self):
        """_ip_changes['dhcp_relay_change'] is True when stale relays need removal."""
        iface = _vlan_intf_with_helper(
            "vlan101", "lab-blue", if_ip_helper=False)
        device_facts = _device_facts_for("vlan101")
        dhcp_relay_facts = {"vlan101": ["172.16.3.10"]}

        result = get_interfaces_needing_config_changes(
            [iface], device_facts,
            dhcp_relay_facts=dhcp_relay_facts,
            ip_helper_addresses=_IP_HELPER_ADDRESSES,
        )

        assert len(result["l3"]) == 1
        assert result["l3"][0].get("_ip_changes", {}).get(
            "dhcp_relay_change") is True

    def test_dhcp_relay_change_flag_not_set_when_match(self):
        """_ip_changes['dhcp_relay_change'] is absent/False when relay already correct."""
        iface = _vlan_intf_with_helper("vlan101", "lab-blue")
        device_facts = _device_facts_for("vlan101")
        dhcp_relay_facts = {"vlan101": ["172.16.3.10", "172.16.3.11"]}

        result = get_interfaces_needing_config_changes(
            [iface], device_facts,
            dhcp_relay_facts=dhcp_relay_facts,
            ip_helper_addresses=_IP_HELPER_ADDRESSES,
        )

        assert len(result["no_changes"]) == 1
        # Flag must not be set on interfaces that went to no_changes
        flag = result["no_changes"][0].get(
            "_ip_changes", {}).get("dhcp_relay_change")
        assert not flag

    def test_dhcp_relay_to_remove_contains_stale_ips(self):
        """dhcp_relay_to_remove holds only the IPs present on device but not in NetBox."""
        iface = _vlan_intf_with_helper("vlan101", "lab-blue")
        device_facts = _device_facts_for("vlan101")
        # Device has an extra stale server (.99) alongside one correct one
        dhcp_relay_facts = {"vlan101": ["172.16.3.10", "172.16.3.99"]}

        result = get_interfaces_needing_config_changes(
            [iface], device_facts,
            dhcp_relay_facts=dhcp_relay_facts,
            ip_helper_addresses=_IP_HELPER_ADDRESSES,
        )

        assert len(result["l3"]) == 1
        to_remove = result["l3"][0].get(
            "_ip_changes", {}).get("dhcp_relay_to_remove", [])
        assert to_remove == ["172.16.3.99"]

    def test_dhcp_relay_to_remove_not_set_when_only_adding(self):
        """dhcp_relay_to_remove is absent when device has no extra IPs (only missing ones)."""
        iface = _vlan_intf_with_helper("vlan101", "lab-blue")
        device_facts = _device_facts_for("vlan101")
        dhcp_relay_facts = {}  # device has no relays at all — only need to add

        result = get_interfaces_needing_config_changes(
            [iface], device_facts,
            dhcp_relay_facts=dhcp_relay_facts,
            ip_helper_addresses=_IP_HELPER_ADDRESSES,
        )

        assert len(result["l3"]) == 1
        to_remove = result["l3"][0].get(
            "_ip_changes", {}).get("dhcp_relay_to_remove", [])
        assert to_remove == []

    def test_dhcp_relay_to_remove_all_when_if_ip_helper_false(self):
        """All device relays go in dhcp_relay_to_remove when if_ip_helper=False."""
        iface = _vlan_intf_with_helper(
            "vlan101", "lab-blue", if_ip_helper=False)
        device_facts = _device_facts_for("vlan101")
        dhcp_relay_facts = {"vlan101": ["172.16.3.10", "172.16.3.11"]}

        result = get_interfaces_needing_config_changes(
            [iface], device_facts,
            dhcp_relay_facts=dhcp_relay_facts,
            ip_helper_addresses=_IP_HELPER_ADDRESSES,
        )

        assert len(result["l3"]) == 1
        to_remove = result["l3"][0].get(
            "_ip_changes", {}).get("dhcp_relay_to_remove", [])
        assert sorted(to_remove) == ["172.16.3.10", "172.16.3.11"]


# ──────────────────────────────────────────────────────────────────────────────
# VRF change detection
# ──────────────────────────────────────────────────────────────────────────────

class TestVrfChangeDetection:
    """Tests for VRF mismatch detection and full L3 reconfiguration override."""

    def _make_vlan_intf(self, name, vrf_name, ip="10.0.0.1/24"):
        """Minimal L3 VLAN interface with a VRF and one IPv4 address."""
        return {
            "name": name,
            "type": {"value": "virtual"},
            "enabled": True,
            "description": "",
            "mtu": None,
            "lag": None,
            "mode": None,
            "mgmt_only": False,
            "custom_fields": {},
            "vrf": {"name": vrf_name} if vrf_name else None,
            "ip_addresses": [
                {"address": ip, "role": None},
            ],
            "tagged_vlans": [],
            "untagged_vlan": None,
        }

    def _device_facts(self, intf_name, ip="10.0.0.1/24", vrf=None):
        """Device facts where the interface is already configured."""
        intf_data = {
            "admin": "up",
            "ip4_address": ip,
            "ip6_addresses": {},
        }
        if vrf is not None:
            intf_data["vrf"] = vrf
        return {
            "network_resources": {
                "interfaces": {intf_name: intf_data}
            }
        }

    def test_no_change_when_vrf_matches_enhanced(self):
        """No change triggered when VRF matches in enhanced facts."""
        iface = self._make_vlan_intf("vlan10", "lab-blue")
        device_facts = self._device_facts("vlan10")
        enhanced_facts = {
            "vlan10": {
                "ip4_address": "10.0.0.1/24",
                "ip6_addresses": {},
                "vrf": {"lab-blue": "/rest/v10.09/system/vrfs/lab-blue"},
            }
        }
        result = get_interfaces_needing_config_changes(
            [iface], device_facts, enhanced_facts
        )
        assert len(result["no_changes"]) == 1
        assert len(result["l3"]) == 0

    def test_vrf_change_detected_via_enhanced_facts(self):
        """VRF mismatch is detected when enhanced facts provide device VRF."""
        iface = self._make_vlan_intf("vlan10", "lab-blue")
        device_facts = self._device_facts("vlan10")
        # Device currently has a different VRF
        enhanced_facts = {
            "vlan10": {
                "ip4_address": "10.0.0.1/24",
                "ip6_addresses": {},
                "vrf": {"lab-red": "/rest/v10.09/system/vrfs/lab-red"},
            }
        }
        result = get_interfaces_needing_config_changes(
            [iface], device_facts, enhanced_facts
        )
        assert len(result["l3"]) == 1
        ip_changes = result["l3"][0].get("_ip_changes", {})
        assert ip_changes.get("vrf_change") is True

    def test_vrf_change_forces_all_ipv4_to_add(self):
        """When VRF changes, all IPv4 addresses are included in ipv4_to_add even if
        they already appear on the device (they will be wiped by the VRF change)."""
        iface = self._make_vlan_intf("vlan10", "lab-blue", ip="10.0.0.1/24")
        # Device already has the same IP but wrong VRF
        device_facts = self._device_facts("vlan10", ip="10.0.0.1/24")
        enhanced_facts = {
            "vlan10": {
                "ip4_address": "10.0.0.1/24",
                "ip6_addresses": {},
                "vrf": {"lab-red": "/rest/v10.09/system/vrfs/lab-red"},
            }
        }
        result = get_interfaces_needing_config_changes(
            [iface], device_facts, enhanced_facts
        )
        assert len(result["l3"]) == 1
        ip_changes = result["l3"][0].get("_ip_changes", {})
        assert "10.0.0.1/24" in ip_changes.get("ipv4_to_add", [])

    def test_vrf_change_detected_via_standard_facts(self):
        """VRF mismatch is detected when standard device facts carry VRF data."""
        iface = self._make_vlan_intf("vlan10", "lab-blue")
        # Standard facts include VRF as a dict (REST-API style)
        device_facts = self._device_facts(
            "vlan10",
            vrf={"lab-red": "/rest/v10.09/system/vrfs/lab-red"},
        )
        result = get_interfaces_needing_config_changes(
            [iface], device_facts
        )
        assert len(result["l3"]) == 1
        ip_changes = result["l3"][0].get("_ip_changes", {})
        assert ip_changes.get("vrf_change") is True

    def test_no_false_positive_when_vrf_absent_from_facts(self):
        """No VRF change triggered when device facts carry no VRF data at all."""
        iface = self._make_vlan_intf("vlan10", "lab-blue")
        # Standard facts with NO vrf field — common with basic aoscx_facts
        device_facts = self._device_facts("vlan10")  # vrf=None (absent)
        result = get_interfaces_needing_config_changes(
            [iface], device_facts
        )
        # IP already matches — no change expected despite missing VRF data
        assert len(result["no_changes"]) == 1
        assert len(result["l3"]) == 0

    def test_netbox_default_vrf_matches_device_default(self):
        """Interface with no VRF in NetBox (defaults to 'default') matches
        a device that explicitly shows the default VRF."""
        iface = self._make_vlan_intf("vlan10", None)  # no VRF → default
        device_facts = self._device_facts("vlan10")
        enhanced_facts = {
            "vlan10": {
                "ip4_address": "10.0.0.1/24",
                "ip6_addresses": {},
                "vrf": {"default": "/rest/v10.09/system/vrfs/default"},
            }
        }
        result = get_interfaces_needing_config_changes(
            [iface], device_facts, enhanced_facts
        )
        assert len(result["no_changes"]) == 1
        assert len(result["l3"]) == 0

    def test_vrf_change_detected_default_to_custom_via_enhanced_facts(self):
        """VRF change is detected when device is in default VRF (vrf=null in REST API)
        but NetBox assigns a custom VRF. The null REST API value must be treated as
        'default', not 'no data', so the mismatch triggers vrf_change=True."""
        iface = self._make_vlan_intf("vlan10", "lab-blue", ip="10.0.0.1/24")
        device_facts = self._device_facts("vlan10", ip="10.0.0.1/24")
        # REST API reports vrf=null → interface is in default VRF on device
        enhanced_facts = {
            "vlan10": {
                "ip4_address": "10.0.0.1/24",
                "ip6_addresses": {},
                "vrf": None,
            }
        }
        result = get_interfaces_needing_config_changes(
            [iface], device_facts, enhanced_facts
        )
        assert len(result["l3"]) == 1
        ip_changes = result["l3"][0].get("_ip_changes", {})
        assert ip_changes.get("vrf_change") is True
        # All IPs must be in ipv4_to_add (device will wipe L3 on VRF change)
        assert "10.0.0.1/24" in ip_changes.get("ipv4_to_add", [])
