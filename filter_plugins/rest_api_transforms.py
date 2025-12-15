"""Transform REST API responses to match aoscx_facts format.

This module provides filters to convert REST API v10.15+ responses
to the format expected by the role's interface change detection logic.

The main differences between REST API and aoscx_facts formats:
- REST API uses 'admin' or 'admin_state', aoscx_facts uses 'admin'
- REST API ip6_addresses is dict with actual addresses at depth=2
- REST API includes vsx_virtual_* fields for anycast/active-gateway
- VLAN IDs in REST API response may be strings or integers
"""

from urllib.parse import unquote


def rest_api_to_aoscx_interfaces(rest_data):
    """Convert REST API interface data to aoscx_facts format.

    Args:
        rest_data: Dict from REST API /system/interfaces?depth=2
                   Format: {"1/1/1": {...}, "vlan10": {...}, ...}

    Returns:
        Dict in aoscx_facts format with normalized interface data

    The REST API returns interface data with these key differences:
    - ip6_addresses: Dict with URL-encoded addresses as keys
    - vsx_virtual_ip4/ip6: Anycast/active-gateway IPs
    - admin or admin_state: Admin status field name varies
    """
    if not isinstance(rest_data, dict):
        return {}

    result = {}
    for intf_name, intf_data in rest_data.items():
        if not isinstance(intf_data, dict):
            # Skip non-dict entries (shouldn't happen but be defensive)
            continue

        # Normalize admin state (REST API may use 'admin' or 'admin_state')
        admin_state = intf_data.get("admin_state") or intf_data.get("admin", "up")

        # Extract IPv6 addresses from the dict format
        # REST API returns: {"2001%3Adb8%3A%3A1%2F64": {...}, ...}
        ip6_addresses = {}
        raw_ip6 = intf_data.get("ip6_addresses")
        if isinstance(raw_ip6, dict):
            for ip6_key, ip6_data in raw_ip6.items():
                # URL-decode the key to get the actual address
                decoded_addr = unquote(ip6_key)
                if isinstance(ip6_data, dict):
                    # Store with decoded address as key
                    ip6_addresses[decoded_addr] = ip6_data
                else:
                    # Simple case - just store the address
                    ip6_addresses[decoded_addr] = {"address": decoded_addr}
        elif isinstance(raw_ip6, str):
            # Fallback: If it's still a URL string (older API version)
            ip6_addresses = raw_ip6

        # Build normalized interface entry
        result[intf_name] = {
            "name": intf_name,
            "admin": admin_state,
            "description": intf_data.get("description", ""),
            "mtu": intf_data.get("mtu"),
            "type": intf_data.get("type"),
            # IPv4 addresses
            "ip4_address": intf_data.get("ip4_address"),
            "ip4_address_secondary": intf_data.get("ip4_address_secondary", []),
            # IPv6 addresses (normalized dict format)
            "ip6_addresses": ip6_addresses,
            # VSX virtual IPs (for anycast/active-gateway)
            "vsx_virtual_ip4": intf_data.get("vsx_virtual_ip4"),
            "vsx_virtual_ip6": intf_data.get("vsx_virtual_ip6"),
            "vsx_virtual_gw_mac_v4": intf_data.get("vsx_virtual_gw_mac_v4"),
            "vsx_virtual_gw_mac_v6": intf_data.get("vsx_virtual_gw_mac_v6"),
            # VLAN configuration
            # vlan_tag and vlan_trunks are dicts with VLAN IDs as keys
            # e.g., {"1": "/rest/v10.16/system/vlans/1"}
            "vlan_mode": intf_data.get("vlan_mode"),
            "vlan_tag": intf_data.get("vlan_tag"),
            "vlan_trunks": intf_data.get("vlan_trunks", {}),
            # LAG configuration
            "lacp_status": intf_data.get("lacp_status"),
            "bond_status": intf_data.get("bond_status"),
            # Routing and VRF
            "routing": intf_data.get("routing"),
            "vrf": intf_data.get("vrf"),
            # Other config (contains additional settings)
            "other_config": intf_data.get("other_config", {}),
        }

    return result


