"""
Unit tests for REST API transform filter functions
"""
import pytest
from rest_api_transforms import (
    rest_api_to_aoscx_interfaces,
    rest_api_to_aoscx_vlans,
    rest_api_to_aoscx_evpn_vlans,
    rest_api_to_aoscx_vnis,
    rest_api_to_aoscx_dhcp_relays,
    rest_api_to_aoscx_bgp,
)


class TestRestApiToAoscxInterfaces:
    """Tests for rest_api_to_aoscx_interfaces function"""

    def test_basic_interface_conversion(self):
        """Test basic interface data conversion"""
        rest_data = {
            "1/1/1": {
                "admin_state": "up",
                "description": "Uplink",
                "mtu": 9198,
                "type": "physical",
            }
        }
        result = rest_api_to_aoscx_interfaces(rest_data)
        assert "1/1/1" in result
        assert result["1/1/1"]["name"] == "1/1/1"
        assert result["1/1/1"]["admin"] == "up"
        assert result["1/1/1"]["description"] == "Uplink"
        assert result["1/1/1"]["mtu"] == 9198

    def test_ipv6_addresses_conversion(self):
        """Test IPv6 addresses are properly decoded from URL-encoded keys"""
        rest_data = {
            "vlan10": {
                "admin_state": "up",
                "ip6_addresses": {
                    "2001%3Adb8%3A%3A1%2F64": {
                        "address": "2001:db8::1/64"
                    }
                },
            }
        }
        result = rest_api_to_aoscx_interfaces(rest_data)
        assert "vlan10" in result
        ip6 = result["vlan10"]["ip6_addresses"]
        assert isinstance(ip6, dict)
        assert "2001:db8::1/64" in ip6

    def test_vsx_virtual_ips(self):
        """Test VSX virtual IPs are included"""
        rest_data = {
            "vlan100": {
                "admin_state": "up",
                "vsx_virtual_ip4": "10.1.100.254/24",
                "vsx_virtual_ip6": "2001:db8:100::fe/64",
                "vsx_virtual_gw_mac_v4": "00:00:5e:00:01:01",
            }
        }
        result = rest_api_to_aoscx_interfaces(rest_data)
        assert result["vlan100"]["vsx_virtual_ip4"] == "10.1.100.254/24"
        assert result["vlan100"]["vsx_virtual_ip6"] == "2001:db8:100::fe/64"
        assert result["vlan100"]["vsx_virtual_gw_mac_v4"] == "00:00:5e:00:01:01"

    def test_empty_input(self):
        """Test with empty input"""
        result = rest_api_to_aoscx_interfaces({})
        assert result == {}

    def test_non_dict_input(self):
        """Test with non-dict input"""
        result = rest_api_to_aoscx_interfaces(None)
        assert result == {}
        result = rest_api_to_aoscx_interfaces([])
        assert result == {}
        result = rest_api_to_aoscx_interfaces("string")
        assert result == {}

    def test_admin_field_fallback(self):
        """Test admin field fallback when admin_state is not present"""
        rest_data = {
            "1/1/1": {
                "admin": "down",
                "description": "Test",
            }
        }
        result = rest_api_to_aoscx_interfaces(rest_data)
        assert result["1/1/1"]["admin"] == "down"

    def test_ipv6_as_url_string(self):
        """Test handling of IPv6 as URL string (older API versions)"""
        rest_data = {
            "vlan10": {
                "admin_state": "up",
                "ip6_addresses": "/rest/v10.09/system/interfaces/vlan10/ip6_addresses",
            }
        }
        result = rest_api_to_aoscx_interfaces(rest_data)
        # Should keep the URL string as-is
        assert result["vlan10"]["ip6_addresses"] == \
            "/rest/v10.09/system/interfaces/vlan10/ip6_addresses"

    def test_multiple_interfaces(self):
        """Test conversion of multiple interfaces"""
        rest_data = {
            "1/1/1": {"admin_state": "up", "description": "Port 1"},
            "1/1/2": {"admin_state": "down", "description": "Port 2"},
            "vlan10": {"admin_state": "up", "description": "VLAN 10"},
        }
        result = rest_api_to_aoscx_interfaces(rest_data)
        assert len(result) == 3
        assert "1/1/1" in result
        assert "1/1/2" in result
        assert "vlan10" in result

    def test_lag_interface_members(self):
        """Test that LAG interface member list is preserved"""
        rest_data = {
            "lag10": {
                "admin": "up",
                "type": "lag",
                "interfaces": {
                    "1/1/1": "/rest/v10.16/system/interfaces/1%2F1%2F1",
                    "1/1/2": "/rest/v10.16/system/interfaces/1%2F1%2F2",
                },
            },
            "1/1/1": {"admin": "up", "type": "system"},
            "1/1/2": {"admin": "up", "type": "system"},
        }
        result = rest_api_to_aoscx_interfaces(rest_data)
        assert "lag10" in result
        assert "1/1/1" in result["lag10"]["interfaces"]
        assert "1/1/2" in result["lag10"]["interfaces"]
        assert result["1/1/1"]["interfaces"] == {}

    def test_admin_null_stays_none_not_up(self):
        """admin/admin_state present but null must stay None, NOT default
        to 'up'.

        Regression test: the AOS-CX REST API has been observed to return
        'admin': null for interfaces regardless of their actual admin
        state - including ones that are genuinely disabled. Guessing "up"
        whenever both fields are null/missing caused
        _get_device_enabled_state() (interface_change_detection.py) to
        report false drift for interfaces that were correctly shut down,
        because it relies on None specifically to mean "unknown, don't
        compare" - see the module docstring NOTE and CHANGELOG.md.
        """
        rest_data = {
            "1/1/1": {"admin_state": None, "admin": None, "type": "system"},
        }
        result = rest_api_to_aoscx_interfaces(rest_data)
        assert result["1/1/1"]["admin"] is None

    def test_admin_and_admin_state_absent_stays_none(self):
        """Neither field present at all - stays None, not guessed as 'up'."""
        rest_data = {"1/1/1": {"type": "system"}}
        result = rest_api_to_aoscx_interfaces(rest_data)
        assert result["1/1/1"]["admin"] is None

    def test_user_config_passed_through(self):
        """user_config is carried through unchanged.

        This is what interface_change_detection.py's
        _get_device_enabled_state() actually relies on when 'admin' itself
        is null/unreliable - see the module docstring NOTE.
        """
        rest_data = {
            "1/1/1": {
                "admin": None,
                "user_config": {"admin": "down"},
            }
        }
        result = rest_api_to_aoscx_interfaces(rest_data)
        assert result["1/1/1"]["user_config"] == {"admin": "down"}

    def test_user_config_defaults_when_absent(self):
        """When not queried/returned, default to an empty dict."""
        rest_data = {"1/1/1": {"admin": "up"}}
        result = rest_api_to_aoscx_interfaces(rest_data)
        assert result["1/1/1"]["user_config"] == {}

    def test_forwarding_state_not_passed_through(self):
        """forwarding_state must NOT appear in the result even if present
        on the raw REST data.

        It reflects operational forwarding readiness (link/traffic), not
        admin-configured intent, and using it as an enabled-state signal
        produces false results in both directions - see the module
        docstring NOTE and CHANGELOG.md.
        """
        rest_data = {
            "1/1/1": {"admin": "up", "forwarding_state": {"enablement": False}}
        }
        result = rest_api_to_aoscx_interfaces(rest_data)
        assert "forwarding_state" not in result["1/1/1"]


