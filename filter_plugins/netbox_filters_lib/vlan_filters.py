#!/usr/bin/env python3
"""
VLAN-related filters for NetBox data transformation
"""

from .utils import _debug


def extract_vlan_ids(interfaces):
    """
    Extract all VLAN IDs in use from interfaces

    Args:
        interfaces: List of interface objects from NetBox

    Returns:
        Sorted list of unique VLAN IDs
    """
    vlan_ids = set()

    for interface in interfaces:
        # VLAN interfaces (e.g., vlan100)
        if interface.get("name", "").startswith("vlan"):
            try:
                vid = int(interface["name"].replace("vlan", ""))
                vlan_ids.add(vid)
            except (ValueError, TypeError):
                pass

        # Untagged VLANs
        if interface.get("untagged_vlan") and interface["untagged_vlan"] is not None:
            vid = interface["untagged_vlan"].get("vid")
            if vid is not None:
                vlan_ids.add(vid)

        # Tagged VLANs
        if interface.get("tagged_vlans") and interface["tagged_vlans"] is not None:
            for vlan in interface["tagged_vlans"]:
                vid = vlan.get("vid")
                if vid is not None:
                    vlan_ids.add(vid)

    _debug(f"Extracted VLAN IDs: {sorted(list(vlan_ids))}")
    return sorted(list(vlan_ids))


def filter_vlans_in_use(vlans, interfaces):
    """
    Filter VLANs to only those actually in use on interfaces

    Args:
        vlans: List of all VLAN objects from NetBox
        interfaces: List of interface objects from NetBox

    Returns:
        List of VLAN objects that are in use
    """
    vlan_ids_in_use = set(extract_vlan_ids(interfaces))

    filtered = [vlan for vlan in vlans if vlan.get("vid") in vlan_ids_in_use]

    _debug(f"Filtered VLANs in use: {[v.get('vid') for v in filtered]}")
    return filtered


def extract_evpn_vlans(vlans, interfaces, check_noevpn=True):
    """
    Extract VLANs that should be configured for EVPN

    Args:
        vlans: List of all VLAN objects from NetBox
        interfaces: List of interface objects from NetBox
        check_noevpn: Whether to check vlan_noevpn custom field

    Returns:
        List of VLAN objects for EVPN configuration
    """
    vlans_in_use = filter_vlans_in_use(vlans, interfaces)

    evpn_vlans = []
    for vlan in vlans_in_use:
        # Check if EVPN is disabled for this VLAN
        if check_noevpn:
            custom_fields = vlan.get("custom_fields", {})
            if custom_fields.get("vlan_noevpn"):
                _debug(f"Skipping VLAN {vlan.get('vid')} - EVPN disabled")
                continue

        # Check if L2VPN is configured
        l2vpn_term = vlan.get("l2vpn_termination")
        if l2vpn_term and l2vpn_term.get("l2vpn"):
            evpn_vlans.append(vlan)
            _debug(f"Including VLAN {vlan.get('vid')} for EVPN")

    _debug(f"Final EVPN VLANs: {[v.get('vid') for v in evpn_vlans]}")
    return evpn_vlans


def extract_vxlan_mappings(vlans, interfaces, use_l2vpn_id=True):
    """
    Extract VXLAN VNI to VLAN mappings

    Args:
        vlans: List of all VLAN objects from NetBox
        interfaces: List of interface objects from NetBox
        use_l2vpn_id: Use L2VPN identifier as VNI, otherwise use VLAN ID

    Returns:
        List of dicts with 'vni' and 'vlan' keys
    """
    vlans_in_use = filter_vlans_in_use(vlans, interfaces)

    mappings = []
    for vlan in vlans_in_use:
        vid = vlan.get("vid")

        # Check if EVPN is disabled
        custom_fields = vlan.get("custom_fields", {})
        if custom_fields.get("vlan_noevpn"):
            _debug(f"Skipping VLAN {vid} for VXLAN - EVPN disabled")
            continue

        if use_l2vpn_id:
            # Use L2VPN identifier as VNI
            l2vpn_term = vlan.get("l2vpn_termination")
            if l2vpn_term and l2vpn_term.get("l2vpn"):
                vni = l2vpn_term["l2vpn"].get("identifier")
                if vni is not None:
                    mappings.append({"vni": vni, "vlan": vid})
                    _debug(f"VXLAN mapping: VNI {vni} -> VLAN {vid} (L2VPN)")
        else:
            # Use VLAN ID as VNI
            if vid is not None:
                mappings.append({"vni": vid, "vlan": vid})
                _debug(f"VXLAN mapping: VNI {vid} -> VLAN {vid}")

    _debug(f"Total VXLAN mappings: {len(mappings)}")
    return mappings


