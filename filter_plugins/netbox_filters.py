#!/usr/bin/env python3
"""
Custom Ansible filters for NetBox data transformation
"""

import os


def _debug(message):
    """Print debug message if DEBUG_ANSIBLE environment variable is set"""
    if os.environ.get('DEBUG_ANSIBLE', '').lower() in ('true', '1', 'yes'):
        print(f"DEBUG: {message}")


def extract_vlan_ids(interfaces):
    """
    Extract all VLAN IDs in use from interfaces
    
    Args:
        interfaces: List of interface objects from NetBox
        
    Returns:
        Sorted list of unique VLAN IDs
    """
    vlan_ids = set()
    
    for interface in interfaces:
        # VLAN interfaces (e.g., vlan100)
        if interface.get('name', '').startswith('vlan'):
            try:
                vid = int(interface['name'].replace('vlan', ''))
                vlan_ids.add(vid)
            except (ValueError, TypeError):
                pass
        
        # Untagged VLANs
        if interface.get('untagged_vlan') and interface['untagged_vlan'] is not None:
            vid = interface['untagged_vlan'].get('vid')
            if vid is not None:
                vlan_ids.add(vid)
        
        # Tagged VLANs
        if interface.get('tagged_vlans') and interface['tagged_vlans'] is not None:
            for vlan in interface['tagged_vlans']:
                vid = vlan.get('vid')
                if vid is not None:
                    vlan_ids.add(vid)
    
    _debug(f"Extracted VLAN IDs: {sorted(list(vlan_ids))}")
    return sorted(list(vlan_ids))


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
        vrf = interface.get('vrf')
        if vrf and vrf is not None:
            vrf_name = vrf.get('name')
            if vrf_name:
                _debug(f"Found VRF '{vrf_name}' on interface {interface.get('name')}")
                vrf_names.add(vrf_name)
    
    _debug(f"All VRFs found in interfaces: {vrf_names}")
    return vrf_names


def filter_vlans_in_use(vlans, interfaces):
    """
    Filter VLANs to only those actually in use on interfaces
    
    Args:
        vlans: List of all VLAN objects from NetBox
        interfaces: List of interface objects from NetBox
        
    Returns:
        List of VLAN objects that are in use
    """
    vlan_ids_in_use = set(extract_vlan_ids(interfaces))
    
    filtered = [
        vlan for vlan in vlans 
        if vlan.get('vid') in vlan_ids_in_use
    ]
    
    _debug(f"Filtered VLANs in use: {[v.get('vid') for v in filtered]}")
    return filtered


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
    
    if os.environ.get('DEBUG_ANSIBLE', '').lower() in ('true', '1', 'yes'):
        for vrf in vrfs:
            _debug(f"Checking VRF: {vrf.get('name')}, tenant: {vrf.get('tenant')}")
    
    filtered_vrfs = []
    for vrf in vrfs:
        vrf_name = vrf.get('name')
        
        # Skip if VRF not in use on any interface
        if vrf_name not in vrf_names_in_use:
            _debug(f"Skipping '{vrf_name}' - not in use")
            continue
        
        # Skip mgmt and Global VRFs
        if vrf_name in ['mgmt', 'Global']:
            _debug(f"Skipping '{vrf_name}' - mgmt or Global")
            continue
        
        _debug(f"VRF '{vrf_name}' passed initial checks")
        
        # If tenant filter is specified, check tenant matching
        if tenant:
            vrf_tenant = vrf.get('tenant')
            # Include VRF if it has no tenant or matches the specified tenant
            if vrf_tenant is None:
                _debug(f"Including '{vrf_name}' - no tenant assigned")
                filtered_vrfs.append(vrf)
            elif vrf_tenant.get('slug') == tenant:
                _debug(f"Including '{vrf_name}' - tenant matches")
                filtered_vrfs.append(vrf)
            else:
                _debug(f"Skipping '{vrf_name}' - tenant mismatch: {vrf_tenant.get('slug')} != {tenant}")
        else:
            # If no tenant filter, include all VRFs in use
            _debug(f"Including '{vrf_name}' - no tenant filter")
            filtered_vrfs.append(vrf)
    
    _debug(f"Final filtered VRFs: {[v.get('name') for v in filtered_vrfs]}")
    return filtered_vrfs


