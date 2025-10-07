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
