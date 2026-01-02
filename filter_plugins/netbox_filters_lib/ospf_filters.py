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


def validate_ospf_config(device_config, interfaces):
    """
    Validate OSPF configuration consistency

    Args:
        device_config (dict): Device configuration from NetBox
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
    device_areas = device_config.get("config_context", {}).get("ospf_areas", [])
    device_area_ids = [area.get("ospf_1_area") for area in device_areas]

    _debug(f"Device OSPF areas from config_context: {device_area_ids}")

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
