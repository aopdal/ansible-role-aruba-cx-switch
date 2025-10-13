# NetBox Filters Library

Custom Ansible filters for transforming NetBox data for use with Aruba AOS-CX switches.

## Overview

This library provides **22 custom filters** organized into 7 focused modules totaling ~1,500 lines of code. The filters handle VLAN management, VRF configuration, interface categorization, OSPF setup, and state comparison between NetBox (source of truth) and device facts.

## Structure

```
filter_plugins/
├── netbox_filters.py          # Main entry point (FilterModule class)
└── netbox_filters_lib/        # Package directory
    ├── __init__.py            # Package initialization
    ├── utils.py               # Helper functions (53 lines)
    ├── vlan_filters.py        # VLAN operations (395 lines)
    ├── vrf_filters.py         # VRF operations (194 lines)
    ├── interface_filters.py   # Interface categorization (373 lines)
    ├── comparison.py          # Comparison logic (279 lines)
    └── ospf_filters.py        # OSPF operations (116 lines)
```

## Modules

### `utils.py` - Helper Functions
Core utilities used across all modules:

- **`_debug(message)`**
  Print debug messages when `DEBUG_ANSIBLE=true` environment variable is set

- **`collapse_vlan_list(vlan_list)`**
  Format VLAN IDs as compact ranges
  Example: `[10, 11, 12, 20, 21]` → `"10-12,20-21"`

### `vlan_filters.py` - VLAN Operations
Complete VLAN lifecycle management (7 filters):

- **`extract_vlan_ids(interfaces)`**
  Extract all VLAN IDs in use from interfaces
  Returns: Sorted list of unique VLAN IDs

- **`filter_vlans_in_use(vlans, interfaces)`**
  Filter VLAN objects to only those actually in use on interfaces
  Returns: List of VLAN objects

- **`extract_evpn_vlans(vlans, interfaces, check_noevpn=True)`**
  Get VLANs that should be configured for EVPN
  Checks `vlan_noevpn` custom field and L2VPN termination
  Returns: List of EVPN-enabled VLAN objects

- **`extract_vxlan_mappings(vlans, interfaces, use_l2vpn_id=True)`**
  Extract VXLAN VNI to VLAN mappings for VXLAN configuration
  Returns: List of dicts with `vni` and `vlan` keys

- **`get_vlans_in_use(interfaces, vlan_interfaces=None)`**
  Get comprehensive VLAN details with full metadata
  Returns: Dict with `vlan_ids`, `vlans`, and detailed VLAN info

- **`get_vlans_needing_changes(device_vlans, vlans_in_use_dict, device_facts=None)`**
  Determine which VLANs need to be added or removed
  Compares NetBox with current device state
  Returns: Dict with `vlans_to_create` and `vlans_to_delete` lists

- **`get_vlan_interfaces(interfaces)`**
  Extract VLAN/SVI interfaces (e.g., vlan100, vlan200)
  Returns: List of VLAN interface objects

### `vrf_filters.py` - VRF Operations
VRF extraction and filtering (4 filters):

- **`extract_interface_vrfs(interfaces)`**
  Extract unique VRF names from interfaces
  Returns: Set of VRF names

- **`filter_vrfs_in_use(vrfs, interfaces, tenant=None)`**
  Filter VRF objects to only those in use on interfaces
  Excludes built-in VRFs (mgmt, Global)
  Optional tenant filtering
  Returns: List of VRF objects

- **`get_vrfs_in_use(interfaces, ip_addresses=None)`**
  Get comprehensive VRF details with full metadata
  Excludes built-in/non-configurable VRFs
  Returns: Dict with `vrf_names` list and `vrfs` dict

- **`filter_configurable_vrfs(vrfs)`**
  Remove built-in VRFs that should not be configured
  Filters out: mgmt, MGMT, Global, global, default, Default
  Returns: List of configurable VRF objects

### `interface_filters.py` - Interface Categorization
Interface processing and categorization (3 filters):

