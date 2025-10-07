#!/usr/bin/env python3
"""
Interface and VLAN comparison logic for determining configuration changes
"""

import traceback
from .utils import _debug


def compare_interface_vlans(netbox_interface, device_facts_interface):
    """
    Compare VLANs between NetBox and device facts to determine required changes

    Args:
        netbox_interface: Interface object from NetBox inventory
        device_facts_interface: Interface object from device facts

    Returns:
        Dict with 'vlans_to_add', 'vlans_to_remove', 'needs_change' keys
    """
    result = {
        "vlans_to_add": [],
        "vlans_to_remove": [],
        "needs_change": False,
        "mode_change": False,
    }

    # Skip if either interface is None
    if not netbox_interface or not device_facts_interface:
        return result

    # Get NetBox VLAN configuration
    mode_obj = netbox_interface.get("mode")
    if not mode_obj or not isinstance(mode_obj, dict):
        return result

    nb_mode = mode_obj.get("value")
    if not nb_mode:
        return result

    # Get untagged VLAN
    nb_untagged = None
    untagged_vlan = netbox_interface.get("untagged_vlan")
    if untagged_vlan and isinstance(untagged_vlan, dict):
        nb_untagged = untagged_vlan.get("vid")

    # Get tagged VLANs
    nb_tagged = set()
    tagged_vlans = netbox_interface.get("tagged_vlans")
    if tagged_vlans and isinstance(tagged_vlans, list):
        for v in tagged_vlans:
            if v and isinstance(v, dict):
                vid = v.get("vid")
                if vid is not None:
                    nb_tagged.add(vid)

    # Get device VLAN configuration - AOS-CX specific structure
    device_mode = device_facts_interface.get("vlan_mode") or device_facts_interface.get(
        "applied_vlan_mode"
    )

    # Get native/access VLAN
    device_native = None
    vlan_tag = device_facts_interface.get("vlan_tag") or device_facts_interface.get(
        "applied_vlan_tag"
    )
    if vlan_tag and isinstance(vlan_tag, dict):
        # vlan_tag is a dict like {"10": "/rest/v10.09/system/vlans/10"}
        # Extract the VLAN ID from the key
        for vlan_id_str in vlan_tag.keys():
            try:
                device_native = int(vlan_id_str)
                break
            except (ValueError, TypeError):
                pass

    # Get trunk VLANs
    device_trunks = set()
    vlan_trunks = device_facts_interface.get(
        "vlan_trunks"
    ) or device_facts_interface.get("applied_vlan_trunks")
    if vlan_trunks and isinstance(vlan_trunks, dict):
        # vlan_trunks dict like {"10": "/rest/.../vlans/10", "20": "/rest/..."}
        for vlan_id_str in vlan_trunks.keys():
            try:
                device_trunks.add(int(vlan_id_str))
            except (ValueError, TypeError):
                pass

    _debug(
        f"Interface {netbox_interface.get('name')}: NB mode={nb_mode}, "
        f"untagged={nb_untagged}, tagged={nb_tagged}"
    )
    _debug(
        f"Interface {netbox_interface.get('name')}: Device mode={device_mode}, "
        f"native={device_native}, trunks={device_trunks}"
    )

    # Check mode change
    if nb_mode == "access" and device_mode != "access":
        result["mode_change"] = True
        result["needs_change"] = True
    elif nb_mode in ["tagged", "tagged-all"] and device_mode not in [
        "native-tagged",
        "native-untagged",
    ]:
        result["mode_change"] = True
        result["needs_change"] = True

    if nb_mode == "access":
        # For access mode, just check if the access VLAN matches
        if nb_untagged and nb_untagged != device_native:
            result["needs_change"] = True
    elif nb_mode == "tagged":
        # Build the complete set of VLANs that should be on the interface
        nb_all_vlans = set(nb_tagged)
        if nb_untagged:
            nb_all_vlans.add(nb_untagged)

        # Check native VLAN
        if nb_untagged and nb_untagged != device_native:
            result["needs_change"] = True

        # Compare trunk VLANs
        result["vlans_to_add"] = list(nb_all_vlans - device_trunks)
        result["vlans_to_remove"] = list(device_trunks - nb_all_vlans)

        if result["vlans_to_add"] or result["vlans_to_remove"]:
            result["needs_change"] = True
    elif nb_mode == "tagged-all":
        # For tagged-all, we only care about native VLAN
        if nb_untagged and nb_untagged != device_native:
            result["needs_change"] = True

    _debug(f"Interface {netbox_interface.get('name')} comparison: {result}")
    return result


