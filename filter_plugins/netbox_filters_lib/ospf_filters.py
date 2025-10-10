"""
OSPF-related filters for NetBox data transformation
"""


def select_ospf_interfaces(interfaces):
    """
    Filter interfaces that have OSPF configuration defined

    Args:
        interfaces (list): List of interface objects from NetBox

    Returns:
        list: Filtered list of interfaces with OSPF configuration
    """
    if not interfaces:
        return []

    ospf_interfaces = []

    for interface in interfaces:
        # Check if interface has OSPF area configuration
        if interface.get("custom_fields", {}).get("if_ip_ospf_1_area") and interface[
            "custom_fields"
        ]["if_ip_ospf_1_area"] not in [None, "", "null"]:
            ospf_interfaces.append(interface)

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
        return []

    areas = set()

    for interface in interfaces:
        area = interface.get("custom_fields", {}).get("if_ip_ospf_1_area")
        if area and area not in [None, "", "null"]:
            areas.add(area)

    return sorted(list(areas))


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
        return []

    area_interfaces = []

    for interface in interfaces:
        if interface.get("custom_fields", {}).get("if_ip_ospf_1_area") == area_id:
            area_interfaces.append(interface)

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

    # Check if router ID is defined when OSPF interfaces exist
    ospf_interfaces = select_ospf_interfaces(interfaces)
    router_id = device_config.get("custom_fields", {}).get("device_ospf_1_routerid")

    if ospf_interfaces and not router_id:
        validation["warnings"].append(
            "OSPF interfaces configured but no router ID defined"
        )

    # Check if all interface areas are defined in device areas
    device_areas = device_config.get("config_context", {}).get("ospf_areas", [])
    device_area_ids = [area.get("ospf_1_area") for area in device_areas]

    interface_areas = extract_ospf_areas(interfaces)

    for area in interface_areas:
        if area not in device_area_ids:
            validation["warnings"].append(
                f"Interface references OSPF area {area} but area not defined in device config"
            )

    return validation
