"""
VSX configuration comparison helpers.

Compares NetBox config_context desired state against REST API ``aoscx_vsx_facts``
and returns a dict describing what needs to change.

REST API response shape (depth=1):
  device_role   → str  ("primary" / "secondary")
  system_mac    → str  ("02:00:00:00:01:00")
  isl_port      → dict ({"lag256": "/rest/…"})
  keepalive_vrf → dict ({"keepalive": "/rest/…"})
  keepalive_src_ip  → str
  keepalive_peer_ip → str
"""


def _extract_dict_key(value):
    """Return the first key of *value* if it is a non-empty dict, else value."""
    if isinstance(value, dict) and value:
        return next(iter(value))
    return value


def vsx_config_diff(desired, facts):
    """Compare desired VSX config against device facts.

    Args:
        desired: dict with keys from NetBox config_context:
            vsx_role, vsx_system_mac, vsx_isl_lag (or vsx_isl_port),
            vsx_keepalive_vrf, vsx_keepalive_src, vsx_keepalive_peer
        facts: ``aoscx_vsx_facts`` dict from REST API (may be empty/None).

    Returns:
        dict with:
            changed (bool): True when at least one field differs.
            changes (list[dict]): per-field diffs with keys
                field, expected, actual.
    """
    if not isinstance(desired, dict):
        return {"changed": False, "changes": []}
    if not isinstance(facts, dict):
        facts = {}

    field_map = [
        ("device_role", desired.get("vsx_role"), facts.get("device_role")),
        ("system_mac", desired.get("vsx_system_mac"), facts.get("system_mac")),
        (
            "isl_port",
            desired.get("vsx_isl_lag") or desired.get("vsx_isl_port"),
            _extract_dict_key(facts.get("isl_port")),
        ),
        (
            "keepalive_vrf",
            desired.get("vsx_keepalive_vrf"),
            _extract_dict_key(facts.get("keepalive_vrf")),
        ),
        (
            "keepalive_src_ip",
            desired.get("vsx_keepalive_src"),
            facts.get("keepalive_src_ip"),
        ),
        (
            "keepalive_peer_ip",
            desired.get("vsx_keepalive_peer"),
            facts.get("keepalive_peer_ip"),
        ),
    ]

    changes = []
    for field, expected, actual in field_map:
        if expected is None:
            continue
        norm_expected = str(expected).lower()
        norm_actual = str(actual).lower() if actual is not None else ""
        if norm_expected != norm_actual:
            changes.append(
                {"field": field, "expected": expected, "actual": actual}
            )

    return {"changed": len(changes) > 0, "changes": changes}
