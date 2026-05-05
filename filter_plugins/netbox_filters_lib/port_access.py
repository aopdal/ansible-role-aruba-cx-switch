"""
Port-access (device-profile) diff filters.

Compares the desired ``port_access`` config_context dict (the role's input)
against the current device state captured in ``aoscx_port_access_facts``
(populated by tasks/gather_facts_rest_api.yml when port-access fact
gathering is enabled), and returns the subset of objects that need to be
configured.

Public filters:
- ``port_access_diff(desired, current)`` -> dict with the keys
  ``lldp_groups``, ``mac_groups``, ``roles``, ``device_profiles``, each
  containing the list of *desired* objects that differ from the device
  (or are missing from it). Items already matching the device are
  filtered out so the configure tasks skip them entirely.
- ``port_access_facts_from_device_profiles(profiles)`` -> flatten a
  single ``/system/device_profiles?depth=4`` REST response into the
  facts shape expected by ``port_access_diff``.

Design notes:
- Pure function. No I/O, no global state.
- "If in doubt, push": when ``current`` is empty, missing, or shaped
  unexpectedly, all desired objects are returned so the configure tasks
  fall back to the previous always-push behaviour. This guarantees we
  never silently miss a needed change.
- Uses the helpers from ``vlan_filters`` to expand VLAN ranges so the
  comparison against the device's ``vlan_trunks`` list is exact.
"""
from __future__ import annotations

from .utils import _debug
from .vlan_filters import parse_vlan_id_spec


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _norm_str(value):
    """Normalise a string for comparison; treat None and '' as equal."""
    if value is None:
        return ""
    return str(value)


def _norm_int(value):
    """Coerce numeric-ish value to int; return None on failure."""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalise_match_entry(entry):
    """
    Normalise an LLDP/MAC group match entry to (match_type, value) tuple.

    Accepts:
    - Desired-side dicts (NetBox config_context) with short keys like
      ``vendor_oui``, ``sys_name``, ``mac_oui``.
    - Device-side dicts from REST ``/system/device_profiles?depth=5``,
      whose ``lldp_groups[*].entries[<seq>]`` dicts use the long REST
      field names ``system_name``, ``system_description`` and the
      ``action`` discriminator.
    - Device-side dicts with an explicit ``match_type`` discriminator.

    Sequence numbers are intentionally ignored - what matters is the
    (match-type, value) tuple.
    """
    if not isinstance(entry, dict):
        return None

    # Desired-side / REST-side: scan known fields for the first non-null
    # value. Both shapes use the same field name for ``vendor_oui``; the
    # other LLDP keys differ between sides (sys_name vs system_name etc.)
    # so list both spellings.
    for key, mtype in (
        ("vendor_oui", "vendor-oui"),
        ("chassis_id", "chassis-id"),
        ("sys_name", "sys-name"),
        ("system_name", "sys-name"),
        ("sys_desc", "sys-desc"),
        ("system_description", "sys-desc"),
        ("mac_oui", "mac-oui"),
        ("mac", "mac"),
    ):
        value = entry.get(key)
        if value not in (None, ""):
            return (mtype, _norm_str(value).lower())

    # Explicit match_type discriminator (rare).
    mtype = entry.get("match_type")
    if mtype:
        value = (
            entry.get("value") or entry.get(mtype.replace("-", "_")) or entry.get(mtype)
        )
        if value is not None:
            return (str(mtype), _norm_str(value).lower())

    return None


def _entries_match_set(entries):
    """
    Convert a list/dict of match entries into a set of (mtype, value) tuples.

    Sequence numbers are intentionally ignored - two configs that match the
    same things in the same way are considered equal regardless of how they
    were numbered. This avoids spurious diffs from auto-renumbering.
    """
    result = set()
    if not entries:
        return result
    iterable = entries.values() if isinstance(entries, dict) else entries
    for entry in iterable:
        norm = _normalise_match_entry(entry)
        if norm is not None:
            result.add(norm)
    return result


