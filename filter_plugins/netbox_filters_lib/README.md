# NetBox Filters Library

Custom Ansible filters for transforming NetBox data for use with Aruba AOS-CX switches.

## Structure

This library is organized as a Python package with focused modules:

```
filter_plugins/
├── netbox_filters.py          # Main entry point (FilterModule)
└── netbox_filters_lib/        # Package directory
    ├── __init__.py            # Package exports
    ├── utils.py               # Helper functions
    ├── vlan_filters.py        # VLAN operations
    ├── vrf_filters.py         # VRF operations
    ├── interface_filters.py   # Interface categorization
    └── comparison.py          # Comparison logic
```

## Modules

### `utils.py`
Helper functions used across other modules:
- `_debug(message)` - Debug output helper (controlled by `DEBUG_ANSIBLE` env var)
- `collapse_vlan_list(vlan_list)` - Format VLAN IDs as ranges (e.g., "1-10,20,30-40")

### `vlan_filters.py`
VLAN extraction and management:
- `extract_vlan_ids(interfaces)` - Extract all VLAN IDs from interfaces
- `filter_vlans_in_use(vlans, interfaces)` - Filter to VLANs in use
- `extract_evpn_vlans(vlans, interfaces, check_noevpn=True)` - Get EVPN-enabled VLANs
- `extract_vxlan_mappings(vlans, interfaces, use_l2vpn_id=True)` - Get VNI→VLAN mappings
- `get_vlans_in_use(interfaces, vlan_interfaces=None)` - Get VLANs with full details
- `get_vlans_needing_changes(device_vlans, vlans_in_use_dict, device_facts=None)` - Determine VLANs to add/remove
- `get_vlan_interfaces(interfaces)` - Extract VLAN/SVI interfaces

### `vrf_filters.py`
VRF extraction and filtering:
- `extract_interface_vrfs(interfaces)` - Extract unique VRF names
- `filter_vrfs_in_use(vrfs, interfaces, tenant=None)` - Filter to VRFs in use
- `get_vrfs_in_use(interfaces, ip_addresses=None)` - Get VRFs with full details
- `filter_configurable_vrfs(vrfs)` - Remove built-in VRFs (mgmt, Global, etc.)

### `interface_filters.py`
Interface categorization and processing:
- `categorize_l2_interfaces(interfaces)` - Categorize L2 interfaces by VLAN mode
  - Returns dict with keys: `access`, `tagged_with_untagged`, `tagged_no_untagged`, etc.
  - Includes variants for LAG and MCLAG interfaces
- `categorize_l3_interfaces(interfaces)` - Categorize L3 interfaces by type and VRF
  - Returns dict with keys: `physical_default_vrf`, `vlan_custom_vrf`, `loopback`, etc.
- `get_interface_ip_addresses(interfaces, ip_addresses)` - Match IPs to interfaces

### `comparison.py`
NetBox vs device state comparison:
- `compare_interface_vlans(netbox_interface, device_facts_interface)` - Compare VLAN configs
  - Returns dict with `vlans_to_add`, `vlans_to_remove`, `needs_change`, `mode_change`
- `get_interfaces_needing_changes(interfaces, device_facts)` - Get interfaces needing updates
  - Returns dict with `cleanup` and `configure` lists
- `get_interfaces_needing_vlan_cleanup(interfaces, device_facts)` - **[DEPRECATED]** Use `get_interfaces_needing_changes()` instead

## Usage in Playbooks

All filters are available through the standard Ansible filter syntax:

```yaml
# VLAN operations
- set_fact:
    vlan_ids: "{{ interfaces | extract_vlan_ids }}"
    vlans_for_evpn: "{{ vlans | extract_evpn_vlans(interfaces) }}"
    vlan_range: "{{ [10, 11, 12, 20, 21] | collapse_vlan_list }}"  # "10-12,20-21"

# VRF operations
- set_fact:
    vrf_names: "{{ interfaces | extract_interface_vrfs }}"
    config_vrfs: "{{ vrfs | filter_configurable_vrfs }}"

# Interface categorization
- set_fact:
    l2_interfaces: "{{ interfaces | categorize_l2_interfaces }}"
    l3_interfaces: "{{ interfaces | categorize_l3_interfaces }}"

# Comparison and change detection
- set_fact:
    changes_needed: "{{ interfaces | get_interfaces_needing_changes(ansible_facts) }}"
    vlans_to_manage: "{{ device_vlans | get_vlans_needing_changes(vlans_in_use, ansible_facts) }}"
```

## Development

### Adding New Filters

1. Choose the appropriate module or create a new one
2. Import the `_debug` helper from `utils.py`
3. Add your function with proper docstring
4. Export it in `__init__.py`
5. Add it to the `FilterModule.filters()` dict in `netbox_filters.py`

### Testing

```bash
# Test module loading
python3 -c "from filter_plugins.netbox_filters import FilterModule; \
            fm = FilterModule(); \
            print(f'Loaded {len(fm.filters())} filters')"

# Run pre-commit checks
pre-commit run --files filter_plugins/netbox_filters.py \
                        filter_plugins/netbox_filters_lib/*.py
```

### Debugging

Enable debug output by setting the `DEBUG_ANSIBLE` environment variable:

```bash
export DEBUG_ANSIBLE=true
ansible-playbook your-playbook.yml
```

This will print detailed debug messages showing how filters process data.

## Module Statistics

- **Total filters**: 18
- **Largest module**: 361 lines (vlan_filters.py)
- **All modules**: Under 1000 lines each
- **Code quality**: Pylint 9.30/10

## Migration from Old Version

No changes needed! The refactored version maintains 100% backward compatibility with the original monolithic `netbox_filters.py` file. All existing playbooks will continue to work without modification.
