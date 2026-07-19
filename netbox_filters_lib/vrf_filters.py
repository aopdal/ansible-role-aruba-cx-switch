#!/usr/bin/env python3
"""
VRF-related filters for NetBox data transformation
"""

import os
from .utils import _debug, _to_dict


def extract_interface_vrfs(interfaces):
    """
    Extract unique VRF names from interfaces

    Args:
        interfaces: List of interface objects from NetBox

    Returns:
        Set of unique VRF names
    """
    vrf_names = set()

    for interface in interfaces:
        vrf = interface.get("vrf")
        if vrf and vrf is not None:
            vrf_name = vrf.get("name")
            if vrf_name:
                _debug(f"Found VRF '{vrf_name}' on interface {interface.get('name')}")
                vrf_names.add(vrf_name)

    _debug(f"All VRFs found in interfaces: {vrf_names}")
    return vrf_names


def filter_vrfs_in_use(vrfs, interfaces, tenant=None):
    """
    Filter VRFs to only those actually in use on interfaces

    Args:
        vrfs: List of all VRF objects from NetBox
        interfaces: List of interface objects from NetBox
        tenant: Optional tenant slug to filter by

    Returns:
        List of VRF objects that are in use
    """
    vrf_names_in_use = extract_interface_vrfs(interfaces)

    _debug(f"VRFs in use from interfaces: {vrf_names_in_use}")
    _debug(f"Total VRFs from NetBox: {len(vrfs)}")
    _debug(f"Tenant filter: {tenant}")

    if os.environ.get("DEBUG_ANSIBLE", "").lower() in ("true", "1", "yes"):
        for vrf in vrfs:
            _debug(f"Checking VRF: {vrf.get('name')}, tenant: {vrf.get('tenant')}")

    filtered_vrfs = []
    for vrf in vrfs:
        vrf_name = vrf.get("name")

        # Skip if VRF not in use on any interface
        if vrf_name not in vrf_names_in_use:
            _debug(f"Skipping '{vrf_name}' - not in use")
            continue

        # Skip mgmt and Global VRFs
        if vrf_name in ["mgmt", "Global"]:
            _debug(f"Skipping '{vrf_name}' - mgmt or Global")
            continue

        _debug(f"VRF '{vrf_name}' passed initial checks")

        # If tenant filter is specified, check tenant matching
        if tenant:
            vrf_tenant = vrf.get("tenant")
            # Include VRF if it has no tenant or matches the specified tenant
            if vrf_tenant is None:
                _debug(f"Including '{vrf_name}' - no tenant assigned")
                filtered_vrfs.append(vrf)
            elif vrf_tenant.get("slug") == tenant:
                _debug(f"Including '{vrf_name}' - tenant matches")
                filtered_vrfs.append(vrf)
            else:
                _debug(
                    f"Skipping '{vrf_name}' - tenant mismatch: "
                    f"{vrf_tenant.get('slug')} != {tenant}"
                )
        else:
            # If no tenant filter, include all VRFs in use
            _debug(f"Including '{vrf_name}' - no tenant filter")
            filtered_vrfs.append(vrf)

    _debug(f"Final filtered VRFs: {[v.get('name') for v in filtered_vrfs]}")
    return filtered_vrfs