def rest_api_to_aoscx_vlans(rest_data):
    """Convert REST API VLAN data to aoscx_facts format.

    Args:
        rest_data: Dict from REST API /system/vlans?depth=2
                   Format: {"1": {...}, "10": {...}, ...}

    Returns:
        Dict in aoscx_facts format with normalized VLAN data
    """
    if not isinstance(rest_data, dict):
        return {}

    result = {}
    for vlan_id, vlan_data in rest_data.items():
        # Skip non-dict entries (URIs returned at depth=1)
        if not isinstance(vlan_data, dict):
            # If it's a string (URI), we can't extract VLAN data
            # This happens when depth < 2
            continue

        # Normalize VLAN ID to string (REST API may return int or string)
        vlan_id_str = str(vlan_id)

        # Extract VLAN ID from data or use key
        actual_id = vlan_data.get("id", vlan_id)
        if isinstance(actual_id, str) and actual_id.isdigit():
            actual_id = int(actual_id)

        result[vlan_id_str] = {
            "id": actual_id,
            "name": vlan_data.get("name", f"VLAN{vlan_id}"),
            "description": vlan_data.get("description", ""),
            "admin": vlan_data.get("admin", "up"),
            "voice": vlan_data.get("voice", False),
            "type": vlan_data.get("type", "static"),
            "oper_state": vlan_data.get("oper_state", "up"),
        }

    return result


def rest_api_to_aoscx_evpn_vlans(rest_data):
    """Convert REST API EVPN VLAN data to a usable format.

    Args:
        rest_data: Dict from REST API /system/evpn/evpn_vlans?depth=1
                   Format: {"10": {...}, "20": {...}, ...}

    Returns:
        Dict with VLAN ID as key and EVPN config as value
    """
    if not isinstance(rest_data, dict):
        return {}

    result = {}
    for vlan_id, evpn_data in rest_data.items():
        if not isinstance(evpn_data, dict):
            continue

        vlan_id_str = str(vlan_id)

        # Get actual VLAN ID from data, or fall back to dict key
        actual_vlan = evpn_data.get("vlan", vlan_id)
        # Ensure it's an integer if it's a numeric string
        if isinstance(actual_vlan, str) and actual_vlan.isdigit():
            actual_vlan = int(actual_vlan)

        result[vlan_id_str] = {
            "vlan": actual_vlan,
            "rd": evpn_data.get("rd"),
            "export_route_targets": evpn_data.get("export_route_targets", []),
            "import_route_targets": evpn_data.get("import_route_targets", []),
            "redistribute": evpn_data.get("redistribute", {}),
        }

    return result


def rest_api_to_aoscx_vnis(rest_data):
    """Convert REST API VNI data to a usable format.

    Args:
        rest_data: Dict from REST API /system/virtual_network_ids?depth=1
                   Format: {"vxlan,100": {...}, "vxlan,200": {...}, ...}

    Returns:
        Dict with VNI ID as key and VNI config as value
    """
    if not isinstance(rest_data, dict):
        return {}

    result = {}
    for _, vni_data in rest_data.items():
        if not isinstance(vni_data, dict):
            continue

        # Key format is "type,id" (e.g., "vxlan,100") - we extract from data instead
        vni_type = vni_data.get("type", "vxlan")
        vni_id = vni_data.get("id")

        if vni_id is not None:
            result[str(vni_id)] = {
                "id": vni_id,
                "type": vni_type,
                "vlan": vni_data.get("vlan"),
                "vrf": vni_data.get("vrf"),
                "routing": vni_data.get("routing"),
                "state": vni_data.get("state"),
                "interface": vni_data.get("interface"),
            }

    return result


class FilterModule:
    """Ansible filter plugin for REST API data transformation."""

    def filters(self):
        """Return the filter functions."""
        return {
            "rest_api_to_aoscx_interfaces": rest_api_to_aoscx_interfaces,
            "rest_api_to_aoscx_vlans": rest_api_to_aoscx_vlans,
            "rest_api_to_aoscx_evpn_vlans": rest_api_to_aoscx_evpn_vlans,
            "rest_api_to_aoscx_vnis": rest_api_to_aoscx_vnis,
        }
