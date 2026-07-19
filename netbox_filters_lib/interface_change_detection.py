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

ENHANCED FACTS SOLUTION (Optional):
===================================
When `aoscx_gather_facts_rest_api: true` is set, the role gathers interface data
via REST API with depth=2, which provides actual IPv6 addresses and VSX virtual IPs.
This enhanced data is passed to the filter and enables:
- IPv6 address comparison (skip already-configured IPv6 addresses)
- VSX virtual IP comparison (proper anycast/active-gateway detection)

PERFORMANCE RATIONALE:
- IPv4 addresses: Full comparison implemented - saves significant time by skipping
  unnecessary configuration tasks
- IPv6 addresses (without enhanced facts): No comparison performed - the overhead
  of fetching IPv6 data exceeds the time saved
- IPv6 addresses (with enhanced facts): Full comparison enabled
- CLI commands are idempotent: Applying duplicate configuration has no effect

WORKAROUND IMPLEMENTATION:
- IPv4: Only addresses needing addition are stored in `_ip_changes.ipv4_to_add`
- IPv6: All addresses stored in `_ip_changes.ipv6_addresses` for reference
  (or only addresses needing addition when enhanced facts are available)
- Tasks: IPv4 filtered by `_needs_add`, IPv6 filtered when enhanced facts available