def extract_evpn_vlans(vlans, interfaces, check_noevpn=True):
    """
    Extract VLANs that should be configured for EVPN
    
    Args:
        vlans: List of all VLAN objects from NetBox
        interfaces: List of interface objects from NetBox
        check_noevpn: Whether to check vlan_noevpn custom field
        
    Returns:
        List of VLAN objects for EVPN configuration
    """
    vlans_in_use = filter_vlans_in_use(vlans, interfaces)
    
    evpn_vlans = []
    for vlan in vlans_in_use:
        # Check if EVPN is disabled for this VLAN
        if check_noevpn:
            custom_fields = vlan.get('custom_fields', {})
            if custom_fields.get('vlan_noevpn'):
                _debug(f"Skipping VLAN {vlan.get('vid')} - EVPN disabled")
                continue
        
        # Check if L2VPN is configured
        l2vpn_term = vlan.get('l2vpn_termination')
        if l2vpn_term and l2vpn_term.get('l2vpn'):
            evpn_vlans.append(vlan)
            _debug(f"Including VLAN {vlan.get('vid')} for EVPN")
    
    _debug(f"Final EVPN VLANs: {[v.get('vid') for v in evpn_vlans]}")
    return evpn_vlans


def extract_vxlan_mappings(vlans, interfaces, use_l2vpn_id=True):
    """
    Extract VXLAN VNI to VLAN mappings
    
    Args:
        vlans: List of all VLAN objects from NetBox
        interfaces: List of interface objects from NetBox
        use_l2vpn_id: Use L2VPN identifier as VNI, otherwise use VLAN ID
        
    Returns:
        List of dicts with 'vni' and 'vlan' keys
    """
    vlans_in_use = filter_vlans_in_use(vlans, interfaces)
    
    mappings = []
    for vlan in vlans_in_use:
        vid = vlan.get('vid')
        
        # Check if EVPN is disabled
        custom_fields = vlan.get('custom_fields', {})
        if custom_fields.get('vlan_noevpn'):
            _debug(f"Skipping VLAN {vid} for VXLAN - EVPN disabled")
            continue
        
        if use_l2vpn_id:
            # Use L2VPN identifier as VNI
            l2vpn_term = vlan.get('l2vpn_termination')
            if l2vpn_term and l2vpn_term.get('l2vpn'):
                vni = l2vpn_term['l2vpn'].get('identifier')
                if vni is not None:
                    mappings.append({'vni': vni, 'vlan': vid})
                    _debug(f"VXLAN mapping: VNI {vni} -> VLAN {vid} (L2VPN)")
        else:
            # Use VLAN ID as VNI
            if vid is not None:
                mappings.append({'vni': vid, 'vlan': vid})
                _debug(f"VXLAN mapping: VNI {vid} -> VLAN {vid}")
    
    _debug(f"Total VXLAN mappings: {len(mappings)}")
    return mappings


def categorize_l2_interfaces(interfaces):
    """
    Categorize L2 interfaces by their VLAN configuration type
    
    Args:
        interfaces: List of interface objects from NetBox
        
    Returns:
        Dict with categorized interface lists
    """
    categorized = {
        'access': [],
        'tagged_with_untagged': [],
        'tagged_no_untagged': [],
        'tagged_all_with_untagged': [],
        'tagged_all_no_untagged': [],
        'lag_access': [],
        'lag_tagged_with_untagged': [],
        'lag_tagged_no_untagged': [],
        'lag_tagged_all_with_untagged': [],
        'lag_tagged_all_no_untagged': [],
        'mclag_access': [],
        'mclag_tagged_with_untagged': [],
        'mclag_tagged_no_untagged': [],
        'mclag_tagged_all_with_untagged': [],
        'mclag_tagged_all_no_untagged': []
    }
    
    # Ensure interfaces is not None
    if not interfaces:
        _debug("No interfaces provided to categorize_l2_interfaces")
        return categorized
    
    for intf in interfaces:
        # Skip if interface is None
        if intf is None:
            _debug("Skipping None interface")
            continue
        
        intf_name = intf.get('name', 'unknown')
        
        # Skip non-L2 interfaces
        if intf.get('mgmt_only'):
            continue
        
        # Skip if no mode defined
        mode_obj = intf.get('mode')
        if not mode_obj or mode_obj is None:
            continue
        
        mode_value = mode_obj.get('value') if isinstance(mode_obj, dict) else None
        if not mode_value:
            continue
        
        # Skip virtual interfaces
        type_obj = intf.get('type')
        if type_obj and isinstance(type_obj, dict):
            type_value = type_obj.get('value')
            if type_value == 'virtual':
                continue
        
        # Determine interface characteristics
        mode = mode_value
        
        # Check for untagged VLAN
        untagged_vlan = intf.get('untagged_vlan')
        has_untagged = False
        untagged_vid = None
        if untagged_vlan and isinstance(untagged_vlan, dict):
            untagged_vid = untagged_vlan.get('vid')
            has_untagged = untagged_vid is not None
        
        # Check for tagged VLANs
        tagged_vlans = intf.get('tagged_vlans')
        has_tagged = False
        if tagged_vlans and isinstance(tagged_vlans, list):
            # Filter out None entries and entries without vid
            valid_tagged = [v for v in tagged_vlans if v and isinstance(v, dict) and v.get('vid') is not None]
            has_tagged = len(valid_tagged) > 0
        
        # Determine if LAG
        is_lag = False
        if type_obj and isinstance(type_obj, dict):
            is_lag = type_obj.get('value') == 'lag'
        
        # Determine if MCLAG
        custom_fields = intf.get('custom_fields')
        is_mclag = False
        if custom_fields and isinstance(custom_fields, dict):
            is_mclag = custom_fields.get('if_mclag', False)
        
        # Determine prefix based on interface type
        if is_mclag:
            prefix = 'mclag_'
        elif is_lag:
            prefix = 'lag_'
        else:
            prefix = ''
        
        # Categorize based on mode and VLAN configuration
        try:
            if mode == 'access':
                # Only add if has valid untagged VLAN
                if has_untagged:
                    categorized[f'{prefix}access'].append(intf)
                else:
                    _debug(f"Skipping {intf_name} - access mode but no untagged VLAN")
            elif mode == 'tagged':
                if has_untagged and has_tagged:
                    categorized[f'{prefix}tagged_with_untagged'].append(intf)
                elif has_tagged:
                    categorized[f'{prefix}tagged_no_untagged'].append(intf)
                else:
                    _debug(f"Skipping {intf_name} - tagged mode but no VLANs configured")
            elif mode == 'tagged-all':
                if has_untagged:
                    categorized[f'{prefix}tagged_all_with_untagged'].append(intf)
                else:
                    categorized[f'{prefix}tagged_all_no_untagged'].append(intf)
        except Exception as e:
            _debug(f"Error categorizing interface {intf_name}: {str(e)}")
            continue
    
    _debug(f"L2 interface categorization:")
    for category, intfs in categorized.items():
        if intfs:
            _debug(f"  {category}: {len(intfs)} interfaces - {[i.get('name') for i in intfs]}")
    
    return categorized


