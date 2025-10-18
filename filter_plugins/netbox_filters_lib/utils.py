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
