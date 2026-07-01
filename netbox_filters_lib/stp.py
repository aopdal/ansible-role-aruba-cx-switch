"""
STP (Spanning Tree Protocol) configuration helpers.

Global MSTP comparison:
  Compares NetBox config_context (mstp_config_name, mstp_config_revision,
  mstp_priority) against REST API ``/system?attributes=stp_config&depth=1``
  response stored as ``aoscx_stp_global_facts``.

Per-interface comparison:
  Compares NetBox custom field desired state against switch REST API stp_config
  facts and returns per-interface CLI command lists for change-only applies.

  NetBox custom field → REST API stp_config field mapping:
    if_stp_bpdu_filter  → stp_config.bpdu_filter_enable
    if_stp_bpdu_guard   → stp_config.bpdu_guard_enable
    if_stp_edge_port    → stp_config.admin_edge_port_enable
    if_stp_root_guard   → stp_config.root_guard_enable
"""

_STP_DEFAULT_PRIORITY = 8

# (netbox_cf_field, device_stp_field, enable_cli_command)
_STP_FIELD_MAP = [
    ("if_stp_bpdu_filter", "bpdu_filter_enable", "spanning-tree bpdu-filter"),
    ("if_stp_bpdu_guard", "bpdu_guard_enable", "spanning-tree bpdu-guard"),
    (
        "if_stp_edge_port",
        "admin_edge_port_enable",
        "spanning-tree port-type admin-edge",
    ),
    ("if_stp_root_guard", "root_guard_enable", "spanning-tree root-guard"),
]


def stp_global_config_diff(desired, facts):
    """Compare desired global MSTP config against device REST API facts.

    Args:
        desired: dict with NetBox config_context keys:
            mstp_config_name, mstp_config_revision, mstp_priority
        facts: ``aoscx_stp_global_facts`` dict from REST API (the stp_config
            object from ``/system?attributes=stp_config&depth=1``).

    Returns:
        dict with:
            changed (bool): True when at least one field differs.
            changes (list[dict]): per-field diffs (field, expected, actual).
            lines (list[str]): CLI lines needed to apply the changes.
    """
    if not isinstance(desired, dict):
        return {"changed": False, "changes": [], "lines": []}
    if not isinstance(facts, dict):
        facts = {}

    config_name = desired.get("mstp_config_name")
    if config_name is None:
        return {"changed": False, "changes": [], "lines": []}

    config_revision = str(desired.get("mstp_config_revision", 0))
    priority = str(desired.get("mstp_priority", _STP_DEFAULT_PRIORITY))

    field_map = [
        ("config_name", config_name, facts.get("mstp_config_name")),
        ("config_revision", config_revision, str(facts.get("mstp_config_revision", ""))),
        ("priority", priority, str(facts.get("priority", ""))),
    ]

    changes = []
    for field, expected, actual in field_map:
        if str(expected).lower() != str(actual).lower():
            changes.append({"field": field, "expected": expected, "actual": actual})

    lines = []
    if changes:
        lines.append("spanning-tree")
        lines.append(f"spanning-tree priority {priority}")
        lines.append(f"spanning-tree config-name {config_name}")
        lines.append(f"spanning-tree config-revision {config_revision}")

    return {"changed": len(changes) > 0, "changes": changes, "lines": lines}


def stp_interface_changes(interfaces, enhanced_facts):
    """Return L2 interfaces that need STP config changes.

    Only L2 interfaces (mode is defined and not None) are considered.
    For each interface, only custom fields explicitly set in NetBox (not None)
    are evaluated.  A change entry is produced when the desired value differs
    from the current device state.

    Args:
        interfaces: list of NetBox interface dicts
        enhanced_facts: aoscx_enhanced_interface_facts dict (raw REST API
                        response keyed by interface name, as stored by
                        gather_facts_rest_api.yml)

    Returns:
        List of {"name": str, "lines": [str]} — only interfaces with changes.
        "lines" contains AOS-CX CLI commands (e.g. "spanning-tree bpdu-guard"
        or "no spanning-tree bpdu-guard").
    """
    if not isinstance(interfaces, list):
        return []
    if not isinstance(enhanced_facts, dict):
        enhanced_facts = {}

    result = []
    for intf in interfaces:
        if not isinstance(intf, dict):
            continue
        # L2 interfaces have mode set (access / tagged / tagged-all).
        # Routed (L3) and unset interfaces are skipped.
        if intf.get("mode") is None:
            continue

        cf = intf.get("custom_fields") or {}
        intf_name = intf.get("name", "")
        device_stp = ((enhanced_facts.get(intf_name) or {}).get("stp_config")) or {}

        lines = []
        for cf_field, device_field, enable_cmd in _STP_FIELD_MAP:
            cf_value = cf.get(cf_field)
            if cf_value is None:
                # Not set in NetBox — leave device setting unchanged.
                continue
            desired = bool(cf_value)
            current = bool(device_stp.get(device_field, False))
            if desired != current:
                lines.append(enable_cmd if desired else f"no {enable_cmd}")

        if lines:
            result.append({"name": intf_name, "lines": lines})

    return result
