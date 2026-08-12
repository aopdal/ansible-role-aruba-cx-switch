"""
Unit tests for netbox_filters_lib.interface_ip_comparisons

Covers the IPv4/IPv6/VRF/encapsulation/anycast/link-local/DHCP-relay
comparison logic split out of interface_change_detection.py per
docs/CODE_AUDIT.md finding F4. See test_interface_change_detection.py for
end-to-end coverage through get_interfaces_needing_config_changes(); these
tests exercise compute_l3_ip_changes()/compute_dhcp_relay_changes()
directly and confirm they are pure (finding F5).
"""
import copy

from netbox_filters_lib.interface_ip_comparisons import (
    compute_dhcp_relay_changes,
    compute_l3_ip_changes,
)


class TestComputeL3IpChangesIpv4:
    """IPv4 add/remove diffing."""

    def test_matching_ipv4_no_change(self):
        nb_intf = {"ip_addresses": [{"address": "10.0.0.1/24"}]}
        device_intf = {"ip4_address": "10.0.0.1/24"}
        needs_change, reasons, ip_changes = compute_l3_ip_changes(
            nb_intf, device_intf, None, "1/1/1"
        )
        assert needs_change is False
        assert reasons == []
        assert ip_changes == {}

    def test_ipv4_to_add(self):
        nb_intf = {"ip_addresses": [{"address": "10.0.0.1/24"}]}
        device_intf = {}
        needs_change, reasons, ip_changes = compute_l3_ip_changes(
            nb_intf, device_intf, None, "1/1/1"
        )
        assert needs_change is True
        assert ip_changes["ipv4_to_add"] == ["10.0.0.1/24"]
        assert any("IPv4 addresses to add" in r for r in reasons)

    def test_ipv4_to_remove_only_is_not_stored_in_ip_changes(self):
        """ipv4_to_remove drives needs_change/reasons but isn't persisted to
        _ip_changes - only ipv4_to_add is (matches the original inline
        behaviour: removal is handled elsewhere, not via _ip_changes)."""
        nb_intf = {"ip_addresses": []}
        device_intf = {"ip4_address": "10.0.0.9/24"}
        needs_change, reasons, ip_changes = compute_l3_ip_changes(
            nb_intf, device_intf, None, "1/1/1"
        )
        assert needs_change is True
        assert any("IPv4 addresses to remove" in r for r in reasons)
        assert "ipv4_to_add" not in ip_changes

    def test_ipv4_secondary_addresses_considered(self):
        nb_intf = {
            "ip_addresses": [
                {"address": "10.0.0.1/24"},
                {"address": "10.0.0.2/24"},
            ]
        }
        device_intf = {
            "ip4_address": "10.0.0.1/24",
            "ip4_address_secondary": ["10.0.0.2/24"],
        }
        needs_change, _, _ = compute_l3_ip_changes(
            nb_intf, device_intf, None, "1/1/1"
        )
        assert needs_change is False


class TestComputeL3IpChangesIpv6:
    """IPv6 comparison, with and without enhanced facts."""

    def test_no_enhanced_facts_marks_all_ipv6_for_config(self):
        nb_intf = {"ip_addresses": [{"address": "2001:db8::1/64"}]}
        device_intf = {}
        needs_change, reasons, ip_changes = compute_l3_ip_changes(
            nb_intf, device_intf, None, "1/1/1"
        )
        assert needs_change is True
        assert any("IPv6 addresses need configuration" in r for r in reasons)
        assert ip_changes["ipv6_addresses"] == ["2001:db8::1/64"]
        assert "ipv6_to_add" not in ip_changes

    def test_enhanced_facts_matching_normalized_address_no_change(self):
        """2001:0db8::1 (device) and 2001:db8::1 (NetBox) are the same
        address in different textual forms - normalization must treat them
        as equal."""
        nb_intf = {"ip_addresses": [{"address": "2001:db8::1/64"}]}
        device_intf = {}
        enhanced_intf = {
            "ip6_addresses": {"2001%3A0db8%3A%3A1%2F64": {}},
        }
        needs_change, reasons, ip_changes = compute_l3_ip_changes(
            nb_intf, device_intf, enhanced_intf, "1/1/1"
        )
        assert needs_change is False
        assert ip_changes["ipv6_to_add"] == []
        assert ip_changes["ipv6_addresses"] == ["2001:db8::1/64"]

    def test_enhanced_facts_ipv6_to_add(self):
        nb_intf = {"ip_addresses": [{"address": "2001:db8::1/64"}]}
        device_intf = {}
        enhanced_intf = {"ip6_addresses": {}}
        needs_change, reasons, ip_changes = compute_l3_ip_changes(
            nb_intf, device_intf, enhanced_intf, "1/1/1"
        )
        assert needs_change is True
        assert ip_changes["ipv6_to_add"] == ["2001:db8::1/64"]

    def test_enhanced_facts_ipv6_to_remove_when_netbox_still_has_ipv6(self):
        nb_intf = {
            "ip_addresses": [
                {"address": "2001:db8::1/64"},
            ]
        }
        device_intf = {}
        enhanced_intf = {
            "ip6_addresses": {
                "2001%3Adb8%3A%3A1%2F64": {},
                "2001%3Adb8%3A%3A2%2F64": {},
            },
        }
        needs_change, reasons, ip_changes = compute_l3_ip_changes(
            nb_intf, device_intf, enhanced_intf, "1/1/1"
        )
        assert needs_change is True
        assert ip_changes["ipv6_to_remove"] == ["2001:db8::2/64"]

    def test_enhanced_facts_ipv6_to_remove_when_netbox_has_no_ipv6(self):
        """Device has IPv6 that NetBox no longer lists at all - still
        reported via ipv6_to_remove even though the 'always store' block
        only runs when nb_ipv6 is truthy."""
        nb_intf = {"ip_addresses": []}
        device_intf = {}
        enhanced_intf = {
            "ip6_addresses": {"2001%3Adb8%3A%3A1%2F64": {}},
        }
        needs_change, reasons, ip_changes = compute_l3_ip_changes(
            nb_intf, device_intf, enhanced_intf, "1/1/1"
        )
        assert needs_change is True
        assert ip_changes["ipv6_to_remove"] == ["2001:db8::1/64"]
        assert "ipv6_addresses" not in ip_changes