def compare_interface_vlans(netbox_interface, device_facts_interface):
    """
    Compare VLANs between NetBox and device facts to determine required changes
    
    Args:
        netbox_interface: Interface object from NetBox inventory
        device_facts_interface: Interface object from device facts
        
    Returns:
        Dict with 'vlans_to_add', 'vlans_to_remove', 'needs_change' keys
    """
    result = {
        'vlans_to_add': [],
        'vlans_to_remove': [],
        'needs_change': False,
        'mode_change': False
    }
    
    # Skip if either interface is None
    if not netbox_interface or not device_facts_interface:
        return result
    
    # Get NetBox VLAN configuration
    mode_obj = netbox_interface.get('mode')
    if not mode_obj or not isinstance(mode_obj, dict):
        return result
    
    nb_mode = mode_obj.get('value')
    if not nb_mode:
        return result
    
    # Get untagged VLAN
    nb_untagged = None
    untagged_vlan = netbox_interface.get('untagged_vlan')
    if untagged_vlan and isinstance(untagged_vlan, dict):
        nb_untagged = untagged_vlan.get('vid')
    
    # Get tagged VLANs
    nb_tagged = set()
    tagged_vlans = netbox_interface.get('tagged_vlans')
    if tagged_vlans and isinstance(tagged_vlans, list):
        for v in tagged_vlans:
            if v and isinstance(v, dict):
                vid = v.get('vid')
                if vid is not None:
                    nb_tagged.add(vid)
    
    # Get device VLAN configuration - AOS-CX specific structure
    device_mode = device_facts_interface.get('vlan_mode') or device_facts_interface.get('applied_vlan_mode')
    
    # Get native/access VLAN
    device_native = None
    vlan_tag = device_facts_interface.get('vlan_tag') or device_facts_interface.get('applied_vlan_tag')
    if vlan_tag and isinstance(vlan_tag, dict):
        # vlan_tag is a dict like {"10": "/rest/v10.09/system/vlans/10"}
        # Extract the VLAN ID from the key
        for vlan_id_str in vlan_tag.keys():
            try:
                device_native = int(vlan_id_str)
                break
            except (ValueError, TypeError):
                pass
    
    # Get trunk VLANs
    device_trunks = set()
    vlan_trunks = device_facts_interface.get('vlan_trunks') or device_facts_interface.get('applied_vlan_trunks')
    if vlan_trunks and isinstance(vlan_trunks, dict):
        # vlan_trunks is a dict like {"10": "/rest/.../vlans/10", "20": "/rest/.../vlans/20"}
        for vlan_id_str in vlan_trunks.keys():
            try:
                device_trunks.add(int(vlan_id_str))
            except (ValueError, TypeError):
                pass
    
    _debug(f"Interface {netbox_interface.get('name')}: NB mode={nb_mode}, untagged={nb_untagged}, tagged={nb_tagged}")
    _debug(f"Interface {netbox_interface.get('name')}: Device mode={device_mode}, native={device_native}, trunks={device_trunks}")
    
    # Check mode change
    if nb_mode == 'access' and device_mode != 'access':
        result['mode_change'] = True
        result['needs_change'] = True
    elif nb_mode in ['tagged', 'tagged-all'] and device_mode not in ['native-tagged', 'native-untagged']:
        result['mode_change'] = True
        result['needs_change'] = True
    
    if nb_mode == 'access':
        # For access mode, just check if the access VLAN matches
        if nb_untagged and nb_untagged != device_native:
            result['needs_change'] = True
    elif nb_mode == 'tagged':
        # Build the complete set of VLANs that should be on the interface
        nb_all_vlans = set(nb_tagged)
        if nb_untagged:
            nb_all_vlans.add(nb_untagged)
        
        # Check native VLAN
        if nb_untagged and nb_untagged != device_native:
            result['needs_change'] = True
        
        # Compare trunk VLANs
        result['vlans_to_add'] = list(nb_all_vlans - device_trunks)
        result['vlans_to_remove'] = list(device_trunks - nb_all_vlans)
        
        if result['vlans_to_add'] or result['vlans_to_remove']:
            result['needs_change'] = True
    elif nb_mode == 'tagged-all':
        # For tagged-all, we only care about native VLAN
        if nb_untagged and nb_untagged != device_native:
            result['needs_change'] = True
    
    _debug(f"Interface {netbox_interface.get('name')} comparison: {result}")
    return result


