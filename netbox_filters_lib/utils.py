#!/usr/bin/env python3
"""
Utility functions for NetBox filters
"""

import os


def _debug(message):
    """Print debug message if DEBUG_ANSIBLE environment variable is set"""
    if os.environ.get("DEBUG_ANSIBLE", "").lower() in ("true", "1", "yes"):
        print(f"DEBUG: {message}")


def collapse_vlan_list(vlan_list):
    """Collapse a list of VLAN IDs into a range string"""
    if not vlan_list:
        return ""

    # Sort and remove duplicates
    sorted_vlans = sorted(set(vlan_list))

    collapsed_ranges = []
    range_start = None
    range_end = None

    for vlan in sorted_vlans:
        if range_start is None:
            # Start a new range
            range_start = vlan
            range_end = vlan
        elif vlan == range_end + 1:
            # Continue the range
            range_end = vlan
        else:
            # Close the current range and start a new one
            if range_start == range_end:
                collapsed_ranges.append(f"{range_start}")
            else:
                collapsed_ranges.append(f"{range_start}-{range_end}")

            range_start = vlan
            range_end = vlan

    # Close the final range
    if range_start is not None:
        if range_start == range_end:
            collapsed_ranges.append(f"{range_start}")
        else:
            collapsed_ranges.append(f"{range_start}-{range_end}")

    return ",".join(collapsed_ranges)


def select_interfaces_to_configure(
    interfaces, idempotent_mode, interfaces_needing_changes=None
):
    """
    Select which interfaces to configure based on the operating mode

    Args:
        interfaces: List of all interface objects from NetBox
        idempotent_mode: Boolean indicating if running in idempotent mode
        interfaces_needing_changes: Dict from get_interfaces_needing_changes()
                                   (only used in idempotent mode)

    Returns:
        List of interfaces to configure:
        - In idempotent mode: only interfaces that need changes
        - In standard mode: all interfaces
    """
    if not interfaces:
        _debug("No interfaces provided to select_interfaces_to_configure")
        return []

    # Standard mode: configure all interfaces
    if not idempotent_mode:
        _debug(
            f"Standard mode: selecting all {len(interfaces)} interfaces for configuration"
        )
        return interfaces

    # Idempotent mode: only configure interfaces that need changes
    if not interfaces_needing_changes or not isinstance(
        interfaces_needing_changes, dict
    ):
        _debug(
            "Idempotent mode but no interfaces_needing_changes provided - "
            "returning all interfaces"
        )
        return interfaces

    configure_list = interfaces_needing_changes.get("configure", [])
    _debug(
        f"Idempotent mode: selecting {len(configure_list)} interfaces "
        f"that need configuration changes"
    )

    return configure_list


def extract_ip_addresses(nb_intf, exclude_anycast=False):
    """
    Extract and categorize IPv4 and IPv6 addresses from a NetBox interface.

    This helper function centralizes the logic for extracting IP addresses
    from NetBox interface data and separating them into IPv4 and IPv6 lists.

    Args:
        nb_intf: NetBox interface object containing ip_addresses
        exclude_anycast: If True, skip IPs with role="anycast" (for change detection,
                        since anycast IPs are configured via active-gateway command
                        and not reported in device facts ip4_address field)

    Returns:
        Tuple of (ipv4_list, ipv6_list) where:
        - ipv4_list: List of IPv4 addresses (e.g., ["192.168.1.1/24"])
        - ipv6_list: List of IPv6 addresses (e.g., ["2001:db8::1/64"])
    """
    nb_ip_addresses = nb_intf.get("ip_addresses", [])
    nb_ipv4 = []
    nb_ipv6 = []

    for ip_obj in nb_ip_addresses:
        if isinstance(ip_obj, dict):
            ip_addr = ip_obj.get("address")
            if ip_addr:
                # Skip anycast IPs if requested (they're configured via active-gateway,
                # not ip address, and aren't in device facts ip4_address)
                if exclude_anycast:
                    role_obj = ip_obj.get("role")
                    if role_obj:
                        role_value = (
                            role_obj.get("value")
                            if isinstance(role_obj, dict)
                            else role_obj
                        )
                        if role_value == "anycast":
                            _debug(f"  Skipping anycast IP from comparison: {ip_addr}")
                            continue

                # Separate IPv4 and IPv6 by presence of colon
                if ":" in ip_addr:
                    nb_ipv6.append(ip_addr)
                else:
                    nb_ipv4.append(ip_addr)

    return nb_ipv4, nb_ipv6


def populate_ip_changes(nb_intf, nb_ipv4, nb_ipv6):
    """
    Populate the _ip_changes dictionary with IP addresses to add.

    This helper function centralizes the logic for populating the _ip_changes
    field in NetBox interface objects, which is used by task files to determine
    which IP addresses need to be configured.

    Args:
        nb_intf: NetBox interface object to modify
        nb_ipv4: List of IPv4 addresses to add
        nb_ipv6: List of IPv6 addresses to add

    Side Effects:
        Modifies nb_intf by adding/updating the _ip_changes dictionary:
        - _ip_changes.ipv4_to_add: IPv4 addresses needing configuration
        - _ip_changes.ipv6_addresses: IPv6 addresses needing configuration
    """
    if nb_ipv4 or nb_ipv6:
        nb_intf["_ip_changes"] = {}
        if nb_ipv4:
            nb_intf["_ip_changes"]["ipv4_to_add"] = nb_ipv4
            _debug(f"  IPv4 addresses to add: {nb_ipv4}")
        if nb_ipv6:
            nb_intf["_ip_changes"]["ipv6_addresses"] = nb_ipv6
            _debug(f"  IPv6 addresses to add: {nb_ipv6}")