Provides functions to compare NetBox interface configuration with device facts
and identify which interfaces need configuration changes.
"""

import ipaddress
from urllib.parse import unquote

from .utils import _debug, extract_ip_addresses, populate_ip_changes


def _normalize_ipv6(addr):
    """Normalize IPv6 address to canonical form for comparison.

    Returns tuple of (normalized_addr_without_prefix, original_addr)
    """
    try:
        if "/" in addr:
            network = ipaddress.IPv6Interface(addr)
            return (str(network.ip), addr)
        ip = ipaddress.IPv6Address(addr)
        return (str(ip), addr)
    except (ValueError, ipaddress.AddressValueError):
        # If parsing fails, use original (stripped of prefix)
        base = addr.split("/")[0] if "/" in addr else addr
        return (base, addr)


def _get_device_vrf_name(device_intf, enhanced_intf=None):
    """Extract VRF name from device interface facts.

    The REST API (enhanced_intf) always includes a ``vrf`` key:
    - ``None``  → interface is in the default VRF (AOS-CX returns null for
      default-VRF interfaces, not the string "default" or a dict)
    - ``{"name": url}`` → interface is attached to a named custom VRF

    Standard aoscx_facts (device_intf) may *omit* the vrf key entirely when the
    interface is in the default VRF, so ``None`` there is ambiguous (could mean
    "default VRF" or "no VRF data at all"). To avoid false positives we return
    ``None`` for that case and let the caller skip the comparison.

    Args:
        device_intf: Interface dict from standard device facts.
        enhanced_intf: Optional interface dict from enhanced REST API facts
                       (preferred source when available).

    Returns:
        VRF name string, or ``None`` when only standard facts are available and
        they carry no VRF data (caller should skip comparison).
    """
    # Enhanced REST API facts: the 'vrf' key is always present in the
    # normalised output from rest_api_transforms.rest_api_to_aoscx_interfaces().
    # null  → default VRF (no VRF attachment on the device)
    # dict  → custom VRF, keyed by VRF name
    if isinstance(enhanced_intf, dict) and "vrf" in enhanced_intf:
        vrf = enhanced_intf["vrf"]
        if vrf is None:
            return "default"
        if isinstance(vrf, dict):
            keys = list(vrf.keys())
            return keys[0] if keys else "default"
        if isinstance(vrf, str):
            return vrf or "default"

    # Standard aoscx_facts fallback: vrf=None is ambiguous (no data vs. default).
    # Only trust a non-None value to avoid false positives.
    if isinstance(device_intf, dict):
        vrf = device_intf.get("vrf")
        if isinstance(vrf, dict):
            keys = list(vrf.keys())
            return keys[0] if keys else "default"
        if isinstance(vrf, str):
            return vrf or "default"

    # No usable VRF data found — caller should skip comparison.
    return None


def get_interfaces_needing_config_changes(
    interfaces,
    device_facts,
    enhanced_facts=None,
    dhcp_relay_facts=None,
    ip_helper_addresses=None,
):
    """
    Compare NetBox interfaces with device facts to identify which interfaces need changes.
    This is the idempotent check to avoid unnecessary API calls.

    Args:
        interfaces: List of interface objects from NetBox
        device_facts: Device facts containing current interface state
        enhanced_facts: Optional dict of enhanced interface facts from REST API with depth=2
                       Provides actual IPv6 addresses and VSX virtual IPs for better comparison
        dhcp_relay_facts: Optional dict keyed by interface name with a sorted list of
                          currently configured IPv4 DHCP relay (ip helper-address) servers.
                          Produced by rest_api_to_aoscx_dhcp_relays from
                          /system/dhcp_relays?depth=2. When provided, the function compares
                          the desired helper addresses (from ip_helper_addresses) with the
                          device state and only marks the interface for reconfiguration when
                          they differ.  When None, any interface with if_ip_helper=True is
                          always included.
        ip_helper_addresses: Optional dict keyed by VRF name, value is a dict of
                             {str_index: ip_address} entries — matches the inventory variable
                             ``ip_helper_addresses``.  Used together with dhcp_relay_facts to
                             compute the desired helper server set for an interface.

    Returns:
        Dict with categorized interfaces:
        - physical: Physical interfaces needing changes (enabled/disabled, description, MTU)
        - lag: LAG interfaces needing changes
        - mclag: MCLAG interfaces needing changes
        - l2: L2 interfaces needing VLAN changes
        - l3: L3 interfaces needing IP address changes (also includes VLAN SVI /
          loopback / sub-interface entries that only need a description update)
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
        else:
            # Virtual interfaces (VLAN SVIs, loopbacks, sub-interfaces) skip the
            # admin/MTU checks above (those properties don't apply), but description
            # is still pushed for them via build_l3_config_lines() in the L3 config
            # path, so compare it here and flag it the same way as other L3 changes
            # (vrf_change, dhcp_relay_change) that group_interface_ips() looks for.
            nb_description = nb_intf.get("description", "")
            device_description = device_intf.get("description", "")
            if nb_description and nb_description != device_description:
                needs_change = True
                change_reasons.append(
                    f"description mismatch (NB: {nb_description}, "
                    f"device: {device_description})"
                )
                if "_ip_changes" not in nb_intf:
                    nb_intf["_ip_changes"] = {}
                nb_intf["_ip_changes"]["description_change"] = True

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
                # Note: "tagged-all" mode implicitly has VLAN config (all VLANs)
                # even without explicit VLAN assignments
                has_vlan_config = (
                    (nb_untagged_vlan is not None)
                    or (nb_tagged_vlans and len(nb_tagged_vlans) > 0)
                    or nb_mode == "tagged-all"
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

                        # Debug L2 VLAN comparison
                        _debug(
                            f"L2 VLAN comparison for {intf_name}: "
                            f"mode={nb_mode}, nb_untagged={nb_untagged}, "
                            f"nb_tagged={nb_tagged}, nb_all_vlans={nb_all_vlans}, "
                            f"device_mode={device_mode}, device_native={device_native}, "
                            f"device_trunks={device_trunks}"
                        )

                        # Check native VLAN and mode
                        # AOS-CX trunk modes:
                        # - native-untagged: native VLAN traffic is untagged (default)
                        # - native-tagged: native VLAN traffic is tagged
                        #
                        # NetBox mapping:
                        # - untagged_vlan set: device should be native-untagged
                        # - no untagged_vlan (all tagged): device should be native-tagged
                        native_vlan_matches = False

                        if nb_untagged:
                            # NetBox wants native-untagged mode
                            if device_native and nb_untagged == device_native:
                                native_vlan_matches = True
                            elif (
                                device_mode == "native-untagged"
                                and nb_untagged in device_trunks
                            ):
                                # In native-untagged mode, native VLAN is in vlan_trunks
                                native_vlan_matches = True
                                _debug(
                                    f"Native VLAN {nb_untagged} found in vlan_trunks "
                                    f"(native-untagged mode)"
                                )
                        else:
                            # NetBox wants native-tagged mode (no untagged VLAN)
                            # Check if device is already in native-tagged mode
                            if device_mode == "native-tagged":
                                native_vlan_matches = True
                                _debug("Device already in native-tagged mode")
                            elif device_mode == "native-untagged":
                                # Device is in native-untagged but NetBox wants native-tagged
                                native_vlan_matches = False
                                _debug(
                                    "Mode mismatch: NetBox wants native-tagged "
                                    "(no untagged_vlan), device has native-untagged"
                                )

                        if nb_untagged and not native_vlan_matches:
                            needs_change = True
                            change_reasons.append(
                                f"native VLAN mismatch (NB: {nb_untagged}, "
                                f"device mode: {device_mode}, device_native: {device_native})"
                            )
                        elif not nb_untagged and not native_vlan_matches:
                            # NetBox wants native-tagged but device is native-untagged
                            needs_change = True
                            change_reasons.append(
                                f"trunk mode mismatch (NB wants native-tagged, "
                                f"device has: {device_mode})"
                            )

                        # For trunk mode comparison, use all VLANs from device
                        # In native-untagged mode, all VLANs (including native) are in vlan_trunks
                        device_all_vlans = set(device_trunks)
                        if device_native:
                            device_all_vlans.add(device_native)

                        vlans_to_add = nb_all_vlans - device_all_vlans
                        vlans_to_remove = device_all_vlans - nb_all_vlans

                        _debug(
                            f"L2 VLAN diff for {intf_name}: "
                            f"device_all_vlans={device_all_vlans}, "
                            f"vlans_to_add={vlans_to_add}, vlans_to_remove={vlans_to_remove}"
                        )

                        if vlans_to_add or vlans_to_remove:
                            needs_change = True
                            if vlans_to_add:
                                change_reasons.append(f"VLANs to add: {vlans_to_add}")
                            if vlans_to_remove:
                                change_reasons.append(
                                    f"VLANs to remove: {vlans_to_remove}"
                                )
                    elif nb_mode == "tagged-all":
                        # For tagged-all, we only care about native VLAN
                        # All VLANs are implicitly allowed, so no membership check needed
                        _debug(
                            f"L2 tagged-all comparison for {intf_name}: "
                            f"nb_untagged={nb_untagged}, device_native={device_native}"
                        )
                        if nb_untagged:
                            # Has native VLAN defined - check if it matches
                            if nb_untagged != device_native:
                                needs_change = True
                                change_reasons.append(
                                    f"native VLAN mismatch for tagged-all "
                                    f"(NB: {nb_untagged}, device: {device_native})"
                                )
                        else:
                            # No native VLAN - should be native-tagged mode
                            if device_mode != "native-tagged":
                                needs_change = True
                                change_reasons.append(
                                    f"trunk mode mismatch for tagged-all "
                                    f"(NB wants native-tagged, device has: {device_mode})"
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
            device_ipv6 = set()
            device_vsx_virtual_ip4 = set()
            device_vsx_virtual_ip6 = set()

            # IPv4 addresses from standard facts
            device_ip4 = device_intf.get("ip4_address")
            if device_ip4:
                device_ipv4.add(device_ip4)

            device_ip4_secondary = device_intf.get("ip4_address_secondary", [])
            if device_ip4_secondary:
                for ip in device_ip4_secondary:
                    if ip:
                        device_ipv4.add(ip)

            # Check for enhanced facts (REST API with depth=2)
            # These provide actual IPv6 addresses and VSX virtual IPs
            enhanced_intf = None
            if enhanced_facts and isinstance(enhanced_facts, dict):
                enhanced_intf = enhanced_facts.get(intf_name)
                if enhanced_intf and isinstance(enhanced_intf, dict):
                    _debug(f"Using enhanced facts for {intf_name}")

                    # Extract IPv6 addresses from enhanced facts
                    # The REST API returns ip6_addresses as a dict where keys are
                    # URL-encoded addresses (e.g., "2001%3Adb8%3A%3A1%2F64")
                    enhanced_ip6 = enhanced_intf.get("ip6_addresses")
                    if enhanced_ip6 and isinstance(enhanced_ip6, dict):
                        for ip6_key, ip6_data in enhanced_ip6.items():
                            # URL-decode the key first
                            decoded_key = unquote(ip6_key)
                            # The key is the address, or extract from data
                            if isinstance(ip6_data, dict):
                                addr = ip6_data.get("address", decoded_key)
                            else:
                                addr = decoded_key
                            if addr and ":" in addr:
                                device_ipv6.add(addr)
                        _debug(f"Enhanced IPv6 for {intf_name}: {device_ipv6}")

                    # Extract VSX virtual IPs (anycast/active-gateway)
                    vsx_ip4 = enhanced_intf.get("vsx_virtual_ip4")
                    if vsx_ip4:
                        if isinstance(vsx_ip4, list):
                            device_vsx_virtual_ip4.update(vsx_ip4)
                        else:
                            device_vsx_virtual_ip4.add(vsx_ip4)

                    vsx_ip6 = enhanced_intf.get("vsx_virtual_ip6")
                    if vsx_ip6:
                        if isinstance(vsx_ip6, list):
                            device_vsx_virtual_ip6.update(vsx_ip6)
                        else:
                            device_vsx_virtual_ip6.add(vsx_ip6)

                    if device_vsx_virtual_ip4 or device_vsx_virtual_ip6:
                        _debug(
                            f"Enhanced VSX virtual IPs for {intf_name}: "
                            f"IPv4={device_vsx_virtual_ip4}, IPv6={device_vsx_virtual_ip6}"
                        )

            # VRF change detection
            # Changing VRF on an AOS-CX interface removes all L3 configuration.
            # When a VRF mismatch is detected we must reconfigure ALL L3 parameters
            # (not just the diff) so nothing is left unconfigured after the VRF change.
            # Comparison is skipped when neither source provides VRF data, which avoids
            # false positives when using standard aoscx_facts (no explicit VRF field).
            vrf_change = False
            nb_vrf_obj = nb_intf.get("vrf")
            nb_vrf_name = (
                nb_vrf_obj.get("name") if isinstance(nb_vrf_obj, dict) else None
            ) or "default"
            device_vrf_name = _get_device_vrf_name(device_intf, enhanced_intf)
            if device_vrf_name is not None and nb_vrf_name != device_vrf_name:
                vrf_change = True
                needs_change = True
                change_reasons.append(
                    f"VRF mismatch (NB: {nb_vrf_name}, device: {device_vrf_name})"
                )
                if "_ip_changes" not in nb_intf:
                    nb_intf["_ip_changes"] = {}
                nb_intf["_ip_changes"]["vrf_change"] = True
                _debug(
                    f"VRF change detected for {intf_name}: "
                    f"NB={nb_vrf_name}, device={device_vrf_name}"
                )

            # Compare the IP addresses
            ipv4_to_add = nb_ipv4 - device_ipv4
            ipv4_to_remove = device_ipv4 - nb_ipv4

            # IPv6 comparison - depends on whether enhanced facts are available
            ipv6_to_add = set()
            ipv6_to_remove = set()
            ipv6_needs_config = False

            if enhanced_intf:
                # Enhanced facts available - we can do proper IPv6 comparison
                # Even if device_ipv6 is empty, we can compare (all nb_ipv6 need adding)
                #
                # IMPORTANT: Normalize IPv6 addresses for comparison
                # IPv6 can have different representations:
                # - "2001:0db8:0a11::2" vs "2001:db8:a11::2" (leading zeros)
                # - "2001:db8:a11:0:0:0:0:2" vs "2001:db8:a11::2" (compression)
                # Use ipaddress module for canonical normalization

                # Build mapping: normalized_addr -> original_netbox_address
                nb_ipv6_normalized = {}
                for addr in nb_ipv6:
                    norm, orig = _normalize_ipv6(addr)
                    nb_ipv6_normalized[norm] = orig

                device_ipv6_normalized = {}
                for addr in device_ipv6:
                    norm, _ = _normalize_ipv6(addr)
                    device_ipv6_normalized[norm] = addr

                # Find addresses in NetBox but not on device (comparing normalized)
                for norm_addr, orig_addr in nb_ipv6_normalized.items():
                    if norm_addr not in device_ipv6_normalized:
                        ipv6_to_add.add(orig_addr)

                # Find addresses on device but not in NetBox (to remove)
                for norm_addr, orig_addr in device_ipv6_normalized.items():
                    if norm_addr not in nb_ipv6_normalized:
                        ipv6_to_remove.add(orig_addr)

                ipv6_needs_config = len(ipv6_to_add) > 0 or len(ipv6_to_remove) > 0
                _debug(
                    f"IPv6 comparison for {intf_name}: "
                    f"NetBox={nb_ipv6}, device={device_ipv6}, "
                    f"nb_normalized={set(nb_ipv6_normalized.keys())}, "
                    f"device_normalized={set(device_ipv6_normalized.keys())}, "
                    f"to_add={ipv6_to_add}, to_remove={ipv6_to_remove}"
                )
            else:
                # No enhanced facts - fall back to marking all IPv6 as needing config
                # The aoscx_facts module returns URLs for ip6_addresses
                # ("/rest/v10.09/system/interfaces/<name>/ip6_addresses")
                # rather than actual address data.
                ipv6_needs_config = len(nb_ipv6) > 0
                ipv6_to_add = nb_ipv6  # Mark all as needing config

            # When VRF changes, ALL L3 parameters must be reconfigured because
            # AOS-CX removes all L3 config when the VRF assignment is changed.
            # Override the diff to include every address from NetBox.
            if vrf_change:
                ipv4_to_add = nb_ipv4
                ipv4_to_remove = set()
                if nb_ipv6:
                    ipv6_needs_config = True
                    ipv6_to_add = nb_ipv6
                    ipv6_to_remove = set()
                _debug(
                    f"VRF change for {intf_name}: forcing full L3 reconfiguration "
                    f"(IPv4={nb_ipv4}, IPv6={nb_ipv6})"
                )

            if ipv4_to_add or ipv4_to_remove or ipv6_needs_config:
                needs_change = True
                if ipv4_to_add:
                    change_reasons.append(f"IPv4 addresses to add: {ipv4_to_add}")
                if ipv4_to_remove:
                    change_reasons.append(f"IPv4 addresses to remove: {ipv4_to_remove}")
                if ipv6_needs_config:
                    if enhanced_intf:
                        if ipv6_to_add:
                            change_reasons.append(
                                f"IPv6 addresses to add: {ipv6_to_add}"
                            )
                        if ipv6_to_remove:
                            change_reasons.append(
                                f"IPv6 addresses to remove: {ipv6_to_remove}"
                            )
                    else:
                        change_reasons.append(
                            f"IPv6 addresses need configuration: {nb_ipv6}"
                        )

                # Store IPv4 change details in the interface object for task-level filtering
                if ipv4_to_add:
                    if "_ip_changes" not in nb_intf:
                        nb_intf["_ip_changes"] = {}
                    nb_intf["_ip_changes"]["ipv4_to_add"] = list(ipv4_to_add)

            # Anycast gateway comparison (active-gateway configuration)
            # Extract anycast IPs from NetBox (these were excluded from regular IP comparison)
            nb_anycast_ipv4 = set()
            nb_anycast_ipv6 = set()
            nb_anycast_ipv6_normalized = {}  # Map: normalized -> addr_without_prefix
            nb_anycast_ipv6_full = {}  # Map: normalized -> full addr with prefix

            for ip_obj in nb_intf.get("ip_addresses", []):
                if isinstance(ip_obj, dict):
                    ip_addr = ip_obj.get("address")
                    role_obj = ip_obj.get("role")
                    if ip_addr and role_obj:
                        role_value = (
                            role_obj.get("value")
                            if isinstance(role_obj, dict)
                            else role_obj
                        )
                        if role_value == "anycast":
                            # Remove /prefix for comparison
                            # (active-gateway uses address without prefix)
                            addr_without_prefix = (
                                ip_addr.split("/")[0] if "/" in ip_addr else ip_addr
                            )
                            if ":" in addr_without_prefix:
                                # IPv6 - normalize for comparison
                                normalized, _ = _normalize_ipv6(addr_without_prefix)
                                nb_anycast_ipv6.add(addr_without_prefix)
                                nb_anycast_ipv6_normalized[
                                    normalized
                                ] = addr_without_prefix
                                nb_anycast_ipv6_full[normalized] = ip_addr
                            else:
                                nb_anycast_ipv4.add(addr_without_prefix)

            # Compare anycast IPs with device VSX virtual IPs (when enhanced facts available)
            anycast_ipv4_to_add = set()
            anycast_ipv6_to_add = set()

            if enhanced_intf and (nb_anycast_ipv4 or nb_anycast_ipv6):
                # Enhanced facts available - compare with device VSX virtual IPs
                anycast_ipv4_to_add = nb_anycast_ipv4 - device_vsx_virtual_ip4

                # IPv6 anycast - normalize both sides for comparison
                device_vsx_virtual_ip6_normalized = set()
                for addr in device_vsx_virtual_ip6:
                    normalized, _ = _normalize_ipv6(addr)
                    device_vsx_virtual_ip6_normalized.add(normalized)

                # Find which normalized NetBox anycast IPv6 are not on device
                for normalized, original in nb_anycast_ipv6_normalized.items():
                    if normalized not in device_vsx_virtual_ip6_normalized:
                        anycast_ipv6_to_add.add(original)

                if anycast_ipv4_to_add or anycast_ipv6_to_add:
                    needs_change = True
                    if anycast_ipv4_to_add:
                        change_reasons.append(
                            f"Anycast gateway IPv4 to add: {anycast_ipv4_to_add}"
                        )
                    if anycast_ipv6_to_add:
                        change_reasons.append(
                            f"Anycast gateway IPv6 to add: {anycast_ipv6_to_add}"
                        )

                _debug(
                    f"Anycast comparison for {intf_name}: "
                    f"NetBox anycast IPv4={nb_anycast_ipv4}, "
                    f"device VSX virtual IPv4={device_vsx_virtual_ip4}, "
                    f"to_add={anycast_ipv4_to_add}; "
                    f"NetBox anycast IPv6={nb_anycast_ipv6}, "
                    f"device VSX virtual IPv6={device_vsx_virtual_ip6}, "
                    f"to_add={anycast_ipv6_to_add}"
                )
            elif nb_anycast_ipv4 or nb_anycast_ipv6:
                # No enhanced facts but anycast IPs configured - mark for configuration
                # We can't compare without enhanced facts, so configure all anycast IPs
                anycast_ipv4_to_add = nb_anycast_ipv4
                anycast_ipv6_to_add = nb_anycast_ipv6
                needs_change = True
                change_reasons.append(
                    "Anycast gateway configuration needed "
                    "(no enhanced facts for comparison)"
                )
                _debug(
                    f"No enhanced facts for {intf_name}, "
                    f"marking all anycast IPs for config: "
                    f"IPv4={nb_anycast_ipv4}, IPv6={nb_anycast_ipv6}"
                )

            # Check for stale anycast gateways to remove
            # (configured on device but no longer present in NetBox)
            # Conservative: only remove if the address is completely absent from
            # NetBox ip_addresses (any role), not merely missing the anycast role.
            # This prevents accidental removal when an IP exists in NetBox without
            # the anycast role (e.g., role not yet set in NetBox).
            anycast_ipv4_to_remove = set()
            anycast_ipv6_to_remove = set()

            if enhanced_intf and (device_vsx_virtual_ip4 or device_vsx_virtual_ip6):
                # Build set of ALL NetBox addresses regardless of role
                all_nb_ipv4_addrs = set()
                all_nb_ipv6_norm = set()
                for ip_obj in nb_intf.get("ip_addresses", []):
                    if isinstance(ip_obj, dict):
                        ip_addr = ip_obj.get("address", "")
                        addr = ip_addr.split("/")[0] if "/" in ip_addr else ip_addr
                        if ":" in addr:
                            norm, _ = _normalize_ipv6(addr)
                            all_nb_ipv6_norm.add(norm)
                        elif addr:
                            all_nb_ipv4_addrs.add(addr)

                # Remove VSX virtual IPs absent from both anycast AND all NetBox IPs
                anycast_ipv4_to_remove = (
                    device_vsx_virtual_ip4 - nb_anycast_ipv4 - all_nb_ipv4_addrs
                )

                # IPv6 removal — normalize both sides for comparison
                nb_anycast_ipv6_norm_set = set(nb_anycast_ipv6_normalized.keys())
                for addr in device_vsx_virtual_ip6:
                    normalized, _ = _normalize_ipv6(addr)
                    if (
                        normalized not in nb_anycast_ipv6_norm_set
                        and normalized not in all_nb_ipv6_norm
                    ):
                        anycast_ipv6_to_remove.add(addr)

                if anycast_ipv4_to_remove or anycast_ipv6_to_remove:
                    needs_change = True
                    if anycast_ipv4_to_remove:
                        change_reasons.append(
                            f"Anycast gateway IPv4 to remove: {anycast_ipv4_to_remove}"
                        )
                    if anycast_ipv6_to_remove:
                        change_reasons.append(
                            f"Anycast gateway IPv6 to remove: {anycast_ipv6_to_remove}"
                        )

                _debug(
                    f"Anycast removal check for {intf_name}: "
                    f"device IPv4={device_vsx_virtual_ip4}, nb={nb_anycast_ipv4}, "
                    f"to_remove={anycast_ipv4_to_remove}; "
                    f"device IPv6={device_vsx_virtual_ip6}, nb={nb_anycast_ipv6}, "
                    f"to_remove={anycast_ipv6_to_remove}"
                )

            # Store stale anycast gateways to remove
            if anycast_ipv4_to_remove or anycast_ipv6_to_remove:
                if "_ip_changes" not in nb_intf:
                    nb_intf["_ip_changes"] = {}
                if anycast_ipv4_to_remove:
                    nb_intf["_ip_changes"]["anycast_ipv4_to_remove"] = list(
                        anycast_ipv4_to_remove
                    )
                if anycast_ipv6_to_remove:
                    nb_intf["_ip_changes"]["anycast_ipv6_to_remove"] = list(
                        anycast_ipv6_to_remove
                    )

            # Store anycast IPs that need to be added
            # (restored to ip_addresses field with anycast info)
            # This allows configure_l3_interfaces.yml to process them
            if anycast_ipv4_to_add or anycast_ipv6_to_add:
                if "_ip_changes" not in nb_intf:
                    nb_intf["_ip_changes"] = {}

                # Add anycast IPs back to the lists with their full
                # address (including prefix)
                anycast_ips_to_add = []
                for ip_obj in nb_intf.get("ip_addresses", []):
                    if isinstance(ip_obj, dict):
                        ip_addr = ip_obj.get("address")
                        role_obj = ip_obj.get("role")
                        if ip_addr and role_obj:
                            role_value = (
                                role_obj.get("value")
                                if isinstance(role_obj, dict)
                                else role_obj
                            )
                            if role_value == "anycast":
                                addr_without_prefix = (
                                    ip_addr.split("/")[0] if "/" in ip_addr else ip_addr
                                )
                                if (
                                    ":" not in addr_without_prefix
                                    and addr_without_prefix in anycast_ipv4_to_add
                                ) or (
                                    ":" in addr_without_prefix
                                    and addr_without_prefix in anycast_ipv6_to_add
                                ):
                                    anycast_ips_to_add.append(ip_addr)

                # Merge with existing ipv4_to_add/ipv6_to_add
                for anycast_ip in anycast_ips_to_add:
                    if ":" in anycast_ip:
                        # IPv6
                        if "ipv6_to_add" not in nb_intf["_ip_changes"]:
                            nb_intf["_ip_changes"]["ipv6_to_add"] = []
                        if anycast_ip not in nb_intf["_ip_changes"]["ipv6_to_add"]:
                            nb_intf["_ip_changes"]["ipv6_to_add"].append(anycast_ip)
                    else:
                        # IPv4
                        if "ipv4_to_add" not in nb_intf["_ip_changes"]:
                            nb_intf["_ip_changes"]["ipv4_to_add"] = []
                        if anycast_ip not in nb_intf["_ip_changes"]["ipv4_to_add"]:
                            nb_intf["_ip_changes"]["ipv4_to_add"].append(anycast_ip)

            # Detect missing 'ipv6 address link-local' for link-local anycast gateways.
            # HPE Aruba recommends using a link-local address (fe80::) as the active-gateway
            # IPv6. When doing so, 'ipv6 address link-local <addr>/<prefix>' must be
            # explicitly configured before the active-gateway command.
            #
            # Detection: ip6_address_link_local (depth=2) returns the currently active
            # link-local address as a dict {addr/prefix: url}. If its key does not match
            # the expected link-local anycast from NetBox, the explicit command is missing.
            link_local_ipv6_to_add = set()
            if enhanced_intf and nb_anycast_ipv6_normalized:
                device_ip6_ll = enhanced_intf.get("ip6_address_link_local")
                if isinstance(device_ip6_ll, dict):
                    device_ll_normalized = {
                        _normalize_ipv6(addr)[0] for addr in device_ip6_ll.keys()
                    }
                else:
                    device_ll_normalized = set()

                for (
                    normalized,
                    addr_without_prefix,
                ) in nb_anycast_ipv6_normalized.items():
                    if normalized.startswith("fe80:"):
                        if normalized not in device_ll_normalized:
                            full_addr = nb_anycast_ipv6_full.get(
                                normalized, addr_without_prefix
                            )
                            link_local_ipv6_to_add.add(full_addr)

                if link_local_ipv6_to_add:
                    needs_change = True
                    change_reasons.append(
                        f"IPv6 link-local address to configure: {link_local_ipv6_to_add}"
                    )
                    _debug(
                        f"Link-local IPv6 missing for {intf_name}: {link_local_ipv6_to_add}"
                    )

            if link_local_ipv6_to_add:
                if "_ip_changes" not in nb_intf:
                    nb_intf["_ip_changes"] = {}
                nb_intf["_ip_changes"]["link_local_ipv6_to_add"] = list(
                    link_local_ipv6_to_add
                )

            # Store IPv6 addresses to remove even when NetBox has no IPv6
            # (device has addresses but they were all removed from NetBox)
            if enhanced_intf and ipv6_to_remove and not nb_ipv6:
                if "_ip_changes" not in nb_intf:
                    nb_intf["_ip_changes"] = {}
                nb_intf["_ip_changes"]["ipv6_to_remove"] = list(ipv6_to_remove)

            # ALWAYS store IPv6 change info when enhanced facts available
            # This allows task-level filtering even when interface needs changes
            # for other reasons (description, MTU, etc.) but IPv6 is already configured
            if nb_ipv6:
                if "_ip_changes" not in nb_intf:
                    nb_intf["_ip_changes"] = {}
                if enhanced_intf:
                    # Enhanced facts available - store addresses that need adding
                    # (might be empty if all are already configured)
                    # Merge regular IPv6 with anycast IPv6 (don't overwrite!)
                    existing_ipv6_to_add = nb_intf["_ip_changes"].get("ipv6_to_add", [])
                    new_ipv6_to_add = list(ipv6_to_add)
                    # Combine and deduplicate
                    all_ipv6_to_add = list(set(existing_ipv6_to_add + new_ipv6_to_add))
                    nb_intf["_ip_changes"]["ipv6_to_add"] = all_ipv6_to_add
                    nb_intf["_ip_changes"]["ipv6_addresses"] = list(nb_ipv6)
                    if ipv6_to_remove:
                        nb_intf["_ip_changes"]["ipv6_to_remove"] = list(ipv6_to_remove)
                else:
                    # No enhanced facts - store all addresses for reference
                    nb_intf["_ip_changes"]["ipv6_addresses"] = list(nb_ipv6)

        # Check DHCP relay / ip helper-address configuration
        # When dhcp_relay_facts are available (gathered via REST API), compare the
        # desired helper servers (from ip_helper_addresses keyed by VRF) with the
        # currently configured servers to decide whether a push is needed.
        # Without dhcp_relay_facts, always include interfaces that have if_ip_helper=True
        # (conservative fall-through — same as the IPv6-without-enhanced-facts path).
        custom_fields = nb_intf.get("custom_fields") or {}
        if_ip_helper = custom_fields.get("if_ip_helper", False)
        if if_ip_helper:
            if dhcp_relay_facts is not None and ip_helper_addresses is not None:
                # Derive expected servers from the VRF-keyed inventory dict
                vrf_obj = nb_intf.get("vrf")
                vrf_name = (
                    vrf_obj.get("name")
                    if isinstance(vrf_obj, dict) and vrf_obj.get("name")
                    else "default"
                )
                vrf_helpers = ip_helper_addresses.get(vrf_name, {})
                expected_servers = set()
                if isinstance(vrf_helpers, dict):
                    expected_servers = set(v for v in vrf_helpers.values() if v)
                device_servers = set(dhcp_relay_facts.get(intf_name, []))
                if expected_servers != device_servers:
                    needs_change = True
                    if "_ip_changes" not in nb_intf:
                        nb_intf["_ip_changes"] = {}
                    nb_intf["_ip_changes"]["dhcp_relay_change"] = True
                    stale = sorted(device_servers - expected_servers)
                    if stale:
                        nb_intf["_ip_changes"]["dhcp_relay_to_remove"] = stale
                    change_reasons.append(
                        f"DHCP relay mismatch (wanted: {sorted(expected_servers)}, "
                        f"device: {sorted(device_servers)})"
                    )
                    _debug(
                        f"DHCP relay diff for {intf_name}: "
                        f"expected={expected_servers}, device={device_servers}"
                    )
                else:
                    _debug(
                        f"DHCP relay already correct for {intf_name}: {device_servers}"
                    )
            else:
                # No relay facts — conservatively mark as needing change
                needs_change = True
                if "_ip_changes" not in nb_intf:
                    nb_intf["_ip_changes"] = {}
                nb_intf["_ip_changes"]["dhcp_relay_change"] = True
                change_reasons.append(
                    "DHCP relay configuration needed (no facts for comparison)"
                )
        elif dhcp_relay_facts is not None and dhcp_relay_facts.get(intf_name):
            # if_ip_helper is False/None but the device has relays configured — stale
            needs_change = True
            if "_ip_changes" not in nb_intf:
                nb_intf["_ip_changes"] = {}
            nb_intf["_ip_changes"]["dhcp_relay_change"] = True
            nb_intf["_ip_changes"]["dhcp_relay_to_remove"] = sorted(
                dhcp_relay_facts[intf_name]
            )
            change_reasons.append(
                f"Stale DHCP relays on device: {dhcp_relay_facts[intf_name]}"
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
