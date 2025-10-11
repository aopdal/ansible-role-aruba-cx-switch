#!/usr/bin/env python3
"""
Interface categorization and processing filters
"""

from .utils import _debug


def categorize_l2_interfaces(interfaces):
    """
    Categorize L2 interfaces by their VLAN configuration type

    Args:
        interfaces: List of interface objects from NetBox

    Returns:
        Dict with categorized interface lists
    """
    categorized = {
        "access": [],
        "tagged_with_untagged": [],
        "tagged_no_untagged": [],
        "tagged_all_with_untagged": [],
        "tagged_all_no_untagged": [],
        "lag_access": [],
        "lag_tagged_with_untagged": [],
        "lag_tagged_no_untagged": [],
        "lag_tagged_all_with_untagged": [],
        "lag_tagged_all_no_untagged": [],
        "mclag_access": [],
        "mclag_tagged_with_untagged": [],
        "mclag_tagged_no_untagged": [],
        "mclag_tagged_all_with_untagged": [],
        "mclag_tagged_all_no_untagged": [],
    }

    # Ensure interfaces is not None
    if not interfaces:
        _debug("No interfaces provided to categorize_l2_interfaces")
        return categorized

    for intf in interfaces:
        # Skip if interface is None
        if intf is None:
            _debug("Skipping None interface")
            continue

        intf_name = intf.get("name", "unknown")

        # Skip non-L2 interfaces
        if intf.get("mgmt_only"):
            continue

        # Skip if no mode defined
        mode_obj = intf.get("mode")
        if not mode_obj or mode_obj is None:
            continue

        mode_value = mode_obj.get("value") if isinstance(mode_obj, dict) else None
        if not mode_value:
            continue

        # Skip virtual interfaces
        type_obj = intf.get("type")
        if type_obj and isinstance(type_obj, dict):
            type_value = type_obj.get("value")
            if type_value == "virtual":
                continue

        # Determine interface characteristics
        mode = mode_value

        # Check for untagged VLAN
        untagged_vlan = intf.get("untagged_vlan")
        has_untagged = False
        untagged_vid = None
        if untagged_vlan and isinstance(untagged_vlan, dict):
            untagged_vid = untagged_vlan.get("vid")
            has_untagged = untagged_vid is not None

        # Check for tagged VLANs
        tagged_vlans = intf.get("tagged_vlans")
        has_tagged = False
        if tagged_vlans and isinstance(tagged_vlans, list):
            # Filter out None entries and entries without vid
            valid_tagged = [
                v
                for v in tagged_vlans
                if v and isinstance(v, dict) and v.get("vid") is not None
            ]
            has_tagged = len(valid_tagged) > 0

        # Determine if LAG
        is_lag = False
        if type_obj and isinstance(type_obj, dict):
            is_lag = type_obj.get("value") == "lag"

        # Determine if MCLAG
        custom_fields = intf.get("custom_fields")
        is_mclag = False
        if custom_fields and isinstance(custom_fields, dict):
            is_mclag = custom_fields.get("if_mclag", False)

        # Determine prefix based on interface type
        if is_mclag:
            prefix = "mclag_"
        elif is_lag:
            prefix = "lag_"
        else:
            prefix = ""

        # Categorize based on mode and VLAN configuration
        try:
            if mode == "access":
                # Only add if has valid untagged VLAN
                if has_untagged:
                    categorized[f"{prefix}access"].append(intf)
                else:
                    _debug(f"Skipping {intf_name} - access mode but no untagged VLAN")
            elif mode == "tagged":
                if has_untagged and has_tagged:
                    categorized[f"{prefix}tagged_with_untagged"].append(intf)
                elif has_tagged:
                    categorized[f"{prefix}tagged_no_untagged"].append(intf)
                else:
                    _debug(
                        f"Skipping {intf_name} - tagged mode but no VLANs configured"
                    )
            elif mode == "tagged-all":
                if has_untagged:
                    categorized[f"{prefix}tagged_all_with_untagged"].append(intf)
                else:
                    categorized[f"{prefix}tagged_all_no_untagged"].append(intf)
        except Exception as e:
            _debug(f"Error categorizing interface {intf_name}: {str(e)}")
            continue

    _debug("L2 interface categorization:")
    for category, intfs in categorized.items():
        if intfs:
            _debug(
                f"  {category}: {len(intfs)} interfaces - "
                f"{[i.get('name') for i in intfs]}"
            )

    return categorized