def get_vlans_in_use(interfaces, vlan_interfaces=None):
    """
    Extract all VLANs that are in use on interfaces

    Args:
        interfaces: List of interface objects from NetBox
        vlan_interfaces: Optional list of VLAN/SVI interfaces

    Returns:
        Dict with:
        - 'vids': Set of VLAN IDs in use
        - 'vlans': List of unique VLAN objects in use
    """
    vlans_in_use = {}  # Dict keyed by vid to avoid duplicates
    vids_in_use = set()

    # Ensure interfaces is not None
    if not interfaces:
        interfaces = []

    # Process physical and LAG interfaces
    for intf in interfaces:
        if not intf:
            continue

        # Skip management interfaces
        if intf.get("mgmt_only"):
            continue

        # Get untagged VLAN
        untagged_vlan = intf.get("untagged_vlan")
        if untagged_vlan and isinstance(untagged_vlan, dict):
            vid = untagged_vlan.get("vid")
            if vid is not None:
                vids_in_use.add(vid)
                vlans_in_use[vid] = untagged_vlan

        # Get tagged VLANs
        tagged_vlans = intf.get("tagged_vlans")
        if tagged_vlans and isinstance(tagged_vlans, list):
            for vlan in tagged_vlans:
                if vlan and isinstance(vlan, dict):
                    vid = vlan.get("vid")
                    if vid is not None:
                        vids_in_use.add(vid)
                        vlans_in_use[vid] = vlan

    # Process VLAN/SVI interfaces
    if vlan_interfaces:
        for vlan_intf in vlan_interfaces:
            if not vlan_intf:
                continue

            # VLAN interfaces have a 'vlan' field or VLAN info in the name
            vlan_obj = vlan_intf.get("vlan")
            if vlan_obj and isinstance(vlan_obj, dict):
                vid = vlan_obj.get("vid")
                if vid is not None:
                    vids_in_use.add(vid)
                    vlans_in_use[vid] = vlan_obj

    result = {"vids": sorted(list(vids_in_use)), "vlans": list(vlans_in_use.values())}

    _debug(f"Found {len(result['vids'])} VLANs in use: {result['vids']}")

    return result


