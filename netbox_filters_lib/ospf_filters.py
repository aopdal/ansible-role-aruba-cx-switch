#!/usr/bin/env python3
"""
OSPF-related filters for NetBox data transformation

Provides functions to select, filter, and validate OSPF interface configurations
from NetBox data for use with Aruba AOS-CX switches.
"""

from .utils import _debug


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