class TestRestApiToAoscxInterfacesIpMtu:
    """ip_mtu is passed through only when the REST query requested it."""

    def test_ip_mtu_passed_through_when_present(self):
        result = rest_api_to_aoscx_interfaces({"vlan5": {"ip_mtu": 9198}})
        assert result["vlan5"]["ip_mtu"] == 9198

    def test_ip_mtu_null_kept_as_none(self):
        result = rest_api_to_aoscx_interfaces({"1/1/1": {"ip_mtu": None}})
        assert "ip_mtu" in result["1/1/1"]
        assert result["1/1/1"]["ip_mtu"] is None

    def test_ip_mtu_absent_when_not_queried(self):
        result = rest_api_to_aoscx_interfaces({"vlan5": {"mtu": 1500}})
        assert "ip_mtu" not in result["vlan5"]


class TestRestApiToAoscxVlans:
    """Tests for rest_api_to_aoscx_vlans function"""

    def test_basic_vlan_conversion(self):
        """Test basic VLAN data conversion"""
        rest_data = {
            "10": {
                "id": 10,
                "name": "DATA",
                "description": "Data VLAN",
                "admin": "up",
                "voice": False,
                "type": "static",
            }
        }
        result = rest_api_to_aoscx_vlans(rest_data)
        assert "10" in result
        assert result["10"]["id"] == 10
        assert result["10"]["name"] == "DATA"
        assert result["10"]["description"] == "Data VLAN"
        assert result["10"]["admin"] == "up"

    def test_vlan_id_as_int_key(self):
        """Test VLAN with integer key"""
        rest_data = {
            10: {
                "id": 10,
                "name": "VLAN10",
            }
        }
        result = rest_api_to_aoscx_vlans(rest_data)
        # Key should be string
        assert "10" in result
        assert result["10"]["id"] == 10

    def test_skip_uri_strings(self):
        """Test that URI strings are skipped (depth=1 behavior)"""
        rest_data = {
            "10": "/rest/v10.17/system/vlans/10",
            "20": {"id": 20, "name": "VLAN20"},
        }
        result = rest_api_to_aoscx_vlans(rest_data)
        # Only the dict entry should be included
        assert len(result) == 1
        assert "20" in result
        assert "10" not in result

    def test_empty_input(self):
        """Test with empty input"""
        result = rest_api_to_aoscx_vlans({})
        assert result == {}

    def test_non_dict_input(self):
        """Test with non-dict input"""
        result = rest_api_to_aoscx_vlans(None)
        assert result == {}

    def test_default_values(self):
        """Test default values for missing fields"""
        rest_data = {
            "100": {
                "id": 100,
            }
        }
        result = rest_api_to_aoscx_vlans(rest_data)
        assert result["100"]["name"] == "VLAN100"
        assert result["100"]["description"] == ""
        assert result["100"]["admin"] == "up"
        assert result["100"]["voice"] is False

    def test_multiple_vlans(self):
        """Test conversion of multiple VLANs"""
        rest_data = {
            "1": {"id": 1, "name": "default", "admin": "up"},
            "10": {"id": 10, "name": "DATA", "admin": "up"},
            "20": {"id": 20, "name": "VOICE", "admin": "up", "voice": True},
        }
        result = rest_api_to_aoscx_vlans(rest_data)
        assert len(result) == 3
        assert result["20"]["voice"] is True


