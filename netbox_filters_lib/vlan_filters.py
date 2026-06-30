#!/usr/bin/env python3
"""
VLAN-related filters for NetBox data transformation
"""

import re

from .utils import _debug


def _is_subinterface(interface):
    """Return True when interface is a subinterface (virtual + parent)."""
    if not interface or not isinstance(interface, dict):
        return False

    type_obj = interface.get("type")
    type_value = type_obj.get("value") if isinstance(type_obj, dict) else None
    has_parent = interface.get("parent") is not None

    return type_value == "virtual" and has_parent


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

        # Tagged VLANs on subinterfaces do not require standalone VLAN creation.
        if _is_subinterface(interface):
            continue

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


def parse_vlan_id_spec(spec):
    """
    Parse a VLAN-ID specification into a sorted list of unique integers.

    Accepts:
    - int (e.g. 11)
    - str: comma-separated list with optional ranges (e.g. "11", "11,13",
      "11-13", "11,13,15-20"). Whitespace is tolerated.
    - list/tuple of any of the above (recursed)

    Returns:
        Sorted list of unique VLAN IDs (1-4094). Invalid tokens are skipped
        with a debug message.
    """
    vids = set()

    if spec is None:
        return []

    if isinstance(spec, bool):
        # bool is a subclass of int - reject explicitly to avoid 0/1 surprises
        return []

    if isinstance(spec, int):
        if 1 <= spec <= 4094:
            vids.add(spec)
        return sorted(vids)

    if isinstance(spec, (list, tuple)):
        for item in spec:
            vids.update(parse_vlan_id_spec(item))
        return sorted(vids)

    if not isinstance(spec, str):
        _debug(f"parse_vlan_id_spec: unsupported type {type(spec).__name__}")
        return []

    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            try:
                start_s, end_s = token.split("-", 1)
                start = int(start_s.strip())
                end = int(end_s.strip())
            except ValueError:
                _debug(f"parse_vlan_id_spec: invalid range '{token}'")
                continue
            if start > end:
                start, end = end, start
            for vid in range(start, end + 1):
                if 1 <= vid <= 4094:
                    vids.add(vid)
        else:
            try:
                vid = int(token)
            except ValueError:
                _debug(f"parse_vlan_id_spec: invalid VLAN id '{token}'")
                continue
            if 1 <= vid <= 4094:
                vids.add(vid)

    return sorted(vids)


def extract_port_access_vlan_ids(port_access):
    """
    Extract all VLAN IDs referenced by port-access roles.

    Looks at every role's ``vlan_trunk_native`` and ``vlan_trunk_allowed``
    fields and expands range/list syntax (e.g. "11-13", "11,13,15-20").

    Args:
        port_access: ``port_access`` dict from NetBox config_context, or None.

    Returns:
        Sorted list of unique VLAN IDs referenced by any role.
    """
    if not port_access or not isinstance(port_access, dict):
        return []

    vids = set()
    for role in port_access.get("roles") or []:
        if not isinstance(role, dict):
            continue
        vids.update(parse_vlan_id_spec(role.get("vlan_trunk_native")))
        vids.update(parse_vlan_id_spec(role.get("vlan_trunk_allowed")))
        # Also accept untagged/tagged shorthand for parity with NetBox
        # interface fields, in case users prefer those names.
        vids.update(parse_vlan_id_spec(role.get("vlan_access")))

    return sorted(vids)