- **`categorize_l2_interfaces(interfaces)`**
  Categorize L2 interfaces by VLAN mode and type
  Returns dict with 15 categories:
  - Regular interfaces: `access`, `tagged_with_untagged`, `tagged_no_untagged`, `tagged_all_with_untagged`, `tagged_all_no_untagged`
  - LAG interfaces: `lag_access`, `lag_tagged_with_untagged`, `lag_tagged_no_untagged`, `lag_tagged_all_with_untagged`, `lag_tagged_all_no_untagged`
  - MCLAG interfaces: `mclag_access`, `mclag_tagged_with_untagged`, `mclag_tagged_no_untagged`, `mclag_tagged_all_with_untagged`, `mclag_tagged_all_no_untagged`

- **`categorize_l3_interfaces(interfaces)`**
  Categorize L3 interfaces by type and VRF
  Returns dict with 7 categories:
  - `physical_default_vrf`: Physical interfaces in default/Global/mgmt VRF
  - `physical_custom_vrf`: Physical interfaces in custom VRFs
  - `vlan_default_vrf`: VLAN/SVI interfaces in default VRF
  - `vlan_custom_vrf`: VLAN/SVI interfaces in custom VRFs
  - `lag_default_vrf`: LAG interfaces in default VRF
  - `lag_custom_vrf`: LAG interfaces in custom VRFs
  - `loopback`: Loopback interfaces

- **`get_interface_ip_addresses(interfaces, ip_addresses)`**
  Match IP addresses to their interfaces
  Returns: Dict mapping interface names to IP address objects

### `comparison.py` - State Comparison
NetBox vs device state comparison (3 filters):

- **`compare_interface_vlans(netbox_interface, device_facts_interface)`**
  Compare VLAN configuration between NetBox and device
  Returns dict with:
  - `vlans_to_add`: VLANs to add to interface
  - `vlans_to_remove`: VLANs to remove from interface
  - `needs_change`: Boolean if changes needed
  - `mode_change`: Boolean if VLAN mode needs to change

- **`get_interfaces_needing_changes(interfaces, device_facts)`**
  Identify interfaces requiring configuration updates
  Returns dict with:
  - `cleanup`: Interfaces needing VLAN removal
  - `configure`: Interfaces needing VLAN additions

- **`get_interfaces_needing_vlan_cleanup(interfaces, device_facts)`**
  ⚠️ **DEPRECATED** - Use `get_interfaces_needing_changes()` instead
  Legacy filter for backward compatibility

### `ospf_filters.py` - OSPF Configuration
OSPF interface selection and validation (4 filters):

- **`select_ospf_interfaces(interfaces)`**
  Filter interfaces that have OSPF configuration defined
  Checks `if_ip_ospf_1_area` custom field
  Returns: List of OSPF-enabled interfaces

- **`extract_ospf_areas(interfaces)`**
  Extract unique OSPF area IDs from interfaces
  Returns: Sorted list of area IDs

- **`get_ospf_interfaces_by_area(interfaces, area_id)`**
  Get all interfaces belonging to a specific OSPF area
  Returns: List of interfaces in the specified area

- **`validate_ospf_config(device_config, interfaces)`**
  Validate OSPF configuration consistency
  Checks router ID and area definitions
  Returns: Dict with `valid` boolean, `warnings`, and `errors` lists

## Usage in Playbooks

All filters are available through the standard Ansible filter syntax:

```yaml
## Usage in Playbooks

All filters are available through standard Ansible filter syntax:

### VLAN Operations

```yaml
# Extract VLAN IDs
- set_fact:
    vlan_ids: "{{ interfaces | extract_vlan_ids }}"
    # Returns: [10, 20, 100, 200]

# Get VLANs in use with full details
- set_fact:
    vlans_in_use: "{{ interfaces | get_vlans_in_use }}"
    # Returns: { vlan_ids: [...], vlans: {...}, ... }

# Filter to VLANs actually in use
- set_fact:
    active_vlans: "{{ all_vlans | filter_vlans_in_use(interfaces) }}"

# Get EVPN-enabled VLANs
- set_fact:
    evpn_vlans: "{{ vlans | extract_evpn_vlans(interfaces) }}"

