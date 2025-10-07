#!/usr/bin/env python3
"""
VRF-related filters for NetBox data transformation
"""

import os
from .utils import _debug


def extract_interface_vrfs(interfaces):
    """
    Extract unique VRF names from interfaces

    Args:
        interfaces: List of interface objects from NetBox

    Returns:
        Set of unique VRF names
    """
    vrf_names = set()

    for interface in interfaces:
        vrf = interface.get("vrf")
        if vrf and vrf is not None:
            vrf_name = vrf.get("name")
            if vrf_name:
                _debug(f"Found VRF '{vrf_name}' on interface {interface.get('name')}")
                vrf_names.add(vrf_name)

    _debug(f"All VRFs found in interfaces: {vrf_names}")
    return vrf_names


def filter_vrfs_in_use(vrfs, interfaces, tenant=None):
    """
    Filter VRFs to only those actually in use on interfaces

    Args:
        vrfs: List of all VRF objects from NetBox
        interfaces: List of interface objects from NetBox
        tenant: Optional tenant slug to filter by

    Returns:
        List of VRF objects that are in use
    """
    vrf_names_in_use = extract_interface_vrfs(interfaces)

    _debug(f"VRFs in use from interfaces: {vrf_names_in_use}")
    _debug(f"Total VRFs from NetBox: {len(vrfs)}")
    _debug(f"Tenant filter: {tenant}")

    if os.environ.get("DEBUG_ANSIBLE", "").lower() in ("true", "1", "yes"):
        for vrf in vrfs:
            _debug(f"Checking VRF: {vrf.get('name')}, tenant: {vrf.get('tenant')}")

    filtered_vrfs = []
    for vrf in vrfs:
        vrf_name = vrf.get("name")

        # Skip if VRF not in use on any interface
        if vrf_name not in vrf_names_in_use:
            _debug(f"Skipping '{vrf_name}' - not in use")
            continue

        # Skip mgmt and Global VRFs
        if vrf_name in ["mgmt", "Global"]:
            _debug(f"Skipping '{vrf_name}' - mgmt or Global")
            continue

        _debug(f"VRF '{vrf_name}' passed initial checks")

        # If tenant filter is specified, check tenant matching
        if tenant:
            vrf_tenant = vrf.get("tenant")
            # Include VRF if it has no tenant or matches the specified tenant
            if vrf_tenant is None:
                _debug(f"Including '{vrf_name}' - no tenant assigned")
                filtered_vrfs.append(vrf)
            elif vrf_tenant.get("slug") == tenant:
                _debug(f"Including '{vrf_name}' - tenant matches")
                filtered_vrfs.append(vrf)
            else:
                _debug(
                    f"Skipping '{vrf_name}' - tenant mismatch: "
                    f"{vrf_tenant.get('slug')} != {tenant}"
                )
        else:
            # If no tenant filter, include all VRFs in use
            _debug(f"Including '{vrf_name}' - no tenant filter")
            filtered_vrfs.append(vrf)

    _debug(f"Final filtered VRFs: {[v.get('name') for v in filtered_vrfs]}")
    return filtered_vrfs


def get_vrfs_in_use(interfaces, ip_addresses=None):
    """
    Extract VRFs that are in use on interfaces

    Args:
        interfaces: List of interface objects from NetBox
        ip_addresses: Optional list of IP address objects

    Returns:
        Dict with:
        - 'vrf_names': Set of VRF names in use (excluding built-in VRFs)
        - 'vrfs': Dict of VRF objects keyed by name
    """
    vrfs_in_use = {}  # Dict keyed by VRF name
    vrf_names = set()

    # Built-in VRFs that should not be configured
    builtin_vrfs = {"mgmt", "MGMT", "Global", "global", "default", "Default"}

    # Ensure interfaces is not None
    if not interfaces:
        interfaces = []

    # Process interfaces
    for intf in interfaces:
        if not intf:
            continue

        # Skip management interfaces (they're always in mgmt VRF)
        if intf.get("mgmt_only"):
            continue

        # Get VRF from interface
        vrf_obj = intf.get("vrf")
        if vrf_obj and isinstance(vrf_obj, dict):
            vrf_name = vrf_obj.get("name")
            if vrf_name and vrf_name not in builtin_vrfs:
                vrf_names.add(vrf_name)
                vrfs_in_use[vrf_name] = vrf_obj

    # Also check IP addresses if provided
    if ip_addresses:
        for ip_obj in ip_addresses:
            if not ip_obj or not isinstance(ip_obj, dict):
                continue

            vrf_obj = ip_obj.get("vrf")
            if vrf_obj and isinstance(vrf_obj, dict):
                vrf_name = vrf_obj.get("name")
                if vrf_name and vrf_name not in builtin_vrfs:
                    vrf_names.add(vrf_name)
                    vrfs_in_use[vrf_name] = vrf_obj

    result = {"vrf_names": sorted(list(vrf_names)), "vrfs": vrfs_in_use}

    _debug(
        f"Found {len(result['vrf_names'])} configurable VRFs in use: "
        f"{result['vrf_names']}"
    )
    _debug(f"Built-in VRFs filtered out: {builtin_vrfs}")

    return result


def filter_configurable_vrfs(vrfs):
    """
    Filter out VRFs that should not be configured (built-in VRFs)

    Args:
        vrfs: List of VRF objects or VRF names

    Returns:
        List of configurable VRFs
    """
    if not vrfs:
        return []

    # Built-in, non-configurable VRFs
    builtin_vrfs = {"mgmt", "MGMT", "Global", "global", "default", "Default"}
    configurable = []

    for vrf in vrfs:
        if isinstance(vrf, dict):
            vrf_name = vrf.get("name")
        elif isinstance(vrf, str):
            vrf_name = vrf
        else:
            continue

        if vrf_name and vrf_name not in builtin_vrfs:
            configurable.append(vrf)
            _debug(f"VRF {vrf_name} is configurable")
        else:
            _debug(f"VRF {vrf_name} is built-in/non-configurable - skipping")

    return configurable