def get_vlans_in_use(interfaces, vlan_interfaces=None, port_access=None):
    """
    Extract all VLANs that are in use on interfaces

    Args:
        interfaces: List of interface objects from NetBox
        vlan_interfaces: Optional list of VLAN/SVI interfaces
        port_access: Optional ``port_access`` dict from NetBox config_context.
            VLAN IDs referenced by port-access roles
            (``vlan_trunk_native`` / ``vlan_trunk_allowed``) are added to the
            in-use set so they are created on the device and protected from
            deletion in idempotent mode.

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
        if _is_subinterface(intf):
            continue

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

    # Merge VLAN IDs referenced by port-access roles (config_context).
    # Only the VID is added here; the full VLAN object is resolved later from
    # the NetBox-provided VLAN list in get_vlans_needing_changes().
    pa_vids = extract_port_access_vlan_ids(port_access)
    if pa_vids:
        _debug(f"Adding {len(pa_vids)} VLANs from port-access roles: {pa_vids}")
        for vid in pa_vids:
            vids_in_use.add(vid)

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
        _debug(f"Device facts provided: {list(device_facts.keys())}")
        # Try both ansible_network_resources and network_resources paths
        network_resources = None
        if "ansible_network_resources" in device_facts:
            network_resources = device_facts.get("ansible_network_resources", {})
            _debug("Using ansible_network_resources path")
        elif "network_resources" in device_facts:
            network_resources = device_facts.get("network_resources", {})
            _debug("Using network_resources path")
        else:
            _debug(
                f"WARNING: No network_resources found in device_facts. "
                f"Keys: {list(device_facts.keys())}"
            )

        if network_resources and isinstance(network_resources, dict):
            vlans_dict = network_resources.get("vlans", {})
            if vlans_dict and isinstance(vlans_dict, dict):
                # AOS-CX stores VLANs as dict keyed by VID
                for vid_str in vlans_dict.keys():
                    try:
                        vid = int(vid_str)
                        # Validate VLAN ID is in valid range (1-4094)
                        if 1 <= vid <= 4094:
                            device_vids.add(vid)
                        else:
                            _debug(
                                f"WARNING: Invalid VLAN ID {vid} found in device facts "
                                f"(out of range 1-4094)"
                            )
                    except (ValueError, TypeError):
                        pass
                _debug(
                    f"Found {len(device_vids)} VLANs on device: "
                    f"{sorted(list(device_vids))}"
                )
            else:
                _debug("WARNING: vlans dict is empty or not a dict")
        else:
            _debug("WARNING: network_resources is empty or not a dict")
    else:
        _debug("WARNING: No device facts provided to get_vlans_needing_changes!")

    # Build dict of available VLANs by VID
    available_vlans = {}
    for vlan in device_vlans:
        if vlan and isinstance(vlan, dict):
            vid = vlan.get("vid")
            if vid is not None:
                # Validate VLAN ID is in valid range (1-4094)
                if 1 <= vid <= 4094:
                    available_vlans[vid] = vlan
                else:
                    _debug(
                        f"WARNING: Invalid VLAN ID {vid} from NetBox "
                        f"(out of range 1-4094), skipping"
                    )

    _debug(f"Available VLANs from NetBox: {sorted(list(available_vlans.keys()))}")
    _debug(f"VLANs in use on interfaces: {sorted(list(vids_in_use))}")
    _debug(f"VLANs on device (from facts): {sorted(list(device_vids))}")

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
            # Skip VLAN 1 - never delete the default VLAN
            if vid == 1:
                continue

            # Validate VLAN ID is in valid range (1-4094)
            if not 1 <= vid <= 4094:
                _debug(
                    f"WARNING: Skipping invalid VLAN ID {vid} for deletion (out of range 1-4094)"
                )
                continue

            # Delete if: on device AND not in use
            # This includes VLANs that are in NetBox but not used,
            # AND VLANs that are NOT in NetBox at all (orphaned VLANs)
            if vid not in vids_in_use:
                vlans_to_delete.append(vid)
                if vid in available_vids:
                    _debug(
                        f"VLAN {vid} can be deleted (on device, in NetBox, "
                        f"but not in use)"
                    )
                else:
                    _debug(
                        f"VLAN {vid} can be deleted (on device, NOT in NetBox, "
                        f"orphaned VLAN)"
                    )

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


def parse_evpn_evi_output(output):
    """
    Parse 'show evpn evi' command output to extract EVPN and VXLAN configuration

    Args:
        output: String output from 'show evpn evi' command

    Returns:
        Dictionary with:
        - evpn_vlans: List of VLAN IDs configured with EVPN (as integers)
        - vxlan_mappings: List of [VNI, VLAN] mappings (as integers)
        - vxlan_vnis: List of VNI values (as integers)
        - vxlan_vlans: List of VLAN IDs configured with VXLAN (as integers)

    Example output format:
        L2VNI : 10100010
            Route Distinguisher        : 172.20.1.33:10
            VLAN                       : 10
            Status                     : up
            RT Import                  : 65005:10
            RT Export                  : 65005:10
        ...

    Usage in Ansible:
        {{ vxlan_config_output.stdout[0] | parse_evpn_evi_output }}
    """
    if not output or not isinstance(output, str):
        return {
            "evpn_vlans": [],
            "vxlan_mappings": [],
            "vxlan_vnis": [],
            "vxlan_vlans": [],
        }

    # Parse L2VNI values (lines starting with "L2VNI")
    vni_pattern = r"^L2VNI\s+:\s+(\d+)"
    vnis = re.findall(vni_pattern, output, re.MULTILINE)
    vnis_int = [int(vni) for vni in vnis]

    # Parse VLAN values (lines starting with whitespace + "VLAN")
    vlan_pattern = r"^\s+VLAN\s+:\s+(\d+)"
    vlans = re.findall(vlan_pattern, output, re.MULTILINE)
    vlans_int = [int(vlan) for vlan in vlans]

    # Create VNI-to-VLAN mappings
    mappings = [[vni, vlan] for vni, vlan in zip(vnis_int, vlans_int)]

    result = {
        "evpn_vlans": vlans_int,  # EVPN uses VLAN list
        "vxlan_mappings": mappings,  # VXLAN uses VNI-to-VLAN mappings
        "vxlan_vnis": vnis_int,  # Just the VNIs
        "vxlan_vlans": vlans_int,  # Just the VLANs
    }

    _debug(f"Parsed EVPN EVI output: {len(vlans_int)} VLANs, {len(vnis_int)} VNIs")
    return result


def get_vlans_needing_igmp_update(
    device_vlans, vlans_in_use_dict, enhanced_vlan_facts=None
):
    """
    Determine which VLANs need IGMP snooping configuration updates

    Filters VLANs to only those that:
    1. Are in use on interfaces
    2. Have vlan_ip_igmp_snooping custom field defined
    3. Have different IGMP setting than current device state (when facts available)

    Args:
        device_vlans: List of VLAN objects available for this device from NetBox
        vlans_in_use_dict: Dict from get_vlans_in_use() with 'vids' and 'vlans'
        enhanced_vlan_facts: Optional dict from REST API with current IGMP state
                           Format: {"101": {"mgmd_enable": {"igmp": false}, ...}, ...}

    Returns:
        List of VLAN objects needing IGMP snooping configuration updates
    """
    vlans_needing_update = []

    # Ensure inputs are valid
    if not device_vlans:
        _debug("No device VLANs provided")
        return vlans_needing_update

    if not vlans_in_use_dict or "vids" not in vlans_in_use_dict:
        _debug("No VLANs in use provided")
        return vlans_needing_update

    vids_in_use = set(vlans_in_use_dict["vids"])
    _debug(f"VLANs in use on interfaces: {sorted(list(vids_in_use))}")

    # Process each VLAN
    for vlan in device_vlans:
        if not vlan or not isinstance(vlan, dict):
            continue

        vid = vlan.get("vid")
        if vid is None or vid < 2 or vid > 4094:
            continue

        # Skip if VLAN is not in use
        if vid not in vids_in_use:
            _debug(f"VLAN {vid} not in use - skipping IGMP check")
            continue

        # Check if IGMP snooping custom field is defined
        custom_fields = vlan.get("custom_fields", {})
        desired_igmp = custom_fields.get("vlan_ip_igmp_snooping")

        if desired_igmp is None:
            _debug(f"VLAN {vid} has no vlan_ip_igmp_snooping custom field - skipping")
            continue

        # Convert to boolean
        desired_igmp_bool = bool(desired_igmp)

        # If we have enhanced facts, compare current vs desired state
        if enhanced_vlan_facts and isinstance(enhanced_vlan_facts, dict):
            vid_str = str(vid)

            if vid_str in enhanced_vlan_facts:
                vlan_facts = enhanced_vlan_facts[vid_str]

                # Get current IGMP state from mgmd_enable.igmp
                if isinstance(vlan_facts, dict):
                    mgmd_enable = vlan_facts.get("mgmd_enable", {})
                    if isinstance(mgmd_enable, dict):
                        current_igmp = mgmd_enable.get("igmp", False)
                        current_igmp_bool = bool(current_igmp)

                        # Only update if different
                        if desired_igmp_bool != current_igmp_bool:
                            vlans_needing_update.append(vlan)
                            _debug(
                                f"VLAN {vid} IGMP needs update: "
                                f"{current_igmp_bool} -> {desired_igmp_bool}"
                            )
                        else:
                            _debug(
                                f"VLAN {vid} IGMP already correct: {current_igmp_bool}"
                            )
                        continue

            # If we get here, VLAN not found in enhanced facts
            # Add it to be safe (assume it needs update)
            _debug(
                f"VLAN {vid} not in enhanced facts - assuming needs update "
                f"to {desired_igmp_bool}"
            )
            vlans_needing_update.append(vlan)
        else:
            # No enhanced facts - assume all VLANs need update
            _debug(
                f"No enhanced facts - VLAN {vid} will be updated to {desired_igmp_bool}"
            )
            vlans_needing_update.append(vlan)

    _debug(
        f"VLANs needing IGMP update: {len(vlans_needing_update)} - "
        f"{[v.get('vid') for v in vlans_needing_update]}"
    )

    return vlans_needing_update