def get_vlans_needing_changes(device_vlans, vlans_in_use_dict, device_facts=None):
    """
    Determine which VLANs need to be added or removed

    Args:
        device_vlans: List of VLAN objects available for this device from NetBox
        vlans_in_use_dict: Dict from get_vlans_in_use() with 'vids' and 'vlans'
        device_facts: Optional device facts for checking current state

    Returns:
        Dict with:
        - 'vlans_to_create': List of VLAN objects to create
        - 'vlans_to_delete': List of VLAN IDs to delete
        - 'vlans_in_use': List of VLAN objects currently in use
    """
    vlans_to_create = []
    vlans_to_delete = []
    vlans_in_use = []

    # Ensure inputs are valid
    if not device_vlans:
        _debug("No device VLANs provided")
        return {
            "vlans_to_create": vlans_to_create,
            "vlans_to_delete": vlans_to_delete,
            "vlans_in_use": vlans_in_use,
        }

    if not vlans_in_use_dict or "vids" not in vlans_in_use_dict:
        _debug("No VLANs in use provided")
        return {
            "vlans_to_create": vlans_to_create,
            "vlans_to_delete": vlans_to_delete,
            "vlans_in_use": vlans_in_use,
        }

    vids_in_use = set(vlans_in_use_dict["vids"])

    # Get VLANs currently on device (if facts provided)
    device_vids = set()
    if device_facts and isinstance(device_facts, dict):
        # Try both ansible_network_resources and network_resources paths
        network_resources = None
        if "ansible_network_resources" in device_facts:
            network_resources = device_facts.get("ansible_network_resources", {})
        elif "network_resources" in device_facts:
            network_resources = device_facts.get("network_resources", {})

        if network_resources and isinstance(network_resources, dict):
            vlans_dict = network_resources.get("vlans", {})
            if vlans_dict and isinstance(vlans_dict, dict):
                # AOS-CX stores VLANs as dict keyed by VID
                for vid_str in vlans_dict.keys():
                    try:
                        device_vids.add(int(vid_str))
                    except (ValueError, TypeError):
                        pass
                _debug(
                    f"Found {len(device_vids)} VLANs on device: "
                    f"{sorted(list(device_vids))}"
                )

    # Build dict of available VLANs by VID
    available_vlans = {}
    for vlan in device_vlans:
        if vlan and isinstance(vlan, dict):
            vid = vlan.get("vid")
            if vid is not None:
                available_vlans[vid] = vlan

    _debug(f"Available VLANs from NetBox: {sorted(list(available_vlans.keys()))}")
    _debug(f"VLANs in use on interfaces: {sorted(list(vids_in_use))}")

    # Determine VLANs to create (in use but not on device or not created yet)
    for vid in vids_in_use:
        if vid in available_vlans:
            vlans_in_use.append(available_vlans[vid])
            # Only add to create list if we have device facts and it's not there
            if device_facts and vid not in device_vids:
                vlans_to_create.append(available_vlans[vid])
                _debug(f"VLAN {vid} needs to be created")
        else:
            _debug(
                f"WARNING: VLAN {vid} is in use but not available "
                f"in NetBox for this device!"
            )

    # If no device facts, assume we need to create all in-use VLANs
    if not device_facts:
        vlans_to_create = vlans_in_use.copy()
        _debug("No device facts provided - will create all VLANs in use")

    # Determine VLANs to delete (on device but not in use)
    if device_facts and device_vids:
        available_vids = set(available_vlans.keys())
        for vid in device_vids:
            # Delete if: on device AND (not in use OR not in NetBox available list)
            if vid not in vids_in_use and vid in available_vids:
                vlans_to_delete.append(vid)
                _debug(f"VLAN {vid} can be deleted (on device but not in use)")
            elif vid not in available_vids and vid != 1:  # Don't delete VLAN 1
                _debug(f"VLAN {vid} on device but not in NetBox scope for this device")

    result = {
        "vlans_to_create": vlans_to_create,
        "vlans_to_delete": sorted(vlans_to_delete),
        "vlans_in_use": vlans_in_use,
    }

    vlan_create_ids = [v.get("vid") for v in result["vlans_to_create"]]
    _debug(f"VLANs to create: {len(result['vlans_to_create'])} - {vlan_create_ids}")
    _debug(
        f"VLANs to delete: {len(result['vlans_to_delete'])} - "
        f"{result['vlans_to_delete']}"
    )

    return result


def get_vlan_interfaces(interfaces):
    """
    Extract VLAN/SVI interfaces from interface list

    Args:
        interfaces: List of interface objects from NetBox

    Returns:
        List of VLAN interface objects
    """
    vlan_interfaces = []

    if not interfaces:
        return vlan_interfaces

    for intf in interfaces:
        if not intf:
            continue

        # Check if it's a virtual interface with 'vlan' in the name
        type_obj = intf.get("type")
        name = intf.get("name", "").lower()

        is_vlan_interface = False

        # Check by type
        if type_obj and isinstance(type_obj, dict):
            type_value = type_obj.get("value", "")
            if type_value == "virtual":
                # Check if name contains 'vlan'
                if "vlan" in name:
                    is_vlan_interface = True

        if is_vlan_interface:
            vlan_interfaces.append(intf)
            _debug(f"Found VLAN interface: {intf.get('name')}")

    _debug(f"Total VLAN interfaces found: {len(vlan_interfaces)}")
    return vlan_interfaces
