#!/usr/bin/env python3
"""
Interface change detection filters

IMPORTANT NOTE ON IPv6 ADDRESS COMPARISON:
==========================================
AOS-CX device facts (gathered via arubanetworks.aoscx.aoscx_facts) return IPv6
addresses as REST API URL references rather than actual address values.

Example from device facts:
    "ip6_addresses": "/rest/v10.09/system/interfaces/vlan11/ip6_addresses"

This makes it impossible to compare NetBox's intended IPv6 addresses with the
device's actual configured addresses within filter plugin context, as filters
cannot make API calls to retrieve the actual IPv6 data.

PERFORMANCE RATIONALE:
- IPv4 addresses: Full comparison implemented - saves significant time by skipping
  unnecessary configuration tasks
- IPv6 addresses: No comparison performed - the overhead of fetching IPv6 data
  (requiring separate CLI connection/command execution) exceeds the time saved
- CLI commands are idempotent: Applying duplicate IPv6 configuration has no effect

Testing confirmed that pre-checking IPv6 addresses via CLI commands is not
time-efficient compared to directly applying idempotent configuration.

WORKAROUND IMPLEMENTATION:
- IPv4: Only addresses needing addition are stored in `_ip_changes.ipv4_to_add`
- IPv6: All addresses stored in `_ip_changes.ipv6_addresses` for reference
- Tasks: IPv4 filtered by `_needs_add`

Provides functions to compare NetBox interface configuration with device facts
and identify which interfaces need configuration changes.
"""

