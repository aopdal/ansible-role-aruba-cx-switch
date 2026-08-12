"""
L3 Interface Configuration Helpers

This module provides helper functions for building L3 interface configuration
to reduce code duplication across physical, LAG, and VLAN interface types.
"""

from .utils import _debug, is_ipv4_address, is_ipv6_address

__all__ = [
    "build_l3_config_lines",
    "build_l3_config_preview",
    "format_interface_name",
    "get_interface_vrf",
    "group_interface_ips",
    "is_ipv4_address",
    "is_ipv6_address",
    "should_add_interface_ip",
]


def format_interface_name(interface_name, interface_type):
    """
    Format interface name for AOS-CX configuration context.

    Different interface types require different formatting:
    - Physical: "1/1/1" stays as "1/1/1"
    - LAG: "lag1" becomes "lag 1" (space added)
    - VLAN: "vlan10" stays as "vlan10"
    - Loopback: "loopback0" becomes "loopback 0" (space added)
    - Sub-interface: "1/1/3.2000" stays as "1/1/3.2000"

    Args:
        interface_name: Raw interface name from NetBox
        interface_type: Type of interface ('physical', 'lag', 'vlan', 'loopback', 'subinterface')

    Returns:
        Formatted interface name for use in configuration
    """
    if interface_type == "lag":
        # LAG interfaces need a space: "lag1" -> "lag 1"
        return interface_name.replace("lag", "lag ")
    if interface_type == "loopback":
        # Loopback interfaces need a space: "loopback0" -> "loopback 0"
        return interface_name.replace("loopback", "loopback ")
    # Physical, VLAN, and sub-interfaces use the name as-is
    return interface_name


def get_interface_vrf(interface_data):
    """
    Extract VRF name from interface data with proper fallback.

    Args:
        interface_data: Interface object from NetBox

    Returns:
        VRF name (defaults to 'default' if not specified)
    """
    if not isinstance(interface_data, dict):
        return "default"

    vrf = interface_data.get("vrf")
    if vrf and isinstance(vrf, dict):
        vrf_name = vrf.get("name")
        if vrf_name:
            return vrf_name

    return "default"