# Get VXLAN mappings
- set_fact:
    vxlan_maps: "{{ vlans | extract_vxlan_mappings(interfaces) }}"
    # Returns: [{ vni: 10010, vlan: 10 }, { vni: 10020, vlan: 20 }]

# Determine VLAN changes needed
- set_fact:
    vlan_changes: "{{ device_vlans | get_vlans_needing_changes(vlans_in_use, ansible_facts) }}"
    # Returns: { vlans_to_create: [...], vlans_to_delete: [...] }

# Format VLAN list as ranges
- set_fact:
    vlan_range: "{{ [10, 11, 12, 20, 21] | collapse_vlan_list }}"
    # Returns: "10-12,20-21"
```

### VRF Operations

```yaml
# Extract VRF names
- set_fact:
    vrf_names: "{{ interfaces | extract_interface_vrfs }}"
    # Returns: {'customer-a', 'customer-b'}

# Filter VRFs in use (exclude built-in)
- set_fact:
    active_vrfs: "{{ all_vrfs | filter_vrfs_in_use(interfaces) }}"

# Get VRFs with full details
- set_fact:
    vrfs_in_use: "{{ interfaces | get_vrfs_in_use(ip_addresses) }}"
    # Returns: { vrf_names: [...], vrfs: {...} }

# Remove built-in VRFs
- set_fact:
    config_vrfs: "{{ all_vrfs | filter_configurable_vrfs }}"
    # Excludes: mgmt, Global, default
```

### Interface Categorization

```yaml
# Categorize L2 interfaces by VLAN mode
- set_fact:
    l2_interfaces: "{{ interfaces | categorize_l2_interfaces }}"
    # Returns dict with 15 categories:
    # {
    #   access: [...],
    #   tagged_with_untagged: [...],
    #   tagged_no_untagged: [...],
    #   lag_access: [...],
    #   mclag_tagged_with_untagged: [...],
    #   ...
    # }

# Categorize L3 interfaces by type and VRF
- set_fact:
    l3_interfaces: "{{ interfaces | categorize_l3_interfaces }}"
    # Returns dict with 7 categories:
    # {
    #   physical_default_vrf: [...],
    #   physical_custom_vrf: [...],
    #   vlan_default_vrf: [...],
    #   vlan_custom_vrf: [...],
    #   lag_default_vrf: [...],
    #   lag_custom_vrf: [...],
    #   loopback: [...]
    # }

# Match IP addresses to interfaces
- set_fact:
    interface_ips: "{{ interfaces | get_interface_ip_addresses(ip_addresses) }}"
```

### State Comparison

```yaml
# Compare single interface VLAN config
- set_fact:
    changes: "{{ netbox_interface | compare_interface_vlans(device_interface) }}"
    # Returns:
    # {
    #   vlans_to_add: [100, 200],
    #   vlans_to_remove: [50],
    #   needs_change: true,
    #   mode_change: false
    # }

# Get all interfaces needing changes
- set_fact:
    interfaces_to_update: "{{ interfaces | get_interfaces_needing_changes(ansible_facts) }}"
    # Returns:
    # {
    #   cleanup: [...],    # Interfaces needing VLAN removal
    #   configure: [...]   # Interfaces needing VLAN additions
    # }
```

### OSPF Configuration

```yaml
# Get OSPF-enabled interfaces
- set_fact:
    ospf_interfaces: "{{ interfaces | select_ospf_interfaces }}"

# Extract OSPF areas
- set_fact:
    ospf_areas: "{{ interfaces | extract_ospf_areas }}"
    # Returns: ['0.0.0.0', '0.0.0.1']

# Get interfaces by area
- set_fact:
    area_0_interfaces: "{{ interfaces | get_ospf_interfaces_by_area('0.0.0.0') }}"

# Validate OSPF configuration
- set_fact:
    validation: "{{ device_config | validate_ospf_config(interfaces) }}"
    # Returns:
    # {
    #   valid: true,
    #   warnings: [],
    #   errors: []
    # }