def collapse_vlan_list(vlan_list):
    """Collapse a list of VLAN IDs into a range string"""
    if not vlan_list:
        return ""
    
    # Sort and remove duplicates
    sorted_vlans = sorted(set(vlan_list))
    
    collapsed_ranges = []
    range_start = None
    range_end = None
    
    for vlan in sorted_vlans:
        if range_start is None:
            # Start a new range
            range_start = vlan
            range_end = vlan
        elif vlan == range_end + 1:
            # Continue the range
            range_end = vlan
        else:
            # Close the current range and start a new one
            if range_start == range_end:
                collapsed_ranges.append(f"{range_start}")
            else:
                collapsed_ranges.append(f"{range_start}-{range_end}")
            
            range_start = vlan
            range_end = vlan
    
    # Close the final range
    if range_start is not None:
        if range_start == range_end:
            collapsed_ranges.append(f"{range_start}")
        else:
            collapsed_ranges.append(f"{range_start}-{range_end}")
    
    return ",".join(collapsed_ranges)


def get_interfaces_needing_changes(interfaces, device_facts):
    """
    Get list of interfaces that need VLAN changes (additions or removals)
    
    Args:
        interfaces: List of interface objects from NetBox inventory
        device_facts: Device facts from ansible_facts
        
    Returns:
        Dict with 'cleanup' (interfaces needing VLAN removal) and 
        'configure' (interfaces needing any changes) lists
    """
    cleanup_list = []
    configure_list = []
    
    # Ensure inputs are valid
    if not interfaces:
        _debug("No interfaces provided to get_interfaces_needing_changes")
        return {'cleanup': cleanup_list, 'configure': configure_list}
    
    if not device_facts:
        _debug("No device facts provided to get_interfaces_needing_changes")
        return {'cleanup': cleanup_list, 'configure': configure_list}
    
    # Convert device facts to a dict keyed by interface name
    # AOS-CX uses network_resources.interfaces as a dict
    facts_by_interface = {}
    
    if 'network_resources' in device_facts:
        network_resources = device_facts.get('network_resources', {})
        if network_resources and isinstance(network_resources, dict):
            interfaces_dict = network_resources.get('interfaces', {})
            if interfaces_dict and isinstance(interfaces_dict, dict):
                facts_by_interface = interfaces_dict
                _debug(f"Found {len(facts_by_interface)} interfaces in network_resources.interfaces")
    
    if not facts_by_interface:
        _debug(f"Device facts structure: {list(device_facts.keys())}")
        return {'cleanup': cleanup_list, 'configure': configure_list}
    
    _debug(f"Found {len(facts_by_interface)} interfaces in device facts")
    _debug(f"Sample interface names: {list(facts_by_interface.keys())[:5]}")
    
    for nb_intf in interfaces:
        # Skip None interfaces
        if not nb_intf:
            continue
        
        intf_name = nb_intf.get('name')
        if not intf_name:
            continue
        
        # Skip non-L2 interfaces
        if nb_intf.get('mgmt_only'):
            continue
        
        mode_obj = nb_intf.get('mode')
        if not mode_obj or not isinstance(mode_obj, dict):
            continue
        
        # Get device facts for this interface
        device_intf = facts_by_interface.get(intf_name)
        if not device_intf:
            # No device facts = interface needs to be configured
            _debug(f"No device facts found for interface {intf_name} - needs configuration")
            configure_list.append(nb_intf)
            continue
        
        _debug(f"Comparing interface {intf_name}")
        
        try:
            comparison = compare_interface_vlans(nb_intf, device_intf)
            
            # If any changes are needed, add to configure list
            if comparison['needs_change']:
                configure_list.append(nb_intf)
                _debug(f"Interface {intf_name} needs configuration changes")
                
                # If VLANs need to be removed, also add to cleanup list
                if comparison['vlans_to_remove']:
                    type_obj = nb_intf.get('type')
                    is_lag = False
                    if type_obj and isinstance(type_obj, dict):
                        is_lag = type_obj.get('value') == 'lag'
                    
                    custom_fields = nb_intf.get('custom_fields')
                    is_mclag = False
                    if custom_fields and isinstance(custom_fields, dict):
                        is_mclag = custom_fields.get('if_mclag', False)
                    
                    cleanup_list.append({
                        'interface': intf_name,
                        'vlans_to_remove': comparison['vlans_to_remove'],
                        'is_lag': is_lag,
                        'is_mclag': is_mclag
                    })
                    _debug(f"Interface {intf_name} needs cleanup: remove VLANs {comparison['vlans_to_remove']}")
            else:
                _debug(f"Interface {intf_name} is already correctly configured - skipping")
                
        except Exception as e:
            _debug(f"Error comparing interface {intf_name}: {str(e)}")
            import traceback
            _debug(f"Traceback: {traceback.format_exc()}")
            # If we can't compare, assume it needs configuration
            configure_list.append(nb_intf)
            continue
    
    _debug(f"Interfaces needing cleanup: {len(cleanup_list)}")
    _debug(f"Interfaces needing configuration: {len(configure_list)}")
    _debug(f"Interfaces skipped (no changes): {len([i for i in interfaces if i and i.get('mode')]) - len(configure_list)}")
    
    return {'cleanup': cleanup_list, 'configure': configure_list}