class TestComputeL3IpChangesVrf:
    """VRF-change short-circuit: forces full L3 reconfiguration."""

    def test_vrf_mismatch_forces_full_ipv4_ipv6_reconfig(self):
        nb_intf = {
            "vrf": {"name": "CUSTOMER"},
            "ip_addresses": [
                {"address": "10.0.0.1/24"},
                {"address": "2001:db8::1/64"},
            ],
        }
        # Device already has the exact same IPv4 - would normally be "no
        # change needed" - but the VRF mismatch must override that.
        device_intf = {"ip4_address": "10.0.0.1/24", "vrf": {"name": "default"}}
        enhanced_intf = {"vrf": {"default": "url"}, "ip6_addresses": {}}

        needs_change, reasons, ip_changes = compute_l3_ip_changes(
            nb_intf, device_intf, enhanced_intf, "vlan10"
        )

        assert needs_change is True
        assert ip_changes["vrf_change"] is True
        assert ip_changes["ipv4_to_add"] == ["10.0.0.1/24"]
        assert ip_changes["ipv6_to_add"] == ["2001:db8::1/64"]
        assert any("VRF mismatch" in r for r in reasons)

    def test_matching_vrf_no_change_flagged(self):
        nb_intf = {"vrf": {"name": "CUSTOMER"}, "ip_addresses": []}
        enhanced_intf = {"vrf": {"CUSTOMER": "url"}}
        needs_change, reasons, ip_changes = compute_l3_ip_changes(
            nb_intf, {}, enhanced_intf, "vlan10"
        )
        assert "vrf_change" not in ip_changes
        assert not any("VRF mismatch" in r for r in reasons)

    def test_no_vrf_data_anywhere_skips_comparison(self):
        """Neither standard nor enhanced facts carry VRF data -> comparison
        is skipped rather than treated as a false-positive default-VRF
        mismatch."""
        nb_intf = {"vrf": {"name": "CUSTOMER"}, "ip_addresses": []}
        needs_change, reasons, ip_changes = compute_l3_ip_changes(
            nb_intf, {}, None, "vlan10"
        )
        assert "vrf_change" not in ip_changes
        assert not any("VRF" in r for r in reasons)


