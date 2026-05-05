"""
Identify orphaned port-access objects (device-profiles, roles, lldp-groups, mac-groups)

Returns a dict with keys:
- device_profiles: list of orphaned device-profile names
- roles: list of orphaned role names
- lldp_groups: list of orphaned lldp-group names
- mac_groups: list of orphaned mac-group names

Args:
    desired: NetBox config_context['port_access'] dict
    current: aoscx_port_access_facts dict (from REST API)

Orphan = present on device but not in NetBox.
"""


def port_access_orphans(desired, current):
    out = {k: [] for k in ("device_profiles", "roles", "lldp_groups", "mac_groups")}
    if not isinstance(current, dict):
        return out
    if not isinstance(desired, dict):
        desired = {}
    # For each kind, find names present in current but not in desired
    for kind in out:
        current_names = set((current.get(kind) or {}).keys())
        desired_names = set(
            x["name"]
            for x in (desired.get(kind) or [])
            if isinstance(x, dict) and "name" in x
        )
        out[kind] = sorted(current_names - desired_names)
    return out


def filters():
    return {"port_access_orphans": port_access_orphans}