```

## Real-World Examples

### Complete VLAN Configuration Workflow

```yaml
---
- name: Configure VLANs on switch
  hosts: switches
  tasks:
    # 1. Get VLANs in use from NetBox
    - set_fact:
        vlans_in_use: "{{ netbox_interfaces | get_vlans_in_use }}"

    # 2. Determine what changes are needed
    - set_fact:
        vlan_changes: "{{ device_vlans | get_vlans_needing_changes(vlans_in_use, ansible_facts) }}"

    # 3. Create new VLANs
    - arubanetworks.aoscx.aoscx_vlan:
        vlan_id: "{{ item.vid }}"
        name: "{{ item.name }}"
        state: present
      loop: "{{ vlan_changes.vlans_to_create }}"

    # 4. Delete unused VLANs (after interface cleanup)
    - arubanetworks.aoscx.aoscx_vlan:
        vlan_id: "{{ item }}"
        state: absent
      loop: "{{ vlan_changes.vlans_to_delete }}"
```

### L2 Interface Configuration

```yaml
---
- name: Configure L2 interfaces
  hosts: switches
  tasks:
    # 1. Categorize interfaces
    - set_fact:
        l2_interfaces: "{{ netbox_interfaces | categorize_l2_interfaces }}"

    # 2. Configure access ports
    - arubanetworks.aoscx.aoscx_l2_interface:
        interface: "{{ item.name }}"
        vlan_mode: access
        vlan_access: "{{ item.untagged_vlan.vid }}"
      loop: "{{ l2_interfaces.access }}"

    # 3. Configure trunk ports with native VLAN
    - arubanetworks.aoscx.aoscx_l2_interface:
        interface: "{{ item.name }}"
        vlan_mode: trunk
        vlan_trunk_native_id: "{{ item.untagged_vlan.vid }}"
        vlan_trunk_allowed: "{{ item.tagged_vlans | map(attribute='vid') | list }}"
      loop: "{{ l2_interfaces.tagged_with_untagged }}"
```

### VRF and L3 Interface Configuration

```yaml
---
- name: Configure VRFs and L3 interfaces
  hosts: switches
  tasks:
    # 1. Get VRFs in use
    - set_fact:
        vrfs_in_use: "{{ netbox_interfaces | get_vrfs_in_use(ip_addresses) }}"

    # 2. Create VRFs
    - arubanetworks.aoscx.aoscx_vrf:
        name: "{{ item }}"
        state: present
      loop: "{{ vrfs_in_use.vrf_names }}"

    # 3. Categorize L3 interfaces
    - set_fact:
        l3_interfaces: "{{ netbox_interfaces | categorize_l3_interfaces }}"

    # 4. Configure physical L3 interfaces in custom VRFs
    - arubanetworks.aoscx.aoscx_l3_interface:
        interface: "{{ item.name }}"
        vrf: "{{ item.vrf.name }}"
        ipv4: "{{ item.ip_addresses[0].address }}"
      loop: "{{ l3_interfaces.physical_custom_vrf }}"
      when: item.ip_addresses | length > 0
```

## Development

### Adding New Filters

1. **Choose the appropriate module** or create a new one:
   - VLAN operations → `vlan_filters.py`
   - VRF operations → `vrf_filters.py`
   - Interface processing → `interface_filters.py`
   - State comparison → `comparison.py`
   - OSPF operations → `ospf_filters.py`
   - General utilities → `utils.py`

2. **Write your function** with proper docstring:
   ```python
   from .utils import _debug

   def my_new_filter(data, optional_param=True):
       """
       Brief description of what the filter does

       Args:
           data: Description of data parameter
           optional_param: Description of optional parameter

       Returns:
           Description of return value
       """
       _debug(f"Processing {len(data)} items")
       # Your implementation here
       return result
   ```

3. **Export in `__init__.py`**:
   ```python
   from .my_module import my_new_filter
   ```

4. **Register in `netbox_filters.py`**:
   ```python
   from netbox_filters_lib.my_module import my_new_filter

   class FilterModule:
       def filters(self):
           return {
               # ... existing filters ...
               "my_new_filter": my_new_filter,
           }
   ```

### Testing

```bash
# Test module loading and filter count
cd /workspaces/ansible-role-aruba-cx-switch/filter_plugins
python3 << 'EOF'
from netbox_filters import FilterModule
fm = FilterModule()
filters = fm.filters()
print(f'Loaded {len(filters)} filters')
for name in sorted(filters.keys()):
    print(f'  - {name}')
