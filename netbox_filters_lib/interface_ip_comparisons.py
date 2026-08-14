"""
L3 IP-related comparison helpers for interface change detection.

Split out of interface_change_detection.py (docs/CODE_AUDIT.md finding F4)
to keep get_interfaces_needing_config_changes() focused on orchestration
(existence checks, physical/L2 property checks, categorization) while the
IPv4/IPv6/VRF/encapsulation/anycast/DHCP-relay comparison logic - the
densest and most independently-testable part of that function - lives
here as its own module.

Both entry points are pure (docs/CODE_AUDIT.md finding F5): they read
`nb_intf` / `device_intf` / `enhanced_intf` but never mutate them, and
return the change-reasons plus an `_ip_changes` fragment for the caller to
merge onto its own (already-copied) interface object. See CLAUDE.md 4.3.
"""

from urllib.parse import unquote

from .utils import (
    _debug,
    extract_ip_addresses,
    is_ipv6_address,
    normalize_ipv6 as _normalize_ipv6,
)


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


def compute_l3_ip_changes(nb_intf, device_intf, enhanced_intf, intf_name):
    """
    Compare NetBox IP-related L3 config for one interface against device
    facts: IPv4/IPv6 addresses, VRF attachment, sub-interface encapsulation
    VLAN, anycast/VSX virtual IPs, and the link-local address required for
    a link-local anycast gateway.

    Only call this when ``nb_intf.get("ip_addresses")`` is truthy - mirrors
    the guard the caller used to apply around this logic inline.

    Args:
        nb_intf: NetBox interface object (read-only; not mutated).
        device_intf: Device interface facts for this interface, from
            standard aoscx_facts (read-only; not mutated).
        enhanced_intf: This interface's entry from the enhanced REST API
            facts dict (depth=2), or None/falsy when unavailable.
        intf_name: Interface name, used for debug logging only.

    Returns:
        Tuple of (needs_change: bool, change_reasons: list[str],
        ip_changes: dict). ``ip_changes`` holds only the keys this call
        determined - the caller merges it onto its own ``_ip_changes``
        dict rather than this function writing to ``nb_intf`` directly.
    """
    needs_change = False
    change_reasons = []
    ip_changes = {}

    # Extract IP addresses from NetBox (format: "192.168.1.1/24" or "2001:db8::1/64")
    # Exclude anycast IPs from comparison - they're configured via active-gateway
    # command and not reported in device facts ip4_address field
    nb_ipv4_list, nb_ipv6_list = extract_ip_addresses(nb_intf, exclude_anycast=True)
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

    # Enhanced facts (REST API with depth=2) provide actual IPv6 addresses
    # and VSX virtual IPs.
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
                if addr and is_ipv6_address(addr):
                    device_ipv6.add(addr)
            _debug(f"Enhanced IPv6 for {intf_name}: {device_ipv6}")

        # Extract VSX virtual IPs (anycast/active-gateway)
        # The REST API may return vsx_virtual_ip4 in CIDR form
        # (e.g. "172.18.19.129/27"), mirroring how ip4_address is
        # stored, even though the active-gateway CLI itself takes
        # no prefix. NetBox anycast addresses are compared without
        # a prefix (see addr_without_prefix below), so strip any
        # "/prefix" here too - otherwise a device that already has
        # the anycast IP configured is reported as needing it
        # added on every run (false positive, non-idempotent).
        vsx_ip4 = enhanced_intf.get("vsx_virtual_ip4")
        if vsx_ip4:
            vsx_ip4_list = vsx_ip4 if isinstance(vsx_ip4, list) else [vsx_ip4]
            for addr in vsx_ip4_list:
                if addr:
                    device_vsx_virtual_ip4.add(
                        addr.split("/")[0] if "/" in addr else addr
                    )

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
        ip_changes["vrf_change"] = True
        _debug(
            f"VRF change detected for {intf_name}: "
            f"NB={nb_vrf_name}, device={device_vrf_name}"
        )

    # Encapsulation VLAN check (sub-interfaces only)
    # AOS-CX reports the subinterface's configured 802.1Q encapsulation
    # VLAN as `subintf_vlan` via the REST API - this is not present in
    # standard aoscx_facts, so the comparison only runs when enhanced
    # facts are available. This is the drift case that motivated the
    # virtual-interface cleanup task: if NetBox re-tags the interface
    # to a different VLAN without renaming it, the device keeps
    # forwarding on the stale VLAN unless this is corrected.
    if enhanced_intf and nb_intf.get("parent") is not None:
        nb_tagged_vlans = nb_intf.get("tagged_vlans")
        nb_encap_vlan = None
        if (
            nb_tagged_vlans
            and isinstance(nb_tagged_vlans, list)
            and isinstance(nb_tagged_vlans[0], dict)
        ):
            nb_encap_vlan = nb_tagged_vlans[0].get("vid")
        device_encap_vlan = enhanced_intf.get("subintf_vlan")
        if nb_encap_vlan is not None and nb_encap_vlan != device_encap_vlan:
            needs_change = True
            change_reasons.append(
                f"encapsulation VLAN mismatch (NB: {nb_encap_vlan}, "
                f"device: {device_encap_vlan})"
            )
            ip_changes["encapsulation_change"] = True
            _debug(
                f"Encapsulation VLAN change detected for {intf_name}: "
                f"NB={nb_encap_vlan}, device={device_encap_vlan}"
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
                    change_reasons.append(f"IPv6 addresses to add: {ipv6_to_add}")
                if ipv6_to_remove:
                    change_reasons.append(
                        f"IPv6 addresses to remove: {ipv6_to_remove}"
                    )
            else:
                change_reasons.append(
                    f"IPv6 addresses need configuration: {nb_ipv6}"
                )

        # Store IPv4 change details for task-level filtering
        if ipv4_to_add:
            ip_changes["ipv4_to_add"] = list(ipv4_to_add)

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
                    role_obj.get("value") if isinstance(role_obj, dict) else role_obj
                )
                if role_value == "anycast":
                    # Remove /prefix for comparison
                    # (active-gateway uses address without prefix)
                    addr_without_prefix = (
                        ip_addr.split("/")[0] if "/" in ip_addr else ip_addr
                    )
                    if is_ipv6_address(addr_without_prefix):
                        # IPv6 - normalize for comparison
                        normalized, _ = _normalize_ipv6(addr_without_prefix)
                        nb_anycast_ipv6.add(addr_without_prefix)
                        nb_anycast_ipv6_normalized[normalized] = addr_without_prefix
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
                if is_ipv6_address(addr):
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
        if anycast_ipv4_to_remove:
            ip_changes["anycast_ipv4_to_remove"] = list(anycast_ipv4_to_remove)
        if anycast_ipv6_to_remove:
            ip_changes["anycast_ipv6_to_remove"] = list(anycast_ipv6_to_remove)

    # Store anycast IPs that need to be added
    # (restored to ip_addresses field with anycast info)
    # This allows configure_l3_interfaces.yml to process them
    if anycast_ipv4_to_add or anycast_ipv6_to_add:
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
                            not is_ipv6_address(addr_without_prefix)
                            and addr_without_prefix in anycast_ipv4_to_add
                        ) or (
                            is_ipv6_address(addr_without_prefix)
                            and addr_without_prefix in anycast_ipv6_to_add
                        ):
                            anycast_ips_to_add.append(ip_addr)

        # Merge with existing ipv4_to_add/ipv6_to_add
        for anycast_ip in anycast_ips_to_add:
            if is_ipv6_address(anycast_ip):
                # IPv6
                if "ipv6_to_add" not in ip_changes:
                    ip_changes["ipv6_to_add"] = []
                if anycast_ip not in ip_changes["ipv6_to_add"]:
                    ip_changes["ipv6_to_add"].append(anycast_ip)
            else:
                # IPv4
                if "ipv4_to_add" not in ip_changes:
                    ip_changes["ipv4_to_add"] = []
                if anycast_ip not in ip_changes["ipv4_to_add"]:
                    ip_changes["ipv4_to_add"].append(anycast_ip)

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
        ip_changes["link_local_ipv6_to_add"] = list(link_local_ipv6_to_add)

    # Store IPv6 addresses to remove even when NetBox has no IPv6
    # (device has addresses but they were all removed from NetBox)
    if enhanced_intf and ipv6_to_remove and not nb_ipv6:
        ip_changes["ipv6_to_remove"] = list(ipv6_to_remove)

    # ALWAYS store IPv6 change info when enhanced facts available
    # This allows task-level filtering even when interface needs changes
    # for other reasons (description, MTU, etc.) but IPv6 is already configured
    if nb_ipv6:
        if enhanced_intf:
            # Enhanced facts available - store addresses that need adding
            # (might be empty if all are already configured)
            # Merge regular IPv6 with anycast IPv6 (don't overwrite!)
            existing_ipv6_to_add = ip_changes.get("ipv6_to_add", [])
            new_ipv6_to_add = list(ipv6_to_add)
            # Combine and deduplicate
            all_ipv6_to_add = list(set(existing_ipv6_to_add + new_ipv6_to_add))
            ip_changes["ipv6_to_add"] = all_ipv6_to_add
            ip_changes["ipv6_addresses"] = list(nb_ipv6)
            if ipv6_to_remove:
                ip_changes["ipv6_to_remove"] = list(ipv6_to_remove)
        else:
            # No enhanced facts - store all addresses for reference
            ip_changes["ipv6_addresses"] = list(nb_ipv6)

    return needs_change, change_reasons, ip_changes