def get_interfaces_needing_changes(interfaces, device_facts):
    """
    Get list of interfaces that need VLAN changes (additions or removals)

    Args:
        interfaces: List of interface objects from NetBox inventory
        device_facts: Device facts from ansible_facts

    Returns:
        Dict with 'cleanup' (interfaces needing VLAN removal) and
        'configure' (interfaces needing any changes) lists
    """
    cleanup_list = []
    configure_list = []

    # Ensure inputs are valid
    if not interfaces:
        _debug("No interfaces provided to get_interfaces_needing_changes")
        return {"cleanup": cleanup_list, "configure": configure_list}

    if not device_facts:
        _debug("No device facts provided to get_interfaces_needing_changes")
        return {"cleanup": cleanup_list, "configure": configure_list}

    # Convert device facts to a dict keyed by interface name
    # AOS-CX uses network_resources.interfaces as a dict
    facts_by_interface = {}

    if "network_resources" in device_facts:
        network_resources = device_facts.get("network_resources", {})
        if network_resources and isinstance(network_resources, dict):
            interfaces_dict = network_resources.get("interfaces", {})
            if interfaces_dict and isinstance(interfaces_dict, dict):
                facts_by_interface = interfaces_dict
                _debug(
                    f"Found {len(facts_by_interface)} interfaces in "
                    f"network_resources.interfaces"
                )

    if not facts_by_interface:
        _debug(f"Device facts structure: {list(device_facts.keys())}")
        return {"cleanup": cleanup_list, "configure": configure_list}

    _debug(f"Found {len(facts_by_interface)} interfaces in device facts")
    _debug(f"Sample interface names: {list(facts_by_interface.keys())[:5]}")

    for nb_intf in interfaces:
        # Skip None interfaces
        if not nb_intf:
            continue

        intf_name = nb_intf.get("name")
        if not intf_name:
            continue

        # Skip non-L2 interfaces
        if nb_intf.get("mgmt_only"):
            continue

        mode_obj = nb_intf.get("mode")
        if not mode_obj or not isinstance(mode_obj, dict):
            continue

        # Get device facts for this interface
        device_intf = facts_by_interface.get(intf_name)
        if not device_intf:
            # No device facts = interface needs to be configured
            _debug(
                f"No device facts found for interface {intf_name} - "
                f"needs configuration"
            )
            configure_list.append(nb_intf)
            continue

        _debug(f"Comparing interface {intf_name}")

        try:
            comparison = compare_interface_vlans(nb_intf, device_intf)

            # If any changes are needed, add to configure list
            if comparison["needs_change"]:
                configure_list.append(nb_intf)
                _debug(f"Interface {intf_name} needs configuration changes")

                # If VLANs need to be removed, also add to cleanup list
                if comparison["vlans_to_remove"]:
                    type_obj = nb_intf.get("type")
                    is_lag = False
                    if type_obj and isinstance(type_obj, dict):
                        is_lag = type_obj.get("value") == "lag"

                    custom_fields = nb_intf.get("custom_fields")
                    is_mclag = False
                    if custom_fields and isinstance(custom_fields, dict):
                        is_mclag = custom_fields.get("if_mclag", False)

                    cleanup_list.append(
                        {
                            "interface": intf_name,
                            "vlans_to_remove": comparison["vlans_to_remove"],
                            "is_lag": is_lag,
                            "is_mclag": is_mclag,
                        }
                    )
                    _debug(
                        f"Interface {intf_name} needs cleanup: "
                        f"remove VLANs {comparison['vlans_to_remove']}"
                    )
            else:
                _debug(
                    f"Interface {intf_name} is already correctly configured - "
                    f"skipping"
                )

        except Exception as e:
            _debug(f"Error comparing interface {intf_name}: {str(e)}")
            _debug(f"Traceback: {traceback.format_exc()}")
            # If we can't compare, assume it needs configuration
            configure_list.append(nb_intf)
            continue

    _debug(f"Interfaces needing cleanup: {len(cleanup_list)}")
    _debug(f"Interfaces needing configuration: {len(configure_list)}")
    skipped_count = len([i for i in interfaces if i and i.get("mode")]) - len(
        configure_list
    )
    _debug(f"Interfaces skipped (no changes): {skipped_count}")

    return {"cleanup": cleanup_list, "configure": configure_list}


# Keep the old function for backwards compatibility, but mark as deprecated
def get_interfaces_needing_vlan_cleanup(interfaces, device_facts):
    """
    DEPRECATED: Use get_interfaces_needing_changes() instead

    Get list of interfaces that need VLAN removal
    """
    result = get_interfaces_needing_changes(interfaces, device_facts)
    return result["cleanup"]
