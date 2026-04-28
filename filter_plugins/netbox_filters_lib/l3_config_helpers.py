#!/usr/bin/env python3
"""
L3 Interface Configuration Helpers

This module provides helper functions for building L3 interface configuration
to reduce code duplication across physical, LAG, and VLAN interface types.
"""

from .utils import _debug


def format_interface_name(interface_name, interface_type):
    """
    Format interface name for AOS-CX configuration context.

    Different interface types require different formatting:
    - Physical: "1/1/1" stays as "1/1/1"
    - LAG: "lag1" becomes "lag 1" (space added)
    - VLAN: "vlan10" stays as "vlan10"
    - Loopback: "loopback0" becomes "loopback 0" (space added)
    - Sub-interface: "1/1/3.2000" stays as "1/1/3.2000"

    Args:
        interface_name: Raw interface name from NetBox
        interface_type: Type of interface ('physical', 'lag', 'vlan', 'loopback', 'subinterface')

    Returns:
        Formatted interface name for use in configuration
    """
    if interface_type == "lag":
        # LAG interfaces need a space: "lag1" -> "lag 1"
        return interface_name.replace("lag", "lag ")
    if interface_type == "loopback":
        # Loopback interfaces need a space: "loopback0" -> "loopback 0"
        return interface_name.replace("loopback", "loopback ")
    # Physical, VLAN, and sub-interfaces use the name as-is
    return interface_name


def is_ipv4_address(address):
    """
    Check if an IP address string is IPv4.

    Args:
        address: IP address string (e.g., "192.168.1.1/24" or "2001:db8::1/64")

    Returns:
        True if IPv4, False if IPv6
    """
    return ":" not in address


def is_ipv6_address(address):
    """
    Check if an IP address string is IPv6.

    Args:
        address: IP address string (e.g., "192.168.1.1/24" or "2001:db8::1/64")

    Returns:
        True if IPv6, False if IPv4
    """
    return ":" in address


def get_interface_vrf(interface_data):
    """
    Extract VRF name from interface data with proper fallback.

    Args:
        interface_data: Interface object from NetBox

    Returns:
        VRF name (defaults to 'default' if not specified)
    """
    if not isinstance(interface_data, dict):
        return "default"

    vrf = interface_data.get("vrf")
    if vrf and isinstance(vrf, dict):
        vrf_name = vrf.get("name")
        if vrf_name:
            return vrf_name

    return "default"