# Keep the old function for backwards compatibility, but mark as deprecated
def get_interfaces_needing_vlan_cleanup(interfaces, device_facts):
    """
    DEPRECATED: Use get_interfaces_needing_changes() instead
    
    Get list of interfaces that need VLAN removal
    """
    result = get_interfaces_needing_changes(interfaces, device_facts)
    return result['cleanup']


def get_vlans_in_use(interfaces, vlan_interfaces=None):
    """
    Extract all VLANs that are in use on interfaces
    
    Args:
        interfaces: List of interface objects from NetBox
        vlan_interfaces: Optional list of VLAN/SVI interfaces
        
    Returns:
        Dict with:
        - 'vids': Set of VLAN IDs in use
        - 'vlans': List of unique VLAN objects in use
    """
    vlans_in_use = {}  # Dict keyed by vid to avoid duplicates
    vids_in_use = set()
    
    # Ensure interfaces is not None
    if not interfaces:
        interfaces = []
    
    # Process physical and LAG interfaces
    for intf in interfaces:
        if not intf:
            continue
            
        # Skip management interfaces
        if intf.get('mgmt_only'):
            continue
        
        # Get untagged VLAN
        untagged_vlan = intf.get('untagged_vlan')
        if untagged_vlan and isinstance(untagged_vlan, dict):
            vid = untagged_vlan.get('vid')
            if vid is not None:
                vids_in_use.add(vid)
                vlans_in_use[vid] = untagged_vlan
        
        # Get tagged VLANs
        tagged_vlans = intf.get('tagged_vlans')
        if tagged_vlans and isinstance(tagged_vlans, list):
            for vlan in tagged_vlans:
                if vlan and isinstance(vlan, dict):
                    vid = vlan.get('vid')
                    if vid is not None:
                        vids_in_use.add(vid)
                        vlans_in_use[vid] = vlan
    
    # Process VLAN/SVI interfaces
    if vlan_interfaces:
        for vlan_intf in vlan_interfaces:
            if not vlan_intf:
                continue
            
            # VLAN interfaces have a 'vlan' field or the VLAN info might be in the name
            vlan_obj = vlan_intf.get('vlan')
            if vlan_obj and isinstance(vlan_obj, dict):
                vid = vlan_obj.get('vid')
                if vid is not None:
                    vids_in_use.add(vid)
                    vlans_in_use[vid] = vlan_obj
    
    result = {
        'vids': sorted(list(vids_in_use)),
        'vlans': list(vlans_in_use.values())
    }
    
    _debug(f"Found {len(result['vids'])} VLANs in use: {result['vids']}")
    
    return result