def group_interface_ips(
    interface_ip_list,
    ospf_facts=None,
    ospf_process_id=1,
):
    """
    Group a flat list of per-IP interface items into per-interface items.

    Each item in the input list represents one IP address on one interface.
    This function groups them so that each output item represents one interface
    with all of its addresses that need to be added (_needs_add=True).

    An interface is included in the result if:
    - At least one IP address has _needs_add=True, OR
    - The interface has OSPF configured (if_ip_ospf_1_area set) AND either:
      - ospf_facts is None (no comparison possible — always include), OR
      - The interface is not already registered in the correct OSPF area, OR
      - The interface's OSPF network type does not match the desired type.
    - The interface has _ip_changes.dhcp_relay_change=True (set by change detection
      when ip helper-address configuration differs from device state).
    - The interface has _ip_changes.description_change=True (set by change detection
      for virtual interfaces — VLAN SVIs, loopbacks, sub-interfaces — when the
      NetBox description differs from the device description).

    Args:
        interface_ip_list: List of per-IP items, each with keys:
            - interface_name: Name of the interface
            - interface: Full NetBox interface object
            - address: IP address string
            - ip_role: Role of the IP (e.g., 'anycast') or None
            - anycast_mac: MAC address for anycast gateway or None
            - _needs_add: Boolean indicating if this IP needs to be configured
        ospf_facts: Optional dict of OSPF interface facts gathered from the device
            REST API, structured as
            ``{vrf: {process_id_str: {area: {intf_name: {ospf_if_type, ...}}}}}``.
            When provided, interfaces already in the correct OSPF area with
            the correct network type are skipped unless IPs also need adding.
            When None, all OSPF interfaces are included.
        ospf_process_id: OSPF process ID to look up in ospf_facts (default: 1)

    Returns:
        List of per-interface items, each with keys:
            - interface_name: Name of the interface
            - interface: Full NetBox interface object
            - addresses: List of {address, ip_role, anycast_mac} dicts
                         sorted regular-before-anycast, IPv4 before IPv6
    """
    if not interface_ip_list:
        return []

    # First pass: group all items; collect only addresses that need adding
    by_name = {}
    for item in interface_ip_list:
        name = item.get("interface_name", "")
        if not name:
            continue
        if name not in by_name:
            by_name[name] = {
                "interface_name": name,
                "interface": item.get("interface", {}),
                "addresses": [],
            }
        if item.get("_needs_add", True):
            by_name[name]["addresses"].append(
                {
                    "address": item.get("address", ""),
                    "ip_role": item.get("ip_role"),
                    "anycast_mac": item.get("anycast_mac"),
                }
            )

    # Sort addresses: regular before anycast, IPv4 before IPv6
    def _addr_sort_key(addr):
        is_ipv6 = is_ipv6_address(addr.get("address", ""))
        is_anycast = addr.get("ip_role") == "anycast" and bool(
            addr.get("anycast_mac"))
        return (int(is_ipv6), int(is_anycast))

    result = []
    for item in by_name.values():
        # Determine whether OSPF config needs to be pushed for this interface.
        # If ospf_facts are available, compare the intended area with device state.
        # If not available, fall back to always including OSPF-configured interfaces.
        interface_obj = (
            item["interface"] if isinstance(
                item.get("interface"), dict) else {}
        )
        custom_fields = (
            interface_obj.get("custom_fields", {})
            if isinstance(interface_obj, dict)
            else {}
        )
        ospf_area = (
            custom_fields.get("if_ip_ospf_1_area")
            if isinstance(custom_fields, dict)
            else None
        )

        if ospf_area:
            if ospf_facts is None:
                # No facts available — always include (conservative)
                has_ospf_change = True
            else:
                vrf_name = get_interface_vrf(interface_obj)
                pid_str = str(ospf_process_id)
                intf_name = item["interface_name"]
                area_data = (
                    ospf_facts.get(vrf_name, {}).get(
                        pid_str, {}).get(ospf_area, {})
                )
                if intf_name not in area_data:
                    # Interface not registered in this OSPF area
                    has_ospf_change = True
                else:
                    # Interface is in the area — also check network type
                    current_type = area_data[intf_name].get("ospf_if_type")
                    desired_network = custom_fields.get("if_ip_ospf_network")
                    if desired_network:
                        # AOS-CX REST OSPF interface-type enum does not
                        # mirror NetBox's hyphenated values 1:1 (e.g.
                        # point-to-point -> ospf_iftype_pointopoint, not
                        # ospf_iftype_point_to_point) - matches how the
                        # AOS-CX Ansible collection builds it:
                        # type.replace('-', '').replace('tt', 't').
                        desired_type = "ospf_iftype_" + desired_network.replace(
                            "-", ""
                        ).replace("tt", "t")
                        if desired_type == "ospf_iftype_broadcast":
                            # broadcast is the AOS-CX default network type -
                            # the device only stores an explicit
                            # ospf_if_type when it differs from broadcast,
                            # so a missing/None value in facts is
                            # equivalent to broadcast.
                            has_ospf_change = current_type not in (
                                None,
                                "ospf_iftype_broadcast",
                            )
                        else:
                            has_ospf_change = current_type != desired_type
                    else:
                        has_ospf_change = current_type is not None
                _debug(
                    f"  OSPF check {intf_name}: area={ospf_area} vrf={vrf_name} "
                    f"change_needed={has_ospf_change}"
                )
        else:
            has_ospf_change = False

        # Check whether a DHCP relay change was flagged during change detection.
        # This covers interfaces where ip helper-address is wrong but all IPs are
        # already on the device (so _needs_add=False for every address).
        ip_changes = interface_obj.get("_ip_changes", {})
        has_dhcp_relay_change = bool(
            ip_changes.get("dhcp_relay_change")
            if isinstance(ip_changes, dict)
            else False
        )

        # Check whether a description-only change was flagged during change
        # detection (virtual interfaces only — see interface_change_detection.py).
        # This covers VLAN SVIs/loopbacks/sub-interfaces where the description
        # differs but no IP/OSPF/DHCP change is otherwise needed.
        has_description_change = bool(
            ip_changes.get("description_change")
            if isinstance(ip_changes, dict)
            else False
        )

        # Check whether a sub-interface encapsulation VLAN change was flagged
        # during change detection (requires enhanced/REST facts - see
        # interface_change_detection.py). Covers sub-interfaces where the IP
        # is already correct but NetBox re-tagged the interface to a
        # different VLAN.
        has_encapsulation_change = bool(
            ip_changes.get("encapsulation_change")
            if isinstance(ip_changes, dict)
            else False
        )

        if (
            item["addresses"]
            or has_ospf_change
            or has_dhcp_relay_change
            or has_description_change
            or has_encapsulation_change
        ):
            item["addresses"].sort(key=_addr_sort_key)
            result.append(item)

    return result