class TestComputeL3IpChangesEncapsulation:
    """Sub-interface 802.1Q encapsulation VLAN drift (enhanced facts only)."""

    def test_encapsulation_mismatch_flagged(self):
        nb_intf = {
            "parent": {"name": "1/1/1"},
            "tagged_vlans": [{"vid": 701}],
            "ip_addresses": [{"address": "10.0.0.1/31"}],
        }
        device_intf = {"ip4_address": "10.0.0.1/31"}
        enhanced_intf = {"subintf_vlan": 999}
        needs_change, reasons, ip_changes = compute_l3_ip_changes(
            nb_intf, device_intf, enhanced_intf, "1/1/1.701"
        )
        assert needs_change is True
        assert ip_changes["encapsulation_change"] is True

    def test_encapsulation_match_not_flagged(self):
        nb_intf = {
            "parent": {"name": "1/1/1"},
            "tagged_vlans": [{"vid": 701}],
            "ip_addresses": [{"address": "10.0.0.1/31"}],
        }
        device_intf = {"ip4_address": "10.0.0.1/31"}
        enhanced_intf = {"subintf_vlan": 701}
        needs_change, reasons, ip_changes = compute_l3_ip_changes(
            nb_intf, device_intf, enhanced_intf, "1/1/1.701"
        )
        assert "encapsulation_change" not in ip_changes

    def test_no_enhanced_facts_skips_encapsulation_check(self):
        nb_intf = {
            "parent": {"name": "1/1/1"},
            "tagged_vlans": [{"vid": 701}],
            "ip_addresses": [{"address": "10.0.0.1/31"}],
        }
        device_intf = {"ip4_address": "10.0.0.1/31"}
        needs_change, reasons, ip_changes = compute_l3_ip_changes(
            nb_intf, device_intf, None, "1/1/1.701"
        )
        assert "encapsulation_change" not in ip_changes


class TestComputeL3IpChangesAnycast:
    """Anycast gateway (active-gateway) IPv4/IPv6 comparison."""

    def _nb_intf_with_anycast(self, ipv4=None, ipv6=None):
        ip_addresses = []
        if ipv4:
            ip_addresses.append(
                {"address": ipv4, "role": {"value": "anycast"}}
            )
        if ipv6:
            ip_addresses.append(
                {"address": ipv6, "role": {"value": "anycast"}}
            )
        return {"ip_addresses": ip_addresses}

    def test_anycast_add_with_enhanced_facts(self):
        nb_intf = self._nb_intf_with_anycast(ipv4="10.0.0.100/24")
        enhanced_intf = {"vsx_virtual_ip4": []}
        needs_change, reasons, ip_changes = compute_l3_ip_changes(
            nb_intf, {}, enhanced_intf, "vlan10"
        )
        assert needs_change is True
        assert ip_changes["ipv4_to_add"] == ["10.0.0.100/24"]
        assert any("Anycast gateway IPv4 to add" in r for r in reasons)

    def test_anycast_already_configured_no_change(self):
        nb_intf = self._nb_intf_with_anycast(ipv4="10.0.0.100/24")
        enhanced_intf = {"vsx_virtual_ip4": "10.0.0.100/24"}
        needs_change, reasons, ip_changes = compute_l3_ip_changes(
            nb_intf, {}, enhanced_intf, "vlan10"
        )
        assert needs_change is False
        assert "ipv4_to_add" not in ip_changes

    def test_anycast_without_enhanced_facts_conservatively_added(self):
        nb_intf = self._nb_intf_with_anycast(ipv4="10.0.0.100/24")
        needs_change, reasons, ip_changes = compute_l3_ip_changes(
            nb_intf, {}, None, "vlan10"
        )
        assert needs_change is True
        assert ip_changes["ipv4_to_add"] == ["10.0.0.100/24"]
        assert any("no enhanced facts" in r for r in reasons)

    def test_stale_anycast_removed_when_absent_from_netbox(self):
        nb_intf = {"ip_addresses": []}
        enhanced_intf = {"vsx_virtual_ip4": "10.0.0.100/24"}
        needs_change, reasons, ip_changes = compute_l3_ip_changes(
            nb_intf, {}, enhanced_intf, "vlan10"
        )
        assert needs_change is True
        # VSX virtual IPs are stored without their prefix (see
        # compute_l3_ip_changes' enhanced-facts extraction), so the removed
        # address has no "/24" suffix even though NetBox's anycast entries do.
        assert ip_changes["anycast_ipv4_to_remove"] == ["10.0.0.100"]

    def test_anycast_not_removed_when_still_present_without_anycast_role(self):
        """Conservative removal: an address present in NetBox under ANY
        role (not just anycast) must not be treated as stale."""
        nb_intf = {"ip_addresses": [{"address": "10.0.0.100/24"}]}
        enhanced_intf = {"vsx_virtual_ip4": "10.0.0.100/24"}
        needs_change, reasons, ip_changes = compute_l3_ip_changes(
            nb_intf, {}, enhanced_intf, "vlan10"
        )
        assert "anycast_ipv4_to_remove" not in ip_changes

    def test_link_local_anycast_missing_flags_link_local_add(self):
        nb_intf = self._nb_intf_with_anycast(ipv6="fe80::100/64")
        enhanced_intf = {"ip6_address_link_local": {}}
        needs_change, reasons, ip_changes = compute_l3_ip_changes(
            nb_intf, {}, enhanced_intf, "vlan10"
        )
        assert needs_change is True
        assert ip_changes["link_local_ipv6_to_add"] == ["fe80::100/64"]

    def test_link_local_anycast_already_present_not_flagged(self):
        nb_intf = self._nb_intf_with_anycast(ipv6="fe80::100/64")
        enhanced_intf = {
            "ip6_address_link_local": {"fe80::100/64": "url"},
        }
        needs_change, reasons, ip_changes = compute_l3_ip_changes(
            nb_intf, {}, enhanced_intf, "vlan10"
        )
        assert "link_local_ipv6_to_add" not in ip_changes