def categorize_l3_interfaces(interfaces):
    """
    Categorize L3 interfaces by type and configuration

    Args:
        interfaces: List of interface objects with IP addresses from NetBox

    Returns:
        Dict with categorized interfaces:
        - physical_default_vrf: Physical interfaces in default/Global/mgmt VRF
        - physical_custom_vrf: Physical interfaces in custom VRFs
        - vlan_default_vrf: VLAN interfaces in default/Global/mgmt VRF
        - vlan_custom_vrf: VLAN interfaces in custom VRFs
        - lag_default_vrf: LAG interfaces in default/Global/mgmt VRF
        - lag_custom_vrf: LAG interfaces in custom VRFs
        - loopback: Loopback interfaces
    """
    result = {
        "physical_default_vrf": [],
        "physical_custom_vrf": [],
        "vlan_default_vrf": [],
        "vlan_custom_vrf": [],
        "lag_default_vrf": [],
        "lag_custom_vrf": [],
        "loopback": [],
    }

    # Built-in, non-configurable VRFs
    builtin_vrfs = {"default", "Default", "Global", "global", "mgmt", "MGMT", None}

    if not interfaces:
        return result

    for intf in interfaces:
        if not intf:
            continue

        # Skip management interfaces
        if intf.get("mgmt_only"):
            interface_name = intf.get("interface_name") or intf.get("name", "unknown")
            _debug(f"Skipping management interface: {interface_name}")
            continue

        # Get interface type - handle both processed and original formats
        type_value = ""
        name = ""

        # Check for processed format (from interface_ips)
        if "interface_type" in intf:
            type_value = intf.get("interface_type", "")
            name = intf.get("interface_name", "").lower()
        # Check for original NetBox interface format
        else:
            type_obj = intf.get("type")
            if type_obj and isinstance(type_obj, dict):
                type_value = type_obj.get("value", "")
            name = intf.get("name", "").lower()

        if not type_value:
            continue

        # Determine VRF (default to built-in)
        # Only check interface VRF, NOT IP address VRF
        vrf_name = None

        # Check for VRF in the original NetBox interface format
        if "vrf" in intf and isinstance(intf["vrf"], dict):
            vrf_name = intf["vrf"].get("name")
        # Check for VRF in nested interface object (from interface_ips format)
        elif "interface" in intf:
            interface_obj = intf["interface"]
            if isinstance(interface_obj, dict):
                vrf_obj = interface_obj.get("vrf")
                if vrf_obj and isinstance(vrf_obj, dict):
                    vrf_name = vrf_obj.get("name")
        # Note: We intentionally do NOT check intf["vrf"] as string
        # because that comes from IP address VRF, not interface VRF

        is_builtin_vrf = vrf_name in builtin_vrfs

        # Get interface name for logging
        interface_name = intf.get("interface_name") or intf.get("name", "unknown")

        # Categorize by type and VRF
        if type_value == "virtual" and "loopback" in name:
            result["loopback"].append(intf)
            _debug(f"Categorized {interface_name} as loopback")
        elif type_value == "virtual" and "vlan" in name:
            if is_builtin_vrf:
                result["vlan_default_vrf"].append(intf)
                _debug(
                    f"Categorized {interface_name} as VLAN interface "
                    f"(Interface built-in VRF: {vrf_name})"
                )
            else:
                result["vlan_custom_vrf"].append(intf)
                _debug(
                    f"Categorized {interface_name} as VLAN interface "
                    f"(Interface VRF: {vrf_name})"
                )
        elif type_value == "lag":
            if is_builtin_vrf:
                result["lag_default_vrf"].append(intf)
                _debug(
                    f"Categorized {interface_name} as LAG interface "
                    f"(Interface built-in VRF: {vrf_name})"
                )
            else:
                result["lag_custom_vrf"].append(intf)
                _debug(
                    f"Categorized {interface_name} as LAG interface "
                    f"(Interface VRF: {vrf_name})"
                )
        else:
            # Physical interface
            if is_builtin_vrf:
                result["physical_default_vrf"].append(intf)
                _debug(
                    f"Categorized {interface_name} as physical interface "
                    f"(Interface built-in VRF: {vrf_name})"
                )
            else:
                result["physical_custom_vrf"].append(intf)
                _debug(
                    f"Categorized {interface_name} as physical interface "
                    f"(Interface VRF: {vrf_name})"
                )

    _debug("L3 interface categorization:")
    _debug(f"  Physical (built-in VRF): {len(result['physical_default_vrf'])}")
    _debug(f"  Physical (custom VRF): {len(result['physical_custom_vrf'])}")
    _debug(f"  VLAN (built-in VRF): {len(result['vlan_default_vrf'])}")
    _debug(f"  VLAN (custom VRF): {len(result['vlan_custom_vrf'])}")
    _debug(f"  LAG (built-in VRF): {len(result['lag_default_vrf'])}")
    _debug(f"  LAG (custom VRF): {len(result['lag_custom_vrf'])}")
    _debug(f"  Loopback: {len(result['loopback'])}")

    return result


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
            }
        )

        _debug(
            f"Matched IP {address} to interface {intf.get('name')} "
            f"(VRF: {vrf_name})"
        )

    _debug(f"Total interface/IP matches: {len(result)}")
    return result
