#!/usr/bin/env python3
"""
OSPF-related filters for NetBox data transformation

Provides functions to select, filter, and validate OSPF interface configurations
from NetBox data for use with Aruba AOS-CX switches.
"""

from .utils import _debug, _to_dict


def select_ospf_interfaces(interfaces):
    """
    Filter interfaces that have OSPF configuration defined

    Args:
        interfaces (list): List of interface objects from NetBox

    Returns:
        list: Filtered list of interfaces with OSPF configuration
    """
    if not interfaces:
        _debug("No interfaces provided to select_ospf_interfaces")
        return []

    ospf_interfaces = []

    for interface in interfaces:
        # Check if interface has OSPF area configuration
        ospf_area = interface.get("custom_fields", {}).get("if_ip_ospf_1_area")
        if ospf_area and ospf_area not in [None, "", "null"]:
            ospf_interfaces.append(interface)
            _debug(f"Found OSPF interface: {interface.get('name')} (area: {ospf_area})")

    _debug(f"Total OSPF interfaces found: {len(ospf_interfaces)}")
    return ospf_interfaces


def extract_ospf_areas(interfaces):
    """
    Extract unique OSPF areas from interfaces

    Args:
        interfaces (list): List of interface objects from NetBox

    Returns:
        list: List of unique OSPF area IDs
    """
    if not interfaces:
        _debug("No interfaces provided to extract_ospf_areas")
        return []

    areas = set()

    for interface in interfaces:
        area = interface.get("custom_fields", {}).get("if_ip_ospf_1_area")
        if area and area not in [None, "", "null"]:
            areas.add(area)

    sorted_areas = sorted(list(areas))
    _debug(f"Extracted OSPF areas: {sorted_areas}")
    return sorted_areas


def get_ospf_interfaces_by_area(interfaces, area_id):
    """
    Get interfaces belonging to a specific OSPF area

    Args:
        interfaces (list): List of interface objects from NetBox
        area_id (str): OSPF area ID to filter by

    Returns:
        list: List of interfaces in the specified area
    """
    if not interfaces or not area_id:
        _debug(f"Missing inputs: interfaces={bool(interfaces)}, area_id={area_id}")
        return []

    area_interfaces = []

    for interface in interfaces:
        if interface.get("custom_fields", {}).get("if_ip_ospf_1_area") == area_id:
            area_interfaces.append(interface)
            _debug(f"Interface {interface.get('name')} belongs to area {area_id}")

    _debug(f"Found {len(area_interfaces)} interfaces in OSPF area {area_id}")
    return area_interfaces


def normalize_ospf_vrfs(ospf_vrfs, ospf_1_vrf=None, ospf_areas=None):
    """
    Normalize NetBox OSPF router/area config context into a single shape.

    Supports both the recommended multi-VRF format (``ospf_vrfs``) and the
    legacy single-VRF format (``ospf_1_vrf`` + ``ospf_areas``, where each
    area entry uses the ``ospf_1_area`` key instead of ``area``). Used by
    both `tasks/configure_ospf.yml` (to build the VRF/area push list) and
    `tasks/gather_facts_rest_api.yml` (to build the REST query list for
    `aoscx_ospf_router_facts`), so the two stay in sync.

    Args:
        ospf_vrfs (list): Multi-VRF config context
            (``[{'vrf': str, 'areas': [{'area': str}, ...]}, ...]``), or
            None/empty if not used.
        ospf_1_vrf (str): Legacy single-VRF name, or None if not used.
        ospf_areas (list): Legacy single-VRF area list
            (``[{'ospf_1_area': str}, ...]`` or ``[{'area': str}, ...]``),
            or None if not used.

    Returns:
        list: Normalized ``[{'vrf': str, 'areas': [{'area': str}, ...]}, ...]``.
        Empty list when neither format is provided.
    """
    if ospf_vrfs:
        return ospf_vrfs

    if ospf_1_vrf is not None or ospf_areas:
        areas = []
        for area_entry in ospf_areas or []:
            area_id = area_entry.get("area") or area_entry.get("ospf_1_area")
            if area_id:
                areas.append({"area": area_id})
        return [{"vrf": ospf_1_vrf or "default", "areas": areas}]

    return []


