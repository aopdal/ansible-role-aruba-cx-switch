"""
Management VRF filters for NetBox data transformation

Determines the VRF a device is managed through: the out-of-band ``mgmt``
port (always named ``mgmt`` on AOS-CX, in the ``mgmt`` VRF) or in-band
(the VRF of the interface carrying ``primary_ip4``). NetBox's ``mgmt_only``
flag is not used for this: it is also set on in-band management interfaces
(e.g. ``vlan1`` on a CX 6000 without an OOBM port).

Used by SNMP (``snmp_vrf: auto``) and the ssh/https-server VRF bindings.
"""

from .utils import _debug

# The AOS-CX out-of-band management port is always named "mgmt".
_OOBM_INTERFACE = "mgmt"


def is_oobm_interface(intf):
    """Return True for the AOS-CX out-of-band management port."""
    return str(intf.get("name", "")).lower() == _OOBM_INTERFACE


def interface_ips(intf):
    """Return the bare IP addresses (no prefix length) on a NetBox interface."""
    ips = []
    for ip in intf.get("ip_addresses") or []:
        address = ip.get("address") if isinstance(ip, dict) else ip
        if address:
            ips.append(str(address).split("/", 1)[0])
    return ips


# NetBox VRF names that mean the AOS-CX default VRF.
_DEFAULT_VRF_NAMES = {"default", "Default", "Global", "global"}


def _intf_vrf(intf):
    """Return the AOS-CX VRF of a NetBox interface (``default`` if none)."""
    vrf = intf.get("vrf")
    name = vrf.get("name") if isinstance(vrf, dict) else vrf
    if not name or name in _DEFAULT_VRF_NAMES:
        return "default"
    return str(name)


def resolve_mgmt_vrf(interfaces=None, primary_ip4=None):
    """Return the VRF the device is managed through.

    The management VRF is the VRF of the interface carrying ``primary_ip4``:
    ``mgmt`` for the out-of-band port (interface named ``mgmt``), otherwise
    the interface's NetBox VRF, or ``default`` when it has none (in-band
    management, e.g. over a VLAN SVI - also when that SVI is flagged
    ``mgmt_only`` in NetBox).

    Args:
        interfaces (list): NetBox interfaces for the device.
        primary_ip4 (str): Device primary IPv4 address (prefix length optional).

    Returns:
        str or None: The VRF name, or ``None`` when ``primary_ip4`` is unset
        or not found on any interface.
    """
    primary = str(primary_ip4).split("/", 1)[0] if primary_ip4 else ""
    if not primary:
        return None
    for intf in interfaces or []:
        if primary in interface_ips(intf):
            vrf = "mgmt" if is_oobm_interface(intf) else _intf_vrf(intf)
            _debug(f"Mgmt VRF: primary_ip4 {primary} on {intf.get('name')} -> {vrf}")
            return vrf
    return None


def get_server_vrfs(interfaces=None, primary_ip4=None, device_roles=None):
    """Return the extra VRFs ssh/https-server must listen in.

    ``ssh server vrf mgmt`` / ``https-server vrf mgmt`` are always
    configured (ZTP starting config); this returns the additional VRFs:

    - ``default`` for devices whose first role is ``access-switch``
    - the in-band management VRF (``resolve_mgmt_vrf``) when the device is
      not managed through the ``mgmt`` port

    Returns:
        list: Sorted, de-duplicated VRF names, never containing ``mgmt``.
    """
    vrfs = set()
    roles = device_roles or []
    if isinstance(roles, str):
        roles = [roles]
    if roles and str(roles[0]).lower() == "access-switch":
        vrfs.add("default")
    mgmt_vrf = resolve_mgmt_vrf(interfaces, primary_ip4)
    if mgmt_vrf and mgmt_vrf != "mgmt":
        vrfs.add(mgmt_vrf)
    return sorted(vrfs)