# ---------------------------------------------------------------------------
# Per-object comparison
# ---------------------------------------------------------------------------


def _lldp_group_matches(desired, current):
    """Return True when device LLDP group entry-set equals desired."""
    if not isinstance(current, dict):
        return False
    return _entries_match_set(desired.get("match")) == _entries_match_set(
        current.get("entries") or current.get("match") or []
    )


def _mac_group_matches(desired, current):
    """Return True when device MAC group entry-set equals desired."""
    if not isinstance(current, dict):
        return False
    return _entries_match_set(desired.get("match")) == _entries_match_set(
        current.get("entries") or current.get("match") or []
    )


def _role_matches(desired, current):
    """
    Compare a desired port-access role against the device-reported role.

    Compared fields (only those that the role uses):
    - description
    - poe_priority
    - trust_mode      (REST: qos_trust_mode)
    - vlan_access     (REST: vlan_tag, when vlan_mode == 'access')
    - vlan_trunk_native (REST: vlan_tag, when vlan_mode in
      'native-tagged'/'native-untagged')
    - vlan_trunk_allowed -> expanded into a set, compared to vlan_trunks
    """
    if not isinstance(current, dict):
        return False

    desired_native = _norm_int(desired.get("vlan_trunk_native"))
    desired_access = _norm_int(desired.get("vlan_access"))
    current_vlan_tag = _norm_int(current.get("vlan_tag"))
    current_trunks_raw = current.get("vlan_trunks") or []
    desired_trunks = set(parse_vlan_id_spec(desired.get("vlan_trunk_allowed")))
    current_trunks = (
        {v for v in (_norm_int(x) for x in current_trunks_raw) if v is not None}
        if isinstance(current_trunks_raw, list)
        else None
    )

    return (
        _norm_str(desired.get("description")) == _norm_str(current.get("description"))
        and _norm_str(desired.get("poe_priority"))
        == _norm_str(current.get("poe_priority"))
        and _norm_str(desired.get("trust_mode"))
        == _norm_str(current.get("qos_trust_mode"))
        and (desired_native is None or desired_native == current_vlan_tag)
        and (desired_access is None or desired_access == current_vlan_tag)
        and current_trunks is not None
        and desired_trunks == current_trunks
    )


def _device_profile_matches(desired, current):
    """
    Compare a desired device-profile against the device-reported profile.

    Compared:
    - enable
    - associate_role         -> single key in current['role']
    - associate_lldp_group   -> single key in current['lldp_groups']
    - associate_mac_group    -> single key in current['mac_groups']
    """
    if not isinstance(current, dict):
        return False

    if bool(desired.get("enable", True)) != bool(current.get("enable", True)):
        return False

    def _single_key(obj, key):
        sub = obj.get(key)
        if isinstance(sub, dict) and sub:
            keys = list(sub.keys())
            return keys[0] if len(keys) == 1 else None
        return None

    # role: REST returns dict keyed by role name (typically a single role).
    if "associate_role" in desired:
        if _norm_str(desired.get("associate_role")) != _norm_str(
            _single_key(current, "role")
        ):
            return False

    if "associate_lldp_group" in desired:
        if _norm_str(desired.get("associate_lldp_group")) != _norm_str(
            _single_key(current, "lldp_groups")
        ):
            return False

    if "associate_mac_group" in desired:
        if _norm_str(desired.get("associate_mac_group")) != _norm_str(
            _single_key(current, "mac_groups")
        ):
            return False

    return True


# ---------------------------------------------------------------------------
# Public filter
# ---------------------------------------------------------------------------


_OBJECT_KINDS = (
    ("lldp_groups", _lldp_group_matches),
    ("mac_groups", _mac_group_matches),
    ("roles", _role_matches),
    ("device_profiles", _device_profile_matches),
)