def group_interface_ips(
    interface_ip_list,
    ospf_facts=None,
    ospf_process_id=1,
):
    """
    Group a flat list of per-IP interface items into per-interface items.

    Each item in the input list represents one IP address on one interface.
    This function groups them so that each output item represents one interface
    with all of its addresses that need to be added (_needs_add=True).

    An interface is included in the result if:
    - At least one IP address has _needs_add=True, OR
    - The interface has OSPF configured (if_ip_ospf_1_area set) AND either:
      - ospf_facts is None (no comparison possible — always include), OR
      - The interface is not already registered in the correct OSPF area, OR
      - The interface's OSPF network type does not match the desired type.

    Args:
        interface_ip_list: List of per-IP items, each with keys:
            - interface_name: Name of the interface
            - interface: Full NetBox interface object
            - address: IP address string
            - ip_role: Role of the IP (e.g., 'anycast') or None
            - anycast_mac: MAC address for anycast gateway or None
            - _needs_add: Boolean indicating if this IP needs to be configured
        ospf_facts: Optional dict of OSPF interface facts gathered from the device
            REST API, structured as
            ``{vrf: {process_id_str: {area: {intf_name: {ospf_if_type, ...}}}}}``.
            When provided, interfaces already in the correct OSPF area with
            the correct network type are skipped unless IPs also need adding.
            When None, all OSPF interfaces are included.
        ospf_process_id: OSPF process ID to look up in ospf_facts (default: 1)

    Returns:
        List of per-interface items, each with keys:
            - interface_name: Name of the interface
            - interface: Full NetBox interface object
            - addresses: List of {address, ip_role, anycast_mac} dicts
                         sorted regular-before-anycast, IPv4 before IPv6
    """
    if not interface_ip_list:
        return []

    # First pass: group all items; collect only addresses that need adding
    by_name = {}
    for item in interface_ip_list:
        name = item.get("interface_name", "")
        if not name:
            continue
        if name not in by_name:
            by_name[name] = {
                "interface_name": name,
                "interface": item.get("interface", {}),
                "addresses": [],
            }
        if item.get("_needs_add", True):
            by_name[name]["addresses"].append(
                {
                    "address": item.get("address", ""),
                    "ip_role": item.get("ip_role"),
                    "anycast_mac": item.get("anycast_mac"),
                }
            )

    # Sort addresses: regular before anycast, IPv4 before IPv6
    def _addr_sort_key(addr):
        is_ipv6 = ":" in addr.get("address", "")
        is_anycast = addr.get("ip_role") == "anycast" and bool(addr.get("anycast_mac"))
        return (int(is_ipv6), int(is_anycast))

    result = []
    for item in by_name.values():
        # Determine whether OSPF config needs to be pushed for this interface.
        # If ospf_facts are available, compare the intended area with device state.
        # If not available, fall back to always including OSPF-configured interfaces.
        interface_obj = (
            item["interface"] if isinstance(item.get("interface"), dict) else {}
        )
        custom_fields = (
            interface_obj.get("custom_fields", {})
            if isinstance(interface_obj, dict)
            else {}
        )
        ospf_area = (
            custom_fields.get("if_ip_ospf_1_area")
            if isinstance(custom_fields, dict)
            else None
        )

        if ospf_area:
            if ospf_facts is None:
                # No facts available — always include (conservative)
                has_ospf_change = True
            else:
                vrf_name = get_interface_vrf(interface_obj)
                pid_str = str(ospf_process_id)
                intf_name = item["interface_name"]
                area_data = (
                    ospf_facts.get(vrf_name, {}).get(pid_str, {}).get(ospf_area, {})
                )
                if intf_name not in area_data:
                    # Interface not registered in this OSPF area
                    has_ospf_change = True
                else:
                    # Interface is in the area — also check network type
                    current_type = area_data[intf_name].get("ospf_if_type")
                    desired_network = custom_fields.get("if_ip_ospf_network")
                    # Map NetBox network type to AOS-CX ospf_if_type value
                    _OSPF_TYPE_MAP = {"point-to-point": "ospf_iftype_pointopoint"}
                    desired_type = (
                        _OSPF_TYPE_MAP.get(desired_network) if desired_network else None
                    )
                    has_ospf_change = current_type != desired_type
                _debug(
                    f"  OSPF check {intf_name}: area={ospf_area} vrf={vrf_name} "
                    f"change_needed={has_ospf_change}"
                )
        else:
            has_ospf_change = False

        if item["addresses"] or has_ospf_change:
            item["addresses"].sort(key=_addr_sort_key)
            result.append(item)

    return result