def get_vlans_needing_changes(device_vlans, vlans_in_use_dict, device_facts=None):
    """
    Determine which VLANs need to be added or removed
    
    Args:
        device_vlans: List of VLAN objects available for this device from NetBox
        vlans_in_use_dict: Dict from get_vlans_in_use() with 'vids' and 'vlans'
        device_facts: Optional device facts for checking current state
        
    Returns:
        Dict with:
        - 'vlans_to_create': List of VLAN objects to create
        - 'vlans_to_delete': List of VLAN IDs to delete
        - 'vlans_in_use': List of VLAN objects currently in use
    """
    vlans_to_create = []
    vlans_to_delete = []
    vlans_in_use = []
    
    # Ensure inputs are valid
    if not device_vlans:
        _debug("No device VLANs provided")
        return {
            'vlans_to_create': vlans_to_create,
            'vlans_to_delete': vlans_to_delete,
            'vlans_in_use': vlans_in_use
        }
    
    if not vlans_in_use_dict or 'vids' not in vlans_in_use_dict:
        _debug("No VLANs in use provided")
        return {
            'vlans_to_create': vlans_to_create,
            'vlans_to_delete': vlans_to_delete,
            'vlans_in_use': vlans_in_use
        }
    
    vids_in_use = set(vlans_in_use_dict['vids'])
    
    # Get VLANs currently on device (if facts provided)
    device_vids = set()
    if device_facts and isinstance(device_facts, dict):
        if 'network_resources' in device_facts:
            network_resources = device_facts.get('network_resources', {})
            if network_resources and isinstance(network_resources, dict):
                vlans_dict = network_resources.get('vlans', {})
                if vlans_dict and isinstance(vlans_dict, dict):
                    # AOS-CX stores VLANs as dict keyed by VID
                    for vid_str in vlans_dict.keys():
                        try:
                            device_vids.add(int(vid_str))
                        except (ValueError, TypeError):
                            pass
                    _debug(f"Found {len(device_vids)} VLANs on device: {sorted(list(device_vids))}")
    
    # Build dict of available VLANs by VID
    available_vlans = {}
    for vlan in device_vlans:
        if vlan and isinstance(vlan, dict):
            vid = vlan.get('vid')
            if vid is not None:
                available_vlans[vid] = vlan
    
    _debug(f"Available VLANs from NetBox: {sorted(list(available_vlans.keys()))}")
    _debug(f"VLANs in use on interfaces: {sorted(list(vids_in_use))}")
    
    # Determine VLANs to create (in use but not on device or not created yet)
    for vid in vids_in_use:
        if vid in available_vlans:
            vlans_in_use.append(available_vlans[vid])
            # Only add to create list if we have device facts and it's not there
            if device_facts and vid not in device_vids:
                vlans_to_create.append(available_vlans[vid])
                _debug(f"VLAN {vid} needs to be created")
        else:
            _debug(f"WARNING: VLAN {vid} is in use but not available in NetBox for this device!")
    
    # If no device facts, assume we need to create all in-use VLANs
    if not device_facts:
        vlans_to_create = vlans_in_use.copy()
        _debug("No device facts provided - will create all VLANs in use")
    
    # Determine VLANs to delete (on device but not in use)
    if device_facts and device_vids:
        available_vids = set(available_vlans.keys())
        for vid in device_vids:
            # Delete if: on device AND (not in use OR not in NetBox available list)
            if vid not in vids_in_use and vid in available_vids:
                vlans_to_delete.append(vid)
                _debug(f"VLAN {vid} can be deleted (on device but not in use)")
            elif vid not in available_vids and vid != 1:  # Don't delete VLAN 1
                _debug(f"VLAN {vid} on device but not in NetBox scope for this device")
    
    result = {
        'vlans_to_create': vlans_to_create,
        'vlans_to_delete': sorted(vlans_to_delete),
        'vlans_in_use': vlans_in_use
    }
    
    _debug(f"VLANs to create: {len(result['vlans_to_create'])} - {[v.get('vid') for v in result['vlans_to_create']]}")
    _debug(f"VLANs to delete: {len(result['vlans_to_delete'])} - {result['vlans_to_delete']}")
    
    return result


def get_vlan_interfaces(interfaces):
    """
    Extract VLAN/SVI interfaces from interface list
    
    Args:
        interfaces: List of interface objects from NetBox
        
    Returns:
        List of VLAN interface objects
    """
    vlan_interfaces = []
    
    if not interfaces:
        return vlan_interfaces
    
    for intf in interfaces:
        if not intf:
            continue
        
        # Check if it's a virtual interface with 'vlan' in the name
        type_obj = intf.get('type')
        name = intf.get('name', '').lower()
        
        is_vlan_interface = False
        
        # Check by type
        if type_obj and isinstance(type_obj, dict):
            type_value = type_obj.get('value', '')
            if type_value == 'virtual':
                # Check if name contains 'vlan'
                if 'vlan' in name:
                    is_vlan_interface = True
        
        if is_vlan_interface:
            vlan_interfaces.append(intf)
            _debug(f"Found VLAN interface: {intf.get('name')}")
    
    _debug(f"Total VLAN interfaces found: {len(vlan_interfaces)}")
    return vlan_interfaces


