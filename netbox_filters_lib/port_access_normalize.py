"""
Normalise the ``port_access`` config_context dict to the role's list form.

NetBox merges config contexts recursively for dicts, but a list in a
later context replaces the whole list from an earlier one. With the list
form below, two contexts that both define ``port_access.roles`` cannot be
combined - only the context applied last survives::

    port_access:
      roles:
        - name: AO-AP-role
          trust_mode: dscp

The name-keyed form merges instead, object by object and attribute by
attribute, so each profile (and a feature overlay such as UBT
``gateway_zone``) can live in its own context::

    port_access:
      roles:
        AO-AP-role:
          trust_mode: dscp

Public filters:
- ``port_access_normalize(port_access)`` -> the same dict with every
  object collection in list form.
- ``port_access_missing_ubt_zones(port_access, ubt)`` -> roles whose
  ``gateway_zone`` is not defined in the ``ubt`` config_context.

Pure functions. No I/O, no global state.
"""
from __future__ import annotations

# Object collections under ``port_access`` that hold named objects.
PORT_ACCESS_KINDS = (
    "classes",
    "policies",
    "lldp_groups",
    "mac_groups",
    "roles",
    "device_profiles",
)


def _normalize_collection(value):
    """Return a collection as a list of object dicts."""
    if isinstance(value, list):
        return value
    if not isinstance(value, dict):
        return []
    out = []
    for name in sorted(value, key=str):
        body = value[name]
        # null removes the object: a higher-weight context can drop an
        # object that a broader context defines.
        if body is None:
            continue
        if not isinstance(body, dict):
            continue
        # The key is the merge identity, so it wins over a `name` field.
        out.append({**body, "name": str(name)})
    return out


def port_access_normalize(port_access):
    """
    Convert name-keyed ``port_access`` collections to the list form.

    Every collection in ``PORT_ACCESS_KINDS`` may be either a list of
    object dicts (each with a ``name``) or a dict keyed by object name.
    Dict entries become ``{**body, "name": key}``, sorted by name. An
    entry whose value is ``null`` is dropped, so a more specific context
    can remove an object a broader one defines. Lists pass through
    unchanged, so the existing list form keeps working. Keys outside
    ``PORT_ACCESS_KINDS`` are returned untouched.

    Args:
        port_access: ``port_access`` dict from NetBox config_context, or
            ``None``.

    Returns:
        dict. ``{}`` when the input is not a dict.

    Example:
        >>> port_access_normalize({"roles": {"AP": {"trust_mode": "dscp"}}})
        {'roles': [{'trust_mode': 'dscp', 'name': 'AP'}]}
    """
    if not isinstance(port_access, dict):
        return {}
    out = dict(port_access)
    for kind in PORT_ACCESS_KINDS:
        if kind in out:
            out[kind] = _normalize_collection(out[kind])
    return out


def port_access_missing_ubt_zones(port_access, ubt=None):
    """
    List roles that tunnel to a UBT zone the device does not define.

    A role with ``gateway_zone`` needs that zone in the device's ``ubt``
    config_context (``ubt.zones[].name``). A device without UBT support
    (e.g. a CX 6000) has no ``ubt`` context, so any role carrying
    ``gateway_zone`` is reported - the push would otherwise fail on the
    device.

    Args:
        port_access: ``port_access`` dict (list or name-keyed form).
        ubt: ``ubt`` dict from config_context, or ``None``.

    Returns:
        Sorted list of ``"<role> -> <zone>"`` strings; empty when every
        referenced zone exists.
    """
    roles = port_access_normalize(port_access).get("roles") or []
    zones = set()
    if isinstance(ubt, dict):
        for zone in ubt.get("zones") or []:
            if isinstance(zone, dict) and zone.get("name"):
                zones.add(str(zone["name"]))
    missing = []
    for role in roles:
        if not isinstance(role, dict):
            continue
        zone = role.get("gateway_zone")
        if zone in (None, ""):
            continue
        if str(zone) not in zones:
            missing.append(f"{role.get('name')} -> {zone}")
    return sorted(missing)