def build_l3_config_lines(
    item,
    interface_type,
    vrf_type,
    l3_counters_enable=True,
    ospf_process_id=1,
):
    """
    Build all L3 configuration lines for a single interface.

    Generates a complete, ordered list of CLI configuration commands for the
    interface. Each per-interface command (vrf attach, ip mtu, l3-counters, OSPF)
    is emitted exactly once regardless of how many IP addresses are present.

    Args:
        item: Per-interface dict produced by group_interface_ips(), with keys:
            - interface_name: Name of the interface
            - interface: Full NetBox interface object (provides mtu, vrf,
                         custom_fields for OSPF, tagged_vlans for sub-interfaces)
            - addresses: List of {address, ip_role, anycast_mac} dicts
        interface_type: Type of interface ('physical', 'lag', 'vlan',
                        'subinterface', 'loopback')
        vrf_type: VRF type ('default' or 'custom')
        l3_counters_enable: Whether to emit 'l3-counters' (default: True)
        ospf_process_id: OSPF process ID used in 'ip ospf <id> area' (default: 1)

    Returns:
        List of configuration command strings in AOS-CX CLI syntax
    """
    lines = []

    interface_name = item.get("interface_name", "unknown")
    interface_obj = (
        item.get("interface") if isinstance(item.get("interface"), dict) else {}
    )
    addresses = item.get("addresses", [])

    _debug(
        f"Building L3 config for {interface_name}: "
        f"interface_type={interface_type}, vrf_type={vrf_type}, "
        f"addresses={len(addresses)}"
    )

    # Encapsulation for sub-interfaces (must come first)
    if interface_type == "subinterface":
        tagged_vlans = interface_obj.get("tagged_vlans", [])
        if tagged_vlans and isinstance(tagged_vlans, list) and len(tagged_vlans) > 0:
            vlan_id = tagged_vlans[0].get("vid")
            if vlan_id:
                lines.append(f"encapsulation dot1q {vlan_id}")
                _debug(f"  Adding encapsulation: dot1q {vlan_id}")

    # VRF attachment — once per interface, not once per IP
    if vrf_type == "custom":
        vrf_name = get_interface_vrf(interface_obj)
        lines.append(f"vrf attach {vrf_name}")
        _debug(f"  Adding VRF attachment: {vrf_name}")

    # MTU — before IP addresses (matches device CLI order)
    mtu = interface_obj.get("mtu")
    if mtu:
        lines.append(f"ip mtu {mtu}")
        _debug(f"  Adding MTU: {mtu}")

    # IP addresses: regular-before-anycast, IPv4 before IPv6
    # AOS-CX requires 'ip address' before 'active-gateway ip' for each address family
    ipv4_addrs = [a for a in addresses if ":" not in a.get("address", "")]
    ipv6_addrs = [a for a in addresses if ":" in a.get("address", "")]

    # Regular IPv4 first, then anycast IPv4
    for addr_item in [
        a
        for a in ipv4_addrs
        if not (a.get("ip_role") == "anycast" and a.get("anycast_mac"))
    ]:
        address = addr_item.get("address", "")
        lines.append(f"ip address {address}")
        _debug(f"  Adding IPv4 address: {address}")
    for addr_item in [
        a for a in ipv4_addrs if a.get("ip_role") == "anycast" and a.get("anycast_mac")
    ]:
        address = addr_item.get("address", "")
        addr_without_prefix = address.split("/")[0] if "/" in address else address
        lines.append(f"active-gateway ip mac {addr_item['anycast_mac']}")
        lines.append(f"active-gateway ip {addr_without_prefix}")
        _debug(
            f"  Adding IPv4 anycast gateway: {address} (MAC: {addr_item['anycast_mac']})"
        )

    # Regular IPv6 first, then anycast IPv6
    for addr_item in [
        a
        for a in ipv6_addrs
        if not (a.get("ip_role") == "anycast" and a.get("anycast_mac"))
    ]:
        address = addr_item.get("address", "")
        lines.append(f"ipv6 address {address}")
        _debug(f"  Adding IPv6 address: {address}")
    for addr_item in [
        a for a in ipv6_addrs if a.get("ip_role") == "anycast" and a.get("anycast_mac")
    ]:
        address = addr_item.get("address", "")
        addr_without_prefix = address.split("/")[0] if "/" in address else address
        # HPE Aruba recommendation: use a link-local address as the anycast gateway.
        # When the anycast IPv6 is link-local, the link-local address must be
        # explicitly configured before the active-gateway command.
        if addr_without_prefix.lower().startswith("fe80:"):
            lines.append(f"ipv6 address link-local {address}")
            _debug(f"  Adding IPv6 link-local address for anycast gateway: {address}")
        lines.append(f"active-gateway ipv6 mac {addr_item['anycast_mac']}")
        lines.append(f"active-gateway ipv6 {addr_without_prefix}")
        _debug(
            f"  Adding IPv6 anycast gateway: {address} (MAC: {addr_item['anycast_mac']})"
        )

    # L3 counters — once per interface (not supported on loopback)
    if l3_counters_enable and interface_type != "loopback":
        lines.append("l3-counters")

    # OSPF interface config from NetBox custom fields
    custom_fields = interface_obj.get("custom_fields", {})
    if not isinstance(custom_fields, dict):
        custom_fields = {}
    ospf_area = custom_fields.get("if_ip_ospf_1_area")
    ospf_network = custom_fields.get("if_ip_ospf_network")
    if ospf_area:
        lines.append(f"ip ospf {ospf_process_id} area {ospf_area}")
        _debug(f"  Adding OSPF area: {ospf_area}")
    # ip ospf network is not applicable to loopback interfaces
    if ospf_network and interface_type != "loopback":
        lines.append(f"ip ospf network {ospf_network}")
        _debug(f"  Adding OSPF network type: {ospf_network}")

    _debug(f"  Generated {len(lines)} config lines for {interface_name}")
    return lines


class FilterModule:
    """Ansible filter plugin for L3 configuration helpers"""

    def filters(self):
        return {
            "format_interface_name": format_interface_name,
            "is_ipv4_address": is_ipv4_address,
            "is_ipv6_address": is_ipv6_address,
            "get_interface_vrf": get_interface_vrf,
            "group_interface_ips": group_interface_ips,
            "build_l3_config_lines": build_l3_config_lines,
        }