from .utils import _debug, extract_ip_addresses, populate_ip_changes


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

    # Build reverse mapping: physical_interface_name -> lag_name
    # This is needed because AOS-CX stores LAG membership on the LAG interface, not on members
    intf_to_lag_map = {}
    for intf_key, intf_data in facts_by_interface.items():
        if not isinstance(intf_data, dict):
            continue
        # Check if this is a LAG interface
        if intf_data.get("type") == "lag":
            # Get member interfaces from the "interfaces" dict
            lag_members = intf_data.get("interfaces", {})
            if isinstance(lag_members, dict):
                lag_name = intf_data.get("name") or intf_key
                for member_name in lag_members.keys():
                    intf_to_lag_map[member_name] = lag_name
                _debug(f"LAG {lag_name} has members: {list(lag_members.keys())}")

    _debug(f"Built LAG membership map with {len(intf_to_lag_map)} member interfaces")

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
        # AOS-CX keeps the original format "1/1/1" as the key in facts
        device_intf_key = intf_name
        device_intf = facts_by_interface.get(device_intf_key)

        if not device_intf:
            # Check if this is a VLAN interface (SVI)
            type_obj = nb_intf.get("type")
            is_vlan_interface = intf_name.startswith("vlan") and (
                type_obj.get("value") == "virtual"
                if isinstance(type_obj, dict)
                else False
            )

            if is_vlan_interface:
                # VLAN interface doesn't exist on device - needs to be created
                # VLAN/SVI interfaces with IP addresses are L3 interfaces that need creation
                _debug(
                    f"VLAN interface {intf_name} not found on device - needs creation"
                )

                # Populate _ip_changes with all IP addresses that need to be added
                # since the interface doesn't exist yet
                if nb_intf.get("ip_addresses"):
                    nb_ipv4, nb_ipv6 = extract_ip_addresses(nb_intf)
                    populate_ip_changes(nb_intf, nb_ipv4, nb_ipv6)

                _categorize_interface_for_changes(nb_intf, result, needs_change=True)
                continue

            # Interface doesn't exist on device yet - needs to be created
            _debug(
                f"Interface {intf_name} (key: {device_intf_key}) "
                "not found in device facts - needs creation"
            )
            available_keys = list(facts_by_interface.keys())[:5]
            _debug(f"Available interface keys: {available_keys}")

            # Populate _ip_changes with all IP addresses for new interfaces
            if nb_intf.get("ip_addresses"):
                nb_ipv4, nb_ipv6 = extract_ip_addresses(nb_intf)
                populate_ip_changes(nb_intf, nb_ipv4, nb_ipv6)

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

            # Try multiple fields to determine actual admin state
            # admin_state can be unreliable for LAG members - it may show "up"
            # even when the interface is administratively down (no explicit shutdown in config)
            # The forwarding_state.enablement field is more reliable
            device_admin_state = device_intf.get("admin") or device_intf.get(
                "admin_state"
            )

            # Check user_config.admin first (most reliable for configured state)
            user_config = device_intf.get("user_config", {})
            if isinstance(user_config, dict) and "admin" in user_config:
                device_admin_state = user_config.get("admin")
                device_enabled = device_admin_state == "up"
                _debug(f"Using user_config.admin for {intf_name}: {device_admin_state}")
            # Check forwarding_state.enablement for more accurate admin state
            # This is especially important for LAG member interfaces
            elif "forwarding_state" in device_intf:
                forwarding_state = device_intf.get("forwarding_state", {})
                if isinstance(forwarding_state, dict):
                    enablement = forwarding_state.get("enablement")
                    if enablement is not None:
                        # Use enablement field as the source of truth
                        device_enabled = enablement
                        device_admin_state = "up" if enablement else "down"
                    else:
                        # Fall back to admin_state
                        device_enabled = (
                            device_admin_state == "up" if device_admin_state else None
                        )
                else:
                    device_enabled = (
                        device_admin_state == "up" if device_admin_state else None
                    )
            else:
                device_enabled = (
                    device_admin_state == "up" if device_admin_state else None
                )

            # Only compare if we have device state information
            if device_enabled is not None and nb_enabled != device_enabled:
                needs_change = True
                change_reasons.append(
                    f"enabled mismatch (NB: {nb_enabled}, device: {device_enabled})"
                )

            # Debug output showing which field was used
            _debug(
                f"Interface {intf_name}: NB enabled={nb_enabled}, "
                f"device admin_state={device_admin_state}, "
                f"device_enabled={device_enabled}, "
                f"user_config.admin="
                f"{user_config.get('admin') if isinstance(user_config, dict) else 'N/A'}, "
                f"needs_change={needs_change}"
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
        # AOS-CX stores LAG membership in the LAG interface's "interfaces" dict,
        # not on the physical interface itself. Use the reverse mapping we built earlier.
        nb_lag = nb_intf.get("lag")
        if nb_lag and isinstance(nb_lag, dict):
            nb_lag_name = nb_lag.get("name", "")
            # Look up current LAG membership from our reverse mapping
            device_lag_name = intf_to_lag_map.get(intf_name, "")

            if nb_lag_name and nb_lag_name != device_lag_name:
                needs_change = True
                change_reasons.append(
                    f"LAG membership mismatch (NB: {nb_lag_name}, "
                    f"device: {device_lag_name})"
                )
            elif not nb_lag_name and device_lag_name:
                # Interface should not be in LAG but is
                needs_change = True
                change_reasons.append(
                    f"Interface should not be in LAG (device has: {device_lag_name})"
                )

        # Check L2 configuration (VLANs)
        # Skip L2 VLAN checks for VLAN interfaces (SVIs) - these are L3 interfaces
        # that provide routing for a VLAN, and don't have vlan_mode/vlan_tag properties.
        # NetBox uses the mode/VLAN fields just to identify which VLAN the SVI represents.
        is_vlan_interface = intf_name.startswith("vlan") and (
            nb_intf.get("type", {}).get("value") == "virtual"
            if isinstance(nb_intf.get("type"), dict)
            else False
        )

        mode_obj = nb_intf.get("mode")
        if mode_obj and isinstance(mode_obj, dict) and not is_vlan_interface:
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
                    # Determine effective mode from NetBox configuration
                    # If mode is "tagged" (not "tagged-all") with no tagged VLANs
                    # and only untagged VLAN, it's effectively an access port.
                    # Note: "tagged-all" with just untagged_vlan is a valid trunk
                    # configuration (native-untagged mode allowing all VLANs).
                    nb_has_tagged_vlans = nb_tagged_vlans and len(nb_tagged_vlans) > 0
                    effective_nb_mode = nb_mode
                    if (
                        nb_mode == "tagged"  # Only "tagged", not "tagged-all"
                        and not nb_has_tagged_vlans
                        and nb_untagged_vlan
                    ):
                        effective_nb_mode = "access"

                    # Mode mismatch check
                    if effective_nb_mode == "access" and device_mode != "access":
                        needs_change = True
                        change_reasons.append(
                            f"VLAN mode mismatch (NB: {effective_nb_mode}, device: {device_mode})"
                        )
                    elif effective_nb_mode in [
                        "tagged",
                        "tagged-all",
                    ] and device_mode not in [
                        "native-tagged",
                        "native-untagged",
                        "trunk",  # Some AOS-CX versions use "trunk"
                    ]:
                        needs_change = True
                        change_reasons.append(
                            f"VLAN mode mismatch (NB: {effective_nb_mode}, device: {device_mode})"
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

        # Check L3 configuration (IP addresses)
        # Compare IP addresses defined in NetBox with those on the device
        if nb_intf.get("ip_addresses"):
            # Extract IP addresses from NetBox (format: "192.168.1.1/24" or "2001:db8::1/64")
            # Exclude anycast IPs from comparison - they're configured via active-gateway
            # command and not reported in device facts ip4_address field
            nb_ipv4_list, nb_ipv6_list = extract_ip_addresses(
                nb_intf, exclude_anycast=True
            )
            nb_ipv4 = set(nb_ipv4_list)
            nb_ipv6 = set(nb_ipv6_list)

            # Extract IP addresses from device facts
            device_ipv4 = set()

            # IPv4 addresses
            device_ip4 = device_intf.get("ip4_address")
            if device_ip4:
                device_ipv4.add(device_ip4)

            device_ip4_secondary = device_intf.get("ip4_address_secondary", [])
            if device_ip4_secondary:
                for ip in device_ip4_secondary:
                    if ip:
                        device_ipv4.add(ip)

            # Compare the IP addresses
            ipv4_to_add = nb_ipv4 - device_ipv4
            ipv4_to_remove = device_ipv4 - nb_ipv4

            # For IPv6: The aoscx_facts module returns URLs for ip6_addresses
            # ("/rest/v10.09/system/interfaces/<name>/ip6_addresses")
            # rather than actual address data, making it impossible to compare
            # IPv6 addresses from device facts.
            # As a workaround, we mark ALL IPv6 addresses as potentially
            # needing configuration.
            # The aoscx_config module with 'match: line' provides some
            # idempotency - it won't apply changes if the line exists.
            # Note: IPv6 configuration tasks may always show 'changed' status
            # even when addresses are correct.
            ipv6_needs_config = len(nb_ipv6) > 0

            if ipv4_to_add or ipv4_to_remove or ipv6_needs_config:
                needs_change = True
                if ipv4_to_add:
                    change_reasons.append(f"IPv4 addresses to add: {ipv4_to_add}")
                if ipv4_to_remove:
                    change_reasons.append(f"IPv4 addresses to remove: {ipv4_to_remove}")
                if ipv6_needs_config:
                    change_reasons.append(
                        f"IPv6 addresses need configuration: {nb_ipv6}"
                    )

                # Store IP change details in the interface object for
                # task-level filtering.
                # Only store IPv4 changes - IPv6 cannot be reliably
                # compared from device facts.
                if ipv4_to_add:
                    if "_ip_changes" not in nb_intf:
                        nb_intf["_ip_changes"] = {}
                    nb_intf["_ip_changes"]["ipv4_to_add"] = list(ipv4_to_add)

                # Store all IPv6 addresses for reference, but don't mark
                # them as needing addition since we cannot verify if they
                # already exist on the device.
                if nb_ipv6:
                    if "_ip_changes" not in nb_intf:
                        nb_intf["_ip_changes"] = {}
                    nb_intf["_ip_changes"]["ipv6_addresses"] = list(nb_ipv6)

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

    Interfaces can appear in MULTIPLE categories because:
    - Interface type (physical/lag/mclag) is independent of routing mode (L2/L3)
    - A LAG can be L2 or L3
    - An MCLAG can be L2 or L3
    - A physical interface can be L2 or L3
    - A LAG member is BOTH lag_members (for LAG assignment) AND physical (for MTU, admin state)

    Categories:
    - lag_members: Physical interfaces that are members of a LAG (for LAG assignment)
    - physical: Physical interfaces including LAG members (for MTU, speed, admin state)
    - lag: LAG interfaces (for LAG creation and basic config)
    - mclag: MCLAG interfaces (for MCLAG-specific config)
    - l2: Interfaces with L2/VLAN configuration (excludes LAG members)
    - l3: Interfaces with L3/IP configuration (excludes LAG members)

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

    # Check if it's a LAG member (physical interface with LAG assignment)
    # LAG members get BOTH lag_members (for LAG assignment) AND physical (for basic config)
    # because they need physical properties configured (MTU, admin state, description, etc.)
    is_lag_member = False
    lag_obj = intf.get("lag")
    if lag_obj and isinstance(lag_obj, dict) and lag_obj.get("name"):
        # This is a LAG member interface
        result_dict["lag_members"].append(intf)
        is_lag_member = True
        # Don't return - continue to add to physical category too

    # Categorize by interface type (LAG, MCLAG, physical)
    if type_value == "lag":
        is_mclag = intf.get("custom_fields", {}).get("if_mclag", False)
        if is_mclag:
            result_dict["mclag"].append(intf)
        else:
            result_dict["lag"].append(intf)
        # Don't return - continue to categorize by L2/L3

    # Categorize by interface type (virtual = L3 only)
    elif type_value == "virtual":
        # Virtual interfaces are always L3
        result_dict["l3"].append(intf)
        return

    # Categorize by interface type (physical interfaces, including LAG members)
    elif type_value not in ["lag", "virtual"]:
        # This is a physical interface (may or may not be a LAG member)
        result_dict["physical"].append(intf)
        # Don't return - continue to categorize by L2/L3

    # Now categorize by L2/L3 configuration
    # LAG members should NOT have L2/L3 config (the LAG itself has that)
    if not is_lag_member:
        # Check if it has L2 configuration (mode defined)
        mode_obj = intf.get("mode")
        if mode_obj and isinstance(mode_obj, dict):
            result_dict["l2"].append(intf)
        # Check if it has L3 configuration (IP addresses)
        elif intf.get("ip_addresses"):
            result_dict["l3"].append(intf)
