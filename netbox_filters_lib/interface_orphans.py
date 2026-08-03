"""
Identify orphaned virtual interfaces (VLAN SVIs, loopbacks, sub-interfaces).

Unlike physical/LAG/MCLAG interfaces (which always exist in hardware
regardless of NetBox), VLAN SVIs, loopbacks, and sub-interfaces are logical
objects created and destroyed by this role. If NetBox is misconfigured -
e.g. an interface renamed or moved to a different parent - the stale
device-side object is never referenced again and can hold the same IP
address as its replacement, causing L3 configuration to fail with a
duplicate IP address.

Orphan = present on device but not in NetBox.
"""

import re

_VLAN_RE = re.compile(r"^vlan[0-9]+$")
_LOOPBACK_RE = re.compile(r"^loopback[0-9]+$")
_SUBINTERFACE_RE = re.compile(r"^\S+\.[0-9]+$")


def _is_virtual_interface(name):
    return bool(
        _VLAN_RE.match(name) or _LOOPBACK_RE.match(name) or _SUBINTERFACE_RE.match(name)
    )


def get_virtual_interfaces_to_delete(desired_interfaces, device_interfaces):
    """
    Args:
        desired_interfaces: NetBox `interfaces` list (dicts with a 'name' key).
        device_interfaces: ansible_facts.network_resources.interfaces dict,
            keyed by interface name.

    Returns:
        Sorted list of virtual interface names (VLAN SVI, loopback,
        sub-interface) present on the device but absent from NetBox.
        Physical and LAG/MCLAG interfaces are never included since they
        cannot be deleted from the device.
    """
    if not isinstance(device_interfaces, dict):
        return []
    desired_names = set(
        i["name"]
        for i in (desired_interfaces or [])
        if isinstance(i, dict) and "name" in i
    )
    return sorted(
        name
        for name in device_interfaces
        if _is_virtual_interface(name) and name not in desired_names
    )


def filters():
    return {"get_virtual_interfaces_to_delete": get_virtual_interfaces_to_delete}