def get_vrfs_in_use(interfaces, ip_addresses=None):
    """
    Extract VRFs that are in use on interfaces

    Args:
        interfaces: List of interface objects from NetBox
        ip_addresses: Optional list of IP address objects

    Returns:
        Dict with:
        - 'vrf_names': Set of VRF names in use (excluding built-in VRFs)
        - 'vrfs': Dict of VRF objects keyed by name
    """
    vrfs_in_use = {}  # Dict keyed by VRF name
    vrf_names = set()

    # Built-in VRFs that should not be configured
    builtin_vrfs = {"mgmt", "MGMT", "Global", "global", "default", "Default"}

    # Ensure interfaces is not None
    if not interfaces:
        interfaces = []

    # Process interfaces
    for intf in interfaces:
        if not intf:
            continue

        # Skip management interfaces (they're always in mgmt VRF)
        if intf.get("mgmt_only"):
            continue

        # Get VRF from interface
        vrf_obj = intf.get("vrf")
        if vrf_obj and isinstance(vrf_obj, dict):
            vrf_name = vrf_obj.get("name")
            if vrf_name and vrf_name not in builtin_vrfs:
                vrf_names.add(vrf_name)
                vrfs_in_use[vrf_name] = vrf_obj

    # Also check IP addresses if provided
    if ip_addresses:
        for ip_obj in ip_addresses:
            if not ip_obj or not isinstance(ip_obj, dict):
                continue

            vrf_obj = ip_obj.get("vrf")
            if vrf_obj and isinstance(vrf_obj, dict):
                vrf_name = vrf_obj.get("name")
                if vrf_name and vrf_name not in builtin_vrfs:
                    vrf_names.add(vrf_name)
                    vrfs_in_use[vrf_name] = vrf_obj

    result = {"vrf_names": sorted(list(vrf_names)), "vrfs": vrfs_in_use}

    _debug(
        f"Found {len(result['vrf_names'])} configurable VRFs in use: "
        f"{result['vrf_names']}"
    )
    _debug(f"Built-in VRFs filtered out: {builtin_vrfs}")

    return result


def get_all_rt_names(vrf_details):
    """
    Extract all unique route target names from VRF export/import targets.

    Args:
        vrf_details: Dict of VRF name -> VRF object (from NetBox nb_lookup),
                     each containing 'export_targets' and 'import_targets' lists.

    Returns:
        Sorted list of unique RT name strings.
    """
    rt_names = set()
    for vrf in vrf_details.values():
        vrf = _to_dict(vrf)
        for rt in vrf.get("export_targets") or []:
            rt = _to_dict(rt) if not isinstance(rt, str) else {"name": rt}
            name = rt.get("name")
            if name:
                rt_names.add(name)
        for rt in vrf.get("import_targets") or []:
            rt = _to_dict(rt) if not isinstance(rt, str) else {"name": rt}
            name = rt.get("name")
            if name:
                rt_names.add(name)
    return sorted(rt_names)


def build_vrf_rt_config(vrf_details):
    """
    Build address-family-aware route target config grouped per VRF.

    Reads the 'address_family' custom field directly from the RT objects
    embedded in each VRF's export_targets / import_targets (values: 'ipv4'
    or 'ipv6').  Defaults to 'ipv4' if the custom field is absent or
    unrecognised.

    nb_lookup for VRFs already returns full RT objects (including
    custom_fields) nested inside export_targets and import_targets, so no
    separate RT lookup is needed.

    Args:
        vrf_details: Dict of VRF name -> VRF object (from nb_lookup .value)
                     with export/import_targets containing full RT objects.

    Returns:
        Dict keyed by VRF name, each value being::

            {
                'ipv4': {'export': [...rt_names...], 'import': [...rt_names...]},
                'ipv6': {'export': [...rt_names...], 'import': [...rt_names...]},
            }
    """
    result = {}
    valid_afs = ("ipv4", "ipv6")

    for vrf_name, vrf in vrf_details.items():
        entry = {
            "ipv4": {"export": [], "import": []},
            "ipv6": {"export": [], "import": []},
        }

        vrf = _to_dict(vrf)
        for direction in ("export_targets", "import_targets"):
            dir_key = direction.replace("_targets", "")  # 'export' or 'import'
            for rt in vrf.get(direction) or []:
                rt = _to_dict(rt)
                rt_name = rt.get("name")
                if not rt_name:
                    continue
                af = _to_dict(rt.get("custom_fields") or {}).get(
                    "address_family", "ipv4"
                )
                if af not in valid_afs:
                    af = "ipv4"
                entry[af][dir_key].append(rt_name)

        result[vrf_name] = entry

    return result