def filter_ospf_vrfs_in_use(ospf_vrfs, vrf_names_in_use):
    """
    Drop OSPF VRF/area entries for VRFs that are not actually in use.

    Config context can list OSPF areas for VRFs that exist in NetBox but
    have no interfaces assigned on this particular device. Pushing OSPF
    router/area config for those VRFs fails (or creates config drift)
    because the VRF itself is never created on the switch. The built-in
    'default' VRF is always exempt since it always exists on the device
    regardless of interface assignment.

    Args:
        ospf_vrfs (list): Normalized OSPF VRF config
            (``[{'vrf': str, 'areas': [...]}, ...]``) as produced by
            `normalize_ospf_vrfs`.
        vrf_names_in_use (list): VRF names actually in use on the device,
            e.g. from ``get_vrfs_in_use(...)['vrf_names']``. Built-in VRFs
            such as 'default' are not expected to appear in this list.

    Returns:
        list: `ospf_vrfs` entries whose VRF is 'default' or present in
        `vrf_names_in_use`.
    """
    if not ospf_vrfs:
        return []

    vrf_names_in_use = set(vrf_names_in_use or [])
    filtered = []
    for entry in ospf_vrfs:
        vrf_name = entry.get("vrf")
        if vrf_name == "default" or vrf_name in vrf_names_in_use:
            filtered.append(entry)
        else:
            _debug(f"Skipping OSPF config for VRF '{vrf_name}' - not in use on device")

    return filtered


def validate_ospf_config(device_config, interfaces):
    """
    Validate OSPF configuration consistency

    Args:
        device_config (dict): Device configuration from NetBox.
                             Can be either nested (with config_context key) or flattened
                             (when using NetBox inventory with plurals: true)
        interfaces (list): List of interface objects from NetBox

    Returns:
        dict: Validation results with warnings and errors
    """
    validation = {"valid": True, "warnings": [], "errors": []}

    _debug("Validating OSPF configuration...")

    # Check if router ID is defined when OSPF interfaces exist
    ospf_interfaces = select_ospf_interfaces(interfaces)
    router_id = device_config.get("custom_fields", {}).get("device_ospf_1_routerid")

    _debug(f"OSPF interfaces: {len(ospf_interfaces)}, Router ID: {router_id}")

    if ospf_interfaces and not router_id:
        validation["warnings"].append(
            "OSPF interfaces configured but no router ID defined"
        )
        _debug("Warning: OSPF interfaces exist but no router ID defined")

    # Check if all interface areas are defined in device areas
    # Support both nested config_context and flattened structure
    if "config_context" in device_config:
        # Nested structure (backward compatibility)
        device_areas = device_config.get("config_context", {}).get("ospf_areas", [])
        _debug("Using nested config_context structure")
    else:
        # Flattened structure (NetBox inventory with plurals: true)
        device_areas = device_config.get("ospf_areas", [])
        _debug("Using flattened structure (plurals: true)")

    device_area_ids = [area.get("ospf_1_area") for area in device_areas]

    _debug(f"Device OSPF areas: {device_area_ids}")

    interface_areas = extract_ospf_areas(interfaces)

    for area in interface_areas:
        if area not in device_area_ids:
            validation["warnings"].append(
                f"Interface references OSPF area {area} but area not defined in device config"
            )
            _debug(f"Warning: Area {area} not in device config")

    if validation["warnings"]:
        _debug(f"OSPF validation completed with {len(validation['warnings'])} warnings")
    else:
        _debug("OSPF validation completed successfully - no issues found")

    return validation


