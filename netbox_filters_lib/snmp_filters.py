"""
SNMP filters for NetBox data transformation

Resolves the global SNMP settings (agent VRF, system location) from NetBox
inventory data and builds the ``snmpv3 user`` CLI lines pushed via
``aoscx_config``.

SNMPv3 auth/priv passphrases are write-only secrets: the device only ever
shows them back as ciphertext, so they can never be compared against a
cleartext value (see CLAUDE.md section 4.7). ``get_snmp_changes`` compares
against REST API facts: ciphertext keys (``encrypted: true``) are compared
exactly, plaintext keys only by user presence, protocols and access level.
Without REST facts, lines are pushed with ``aoscx_config`` ``match: line``,
where plaintext keys report ``changed`` on every run.
"""

from .utils import _debug

SNMPV3_AUTH_PROTOCOLS = ("md5", "sha", "sha224", "sha256", "sha384", "sha512")
SNMPV3_PRIV_PROTOCOLS = ("aes", "aes192", "aes256", "des")
SNMPV3_ACCESS_LEVELS = ("ro", "rw")
SNMPV3_WEAK_PROTOCOLS = ("md5", "des")

_AUTO_VRF_VALUES = (None, "", "auto")


def _first(value):
    """Return the first element of a list, or the value itself if scalar."""
    if isinstance(value, (list, tuple)):
        for item in value:
            if item:
                return item
        return None
    return value or None


def _intf_ips(intf):
    """Return the bare IP addresses (no prefix length) on a NetBox interface."""
    ips = []
    for ip in intf.get("ip_addresses") or []:
        address = ip.get("address") if isinstance(ip, dict) else ip
        if address:
            ips.append(str(address).split("/", 1)[0])
    return ips


def resolve_snmp_vrf(snmp_vrf, interfaces=None, primary_ip4=None):
    """Resolve the VRF the SNMP agent should listen in.

    Args:
        snmp_vrf (str): Configured value. Any value other than ``auto``
            (or empty) is returned unchanged, e.g. a user-defined VRF.
        interfaces (list): NetBox interfaces for the device.
        primary_ip4 (str): Device primary IPv4 address (no prefix length).

    Returns:
        str: ``mgmt`` when management runs over the dedicated mgmt port
        (the interface carrying ``primary_ip4`` is ``mgmt_only``),
        otherwise ``default`` (in-band management over a VLAN SVI).
        When ``primary_ip4`` is unknown, ``mgmt`` is chosen if any
        ``mgmt_only`` interface has an IP address.
    """
    if snmp_vrf not in _AUTO_VRF_VALUES:
        return snmp_vrf

    interfaces = interfaces or []
    primary = str(primary_ip4).split("/", 1)[0] if primary_ip4 else ""

    if primary:
        for intf in interfaces:
            if primary in _intf_ips(intf):
                vrf = "mgmt" if intf.get("mgmt_only") else "default"
                _debug(f"SNMP VRF: primary_ip4 {primary} on {intf.get('name')} -> {vrf}")
                return vrf

    for intf in interfaces:
        if intf.get("mgmt_only") and _intf_ips(intf):
            _debug(f"SNMP VRF: mgmt_only interface {intf.get('name')} has IP -> mgmt")
            return "mgmt"

    return "default"


def build_snmp_system_location(snmp_system_location, sites=None, locations=None):
    """Build the SNMP system-location string.

    Args:
        snmp_system_location (str): Explicit value. When non-empty it is
            returned unchanged.
        sites (list or str): NetBox site(s) of the device (``sites`` with
            inventory ``plurals: true``, ``site`` otherwise).
        locations (list or str): NetBox location(s) of the device.

    Returns:
        str: ``<site>/<location>``, ``<site>`` when the device has no
        location, or ``""`` when neither is known.
    """
    if snmp_system_location:
        return str(snmp_system_location)

    parts = [p for p in (_first(sites), _first(locations)) if p]
    return "/".join(str(p) for p in parts)


def _key_obj(keys, user_name, field):
    """Return ``(secret, encrypted)`` for a user's auth_pass/priv_pass key."""
    user_keys = (keys or {}).get(user_name) or {}
    key = user_keys.get(field) if isinstance(user_keys, dict) else None
    if isinstance(key, dict):
        return key.get("secret") or "", bool(key.get("encrypted", False))
    return (key or ""), False


