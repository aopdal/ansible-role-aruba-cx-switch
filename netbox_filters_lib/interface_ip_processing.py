#!/usr/bin/env python3
"""
Interface IP address processing filters

Provides functions to match and process IP addresses with their interfaces.
"""

from .utils import _debug


def get_interface_ip_addresses(interfaces, ip_addresses):
    """
    Match IP addresses to their interfaces

    Args:
        interfaces: List of interface objects from NetBox
        ip_addresses: List of IP address objects from NetBox

    Returns:
        List of dicts with interface and IP address information
    """
    result = []

    if not interfaces or not ip_addresses:
        _debug("No interfaces or IP addresses provided")
        return result

    # Build a dict of interfaces by ID for quick lookup
    intf_by_id = {}
    for intf in interfaces:
        if intf and isinstance(intf, dict):
            intf_id = intf.get("id")
            if intf_id:
                intf_by_id[intf_id] = intf

    # Match IP addresses to interfaces
    for ip_obj in ip_addresses:
        if not ip_obj or not isinstance(ip_obj, dict):
            continue

        assigned_object = ip_obj.get("assigned_object")
        if not assigned_object or not isinstance(assigned_object, dict):
            continue

        assigned_object_id = assigned_object.get("id")
        if not assigned_object_id:
            continue

        # Find the matching interface
        intf = intf_by_id.get(assigned_object_id)
        if not intf:
            continue

        # Skip management interfaces
        if intf.get("mgmt_only"):
            continue

        address = ip_obj.get("address")
        if not address:
            continue

        # Get VRF info
        vrf_obj = ip_obj.get("vrf")
        vrf_name = "default"
        if vrf_obj and isinstance(vrf_obj, dict):
            vrf_name = vrf_obj.get("name", "default")

        # Get IP address role (e.g., "anycast")
        ip_role = None
        if ip_obj.get("role"):
            ip_role_obj = ip_obj.get("role")
            if isinstance(ip_role_obj, dict):
                ip_role = ip_role_obj.get("value")
            else:
                ip_role = ip_role_obj

        # Get anycast gateway MAC from interface custom fields
        anycast_mac = None
        if intf.get("custom_fields"):
            custom_fields = intf.get("custom_fields")
            if isinstance(custom_fields, dict):
                anycast_mac = custom_fields.get("if_anycast_gateway_mac")

        result.append(
            {
                "interface": intf,
                "interface_name": intf.get("name"),
                "interface_type": intf.get("type", {}).get("value")
                if isinstance(intf.get("type"), dict)
                else None,
                "address": address,
                "vrf": vrf_name,
                "description": intf.get("description", ""),
                "enabled": intf.get("enabled", True),
                "ip_role": ip_role,
                "anycast_mac": anycast_mac,
            }
        )

        _debug(
            f"Matched IP {address} to interface {intf.get('name')} "
            f"(VRF: {vrf_name}, Role: {ip_role}, Anycast MAC: {anycast_mac})"
        )

    _debug(f"Total interface/IP matches: {len(result)}")
    return result