def categorize_l3_interfaces(interfaces):
    """
    Categorize L3 interfaces by type and configuration
    
    Args:
        interfaces: List of interface objects with IP addresses from NetBox
        
    Returns:
        Dict with categorized interfaces:
        - physical_default_vrf: Physical interfaces in default/Global/mgmt VRF
        - physical_custom_vrf: Physical interfaces in custom VRFs
        - vlan_default_vrf: VLAN interfaces in default/Global/mgmt VRF
        - vlan_custom_vrf: VLAN interfaces in custom VRFs
        - lag_default_vrf: LAG interfaces in default/Global/mgmt VRF
        - lag_custom_vrf: LAG interfaces in custom VRFs
        - loopback: Loopback interfaces
    """
    result = {
        'physical_default_vrf': [],
        'physical_custom_vrf': [],
        'vlan_default_vrf': [],
        'vlan_custom_vrf': [],
        'lag_default_vrf': [],
        'lag_custom_vrf': [],
        'loopback': []
    }
    
    # Built-in, non-configurable VRFs
    builtin_vrfs = {'default', 'Default', 'Global', 'global', 'mgmt', 'MGMT', None}
    
    if not interfaces:
        return result
    
    for intf in interfaces:
        if not intf:
            continue
        
        # Skip management interfaces
        if intf.get('mgmt_only'):
            _debug(f"Skipping management interface: {intf.get('name')}")
            continue
        
        # Get interface type
        type_obj = intf.get('type')
        if not type_obj or not isinstance(type_obj, dict):
            continue
        
        type_value = type_obj.get('value', '')
        name = intf.get('name', '').lower()
        
        # Determine VRF (default to built-in)
        vrf_name = None
        vrf_obj = intf.get('vrf')
        if vrf_obj and isinstance(vrf_obj, dict):
            vrf_name = vrf_obj.get('name')
        
        is_builtin_vrf = vrf_name in builtin_vrfs
        
        # Categorize by type and VRF
        if type_value == 'virtual' and 'loopback' in name:
            result['loopback'].append(intf)
            _debug(f"Categorized {intf.get('name')} as loopback")
        elif type_value == 'virtual' and 'vlan' in name:
            if is_builtin_vrf:
                result['vlan_default_vrf'].append(intf)
                _debug(f"Categorized {intf.get('name')} as VLAN interface (built-in VRF: {vrf_name})")
            else:
                result['vlan_custom_vrf'].append(intf)
                _debug(f"Categorized {intf.get('name')} as VLAN interface (VRF: {vrf_name})")
        elif type_value == 'lag':
            if is_builtin_vrf:
                result['lag_default_vrf'].append(intf)
                _debug(f"Categorized {intf.get('name')} as LAG interface (built-in VRF: {vrf_name})")
            else:
                result['lag_custom_vrf'].append(intf)
                _debug(f"Categorized {intf.get('name')} as LAG interface (VRF: {vrf_name})")
        else:
            # Physical interface
            if is_builtin_vrf:
                result['physical_default_vrf'].append(intf)
                _debug(f"Categorized {intf.get('name')} as physical interface (built-in VRF: {vrf_name})")
            else:
                result['physical_custom_vrf'].append(intf)
                _debug(f"Categorized {intf.get('name')} as physical interface (VRF: {vrf_name})")
    
    _debug(f"L3 interface categorization:")
    _debug(f"  Physical (built-in VRF): {len(result['physical_default_vrf'])}")
    _debug(f"  Physical (custom VRF): {len(result['physical_custom_vrf'])}")
    _debug(f"  VLAN (built-in VRF): {len(result['vlan_default_vrf'])}")
    _debug(f"  VLAN (custom VRF): {len(result['vlan_custom_vrf'])}")
    _debug(f"  LAG (built-in VRF): {len(result['lag_default_vrf'])}")
    _debug(f"  LAG (custom VRF): {len(result['lag_custom_vrf'])}")
    _debug(f"  Loopback: {len(result['loopback'])}")
    
    return result


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
    builtin_vrfs = {'mgmt', 'MGMT', 'Global', 'global', 'default', 'Default'}
    
    # Ensure interfaces is not None
    if not interfaces:
        interfaces = []
    
    # Process interfaces
    for intf in interfaces:
        if not intf:
            continue
            
        # Skip management interfaces (they're always in mgmt VRF)
        if intf.get('mgmt_only'):
            continue
        
        # Get VRF from interface
        vrf_obj = intf.get('vrf')
        if vrf_obj and isinstance(vrf_obj, dict):
            vrf_name = vrf_obj.get('name')
            if vrf_name and vrf_name not in builtin_vrfs:
                vrf_names.add(vrf_name)
                vrfs_in_use[vrf_name] = vrf_obj
    
    # Also check IP addresses if provided
    if ip_addresses:
        for ip_obj in ip_addresses:
            if not ip_obj or not isinstance(ip_obj, dict):
                continue
            
            vrf_obj = ip_obj.get('vrf')
            if vrf_obj and isinstance(vrf_obj, dict):
                vrf_name = vrf_obj.get('name')
                if vrf_name and vrf_name not in builtin_vrfs:
                    vrf_names.add(vrf_name)
                    vrfs_in_use[vrf_name] = vrf_obj
    
    result = {
        'vrf_names': sorted(list(vrf_names)),
        'vrfs': vrfs_in_use
    }
    
    _debug(f"Found {len(result['vrf_names'])} configurable VRFs in use: {result['vrf_names']}")
    _debug(f"Built-in VRFs filtered out: {builtin_vrfs}")
    
    return result


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
    builtin_vrfs = {'mgmt', 'MGMT', 'Global', 'global', 'default', 'Default'}
    configurable = []
    
    for vrf in vrfs:
        if isinstance(vrf, dict):
            vrf_name = vrf.get('name')
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