class TestComputeL3IpChangesPurity:
    """Finding F5: this function must never mutate its arguments."""

    def test_does_not_mutate_any_input(self):
        nb_intf = {
            "vrf": {"name": "CUSTOMER"},
            "parent": {"name": "1/1/1"},
            "tagged_vlans": [{"vid": 701}],
            "ip_addresses": [
                {"address": "10.0.0.1/31"},
                {"address": "10.0.0.200/31", "role": {"value": "anycast"}},
            ],
        }
        device_intf = {"ip4_address": "10.0.0.9/31"}
        enhanced_intf = {
            "vrf": {"default": "url"},
            "subintf_vlan": 1,
            "ip6_addresses": {},
            "vsx_virtual_ip4": [],
        }
        nb_before = copy.deepcopy(nb_intf)
        device_before = copy.deepcopy(device_intf)
        enhanced_before = copy.deepcopy(enhanced_intf)

        compute_l3_ip_changes(nb_intf, device_intf, enhanced_intf, "1/1/1.701")

        assert nb_intf == nb_before
        assert device_intf == device_before
        assert enhanced_intf == enhanced_before


class TestComputeDhcpRelayChanges:
    """DHCP relay / ip helper-address comparison."""

    def test_matching_servers_no_change_but_state_recorded(self):
        nb_intf = {
            "vrf": {"name": "default"},
            "custom_fields": {"if_ip_helper": True},
        }
        needs_change, reasons, ip_changes = compute_dhcp_relay_changes(
            nb_intf,
            "vlan10",
            dhcp_relay_facts={"vlan10": ["10.0.0.53"]},
            ip_helper_addresses={"default": {"1": "10.0.0.53"}},
        )
        assert needs_change is False
        assert ip_changes["dhcp_relay_expected"] == ["10.0.0.53"]
        assert ip_changes["dhcp_relay_actual"] == ["10.0.0.53"]
        assert "dhcp_relay_change" not in ip_changes

    def test_mismatch_flags_change_and_stale_removal(self):
        nb_intf = {
            "vrf": {"name": "default"},
            "custom_fields": {"if_ip_helper": True},
        }
        needs_change, reasons, ip_changes = compute_dhcp_relay_changes(
            nb_intf,
            "vlan10",
            dhcp_relay_facts={"vlan10": ["10.0.0.99"]},
            ip_helper_addresses={"default": {"1": "10.0.0.53"}},
        )
        assert needs_change is True
        assert ip_changes["dhcp_relay_change"] is True
        assert ip_changes["dhcp_relay_to_remove"] == ["10.0.0.99"]

    def test_no_relay_facts_conservatively_flagged(self):
        nb_intf = {"custom_fields": {"if_ip_helper": True}}
        needs_change, reasons, ip_changes = compute_dhcp_relay_changes(
            nb_intf, "vlan10", dhcp_relay_facts=None, ip_helper_addresses=None
        )
        assert needs_change is True
        assert ip_changes["dhcp_relay_change"] is True

    def test_helper_disabled_but_device_has_stale_relay(self):
        nb_intf = {"custom_fields": {"if_ip_helper": False}}
        needs_change, reasons, ip_changes = compute_dhcp_relay_changes(
            nb_intf,
            "vlan10",
            dhcp_relay_facts={"vlan10": ["10.0.0.53"]},
            ip_helper_addresses={},
        )
        assert needs_change is True
        assert ip_changes["dhcp_relay_to_remove"] == ["10.0.0.53"]

    def test_helper_disabled_and_nothing_on_device_no_change(self):
        nb_intf = {"custom_fields": {"if_ip_helper": False}}
        needs_change, reasons, ip_changes = compute_dhcp_relay_changes(
            nb_intf,
            "vlan10",
            dhcp_relay_facts={},
            ip_helper_addresses={},
        )
        assert needs_change is False
        assert ip_changes == {}

    def test_does_not_mutate_input(self):
        nb_intf = {
            "vrf": {"name": "default"},
            "custom_fields": {"if_ip_helper": True},
        }
        nb_before = copy.deepcopy(nb_intf)
        compute_dhcp_relay_changes(
            nb_intf,
            "vlan10",
            dhcp_relay_facts={"vlan10": []},
            ip_helper_addresses={"default": {"1": "10.0.0.53"}},
        )
        assert nb_intf == nb_before