class TestRestApiToAoscxEvpnVlans:
    """Tests for rest_api_to_aoscx_evpn_vlans function"""

    def test_basic_evpn_vlan_conversion(self):
        """Test basic EVPN VLAN data conversion"""
        rest_data = {
            "10": {
                "vlan": 10,
                "rd": "auto",
                "export_route_targets": ["auto"],
                "import_route_targets": ["auto"],
            }
        }
        result = rest_api_to_aoscx_evpn_vlans(rest_data)
        assert "10" in result
        assert result["10"]["vlan"] == 10
        assert result["10"]["rd"] == "auto"
        assert "auto" in result["10"]["export_route_targets"]

    def test_empty_input(self):
        """Test with empty input"""
        result = rest_api_to_aoscx_evpn_vlans({})
        assert result == {}

    def test_non_dict_input(self):
        """Test with non-dict input"""
        result = rest_api_to_aoscx_evpn_vlans(None)
        assert result == {}

    def test_redistribute_options(self):
        """Test redistribute options"""
        rest_data = {
            "100": {
                "vlan": 100,
                "redistribute": {"host-route": True},
            }
        }
        result = rest_api_to_aoscx_evpn_vlans(rest_data)
        assert result["100"]["redistribute"]["host-route"] is True


class TestRestApiToAoscxVnis:
    """Tests for rest_api_to_aoscx_vnis function"""

    def test_basic_vni_conversion(self):
        """Test basic VNI data conversion"""
        rest_data = {
            "vxlan,10100": {
                "type": "vxlan",
                "id": 10100,
                "vlan": "/rest/v10.17/system/vlans/100",
                "vrf": None,
            }
        }
        result = rest_api_to_aoscx_vnis(rest_data)
        assert "10100" in result
        assert result["10100"]["id"] == 10100
        assert result["10100"]["type"] == "vxlan"
        assert result["10100"]["vlan"] == 100

    def test_l3_vni(self):
        """Test L3 VNI with VRF"""
        rest_data = {
            "vxlan,50000": {
                "type": "vxlan",
                "id": 50000,
                "vlan": None,
                "vrf": "/rest/v10.17/system/vrfs/CUSTOMER_A",
                "routing": True,
            }
        }
        result = rest_api_to_aoscx_vnis(rest_data)
        assert "50000" in result
        assert result["50000"]["routing"] is True

    def test_empty_input(self):
        """Test with empty input"""
        result = rest_api_to_aoscx_vnis({})
        assert result == {}

    def test_non_dict_input(self):
        """Test with non-dict input"""
        result = rest_api_to_aoscx_vnis(None)
        assert result == {}

    def test_skip_entries_without_id(self):
        """Test that entries without id are skipped"""
        rest_data = {
            "vxlan,invalid": {
                "type": "vxlan",
                # No id field
            }
        }
        result = rest_api_to_aoscx_vnis(rest_data)
        assert len(result) == 0

    def test_depth2_references_normalised(self):
        """depth=2 REST shape: dict references become plain values"""
        rest_data = {
            "vxlan_vni,1000101": {
                "id": 1000101,
                "type": "vxlan_vni",
                "vlan": {"101": "/rest/v10.16/system/vlans/101"},
                "vrf": None,
                "routing": False,
                "state": "operational",
                "interface": {"vxlan1": "/rest/v10.16/system/interfaces/vxlan1"},
            }
        }
        result = rest_api_to_aoscx_vnis(rest_data)
        assert result["1000101"] == {
            "id": 1000101,
            "type": "vxlan_vni",
            "vlan": 101,
            "vrf": None,
            "routing": False,
            "state": "operational",
            "interface": "vxlan1",
        }

    def test_uri_string_references(self):
        """Bare URI string references resolve to the last path segment"""
        rest_data = {
            "vxlan_vni,50000": {
                "id": 50000,
                "vlan": None,
                "vrf": "/rest/v10.16/system/vrfs/CUSTOMER_A",
                "routing": True,
            }
        }
        result = rest_api_to_aoscx_vnis(rest_data)
        assert result["50000"]["vrf"] == "CUSTOMER_A"
        assert result["50000"]["vlan"] is None
        assert result["50000"]["type"] == "vxlan_vni"

    def test_depth1_uri_values_skipped(self):
        """depth=1 returns URI strings per VNI; nothing usable"""
        rest_data = {"vxlan_vni,100": "/rest/v10.16/system/virtual_network_ids/vxlan_vni,100"}
        assert rest_api_to_aoscx_vnis(rest_data) == {}

    def test_multiple_vnis(self):
        """Test conversion of multiple VNIs"""
        rest_data = {
            "vxlan,10100": {"type": "vxlan", "id": 10100},
            "vxlan,10200": {"type": "vxlan", "id": 10200},
            "vxlan,50000": {"type": "vxlan", "id": 50000, "routing": True},
        }
        result = rest_api_to_aoscx_vnis(rest_data)
        assert len(result) == 3