def validate_snmpv3_users(snmpv3_users, snmpv3_user_keys=None):
    """Validate SNMPv3 user definitions against their keys.

    Messages never contain secret values.

    Args:
        snmpv3_users (list): User dicts with ``name``, optional
            ``auth_protocol``, ``priv_protocol`` and ``access_level``.
        snmpv3_user_keys (dict): Keyed by user name, each with
            ``auth_pass`` / ``priv_pass`` as ``{secret, encrypted}``.

    Returns:
        dict: ``{"valid": bool, "warnings": [...], "errors": [...]}``.
    """
    result = {"valid": True, "warnings": [], "errors": []}
    seen = set()

    if not isinstance(snmpv3_users, list):
        result["errors"].append("snmpv3_users must be a list")
        result["valid"] = False
        return result

    for idx, user in enumerate(snmpv3_users):
        if not isinstance(user, dict) or not user.get("name"):
            result["errors"].append(f"snmpv3_users[{idx}]: 'name' is required")
            continue
        name = user["name"]
        if name in seen:
            result["errors"].append(f"{name}: duplicate SNMPv3 user")
        seen.add(name)

        auth = user.get("auth_protocol")
        priv = user.get("priv_protocol")
        access = user.get("access_level", "ro")

        if auth and auth not in SNMPV3_AUTH_PROTOCOLS:
            result["errors"].append(
                f"{name}: invalid auth_protocol '{auth}' "
                f"(valid: {', '.join(SNMPV3_AUTH_PROTOCOLS)})"
            )
        if priv and priv not in SNMPV3_PRIV_PROTOCOLS:
            result["errors"].append(
                f"{name}: invalid priv_protocol '{priv}' "
                f"(valid: {', '.join(SNMPV3_PRIV_PROTOCOLS)})"
            )
        if priv and not auth:
            result["errors"].append(f"{name}: priv_protocol requires auth_protocol")
        if access not in SNMPV3_ACCESS_LEVELS:
            result["errors"].append(
                f"{name}: invalid access_level '{access}' (valid: ro, rw)"
            )
        if auth and not _key_obj(snmpv3_user_keys, name, "auth_pass")[0]:
            result["errors"].append(f"{name}: missing snmpv3_user_keys.{name}.auth_pass")
        if priv and not _key_obj(snmpv3_user_keys, name, "priv_pass")[0]:
            result["errors"].append(f"{name}: missing snmpv3_user_keys.{name}.priv_pass")

        for proto in (auth, priv):
            if proto in SNMPV3_WEAK_PROTOCOLS:
                result["warnings"].append(f"{name}: '{proto}' is a weak protocol")

    result["valid"] = not result["errors"]
    return result


def build_snmpv3_user_line(user, snmpv3_user_keys=None):
    """Build the ``snmpv3 user`` CLI line for one user.

    Assumes the input passed ``validate_snmpv3_users``. The line matches
    the device's running-config rendering so ``aoscx_config`` with
    ``match: line`` is idempotent: ``access-level ro`` is the default and
    is omitted by AOS-CX, so it is only emitted for ``rw``.

    Returns:
        str: e.g. ``snmpv3 user snmplab auth sha auth-pass ciphertext <..>
        priv aes priv-pass ciphertext <..>``.
    """
    name = user["name"]
    line = f"snmpv3 user {name}"

    auth = user.get("auth_protocol")
    if auth:
        secret, encrypted = _key_obj(snmpv3_user_keys, name, "auth_pass")
        mode = "ciphertext" if encrypted else "plaintext"
        line += f" auth {auth} auth-pass {mode} {secret}"

        priv = user.get("priv_protocol")
        if priv:
            secret, encrypted = _key_obj(snmpv3_user_keys, name, "priv_pass")
            mode = "ciphertext" if encrypted else "plaintext"
            line += f" priv {priv} priv-pass {mode} {secret}"

    if user.get("access_level", "ro") == "rw":
        line += " access-level rw"
    return line