def get_interface_ip_addresses(interfaces, ip_addresses):
    """
    Match IP addresses to their interfaces
    
    Args:
        interfaces: List of interface objects from NetBox
        ip_addresses: List of IP address objects from NetBox
        
    Returns:
        List of dicts with interface and IP address information
    """
    result = []
    
    if not interfaces or not ip_addresses:
        _debug("No interfaces or IP addresses provided")
        return result
    
    # Build a dict of interfaces by ID for quick lookup
    intf_by_id = {}
    for intf in interfaces:
        if intf and isinstance(intf, dict):
            intf_id = intf.get('id')
            if intf_id:
                intf_by_id[intf_id] = intf
    
    # Match IP addresses to interfaces
    for ip_obj in ip_addresses:
        if not ip_obj or not isinstance(ip_obj, dict):
            continue
        
        assigned_object = ip_obj.get('assigned_object')
        if not assigned_object or not isinstance(assigned_object, dict):
            continue
        
        assigned_object_id = assigned_object.get('id')
        if not assigned_object_id:
            continue
        
        # Find the matching interface
        intf = intf_by_id.get(assigned_object_id)
        if not intf:
            continue
        
        # Skip management interfaces
        if intf.get('mgmt_only'):
            continue
        
        address = ip_obj.get('address')
        if not address:
            continue
        
        # Get VRF info
        vrf_obj = ip_obj.get('vrf')
        vrf_name = 'default'
        if vrf_obj and isinstance(vrf_obj, dict):
            vrf_name = vrf_obj.get('name', 'default')
        
        result.append({
            'interface': intf,
            'interface_name': intf.get('name'),
            'interface_type': intf.get('type', {}).get('value') if isinstance(intf.get('type'), dict) else None,
            'address': address,
            'vrf': vrf_name,
            'description': intf.get('description', ''),
            'enabled': intf.get('enabled', True)
        })
        
        _debug(f"Matched IP {address} to interface {intf.get('name')} (VRF: {vrf_name})")
    
    _debug(f"Total interface/IP matches: {len(result)}")
    return result


# Update the FilterModule class
class FilterModule(object):
    """Custom filters for NetBox data transformation"""

    def filters(self):
        return {
            'extract_vlan_ids': extract_vlan_ids,
            'extract_interface_vrfs': extract_interface_vrfs,
            'filter_vlans_in_use': filter_vlans_in_use,
            'filter_vrfs_in_use': filter_vrfs_in_use,
            'extract_evpn_vlans': extract_evpn_vlans,
            'extract_vxlan_mappings': extract_vxlan_mappings,
            'categorize_l2_interfaces': categorize_l2_interfaces,
            'compare_interface_vlans': compare_interface_vlans,
            'get_interfaces_needing_vlan_cleanup': get_interfaces_needing_vlan_cleanup,
            'get_interfaces_needing_changes': get_interfaces_needing_changes,
            'collapse_vlan_list': collapse_vlan_list,
            'get_vlans_in_use': get_vlans_in_use,
            'get_vlans_needing_changes': get_vlans_needing_changes,
            'get_vlan_interfaces': get_vlan_interfaces,
            'categorize_l3_interfaces': categorize_l3_interfaces,
            'get_interface_ip_addresses': get_interface_ip_addresses,
            'get_vrfs_in_use': get_vrfs_in_use,
            'filter_configurable_vrfs': filter_configurable_vrfs,
        }