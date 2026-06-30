"""
STP (Spanning Tree Protocol) interface configuration helpers.

Compares NetBox custom field desired state against switch REST API stp_config
facts and returns per-interface CLI command lists for change-only applies.

NetBox custom field → REST API stp_config field mapping:
  if_stp_bpdu_filter  → stp_config.bpdu_filter_enable
  if_stp_bpdu_guard   → stp_config.bpdu_guard_enable
  if_stp_edge_port    → stp_config.admin_edge_port_enable
  if_stp_root_guard   → stp_config.root_guard_enable
"""

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