def _user_needs_push(user, actual, snmpv3_user_keys):
    """Return True when a desired SNMPv3 user differs from device state.

    Protocols and access level are always compared. Passphrases are only
    compared for ``encrypted: true`` keys (device ciphertext vs. vault
    ciphertext); plaintext passphrases can never be compared against the
    device and are treated as matching (see CLAUDE.md section 4.7).
    """
    if not actual:
        return True
    auth = user.get("auth_protocol") or None
    priv = (user.get("priv_protocol") or None) if auth else None
    if auth != (actual.get("auth_protocol") or None):
        return True
    if priv != (actual.get("priv_protocol") or None):
        return True
    if user.get("access_level", "ro") != (actual.get("access_level") or "ro"):
        return True

    name = user["name"]
    for field, fact, enabled in (
        ("auth_pass", "auth_pass_phrase", auth),
        ("priv_pass", "priv_pass_phrase", priv),
    ):
        if not enabled:
            continue
        secret, encrypted = _key_obj(snmpv3_user_keys, name, field)
        if encrypted and secret != actual.get(fact):
            return True
    return False


def get_snmp_changes(
    snmp_facts,
    snmp_vrf,
    snmp_system_location="",
    snmp_system_contact="",
    snmpv3_users=None,
    snmpv3_user_keys=None,
):
    """Compare desired SNMP settings against REST API facts.

    Args:
        snmp_facts (dict or None): ``aoscx_snmp_facts`` from
            gather_facts_rest_api.yml (``system_location``,
            ``system_contact``, ``vrfs``, ``users``). ``None`` when REST
            facts are unavailable: everything desired is pushed and no
            removals are computed.
        snmp_vrf (str): Resolved agent VRF (see ``resolve_snmp_vrf``).
            Empty when SNMP is not desired: no VRF is pushed and every
            enabled agent VRF is removed.
        snmp_system_location (str): Resolved location ("" = none).
        snmp_system_contact (str): Desired contact ("" = none).
        snmpv3_users (list): Desired users (validated).
        snmpv3_user_keys (dict): Secrets per user name.

    Returns:
        dict: ``lines_to_push`` (global CLI lines), ``users_to_push``
        (user dicts; render with ``build_snmpv3_user_line`` under no_log)
        and ``lines_to_remove`` (``no ...`` CLI lines, for idempotent mode).
    """
    users = snmpv3_users or []
    desired_global = [f"snmp-server vrf {snmp_vrf}"] if snmp_vrf else []
    if snmp_system_location:
        desired_global.append(f"snmp-server system-location {snmp_system_location}")
    if snmp_system_contact:
        desired_global.append(f"snmp-server system-contact {snmp_system_contact}")

    if snmp_facts is None:
        return {
            "lines_to_push": desired_global,
            "users_to_push": list(users),
            "lines_to_remove": [],
        }

    actual_vrfs = snmp_facts.get("vrfs") or []
    actual_users = snmp_facts.get("users") or {}
    actual_location = snmp_facts.get("system_location") or ""
    actual_contact = snmp_facts.get("system_contact") or ""

    lines_to_push = []
    if snmp_vrf and snmp_vrf not in actual_vrfs:
        lines_to_push.append(f"snmp-server vrf {snmp_vrf}")
    if snmp_system_location and snmp_system_location != actual_location:
        lines_to_push.append(f"snmp-server system-location {snmp_system_location}")
    if snmp_system_contact and snmp_system_contact != actual_contact:
        lines_to_push.append(f"snmp-server system-contact {snmp_system_contact}")

    users_to_push = [
        u for u in users
        if _user_needs_push(u, actual_users.get(u["name"]), snmpv3_user_keys)
    ]

    desired_names = {u["name"] for u in users}
    lines_to_remove = [
        f"no snmpv3 user {name}"
        for name in sorted(actual_users)
        if name not in desired_names
    ]
    lines_to_remove += [
        f"no snmp-server vrf {vrf}" for vrf in sorted(actual_vrfs) if vrf != snmp_vrf
    ]
    if not snmp_system_location and actual_location:
        lines_to_remove.append("no snmp-server system-location")
    if not snmp_system_contact and actual_contact:
        lines_to_remove.append("no snmp-server system-contact")

    _debug(
        f"SNMP changes: push={lines_to_push}, users={[u['name'] for u in users_to_push]}, "
        f"remove={lines_to_remove}"
    )
    return {
        "lines_to_push": lines_to_push,
        "users_to_push": users_to_push,
        "lines_to_remove": lines_to_remove,
    }