def build_l3_config_lines(
    item,
    interface_type,
    vrf_type,
    l3_counters_enable=True,
    ip_helper_addresses=None,
):
    """
    Build all L3 configuration lines for a single interface.

    Generates a complete, ordered list of CLI configuration commands for the
    interface. Each per-interface command (vrf attach, ip mtu, l3-counters)
    is emitted exactly once regardless of how many IP addresses are present.

    For 'vlan', 'loopback', and 'subinterface' types, also emits a
    'description' line when the NetBox interface has one set. 'physical' and
    'lag' types do NOT get a description line here — those are handled by
    configure_physical_interfaces.yml / configure_lag_interfaces.yml /
    configure_mclag_interfaces.yml regardless of L2/L3 role, so adding it here
    too would duplicate the command.

    Args:
        item: Per-interface dict produced by group_interface_ips(), with keys:
            - interface_name: Name of the interface
            - interface: Full NetBox interface object (provides mtu, vrf,
                         description, tagged_vlans for sub-interfaces)
            - addresses: List of {address, ip_role, anycast_mac} dicts
        interface_type: Type of interface ('physical', 'lag', 'vlan',
                        'subinterface', 'loopback')
        vrf_type: VRF type ('default' or 'custom')
        l3_counters_enable: Whether to emit 'l3-counters' (default: True)
        ip_helper_addresses: Dict keyed by VRF name, values are dicts of
            {str_index: ip_address} (e.g. {"lab-blue": {"0": "1.1.1.1"}}).
            When provided and the interface has if_ip_helper=True, emits
            'ip helper-address' lines for each address in the interface's VRF.
            (default: None — no helper addresses emitted)

    Returns:
        List of configuration command strings in AOS-CX CLI syntax
    """
    lines = []

    interface_name = item.get("interface_name", "unknown")
    interface_obj = (
        item.get("interface") if isinstance(
            item.get("interface"), dict) else {}
    )
    addresses = item.get("addresses", [])

    _debug(
        f"Building L3 config for {interface_name}: "
        f"interface_type={interface_type}, vrf_type={vrf_type}, "
        f"addresses={len(addresses)}"
    )

    # Description — only for VLAN SVI, loopback, and sub-interface types.
    # Physical, LAG, and MCLAG interfaces already get description applied via
    # configure_physical_interfaces.yml / configure_lag_interfaces.yml /
    # configure_mclag_interfaces.yml regardless of L2/L3 role (those tasks push
    # description whenever the interface has ANY pending change), so emitting
    # it again here would just duplicate that command.
    if interface_type in ("vlan", "loopback", "subinterface"):
        description = interface_obj.get("description")
        if description:
            lines.append(f"description {description}")
            _debug(f"  Adding description: {description}")

    # Encapsulation for sub-interfaces (must come first)
    if interface_type == "subinterface":
        tagged_vlans = interface_obj.get("tagged_vlans", [])
        if tagged_vlans and isinstance(tagged_vlans, list) and len(tagged_vlans) > 0:
            vlan_id = tagged_vlans[0].get("vid")
            if vlan_id:
                lines.append(f"encapsulation dot1q {vlan_id}")
                _debug(f"  Adding encapsulation: dot1q {vlan_id}")

    # Explicit "routing" for physical and LAG interfaces (must come first, after
    # encapsulation). Some AOS-CX hardware/firmware defaults physical and LAG
    # ports to L2 (switching) mode, so routed mode must be enabled explicitly.
    # VLAN SVIs and loopbacks are always L3 by nature on every platform and
    # never need this; sub-interface parents are handled separately in
    # tasks/configure_physical_interfaces.yml.
    if interface_type in ("physical", "lag"):
        lines.append("routing")
        _debug("  Adding routing (L3 mode)")

    # VRF attachment — once per interface, not once per IP
    # Two cases require "vrf attach":
    #   1. Normal custom-VRF configuration (vrf_type == "custom"): attach the named VRF.
    #   2. VRF detachment (vrf_type == "default" + _ip_changes.vrf_change=True): the
    #      interface is being moved from a custom VRF back to the default VRF.
    #      AOS-CX requires "vrf attach default" explicitly to clear the old VRF; simply
    #      omitting the command does NOT revert the interface to default.
    ip_changes = interface_obj.get("_ip_changes", {})
    vrf_change = bool(
        ip_changes.get("vrf_change") if isinstance(ip_changes, dict) else False
    )
    if vrf_type == "custom":
        vrf_name = get_interface_vrf(interface_obj)
        lines.append(f"vrf attach {vrf_name}")
        _debug(f"  Adding VRF attachment: {vrf_name}")
    elif vrf_change:
        # Moving from a custom VRF back to default — must explicitly attach default.
        lines.append("vrf attach default")
        _debug("  Adding VRF attachment: default (reverting from custom VRF)")

    # MTU — before IP addresses (matches device CLI order)
    mtu = interface_obj.get("mtu")
    if mtu:
        lines.append(f"ip mtu {mtu}")
        _debug(f"  Adding MTU: {mtu}")

    # IP addresses: regular-before-anycast, IPv4 before IPv6
    # AOS-CX requires 'ip address' before 'active-gateway ip' for each address family
    ipv4_addrs = [a for a in addresses if is_ipv4_address(
        a.get("address", ""))]
    ipv6_addrs = [a for a in addresses if is_ipv6_address(
        a.get("address", ""))]

    # Regular IPv4 first, then anycast IPv4
    for addr_item in [
        a
        for a in ipv4_addrs
        if not (a.get("ip_role") == "anycast" and a.get("anycast_mac"))
    ]:
        address = addr_item.get("address", "")
        lines.append(f"ip address {address}")
        _debug(f"  Adding IPv4 address: {address}")
    for addr_item in [
        a for a in ipv4_addrs if a.get("ip_role") == "anycast" and a.get("anycast_mac")
    ]:
        address = addr_item.get("address", "")
        addr_without_prefix = address.split(
            "/")[0] if "/" in address else address
        lines.append(f"active-gateway ip mac {addr_item['anycast_mac']}")
        lines.append(f"active-gateway ip {addr_without_prefix}")
        _debug(
            f"  Adding IPv4 anycast gateway: {address} (MAC: {addr_item['anycast_mac']})"
        )

    # Regular IPv6 first, then anycast IPv6
    for addr_item in [
        a
        for a in ipv6_addrs
        if not (a.get("ip_role") == "anycast" and a.get("anycast_mac"))
    ]:
        address = addr_item.get("address", "")
        lines.append(f"ipv6 address {address}")
        _debug(f"  Adding IPv6 address: {address}")
    for addr_item in [
        a for a in ipv6_addrs if a.get("ip_role") == "anycast" and a.get("anycast_mac")
    ]:
        address = addr_item.get("address", "")
        addr_without_prefix = address.split(
            "/")[0] if "/" in address else address
        # HPE Aruba recommendation: use a link-local address as the anycast gateway.
        # When the anycast IPv6 is link-local, the link-local address must be
        # explicitly configured before the active-gateway command.
        if addr_without_prefix.lower().startswith("fe80:"):
            lines.append(f"ipv6 address link-local {address}")
            _debug(
                f"  Adding IPv6 link-local address for anycast gateway: {address}")
        lines.append(f"active-gateway ipv6 mac {addr_item['anycast_mac']}")
        lines.append(f"active-gateway ipv6 {addr_without_prefix}")
        _debug(
            f"  Adding IPv6 anycast gateway: {address} (MAC: {addr_item['anycast_mac']})"
        )

    # IP helper addresses — emitted after all IP/anycast lines, before l3-counters
    custom_fields = interface_obj.get("custom_fields", {})
    if not isinstance(custom_fields, dict):
        custom_fields = {}
    if_ip_helper = custom_fields.get("if_ip_helper", False)
    if if_ip_helper and ip_helper_addresses and isinstance(ip_helper_addresses, dict):
        vrf_name = get_interface_vrf(interface_obj)
        helpers = ip_helper_addresses.get(vrf_name, {})
        if isinstance(helpers, dict):
            for idx in sorted(
                helpers.keys(), key=lambda x: int(x) if str(x).isdigit() else x
            ):
                helper_ip = helpers[idx]
                if helper_ip:
                    lines.append(f"ip helper-address {helper_ip}")
                    _debug(f"  Adding IP helper-address: {helper_ip}")

    # L3 counters — once per interface (not supported on loopback)
    if l3_counters_enable and interface_type != "loopback":
        lines.append("l3-counters")

    _debug(f"  Generated {len(lines)} config lines for {interface_name}")
    return lines