def port_access_diff(desired, current):
    """
    Return the subset of ``desired`` port-access objects that need to be
    configured on the device.

    Args:
        desired: ``port_access`` dict from NetBox config_context, with any
            of the keys ``lldp_groups``, ``mac_groups``, ``roles``,
            ``device_profiles``. Each value is a list of object dicts.
        current: ``aoscx_port_access_facts`` dict from
            ``gather_facts_rest_api.yml``, with the keys ``device_profiles``,
            ``roles``, ``lldp_groups``, ``mac_groups`` (each a REST payload
            keyed by object name). May be ``None`` or empty.

    Returns:
        dict with the same four keys as the input. Each value is the list of
        desired items that differ from the device or are missing entirely.
        Items that already match are omitted, so the configure tasks skip
        them and avoid the SSH round-trip.

    Behaviour when ``current`` is empty / missing / wrong shape: every
    desired object is returned (safe default - never skip work we can't
    verify).
    """
    if not isinstance(desired, dict):
        return {
            "lldp_groups": [],
            "mac_groups": [],
            "roles": [],
            "device_profiles": [],
        }

    safe_current = current if isinstance(current, dict) else {}

    out = {}
    for kind, matcher in _OBJECT_KINDS:
        desired_list = desired.get(kind) or []
        if not isinstance(desired_list, list):
            out[kind] = []
            continue

        current_for_kind = safe_current.get(kind) or {}
        if not isinstance(current_for_kind, dict):
            current_for_kind = {}

        # If we have no current data at all, fall back to "push everything".
        if not current_for_kind:
            out[kind] = list(desired_list)
            _debug(
                f"port_access_diff: no current data for {kind}; "
                f"returning all {len(desired_list)} desired item(s)"
            )
            continue

        needs_change = []
        for item in desired_list:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not name:
                # Can't match without a name; safer to push.
                needs_change.append(item)
                continue
            current_item = current_for_kind.get(name)
            if current_item is None:
                _debug(f"port_access_diff: {kind}/{name} missing on device")
                needs_change.append(item)
                continue
            if not matcher(item, current_item):
                _debug(f"port_access_diff: {kind}/{name} differs from device")
                needs_change.append(item)

        out[kind] = needs_change
        _debug(
            f"port_access_diff: {kind} - "
            f"{len(needs_change)}/{len(desired_list)} need configuration"
        )

    return out


def port_access_facts_from_device_profiles(profiles_payload):
    """
    Flatten ``/system/device_profiles?depth=4`` REST payload into the
    ``aoscx_port_access_facts`` shape expected by ``port_access_diff``.

    The depth=4 response nests each profile's ``role``, ``lldp_groups`` and
    ``mac_groups`` inline, so a single REST call is enough to compare every
    object kind. This filter merges those nested dicts up to the top level.

    Args:
        profiles_payload: dict keyed by profile name, e.g.
            ``{"LAB-SW": {"role": {"LAB-SW01": {...}},
                          "lldp_groups": {"AP-group": {...}}, ...}, ...}``.
            ``None`` / non-dict / empty inputs return empty sub-dicts.

    Returns:
        dict with keys ``device_profiles``, ``roles``, ``lldp_groups``,
        ``mac_groups``. Each value is a flat dict keyed by object name. If
        the same role/group name appears under multiple profiles the last
        one wins (the device guarantees uniqueness, so this is just a
        defensive merge).
    """
    out = {
        "device_profiles": {},
        "roles": {},
        "lldp_groups": {},
        "mac_groups": {},
    }
    if not isinstance(profiles_payload, dict):
        return out

    out["device_profiles"] = profiles_payload

    for profile in profiles_payload.values():
        if not isinstance(profile, dict):
            continue
        for src_key, dst_key in (
            ("role", "roles"),
            ("lldp_groups", "lldp_groups"),
            ("mac_groups", "mac_groups"),
        ):
            sub = profile.get(src_key)
            if isinstance(sub, dict):
                out[dst_key].update(sub)

    return out
