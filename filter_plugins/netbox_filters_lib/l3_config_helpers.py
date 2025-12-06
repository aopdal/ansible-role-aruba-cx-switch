#!/usr/bin/env python3
"""
L3 Interface Configuration Helpers

This module provides helper functions for building L3 interface configuration
to reduce code duplication across physical, LAG, and VLAN interface types.
"""


def format_interface_name(interface_name, interface_type):
    """
    Format interface name for AOS-CX configuration context.

    Different interface types require different formatting:
    - Physical: "1/1/1" stays as "1/1/1"
    - LAG: "lag1" becomes "lag 1" (space added)
    - VLAN: "vlan10" stays as "vlan10"

    Args:
        interface_name: Raw interface name from NetBox
        interface_type: Type of interface ('physical', 'lag', 'vlan')

    Returns:
        Formatted interface name for use in configuration
    """
    if interface_type == "lag":
        # LAG interfaces need a space: "lag1" -> "lag 1"
        return interface_name.replace("lag", "lag ")
    # Physical and VLAN interfaces use the name as-is
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


def build_l3_config_lines(
    item, interface_type, ip_version, vrf_type, l3_counters_enable=True
):
    """
    Build L3 configuration lines for an interface.

    This centralizes the logic for building configuration commands for L3 interfaces,
    handling differences between interface types, IP versions, VRF types, and anycast
    gateway configurations.

    Args:
        item: Interface/IP combination dict with keys:
            - interface: Full interface object
            - interface_name: Name of interface
            - address: IP address to configure
            - ip_role: Role of IP (e.g., 'anycast')
            - anycast_mac: MAC address for anycast gateway (optional)
        interface_type: Type of interface ('physical', 'lag', 'vlan')
                       Note: Currently not used in logic but kept for API consistency
        ip_version: IP version ('ipv4' or 'ipv6')
        vrf_type: VRF type ('default' or 'custom')
        l3_counters_enable: Whether to enable L3 counters (default: True)

    Returns:
        List of configuration command strings
    """
    # Note: interface_type parameter kept for API consistency and potential future use
    _ = interface_type  # Suppress unused argument warning
    lines = []

    # VRF attachment (only for custom VRFs)
    if vrf_type == "custom":
        interface_obj = item.get("interface", {})
        vrf_name = get_interface_vrf(interface_obj)
        lines.append(f"vrf attach {vrf_name}")

    # IP address or anycast gateway configuration
    ip_role = item.get("ip_role")
    anycast_mac = item.get("anycast_mac")
    address = item.get("address", "")

    if ip_role == "anycast" and anycast_mac:
        # Anycast gateway configuration (VLAN interfaces only typically)
        if ip_version == "ipv6":
            # IPv6 anycast: active-gateway ipv6 mac <mac>, active-gateway ipv6 <addr>
            lines.append(f"active-gateway ipv6 mac {anycast_mac}")
            # Remove prefix for anycast gateway command
            addr_without_prefix = address.split("/")[0] if "/" in address else address
            lines.append(f"active-gateway ipv6 {addr_without_prefix}")
        else:
            # IPv4 anycast: active-gateway ip mac <mac>, active-gateway ip <addr>
            lines.append(f"active-gateway ip mac {anycast_mac}")
            # Remove prefix for anycast gateway command
            addr_without_prefix = address.split("/")[0] if "/" in address else address
            lines.append(f"active-gateway ip {addr_without_prefix}")
    else:
        # Regular IP address configuration
        if ip_version == "ipv6":
            lines.append(f"ipv6 address {address}")
        else:
            lines.append(f"ip address {address}")

    # MTU configuration
    interface_obj = item.get("interface", {})
    if isinstance(interface_obj, dict):
        mtu = interface_obj.get("mtu")
        if mtu:
            lines.append(f"ip mtu {mtu}")

    # L3 counters
    if l3_counters_enable:
        lines.append("l3-counters")

    return lines


class FilterModule:
    """Ansible filter plugin for L3 configuration helpers"""

    def filters(self):
        return {
            "format_interface_name": format_interface_name,
            "is_ipv4_address": is_ipv4_address,
            "is_ipv6_address": is_ipv6_address,
            "get_interface_vrf": get_interface_vrf,
            "build_l3_config_lines": build_l3_config_lines,
        }