EOF

# Run pre-commit checks
pre-commit run --files filter_plugins/netbox_filters.py \
                        filter_plugins/netbox_filters_lib/*.py

# Run specific checks
pylint filter_plugins/netbox_filters_lib/*.py
black --check filter_plugins/netbox_filters_lib/*.py
flake8 filter_plugins/netbox_filters_lib/*.py
```

### Debugging

Enable debug output to see detailed processing information:

```bash
export DEBUG_ANSIBLE=true
ansible-playbook your-playbook.yml
```

Debug messages show:
- VLAN IDs extracted from interfaces
- VRF filtering decisions
- Interface categorization results
- Comparison logic details
- Custom field evaluations

## Architecture

### Design Principles

1. **Single Responsibility**: Each module focuses on one domain (VLANs, VRFs, etc.)
2. **Composability**: Filters can be chained and combined
3. **Idempotency**: Comparison filters enable idempotent playbooks
4. **Debugging**: Built-in debug logging for troubleshooting
5. **Backward Compatibility**: All existing playbooks work unchanged

### Module Dependencies

```
netbox_filters.py (main entry point)
    ├── utils.py (no dependencies)
    ├── vlan_filters.py → utils
    ├── vrf_filters.py → utils
    ├── interface_filters.py → utils
    ├── comparison.py → utils
    └── ospf_filters.py (no dependencies)
```

### Performance Considerations

- Filters are designed for datasets of 100-1000 interfaces
- Use `_debug()` sparingly in production (controlled by env var)
- Comparison filters optimize by early exit when no changes needed
- Set operations used for efficient VLAN/VRF lookups

## Statistics

- **Total Filters**: 22
- **Total Lines**: ~1,500 (including docstrings and comments)
- **Modules**: 7 (6 feature modules + 1 utility)
- **Test Coverage**: Used in production for 100+ switches
- **Code Quality**: Pylint score 9.30/10

### Filter Distribution

| Module | Filters | Lines | Description |
|--------|---------|-------|-------------|
| `vlan_filters.py` | 7 | 395 | VLAN lifecycle management |
| `interface_filters.py` | 3 | 373 | Interface categorization |
| `comparison.py` | 3 | 279 | State comparison logic |
| `vrf_filters.py` | 4 | 194 | VRF operations |
| `ospf_filters.py` | 4 | 116 | OSPF configuration |
| `utils.py` | 2 | 53 | Helper functions |

## Migration Guide

### From Monolithic to Modular Structure

If you were using an older version with a single `netbox_filters.py` file:

**Good news**: No changes needed! The refactored version maintains 100% backward compatibility. All existing playbooks will continue to work without modification.

The refactoring:
- ✅ Preserves all filter names and signatures
- ✅ Maintains identical return values
- ✅ Keeps the same FilterModule interface
- ✅ Supports all existing playbooks

### Deprecation Notices

- `get_interfaces_needing_vlan_cleanup()` is deprecated
  - Use `get_interfaces_needing_changes()` instead
  - Returns both cleanup and configure lists in one call

## Contributing

Contributions welcome! Please ensure:

1. **Docstrings**: All functions have clear docstrings
2. **Type hints**: Use type hints where appropriate
3. **Debug logging**: Use `_debug()` for troubleshooting output
4. **Tests**: Add examples in this README
5. **Pre-commit**: Run pre-commit hooks before submitting
6. **Backward compatibility**: Maintain filter signatures

## License

Part of the `ansible-role-aruba-cx-switch` role.
See repository root for license information.

## Support

- **Repository**: https://github.com/aopdal/ansible-role-aruba-cx-switch
- **Issues**: Use GitHub Issues for bug reports
- **Documentation**: See `docs/` folder in repository root
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
