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

        # Skip mgmt interface by name (special case not handled by L3 workflow)
        interface_name = intf.get("interface_name") or intf.get("name", "unknown")
        if interface_name.lower() == "mgmt":
            _debug(f"Skipping mgmt interface: {interface_name}")
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


def get_interfaces_needing_config_changes(interfaces, device_facts):
    """
    Compare NetBox interfaces with device facts to identify which interfaces need changes.
    This is the idempotent check to avoid unnecessary API calls.

    Args:
        interfaces: List of interface objects from NetBox
        device_facts: Device facts containing current interface state

    Returns:
        Dict with categorized interfaces:
        - physical: Physical interfaces needing changes (enabled/disabled, description, MTU)
        - lag: LAG interfaces needing changes
        - mclag: MCLAG interfaces needing changes
        - l2: L2 interfaces needing VLAN changes
        - l3: L3 interfaces needing IP address changes
        - lag_members: Physical interfaces needing LAG assignment changes
        - no_changes: Interfaces that don't need any changes
    """
    result = {
        "physical": [],
        "lag": [],
        "mclag": [],
        "l2": [],
        "l3": [],
        "lag_members": [],
        "no_changes": [],
    }

    if not interfaces:
        _debug("No interfaces provided to get_interfaces_needing_config_changes")
        return result

    if not device_facts:
        _debug("No device facts provided - assuming all interfaces need changes")
        # Without facts, we can't compare, so assume all need changes
        for intf in interfaces:
            if not intf:
                continue
            _categorize_interface_for_changes(intf, result, needs_change=True)
        return result

    # Get device interface facts
    facts_by_interface = {}
    if "network_resources" in device_facts:
        network_resources = device_facts.get("network_resources", {})
        if network_resources and isinstance(network_resources, dict):
            interfaces_dict = network_resources.get("interfaces", {})
            if interfaces_dict and isinstance(interfaces_dict, dict):
                facts_by_interface = interfaces_dict
                _debug(f"Loaded {len(facts_by_interface)} interfaces from device facts")
                _debug(f"Sample interface keys: {list(facts_by_interface.keys())[:10]}")
                # Show structure of first interface
                if facts_by_interface:
                    first_key = list(facts_by_interface.keys())[0]
                    _debug(
                        f"Sample interface structure ({first_key}): {facts_by_interface[first_key]}"
                    )

    if not facts_by_interface:
        _debug("No interface facts found - assuming all interfaces need changes")
        # Same as above - without facts, assume all need changes
        for intf in interfaces:
            if not intf:
                continue
            _categorize_interface_for_changes(intf, result, needs_change=True)
        return result

    _debug(f"Comparing {len(interfaces)} NetBox interfaces with device facts")

    for nb_intf in interfaces:
        if not nb_intf:
            continue

        intf_name = nb_intf.get("name")
        if not intf_name:
            continue

        _debug(f"Processing interface: {intf_name} (type: {nb_intf.get('type')})")

        # Skip management interfaces
        if nb_intf.get("mgmt_only"):
            _debug(f"Skipping management interface: {intf_name}")
            result["no_changes"].append(nb_intf)
            continue

        # Skip interface if it's named "mgmt" (case insensitive)
        if intf_name.lower() == "mgmt":
            _debug(f"Skipping mgmt interface by name: {intf_name}")
            result["no_changes"].append(nb_intf)
            continue

        # Get device facts for this interface
        # AOS-CX uses format "1/1/1" which becomes key "1_1_1" in facts
        device_intf_key = intf_name.replace("/", "_").replace(" ", "_")
        device_intf = facts_by_interface.get(device_intf_key)

        if not device_intf:
            # Interface doesn't exist on device yet - needs to be created
            _debug(
                f"Interface {intf_name} (key: {device_intf_key}) "
                "not found in device facts - needs creation"
            )
            available_keys = list(facts_by_interface.keys())[:5]
            _debug(f"Available interface keys: {available_keys}")
            _categorize_interface_for_changes(nb_intf, result, needs_change=True)
            continue

        _debug(f"Found device facts for {intf_name}: {device_intf}")

        # Check if interface needs changes
        needs_change = False
        change_reasons = []

        # Get interface type
        type_obj = nb_intf.get("type")
        type_value = ""
        if type_obj and isinstance(type_obj, dict):
            type_value = type_obj.get("value")

        # Check physical/LAG interface properties
        if type_value not in ["virtual"]:
            # Check enabled state
            nb_enabled = nb_intf.get("enabled", True)
            device_admin_state = device_intf.get("admin") or device_intf.get(
                "admin_state"
            )
            device_enabled = device_admin_state == "up" if device_admin_state else None

            # Only compare if we have device state information
            if device_enabled is not None and nb_enabled != device_enabled:
                needs_change = True
                change_reasons.append(
                    f"enabled mismatch (NB: {nb_enabled}, device: {device_enabled})"
                )

            _debug(
                f"Interface {intf_name}: NB enabled={nb_enabled}, "
                f"device admin_state={device_admin_state}, "
                f"device_enabled={device_enabled}"
            )

            # Check description (only if NetBox has a description)
            nb_description = nb_intf.get("description", "")
            device_description = device_intf.get("description", "")

            # Only check if NetBox has a description set
            if nb_description:
                # Special handling for AP_Aruba description
                if nb_description == "AP_Aruba":
                    expected_description = f"{intf_name} {nb_description}"
                    if device_description != expected_description:
                        needs_change = True
                        change_reasons.append(
                            f"description mismatch (NB: {expected_description}, "
                            f"device: {device_description})"
                        )
                elif nb_description != device_description:
                    needs_change = True
                    change_reasons.append(
                        f"description mismatch (NB: {nb_description}, "
                        f"device: {device_description})"
                    )

            # Check MTU (if specified in NetBox)
            nb_mtu = nb_intf.get("mtu")
            if nb_mtu and nb_mtu != "" and nb_mtu is not None:
                device_mtu = device_intf.get("mtu")
                if device_mtu and int(nb_mtu) != int(device_mtu):
                    needs_change = True
                    change_reasons.append(
                        f"MTU mismatch (NB: {nb_mtu}, device: {device_mtu})"
                    )

        # Check LAG membership
        nb_lag = nb_intf.get("lag")
        if nb_lag and isinstance(nb_lag, dict):
            nb_lag_name = nb_lag.get("name", "")
            device_lag_id = device_intf.get("lag_id")

            if device_lag_id:
                # Parse device lag_id (e.g., "lag10" -> "lag10" or just "10" -> "lag10")
                device_lag_name = (
                    device_lag_id
                    if isinstance(device_lag_id, str)
                    else str(device_lag_id)
                )
                # Ensure it has "lag" prefix
                if not device_lag_name.startswith("lag"):
                    device_lag_name = f"lag{device_lag_name}"
            else:
                device_lag_name = ""

            if nb_lag_name and nb_lag_name != device_lag_name:
                needs_change = True
                change_reasons.append(
                    f"LAG membership mismatch (NB: {nb_lag_name}, "
                    f"device: {device_lag_name})"
                )
                result["lag_members"].append(nb_intf)
            elif not nb_lag_name and device_lag_name:
                # Interface should not be in LAG but is
                needs_change = True
                change_reasons.append(
                    f"Interface should not be in LAG (device has: {device_lag_name})"
                )
                result["lag_members"].append(nb_intf)

        # Check L2 configuration (VLANs)
        mode_obj = nb_intf.get("mode")
        if mode_obj and isinstance(mode_obj, dict):
            # Has L2 mode - check VLAN configuration
            nb_mode = mode_obj.get("value")
            device_mode = device_intf.get("vlan_mode") or device_intf.get(
                "applied_vlan_mode"
            )

            # Only check if NetBox has a mode configured
            if nb_mode:
                # Get VLAN configuration from NetBox to determine if we need to check
                nb_untagged_vlan = nb_intf.get("untagged_vlan")
                nb_tagged_vlans = nb_intf.get("tagged_vlans")

                # Only compare mode if NetBox has actual VLAN assignments
                has_vlan_config = (nb_untagged_vlan is not None) or (
                    nb_tagged_vlans and len(nb_tagged_vlans) > 0
                )

                if has_vlan_config and device_mode:
                    # Mode mismatch check
                    if nb_mode == "access" and device_mode != "access":
                        needs_change = True
                        change_reasons.append(
                            f"VLAN mode mismatch (NB: {nb_mode}, device: {device_mode})"
                        )
                    elif nb_mode in ["tagged", "tagged-all"] and device_mode not in [
                        "native-tagged",
                        "native-untagged",
                        "trunk",  # Some AOS-CX versions use "trunk"
                    ]:
                        needs_change = True
                        change_reasons.append(
                            f"VLAN mode mismatch (NB: {nb_mode}, device: {device_mode})"
                        )
                elif has_vlan_config and not device_mode:
                    # NetBox has VLAN config but device doesn't
                    needs_change = True
                    change_reasons.append(
                        "VLANs configured in NetBox but not on device"
                    )

                # Only check VLAN membership if we have VLAN configuration
                if has_vlan_config:
                    # VLAN membership check
                    nb_untagged = None
                    untagged_vlan = nb_intf.get("untagged_vlan")
                    if untagged_vlan and isinstance(untagged_vlan, dict):
                        nb_untagged = untagged_vlan.get("vid")

                    nb_tagged = set()
                    tagged_vlans = nb_intf.get("tagged_vlans")
                    if tagged_vlans and isinstance(tagged_vlans, list):
                        for v in tagged_vlans:
                            if v and isinstance(v, dict):
                                vid = v.get("vid")
                                if vid is not None:
                                    nb_tagged.add(vid)

                    # Get device VLANs
                    device_native = None
                    vlan_tag = device_intf.get("vlan_tag") or device_intf.get(
                        "applied_vlan_tag"
                    )
                    if vlan_tag and isinstance(vlan_tag, dict):
                        for vlan_id_str in vlan_tag.keys():
                            try:
                                device_native = int(vlan_id_str)
                                break
                            except (ValueError, TypeError):
                                pass

                    device_trunks = set()
                    vlan_trunks = device_intf.get("vlan_trunks") or device_intf.get(
                        "applied_vlan_trunks"
                    )
                    if vlan_trunks and isinstance(vlan_trunks, dict):
                        for vlan_id_str in vlan_trunks.keys():
                            try:
                                device_trunks.add(int(vlan_id_str))
                            except (ValueError, TypeError):
                                pass

                    # Check for VLAN mismatches
                    if nb_mode == "access":
                        if nb_untagged and nb_untagged != device_native:
                            needs_change = True
                            change_reasons.append(
                                f"access VLAN mismatch (NB: {nb_untagged}, "
                                f"device: {device_native})"
                            )
                    elif nb_mode == "tagged":
                        nb_all_vlans = set(nb_tagged)
                        if nb_untagged:
                            nb_all_vlans.add(nb_untagged)

                        if nb_untagged and nb_untagged != device_native:
                            needs_change = True
                            change_reasons.append(
                                f"native VLAN mismatch (NB: {nb_untagged}, "
                                f"device: {device_native})"
                            )

                        vlans_to_add = nb_all_vlans - device_trunks
                        vlans_to_remove = device_trunks - nb_all_vlans

                        if vlans_to_add or vlans_to_remove:
                            needs_change = True
                            if vlans_to_add:
                                change_reasons.append(f"VLANs to add: {vlans_to_add}")
                            if vlans_to_remove:
                                change_reasons.append(
                                    f"VLANs to remove: {vlans_to_remove}"
                                )

        if needs_change:
            _debug(f"Interface {intf_name} needs changes: {', '.join(change_reasons)}")
            _categorize_interface_for_changes(nb_intf, result, needs_change=True)
        else:
            _debug(f"Interface {intf_name} does not need changes")
            result["no_changes"].append(nb_intf)

    # Summary
    _debug("Interface change analysis summary:")
    _debug(f"  Physical interfaces needing changes: {len(result['physical'])}")
    _debug(f"  LAG interfaces needing changes: {len(result['lag'])}")
    _debug(f"  MCLAG interfaces needing changes: {len(result['mclag'])}")
    _debug(f"  L2 interfaces needing changes: {len(result['l2'])}")
    _debug(f"  L3 interfaces needing changes: {len(result['l3'])}")
    _debug(f"  LAG member changes: {len(result['lag_members'])}")
    _debug(f"  Interfaces not needing changes: {len(result['no_changes'])}")

    return result


def _categorize_interface_for_changes(intf, result_dict, needs_change=True):
    """
    Helper function to categorize an interface into the appropriate change category

    Args:
        intf: Interface object from NetBox
        result_dict: Dictionary to append the interface to
        needs_change: Whether the interface needs changes
    """
    if not needs_change:
        result_dict["no_changes"].append(intf)
        return

    type_obj = intf.get("type")
    if not type_obj or not isinstance(type_obj, dict):
        return

    type_value = type_obj.get("value")

    # Check if it's a LAG interface
    if type_value == "lag":
        is_mclag = intf.get("custom_fields", {}).get("if_mclag", False)
        if is_mclag:
            result_dict["mclag"].append(intf)
        else:
            result_dict["lag"].append(intf)
        return

    # Check if it's a virtual interface
    if type_value == "virtual":
        # Check if it has L3 configuration
        result_dict["l3"].append(intf)
        return

    # Check if it has L2 configuration (mode defined)
    mode_obj = intf.get("mode")
    if mode_obj and isinstance(mode_obj, dict):
        result_dict["l2"].append(intf)
    else:
        # Physical interface without L2 mode - just basic config
        result_dict["physical"].append(intf)