def should_add_interface_ip(interface, address):
    """
    Decide whether a specific IP address on an interface must be pushed.

    Replaces the 5-deep Jinja ternary previously inlined as ``_needs_add``
    in ``tasks/configure_l3_interfaces.yml``. Semantics preserved exactly:

    - If ``interface._ip_changes.vrf_change`` is True, always True — a VRF
      move wipes all L3 config on the switch and every address must be
      re-applied (including anycast addresses that are excluded from the
      ``ipv4_to_add`` diff).
    - IPv4 (no colon in the address string):
        * If ``_ip_changes.ipv4_to_add`` exists, return whether the address
          is a member.
        * Else if ``_ip_changes`` exists at all, return False (change
          detection ran and found no change for this address).
        * Else return True (no ``_ip_changes`` — new interface).
    - IPv6 (colon in the address string):
        * If ``_ip_changes.ipv6_to_add`` exists (enhanced facts), return
          whether the address is a member.
        * Else if ``_ip_changes`` exists at all, return True (no enhanced
          facts, configure all IPv6 addresses).
        * Else return True (no ``_ip_changes`` — new interface).

    Args:
        interface: NetBox interface dict; may contain ``_ip_changes``.
        address: IP address string with prefix, e.g. ``"172.16.0.1/24"``
            or ``"2001:db8::1/64"``. Presence of ``:`` classifies as IPv6.

    Returns:
        Boolean.
    """
    if not isinstance(interface, dict):
        return True

    changes = interface.get("_ip_changes")

    if isinstance(changes, dict) and changes.get("vrf_change"):
        return True

    is_ipv6 = is_ipv6_address(address or "")

    if not isinstance(changes, dict):
        return True

    if is_ipv6:
        if "ipv6_to_add" in changes:
            return address in changes["ipv6_to_add"]
        # No enhanced facts: configure all IPv6 addresses
        return True

    if "ipv4_to_add" in changes:
        return address in changes["ipv4_to_add"]
    return False