def get_vrf_rt_removals(vrf_rt_config, vrf_rt_facts=None):
    """
    Compute route-targets present on the device but no longer desired in
    NetBox, so they can be removed with ``no route-target <direction> <rt>``.

    Route-target *additions* stay idempotent via ``aoscx_config``'s
    ``match: line`` (it already skips lines already present on the device),
    so this filter only closes the "stale RT" gap - it does not need to
    compute anything to add.

    Args:
        vrf_rt_config: Desired config as returned by ``build_vrf_rt_config``,
            keyed by VRF name::

                {'ipv4': {'export': [...], 'import': [...]},
                 'ipv6': {'export': [...], 'import': [...]}}

        vrf_rt_facts: Current device state (``aoscx_vrf_rt_facts``, gathered
            via REST API), same per-VRF shape as ``vrf_rt_config``, or
            ``None`` when REST API fact gathering is disabled - in that case
            there is no reliable view of device state to diff against, so no
            removals are computed.

    Returns:
        List of dicts, each ``{'vrf': ..., 'address_family': 'ipv4'|'ipv6',
        'direction': 'export'|'import', 'rt': <rt_name>}``.
    """
    if not isinstance(vrf_rt_facts, dict):
        _debug("No vrf_rt_facts provided - no route-target removals computed")
        return []

    empty_af = {"export": [], "import": []}
    removals = []

    for vrf_name, actual_afs in vrf_rt_facts.items():
        actual_afs = _to_dict(actual_afs)
        desired_afs = vrf_rt_config.get(vrf_name) or {}
        for af in ("ipv4", "ipv6"):
            desired_af = desired_afs.get(af) or empty_af
            actual_af = _to_dict(actual_afs.get(af)) or empty_af
            for direction in ("export", "import"):
                desired_rts = set(desired_af.get(direction) or [])
                actual_rts = set(actual_af.get(direction) or [])
                for rt in sorted(actual_rts - desired_rts):
                    _debug(
                        f"VRF {vrf_name} {af} {direction} route-target {rt} "
                        "not in NetBox - will remove"
                    )
                    removals.append(
                        {
                            "vrf": vrf_name,
                            "address_family": af,
                            "direction": direction,
                            "rt": rt,
                        }
                    )

    return removals