def get_ospf_router_changes(ospf_config, ospf_router_facts=None):
    """
    Categorize which OSPF router instances/areas actually need configuration
    changes, comparing NetBox desired state against device REST facts -
    mirroring `get_vrf_changes` so `configure_ospf.yml` only pushes the diff
    instead of relying solely on `aoscx_ospf_router`/`aoscx_ospf_area`'s own
    idempotency.

    When facts are unavailable (``ospf_router_facts`` is ``None`` - REST API
    fact gathering disabled, or OSPF facts not gathered for this device),
    every desired VRF/area is returned for push, matching the role's previous
    behaviour - same convention as `get_vrf_changes`.

    Args:
        ospf_config: Normalized OSPF config as built in
            `tasks/identify_ospf_changes.yml` - ``{'process_id': int,
            'router_id': str, 'vrfs': [{'vrf': str, 'areas': [{'area': str},
            ...]}, ...]}``.
        ospf_router_facts: Device REST facts (``aoscx_ospf_router_facts``) -
            ``{vrf: {process_id_str: {'router_id': str, 'areas': [...],
            'passive_interfaces': [...]}}}``, or ``None``/not a dict when
            unavailable.

    Returns:
        dict with:
        - router_changes: list of VRF entries (from ``ospf_config['vrfs']``)
          whose router-id needs (re)configuring.
        - area_additions: list of ``{'vrf': str, 'area': str}`` for areas
          not yet present on the device.
        - no_changes: list of VRF names with nothing to push.
    """
    facts_available = isinstance(ospf_router_facts, dict)
    process_id = str(ospf_config.get("process_id", 1))
    router_id = ospf_config.get("router_id") or ""
    vrfs = ospf_config.get("vrfs") or []

    router_changes = []
    area_additions = []
    no_changes = []

    for vrf_entry in vrfs:
        vrf_name = vrf_entry.get("vrf")
        areas = vrf_entry.get("areas") or []
        changed = False

        actual = _to_dict(ospf_router_facts.get(vrf_name)) if facts_available else {}
        actual = _to_dict(actual.get(process_id))

        if router_id:
            actual_router_id = actual.get("router_id") or ""
            if not facts_available or actual_router_id != router_id:
                _debug(f"OSPF router-id for VRF {vrf_name} differs from device state - will set")
                router_changes.append(vrf_entry)
                changed = True

        actual_areas = set(actual.get("areas") or []) if facts_available else set()
        for area_entry in areas:
            area_id = area_entry.get("area")
            if not area_id:
                continue
            if not facts_available or area_id not in actual_areas:
                _debug(f"OSPF area {area_id} for VRF {vrf_name} not on device - will add")
                area_additions.append({"vrf": vrf_name, "area": area_id})
                changed = True

        if not changed:
            no_changes.append(vrf_name)

    return {
        "router_changes": router_changes,
        "area_additions": area_additions,
        "no_changes": no_changes,
    }