def build_l3_config_preview(
    l3_interfaces,
    aoscx_builtin_vrfs,
    l3_counters_enable=True,
):
    """
    Build a dict mapping formatted interface name -> list of L3 config lines.

    Debug-only preview replacing the ~15-line Jinja block previously inlined
    as ``_l3_config_preview`` in ``tasks/configure_l3_interfaces.yml``.
    Iterates every ``(interface_type, vrf_type)`` category in
    ``l3_interfaces``, groups per-IP items with :func:`group_interface_ips`
    (default OSPF-facts handling), and emits :func:`build_l3_config_lines`
    output keyed by :func:`format_interface_name`.

    ``ip_helper_addresses`` is intentionally not exposed here: the preview
    is a lightweight summary; helper-address lines are only added in the
    live ``configure_l3_interface_common.yml`` push.

    Args:
        l3_interfaces: Output of ``categorize_l3_interfaces``, containing
            ``physical_default_vrf``, ``physical_custom_vrf``,
            ``vlan_default_vrf``, ``vlan_custom_vrf``,
            ``lag_default_vrf``, ``lag_custom_vrf``,
            ``subinterface_default_vrf``, ``subinterface_custom_vrf``, and
            ``loopback`` (which is split by VRF here).
        aoscx_builtin_vrfs: List of VRF names treated as built-in
            (``["default", "mgmt"]``) for the loopback split. Loopbacks
            with ``vrf in aoscx_builtin_vrfs + [None]`` go to the default
            bucket; the rest to custom.
        l3_counters_enable: Passed through to
            :func:`build_l3_config_lines`. Default True.

    Returns:
        Dict of ``{formatted_interface_name: [line, line, ...]}``.
        Interfaces with no lines are still included with an empty list
        (matches the prior Jinja behavior).
    """
    if not isinstance(l3_interfaces, dict):
        return {}

    builtin = list(aoscx_builtin_vrfs or []) + [None]
    loopback = l3_interfaces.get("loopback") or []
    loopback_default = [i for i in loopback if i.get("vrf") in builtin]
    loopback_custom = [i for i in loopback if i.get("vrf") not in builtin]

    categories = [
        (l3_interfaces.get("physical_default_vrf") or [], "physical", "default"),
        (l3_interfaces.get("physical_custom_vrf") or [], "physical", "custom"),
        (l3_interfaces.get("vlan_default_vrf") or [], "vlan", "default"),
        (l3_interfaces.get("vlan_custom_vrf") or [], "vlan", "custom"),
        (l3_interfaces.get("lag_default_vrf") or [], "lag", "default"),
        (l3_interfaces.get("lag_custom_vrf") or [], "lag", "custom"),
        (l3_interfaces.get("subinterface_default_vrf")
         or [], "subinterface", "default"),
        (l3_interfaces.get("subinterface_custom_vrf")
         or [], "subinterface", "custom"),
        (loopback_default, "loopback", "default"),
        (loopback_custom, "loopback", "custom"),
    ]

    result = {}
    for items, itype, vrf in categories:
        for item in group_interface_ips(items):
            lines = build_l3_config_lines(
                item, itype, vrf, l3_counters_enable
            )
            iname = format_interface_name(item["interface_name"], itype)
            result[iname] = lines

    return result