class TestRestApiToAoscxDhcpRelays:
    """Tests for rest_api_to_aoscx_dhcp_relays function"""

    _SAMPLE = {
        "lab-blue,vlan101": {
            "ipv4_ucast_server": ["172.16.3.10", "172.16.3.11"],
            "ipv6_ucast_server": [],
            "port": {"vlan101": "/rest/v10.16/system/interfaces/vlan101"},
            "vrf": {"lab-blue": "/rest/v10.16/system/vrfs/lab-blue"},
        }
    }

    def test_basic_conversion(self):
        """Basic relay entry is keyed by interface name"""
        result = rest_api_to_aoscx_dhcp_relays(self._SAMPLE)
        assert "vlan101" in result
        assert result["vlan101"] == ["172.16.3.10", "172.16.3.11"]

    def test_servers_are_sorted(self):
        """Servers are returned in sorted order"""
        rest_data = {
            "lab-blue,vlan101": {
                "ipv4_ucast_server": ["172.16.3.11", "172.16.3.10"],
                "port": {"vlan101": "/rest/v10.16/system/interfaces/vlan101"},
            }
        }
        result = rest_api_to_aoscx_dhcp_relays(rest_data)
        assert result["vlan101"] == ["172.16.3.10", "172.16.3.11"]

    def test_multiple_interfaces(self):
        """Multiple relay entries produce separate interface keys"""
        rest_data = {
            "lab-blue,vlan101": {
                "ipv4_ucast_server": ["172.16.3.10"],
                "port": {"vlan101": "/rest/v10.16/system/interfaces/vlan101"},
            },
            "lab-green,vlan201": {
                "ipv4_ucast_server": ["172.16.3.12", "172.16.3.13"],
                "port": {"vlan201": "/rest/v10.16/system/interfaces/vlan201"},
            },
        }
        result = rest_api_to_aoscx_dhcp_relays(rest_data)
        assert result["vlan101"] == ["172.16.3.10"]
        assert result["vlan201"] == ["172.16.3.12", "172.16.3.13"]

    def test_empty_server_list(self):
        """Entry with empty ipv4_ucast_server is included as empty list"""
        rest_data = {
            "lab-blue,vlan101": {
                "ipv4_ucast_server": [],
                "port": {"vlan101": "/rest/v10.16/system/interfaces/vlan101"},
            }
        }
        result = rest_api_to_aoscx_dhcp_relays(rest_data)
        assert result["vlan101"] == []

    def test_missing_port_key_skipped(self):
        """Entry without port dict is skipped"""
        rest_data = {
            "lab-blue,vlan101": {
                "ipv4_ucast_server": ["172.16.3.10"],
                # no "port" key
            }
        }
        result = rest_api_to_aoscx_dhcp_relays(rest_data)
        assert len(result) == 0

    def test_empty_input(self):
        """Empty input returns empty dict"""
        assert rest_api_to_aoscx_dhcp_relays({}) == {}

    def test_non_dict_input(self):
        """Non-dict input returns empty dict"""
        assert rest_api_to_aoscx_dhcp_relays(None) == {}
        assert rest_api_to_aoscx_dhcp_relays([]) == {}

    def test_duplicate_servers_deduplicated(self):
        """Duplicate server addresses are deduplicated"""
        rest_data = {
            "lab-blue,vlan101": {
                "ipv4_ucast_server": ["172.16.3.10", "172.16.3.10"],
                "port": {"vlan101": "/rest/v10.16/system/interfaces/vlan101"},
            }
        }
        result = rest_api_to_aoscx_dhcp_relays(rest_data)
        assert result["vlan101"] == ["172.16.3.10"]