def compute_dhcp_relay_changes(nb_intf, intf_name, dhcp_relay_facts, ip_helper_addresses):
    """
    Compare desired DHCP relay / ip helper-address servers with the
    currently configured servers for one interface.

    When dhcp_relay_facts/ip_helper_addresses are available (gathered via
    REST API), the desired helper servers (from ip_helper_addresses, keyed
    by VRF) are compared with the device state and a change is only flagged
    when they differ. Without dhcp_relay_facts, any interface with
    if_ip_helper=True is conservatively always flagged (same fall-through
    pattern used for IPv6 without enhanced facts).

    Args:
        nb_intf: NetBox interface object (read-only; not mutated).
        intf_name: Interface name, used to key dhcp_relay_facts.
        dhcp_relay_facts: Optional dict keyed by interface name with a
            sorted list of currently configured IPv4 DHCP relay servers,
            or None when not gathered.
        ip_helper_addresses: Optional dict keyed by VRF name, value a dict
            of {str_index: ip_address} entries, or None.

    Returns:
        Tuple of (needs_change: bool, change_reasons: list[str],
        ip_changes: dict) - see compute_l3_ip_changes() for the merge
        contract.
    """
    needs_change = False
    change_reasons = []
    ip_changes = {}

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

            # ALWAYS store the expected/actual helper servers when facts are
            # available, even when they match — mirrors the "always store
            # IPv6 change info" pattern above, so report/verification tasks
            # can display current ip helper state regardless of drift.
            ip_changes["dhcp_relay_expected"] = sorted(expected_servers)
            ip_changes["dhcp_relay_actual"] = sorted(device_servers)

            if expected_servers != device_servers:
                needs_change = True
                ip_changes["dhcp_relay_change"] = True
                stale = sorted(device_servers - expected_servers)
                if stale:
                    ip_changes["dhcp_relay_to_remove"] = stale
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
            ip_changes["dhcp_relay_change"] = True
            change_reasons.append(
                "DHCP relay configuration needed (no facts for comparison)"
            )
    elif dhcp_relay_facts is not None and dhcp_relay_facts.get(intf_name):
        # if_ip_helper is False/None but the device has relays configured — stale
        needs_change = True
        ip_changes["dhcp_relay_change"] = True
        ip_changes["dhcp_relay_to_remove"] = sorted(dhcp_relay_facts[intf_name])
        change_reasons.append(
            f"Stale DHCP relays on device: {dhcp_relay_facts[intf_name]}"
        )

    return needs_change, change_reasons, ip_changes