def get_vrf_changes(vrfs_in_use, vrf_rt_config, vrf_facts=None, vrf_rt_facts=None):
    """
    Categorize which VRFs actually need configuration changes, comparing
    NetBox desired state against device REST facts - mirroring the
    interface/VLAN change-identification pattern so ``configure_vrfs.yml``
    only pushes the diff instead of relying solely on ``aoscx_vrf``'s own
    idempotency and ``aoscx_config``'s ``match: line`` to no-op unnecessary
    pushes.

    When facts are unavailable (``vrf_facts``/``vrf_rt_facts`` is ``None`` -
    REST API fact gathering disabled), every desired VRF/RD/RT is returned
    for push, matching the role's previous behaviour (push everything, let
    the module/CLI match handle idempotency) - same convention as
    ``get_static_route_changes`` and ``get_vrf_rt_removals``.

    Args:
        vrfs_in_use: ``get_vrfs_in_use()`` output - ``{'vrf_names': [...],
            'vrfs': {name: vrf_obj}}``, where each ``vrf_obj`` may carry an
            ``rd`` key (NetBox's nested VRF serializer includes it).
        vrf_rt_config: ``build_vrf_rt_config()`` output - ``{name: {'ipv4':
            {'export': [...], 'import': [...]}, 'ipv6': {...}}}``.
        vrf_facts: Device REST facts (``aoscx_vrf_facts``) - ``{name: {'rd':
            <str or None>}, ...}``, or ``None`` when unavailable.
        vrf_rt_facts: Device REST facts (``aoscx_vrf_rt_facts``), same shape
            as ``vrf_rt_config``, or ``None`` when unavailable.

    Returns:
        dict: ``{
            'to_create': [vrf_name, ...],
            'rd_changes': [{'vrf': ..., 'rd': ...}, ...],
            'rt_additions': [{'vrf': ..., 'address_family': ..., 'direction': ..., 'rt': ...}, ...],
            'rt_removals': [... same shape as rt_additions ...],
            'no_changes': [vrf_name, ...],
        }``
    """
    vrf_names = (vrfs_in_use or {}).get("vrf_names") or []
    vrf_objs = (vrfs_in_use or {}).get("vrfs") or {}
    vrf_rt_config = vrf_rt_config or {}

    facts_available = isinstance(vrf_facts, dict)
    rt_facts_available = isinstance(vrf_rt_facts, dict)

    empty_af = {"export": [], "import": []}
    to_create = []
    rd_changes = []
    rt_additions = []
    no_changes = []

    for vrf_name in vrf_names:
        changed = False

        actual_vrf = vrf_facts.get(vrf_name) if facts_available else None
        if not facts_available or actual_vrf is None:
            _debug(f"VRF {vrf_name} not found on device (or facts unavailable) - will create")
            to_create.append(vrf_name)
            changed = True

        desired_rd = (vrf_objs.get(vrf_name) or {}).get("rd") or None
        if desired_rd:
            actual_rd = _to_dict(actual_vrf).get("rd") or None
            if not facts_available or actual_rd != desired_rd:
                _debug(f"VRF {vrf_name} RD differs from device state - will set to {desired_rd}")
                rd_changes.append({"vrf": vrf_name, "rd": desired_rd})
                changed = True

        desired_afs = vrf_rt_config.get(vrf_name) or {}
        actual_afs = _to_dict(vrf_rt_facts.get(vrf_name)) if rt_facts_available else {}
        for af in ("ipv4", "ipv6"):
            desired_af = desired_afs.get(af) or empty_af
            actual_af = _to_dict(actual_afs.get(af)) or empty_af
            for direction in ("export", "import"):
                desired_rts = set(desired_af.get(direction) or [])
                actual_rts = set(actual_af.get(direction) or []) if rt_facts_available else set()
                missing = desired_rts if not rt_facts_available else (desired_rts - actual_rts)
                for rt in sorted(missing):
                    _debug(f"VRF {vrf_name} {af} {direction} route-target {rt} not on device - will add")
                    rt_additions.append(
                        {"vrf": vrf_name, "address_family": af, "direction": direction, "rt": rt}
                    )
                    changed = True

        if not changed:
            no_changes.append(vrf_name)

    rt_removals = get_vrf_rt_removals(vrf_rt_config, vrf_rt_facts)
    vrfs_with_removals = {removal["vrf"] for removal in rt_removals}
    no_changes = [vrf_name for vrf_name in no_changes if vrf_name not in vrfs_with_removals]

    return {
        "to_create": to_create,
        "rd_changes": rd_changes,
        "rt_additions": rt_additions,
        "rt_removals": rt_removals,
        "no_changes": no_changes,
    }


def filter_configurable_vrfs(vrfs):
    """
    Filter out VRFs that should not be configured (built-in VRFs)

    Args:
        vrfs: List of VRF objects or VRF names

    Returns:
        List of configurable VRFs
    """
    if not vrfs:
        return []

    # Built-in, non-configurable VRFs
    builtin_vrfs = {"mgmt", "MGMT", "Global", "global", "default", "Default"}
    configurable = []

    for vrf in vrfs:
        if isinstance(vrf, dict):
            vrf_name = vrf.get("name")
        elif isinstance(vrf, str):
            vrf_name = vrf
        else:
            continue

        if vrf_name and vrf_name not in builtin_vrfs:
            configurable.append(vrf)
            _debug(f"VRF {vrf_name} is configurable")
        else:
            _debug(f"VRF {vrf_name} is built-in/non-configurable - skipping")

    return configurable