class TestRestApiToAoscxBgp:
    """Tests for rest_api_to_aoscx_bgp (payloads trimmed from an 8360, 10.16)"""

    _VRFS = {
        "default": {
            "name": "default",
            "bgp_routers": {
                "65015": {
                    "router_id": "172.27.252.0",
                    "redistribute": {},
                    "bgp_neighbors": "/rest/v10.16/system/vrfs/default/bgp_routers/65015/bgp_neighbors",
                }
            },
        },
        "lab-blue": {
            "name": "lab-blue",
            "bgp_routers": {
                "65015": {
                    "router_id": None,
                    "redistribute": {"ipv4-unicast": ["static"], "ipv6-unicast": ["static", "connected"]},
                }
            },
        },
        "mgmt": {"name": "mgmt", "bgp_routers": {}},
    }

    _EVPN_NEIGHBOR = {
        "remote_as": 65015,
        "update_source": "172.27.252.0",
        "activate": {"ipv4-unicast": False, "ipv6-unicast": False, "l2vpn-evpn": True, "vpnv4-unicast": False},
        "next_hop_self": {"ipv4-unicast": False, "ipv6-unicast": False, "l2vpn-evpn": False},
        "route_reflector_client": {"ipv4-unicast": False, "l2vpn-evpn": False},
        "send_community": {"ipv4-unicast": "none", "l2vpn-evpn": "extended"},
        "route_maps": {},
        "inbound_soft_reconfiguration": {"ipv4-unicast": False, "ipv6-unicast": False},
        "bfd_enable": False,
        "fall_over": False,
        "password": "AQBapWeH",
        "shutdown": False,
        "status": {"bgp_peer_state": "Established"},
    }

    _EBGP_NEIGHBOR = {
        "remote_as": 65020,
        "update_source": None,
        "activate": {"ipv4-unicast": True, "ipv6-unicast": False},
        "next_hop_self": {"ipv4-unicast": False},
        "route_reflector_client": {"ipv4-unicast": False},
        "send_community": {"ipv4-unicast": "none"},
        "route_maps": {
            "ipv4-unicast,in": "/rest/v10.16/system/route_maps/LAB-GW-IPV4-IN-01",
            "ipv4-unicast,out": "/rest/v10.16/system/route_maps/LAB-BLUE%2DOUT",
        },
        "inbound_soft_reconfiguration": {"ipv4-unicast": True, "ipv6-unicast": False},
        "bfd_enable": True,
        "fall_over": False,
        "password": None,
        "shutdown": False,
        "status": {"bgp_peer_state": "Idle"},
    }

    def _results(self):
        return [
            {"item": {"vrf": "default", "asn": "65015"}, "status": 200,
             "json": {"172.27.252.1": self._EVPN_NEIGHBOR}},
            {"item": {"vrf": "lab-blue", "asn": "65015"}, "status": 200,
             "json": {"172.27.250.32": self._EBGP_NEIGHBOR}},
        ]

    def test_router_and_redistribute(self):
        result = rest_api_to_aoscx_bgp(self._VRFS, self._results(), {"bfd_enable": True})
        assert result["asn"] == 65015
        assert result["bfd_enable"] is True
        assert sorted(result["vrfs"]) == ["default", "lab-blue"]
        assert result["vrfs"]["default"]["router_id"] == "172.27.252.0"
        assert result["vrfs"]["default"]["redistribute"] == {}
        assert result["vrfs"]["lab-blue"]["router_id"] is None
        assert result["vrfs"]["lab-blue"]["redistribute"] == {
            "ipv4": ["static"], "ipv6": ["connected", "static"]}

    def test_evpn_neighbor(self):
        n = rest_api_to_aoscx_bgp(self._VRFS, self._results())["vrfs"]["default"]["neighbors"]["172.27.252.1"]
        assert n["remote_as"] == 65015
        assert n["update_source"] == "172.27.252.0"
        assert n["activate"] == ["evpn"]
        assert n["next_hop_self"] == []
        assert n["send_community"] == {"evpn": "extended"}
        assert n["password"] == "AQBapWeH"
        assert n["state"] == "Established"

    def test_ebgp_neighbor_route_maps_and_options(self):
        n = rest_api_to_aoscx_bgp(self._VRFS, self._results())["vrfs"]["lab-blue"]["neighbors"]["172.27.250.32"]
        assert n["activate"] == ["ipv4"]
        assert n["route_maps"] == {"ipv4": {"in": "LAB-GW-IPV4-IN-01", "out": "LAB-BLUE-OUT"}}
        assert n["soft_reconfiguration_inbound"] == ["ipv4"]
        assert n["bfd"] is True
        assert n["send_community"] == {}
        assert n["password"] is None
        assert n["state"] == "Idle"

    def test_non_200_and_unknown_vrf_results_ignored(self):
        results = [
            {"item": {"vrf": "default", "asn": "65015"}, "status": 404, "json": None},
            {"item": {"vrf": "other", "asn": "65015"}, "status": 200,
             "json": {"10.0.0.1": self._EBGP_NEIGHBOR}},
        ]
        result = rest_api_to_aoscx_bgp(self._VRFS, results)
        assert result["vrfs"]["default"]["neighbors"] == {}
        assert "other" not in result["vrfs"]

    def test_no_bgp_configured(self):
        result = rest_api_to_aoscx_bgp({"default": {"bgp_routers": {}}}, [], {"bfd_enable": False})
        assert result == {"asn": None, "bfd_enable": False, "prefix_lists": None, "route_maps": None, "vrfs": {}}

    @pytest.mark.parametrize("bad", [None, [], "x"])
    def test_invalid_input(self, bad):
        assert rest_api_to_aoscx_bgp(bad, bad, bad) == {"asn": None, "bfd_enable": False, "prefix_lists": None, "route_maps": None, "vrfs": {}}

    def test_prefix_lists_and_route_maps(self):
        prefix_lists = {
            "LAB-GW-IPV4": {
                "address_family": "ipv4", "name": "LAB-GW-IPV4", "origin": "local-prefix-list",
                "prefix_list_entries": {
                    "10": {"action": "permit", "ge": None, "le": None, "preference": 10, "prefix": "0.0.0.0/0"},
                    "15": {"action": "permit", "ge": None, "le": 24, "preference": 15, "prefix": "172.16.3.0/24"},
                },
            },
            "EMPTY": {"address_family": "ipv6", "name": "EMPTY", "prefix_list_entries": {}},
        }
        route_maps = {
            "LAB-GW-IPV4-IN-01": {
                "name": "LAB-GW-IPV4-IN-01",
                "route_map_entries": {
                    "10": {
                        "action": "permit", "preference": 10,
                        "match_ipv4_prefix_list": {"LAB-GW-IPV4": "/rest/v10.16/system/prefix_lists/LAB-GW-IPV4"},
                        "match_ipv6_prefix_list": None,
                        "set": {"local_preference": 300},
                    },
                    "20": {
                        "action": "deny", "preference": 20,
                        "match_ipv4_prefix_list": None,
                        "match_ipv6_prefix_list": {"LAB-GW-IPV6": "/x"},
                        "set": {"as_path_prepend": "65015  65015", "metric": 5, "weight": None},
                    },
                },
            },
        }
        result = rest_api_to_aoscx_bgp(self._VRFS, None, None, prefix_lists, route_maps)
        assert result["prefix_lists"] == {
            "LAB-GW-IPV4": {"af": "ipv4", "entries": {
                10: {"action": "permit", "prefix": "0.0.0.0/0", "ge": None, "le": None},
                15: {"action": "permit", "prefix": "172.16.3.0/24", "ge": None, "le": 24},
            }},
            "EMPTY": {"af": "ipv6", "entries": {}},
        }
        assert result["route_maps"] == {
            "LAB-GW-IPV4-IN-01": {
                10: {"action": "permit", "lines": [
                    "match ip address prefix-list LAB-GW-IPV4",
                    "set local-preference 300"]},
                20: {"action": "deny", "lines": [
                    "match ipv6 address prefix-list LAB-GW-IPV6",
                    "set as-path prepend 65015 65015",
                    "set metric 5"]},
            }
        }

    def test_policy_facts_none_when_not_queried(self):
        result = rest_api_to_aoscx_bgp(self._VRFS)
        assert result["prefix_lists"] is None
        assert result["route_maps"] is None

    def test_no_policies_on_device(self):
        result = rest_api_to_aoscx_bgp(self._VRFS, None, None, {}, {})
        assert result["prefix_lists"] == {}
        assert result["route_maps"] == {}
