#!/usr/bin/env python3
"""
BGP-related filters for NetBox data transformation.

Provides functions to enrich BGP session data with VRF and address-family
information derived from the device's interface assignments in NetBox.
"""

from .utils import _debug

# VRF names that are built-in / non-configurable; treated as 'default'
_BUILTIN_VRFS = {"mgmt", "MGMT", "Global", "global", "default", "Default"}


def get_bgp_session_vrf_info(sessions, interfaces):
    """
    Enrich BGP sessions with VRF and address-family information.

    For each session, the function:
      1. Looks up ``local_address.address`` (CIDR) against every IP address
         that is assigned to a device interface (``interface.ip_addresses``).
      2. Takes the VRF from the matched interface.
         - Non-default / custom VRF  → ``_vrf`` is set to that VRF name.
         - Default / no VRF          → ``_vrf`` is set to ``'default'``.
      3. Determines the address family from the IP address syntax:
         - Contains ':'  → ``_af = 'ipv6'``
         - Otherwise     → ``_af = 'ipv4'``

    This allows downstream tasks to split sessions into:
      - Global BGP sessions  (_vrf == 'default')  → EVPN / underlay
      - VRF BGP sessions     (_vrf != 'default')  → L3VPN / VRF peering

    Args:
        sessions:   List of BGP session objects from the NetBox BGP plugin.
        interfaces: List of interface objects from NetBox inventory
                    (nb_inventory with ``interfaces: true``).  Each interface
                    is expected to have an ``ip_addresses`` list and an
                    optional ``vrf`` dict.

    Returns:
        List of session dicts, each enriched with:
          - ``_vrf`` (str): VRF name, or ``'default'``.
          - ``_af``  (str): ``'ipv4'`` or ``'ipv6'``.
    """
    # ------------------------------------------------------------------
    # Build a lookup: IP address (CIDR) -> VRF name, from interface data
    # ------------------------------------------------------------------
    ip_vrf_map = {}

    for intf in interfaces or []:
        if not isinstance(intf, dict):
            continue

        # Skip management-only interfaces
        if intf.get("mgmt_only"):
            continue

        vrf_obj = intf.get("vrf")
        if vrf_obj and isinstance(vrf_obj, dict):
            vrf_name = vrf_obj.get("name") or "default"
        else:
            vrf_name = "default"

        # Normalise built-in VRF names to 'default'
        if vrf_name in _BUILTIN_VRFS and vrf_name != "default":
            vrf_name = "default"

        for ip_obj in intf.get("ip_addresses") or []:
            addr = ip_obj.get("address") if isinstance(ip_obj, dict) else str(ip_obj)
            if addr:
                ip_vrf_map[addr] = vrf_name
                _debug(
                    f"IP→VRF map: {addr} → '{vrf_name}' "
                    f"(interface '{intf.get('name')}')"
                )

    _debug(f"IP→VRF map built with {len(ip_vrf_map)} entries")

    # ------------------------------------------------------------------
    # Enrich each BGP session
    # ------------------------------------------------------------------
    result = []

    for session in sessions or []:
        if not isinstance(session, dict):
            continue

        local_addr_obj = session.get("local_address") or {}
        local_addr = (
            local_addr_obj.get("address", "")
            if isinstance(local_addr_obj, dict)
            else ""
        )

        vrf_name = ip_vrf_map.get(local_addr, "default")
        af = "ipv6" if ":" in local_addr else "ipv4"

        enriched = dict(session)
        enriched["_vrf"] = vrf_name
        enriched["_af"] = af

        _debug(
            f"Session '{session.get('name', '?')}': "
            f"local_address={local_addr} → VRF='{vrf_name}', AF='{af}'"
        )

        result.append(enriched)

    return result