def get_ospf_interface_changes(
    ospf_interface_items, ospf_interface_facts=None, ospf_router_facts=None, process_id=1
):
    """
    Categorize which per-interface OSPF settings actually need configuration
    changes, comparing NetBox desired state against device REST facts -
    mirroring `get_vrf_changes`/`get_ospf_router_changes` so
    `configure_ospf.yml` only pushes the diff instead of unconditionally
    looping over every OSPF interface on every run.

    Reuses the same network-type enum mapping and MD5-auth-presence
    semantics as `l3_config_helpers.group_interface_ips` /
    `configure_ospf.yml`'s inline auth computation, so the three stay
    consistent.

    When facts are unavailable (``ospf_interface_facts`` /
    ``ospf_router_facts`` is ``None`` - REST API fact gathering disabled),
    every item is returned for push, matching the role's previous
    behaviour.

    Args:
        ospf_interface_items: List of per-interface dicts as built in
            `tasks/identify_ospf_changes.yml` - each with keys
            ``interface_name``, ``vrf``, ``area_id``, ``network_type``,
            ``passive`` (bool), and ``md5_auth_desired`` (bool, precomputed
            from ``ospf_auth_keys``/``ospf_auth_key_id``).
        ospf_interface_facts: Device REST facts
            (``aoscx_ospf_interface_facts``) - ``{vrf: {process_id_str:
            {area: {intf_name: {'ospf_if_type': ..., 'ospf_auth_type':
            ...}}}}}``, or ``None``/not a dict when unavailable.
        ospf_router_facts: Device REST facts (``aoscx_ospf_router_facts``) -
            used here only for ``passive_interfaces``, or ``None``/not a
            dict when unavailable.
        process_id: OSPF process ID to look up in the facts (default: 1).

    Returns:
        dict with:
        - config_changes: items needing area/network-type/authentication
          reconciled via `aoscx_config`.
        - passive_set: items needing `ip ospf passive` pushed.
        - passive_clear: items needing `no ip ospf passive` pushed.
        - no_changes: interface names with nothing to push.
    """
    facts_available = isinstance(ospf_interface_facts, dict)
    router_facts_available = isinstance(ospf_router_facts, dict)
    pid_str = str(process_id)

    config_changes = []
    passive_set = []
    passive_clear = []
    no_changes = []

    for item in ospf_interface_items or []:
        intf_name = item.get("interface_name")
        vrf_name = item.get("vrf") or "default"
        area_id = item.get("area_id")
        network_type = item.get("network_type") or ""
        passive = bool(item.get("passive"))
        md5_auth_desired = bool(item.get("md5_auth_desired"))
        is_loopback = "loopback" in (intf_name or "")

        changed = False

        area_data = {}
        if facts_available:
            vrf_facts = _to_dict(ospf_interface_facts.get(vrf_name))
            pid_facts = _to_dict(vrf_facts.get(pid_str))
            area_data = _to_dict(pid_facts.get(area_id))

        if not facts_available or intf_name not in area_data:
            _debug(f"OSPF interface {intf_name} not registered in area {area_id} - will configure")
            config_changes.append(item)
            changed = True
        else:
            intf_facts = _to_dict(area_data.get(intf_name))
            current_type = intf_facts.get("ospf_if_type")

            if network_type and network_type != "loopback":
                # AOS-CX REST OSPF interface-type enum does not mirror
                # NetBox's hyphenated values 1:1 (e.g. point-to-point ->
                # ospf_iftype_pointopoint) - matches how the AOS-CX Ansible
                # collection builds it: type.replace('-', '').replace('tt', 't').
                desired_type = "ospf_iftype_" + network_type.replace("-", "").replace(
                    "tt", "t"
                )
            else:
                desired_type = "ospf_iftype_broadcast"

            if desired_type == "ospf_iftype_broadcast":
                # broadcast is the AOS-CX default network type - the device
                # only stores an explicit ospf_if_type when it differs from
                # broadcast, so a missing/None value in facts is equivalent
                # to broadcast.
                type_changed = current_type not in (None, "ospf_iftype_broadcast")
            else:
                type_changed = current_type != desired_type

            # AOS-CX returns the string "null" (not JSON null) when MD5 auth
            # is disabled.
            current_auth_type = intf_facts.get("ospf_auth_type")
            auth_active = current_auth_type not in (None, "", "null")
            auth_changed = auth_active != md5_auth_desired

            if type_changed or auth_changed:
                _debug(f"OSPF interface {intf_name} config differs from device state - will configure")
                config_changes.append(item)
                changed = True

        if not is_loopback:
            actual_passive_interfaces = set()
            currently_passive = False
            if router_facts_available:
                vrf_router_facts = _to_dict(ospf_router_facts.get(vrf_name))
                pid_router_facts = _to_dict(vrf_router_facts.get(pid_str))
                actual_passive_interfaces = set(
                    pid_router_facts.get("passive_interfaces") or []
                )
                currently_passive = intf_name in actual_passive_interfaces

            if passive:
                if not router_facts_available or not currently_passive:
                    passive_set.append(item)
                    changed = True
            else:
                if not router_facts_available or currently_passive:
                    passive_clear.append(item)
                    changed = True

        if not changed:
            no_changes.append(intf_name)

    return {
        "config_changes": config_changes,
        "passive_set": passive_set,
        "passive_clear": passive_clear,
        "no_changes": no_changes,
    }
