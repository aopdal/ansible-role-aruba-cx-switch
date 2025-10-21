# Filter Plugins - Detailed Reference

Comprehensive documentation for the NetBox Filters Library used with Aruba AOS-CX switches.

## Overview

The filter plugins library provides 22 custom Ansible filters organized into 6 specialized modules. These filters transform NetBox data for use in switch configuration playbooks, handle state comparison for idempotent operations, and categorize interfaces for targeted configuration.

**Total Filters**: 22
**Total Lines of Code**: ~1,500
**Modules**: 6 feature modules + 1 utility module

---

## Module Documentation

### Core Utilities

**[Utils Module](utils.md)** - Helper functions and debugging
**Functions**: 3
**Lines**: 100

Foundation module providing:
- Debug message printing with environment variable control
- VLAN list range formatting (e.g., `10-12,20-21`)
- Interface selection for idempotent mode

---

### VLAN Operations

**[VLAN Filters](vlan_filters.md)** - Complete VLAN lifecycle management
**Filters**: 8 + 1 parser
**Lines**: 455

Most comprehensive module handling:
- VLAN ID extraction from interfaces
- VLAN filtering and selection
- EVPN/VXLAN configuration extraction
- Idempotent VLAN change detection
- VLAN interface (SVI) identification
- EVPN EVI output parsing

**Key Filters:**
- `extract_vlan_ids()` - Get all VLAN IDs in use
- `get_vlans_in_use()` - Comprehensive VLAN details
- `get_vlans_needing_changes()` - Idempotent change detection
- `extract_evpn_vlans()` - EVPN-enabled VLANs
- `extract_vxlan_mappings()` - VNI-to-VLAN mappings

---

### VRF Operations

**[VRF Filters](vrf_filters.md)** - VRF extraction and filtering
**Filters**: 4
**Lines**: 192

Manages VRF identification and filtering:
- VRF extraction from interfaces and IP addresses
- Automatic exclusion of built-in VRFs (mgmt, Global, default)
- Multi-tenant VRF filtering
- VRF validation and safety checks

**Key Filters:**
- `extract_interface_vrfs()` - Get VRF names from interfaces
- `filter_vrfs_in_use()` - Filter with tenant support
- `get_vrfs_in_use()` - Comprehensive VRF details
- `filter_configurable_vrfs()` - Safety filter for built-in VRFs

---

### Interface Processing

**[Interface Filters](interface_filters.md)** - Interface categorization and processing
**Filters**: 4
**Lines**: 802

Advanced interface categorization:
- L2 interface categorization (15 categories)
- L3 interface categorization (7 categories)
- Interface/IP address matching
- Idempotent change detection for interfaces

**Key Filters:**
- `categorize_l2_interfaces()` - 15 L2 categories
- `categorize_l3_interfaces()` - 7 L3 categories by type/VRF
- `get_interface_ip_addresses()` - Match IPs to interfaces
- `get_interfaces_needing_config_changes()` - Idempotent interface updates

---

### State Comparison

**[Comparison Module](comparison.md)** - NetBox vs device state comparison
**Filters**: 3 (1 deprecated)
**Lines**: 279

Enables idempotent operations:
- VLAN configuration comparison
- Interface change detection
- VLAN cleanup identification
- Two-phase update support (cleanup then configure)

**Key Filters:**
- `compare_interface_vlans()` - Single interface VLAN comparison
- `get_interfaces_needing_changes()` - Batch interface analysis
- ~~`get_interfaces_needing_vlan_cleanup()`~~ - Deprecated

---

### OSPF Configuration

**[OSPF Filters](ospf_filters.md)** - OSPF interface selection and validation
**Filters**: 4
**Lines**: 112

OSPF-specific operations:
- OSPF interface identification from custom fields
- OSPF area extraction
- Area-based interface filtering
- Configuration validation

**Key Filters:**
- `select_ospf_interfaces()` - Get OSPF-enabled interfaces
- `extract_ospf_areas()` - List all areas in use
- `get_ospf_interfaces_by_area()` - Filter by area
- `validate_ospf_config()` - Pre-deployment validation

---

## Quick Reference

### Common Workflows

#### VLAN Management
```yaml
# Get VLANs in use
- set_fact:
    vlans: "{{ interfaces | get_vlans_in_use }}"

# Determine changes needed
- set_fact:
    changes: "{{ device_vlans | get_vlans_needing_changes(vlans, ansible_facts) }}"

# Create/delete VLANs
- arubanetworks.aoscx.aoscx_vlan:
    vlan_id: "{{ item.vid }}"
  loop: "{{ changes.vlans_to_create }}"
```

#### VRF Management
```yaml
# Get VRFs in use (auto-filters built-in VRFs)
- set_fact:
    vrfs: "{{ interfaces | get_vrfs_in_use(ip_addresses) }}"

# Create VRFs
- arubanetworks.aoscx.aoscx_vrf:
    name: "{{ item }}"
  loop: "{{ vrfs.vrf_names }}"
```

#### L2 Interface Configuration
```yaml
# Categorize interfaces
- set_fact:
    l2: "{{ interfaces | categorize_l2_interfaces }}"

# Configure access ports
- arubanetworks.aoscx.aoscx_l2_interface:
    interface: "{{ item.name }}"
    vlan_mode: access
    vlan_access: "{{ item.untagged_vlan.vid }}"
  loop: "{{ l2.access }}"

# Configure trunk ports
- arubanetworks.aoscx.aoscx_l2_interface:
    interface: "{{ item.name }}"
    vlan_mode: trunk
    vlan_trunk_native_id: "{{ item.untagged_vlan.vid | default(omit) }}"
    vlan_trunk_allowed: "{{ item.tagged_vlans | map(attribute='vid') | list }}"
  loop: "{{ l2.tagged_with_untagged }}"
```

#### L3 Interface Configuration
```yaml
# Match IPs to interfaces
- set_fact:
    intf_ips: "{{ interfaces | get_interface_ip_addresses(ip_addresses) }}"

# Categorize
- set_fact:
    l3: "{{ intf_ips | categorize_l3_interfaces }}"

# Configure physical L3 in custom VRF
- arubanetworks.aoscx.aoscx_l3_interface:
    interface: "{{ item.interface_name }}"
    vrf: "{{ item.interface.vrf.name }}"
    ipv4: "{{ item.address }}"
  loop: "{{ l3.physical_custom_vrf }}"
```

#### Idempotent Updates
```yaml
# Detect changes
- set_fact:
    changes: "{{ interfaces | get_interfaces_needing_changes(ansible_facts) }}"

# Configure only changed interfaces
- arubanetworks.aoscx.aoscx_l2_interface:
    interface: "{{ item.name }}"
    # ... configuration ...
  loop: "{{ changes.configure }}"
  when: changes.configure | length > 0
```

#### OSPF Configuration
```yaml
# Get OSPF interfaces
- set_fact:
    ospf_intfs: "{{ interfaces | select_ospf_interfaces }}"

# Validate configuration
- set_fact:
    validation: "{{ device | validate_ospf_config(interfaces) }}"

# Configure OSPF
- arubanetworks.aoscx.aoscx_ospf_interface:
    interface: "{{ item.name }}"
    area: "{{ item.custom_fields.if_ip_ospf_1_area }}"
  loop: "{{ ospf_intfs }}"
```

---

## Filter Index

### By Module

#### Utils (3 functions)
- `_debug(message)` - Debug output
- `collapse_vlan_list(vlan_list)` - Format VLAN ranges
- `select_interfaces_to_configure(interfaces, idempotent_mode, changes)` - Idempotent selection

#### VLAN Filters (9)
- `extract_vlan_ids(interfaces)` - Extract VLAN IDs
- `filter_vlans_in_use(vlans, interfaces)` - Filter to used VLANs
- `extract_evpn_vlans(vlans, interfaces, check_noevpn)` - EVPN VLANs
- `extract_vxlan_mappings(vlans, interfaces, use_l2vpn_id)` - VXLAN mappings
- `get_vlans_in_use(interfaces, vlan_interfaces)` - Comprehensive VLAN data
- `get_vlans_needing_changes(device_vlans, vlans_in_use, facts)` - Change detection
- `get_vlan_interfaces(interfaces)` - Extract SVIs
- `parse_evpn_evi_output(output)` - Parse show command

#### VRF Filters (4)
- `extract_interface_vrfs(interfaces)` - Extract VRF names
- `filter_vrfs_in_use(vrfs, interfaces, tenant)` - Filter VRFs
- `get_vrfs_in_use(interfaces, ip_addresses)` - Comprehensive VRF data
- `filter_configurable_vrfs(vrfs)` - Remove built-in VRFs

#### Interface Filters (4)
- `categorize_l2_interfaces(interfaces)` - 15 L2 categories
- `categorize_l3_interfaces(interfaces)` - 7 L3 categories
- `get_interface_ip_addresses(interfaces, ip_addresses)` - Match IPs
- `get_interfaces_needing_config_changes(interfaces, facts)` - Change detection

#### Comparison (2 active)
- `compare_interface_vlans(nb_intf, device_intf)` - Single interface comparison
- `get_interfaces_needing_changes(interfaces, facts)` - Batch comparison

#### OSPF Filters (4)
- `select_ospf_interfaces(interfaces)` - Get OSPF interfaces
- `extract_ospf_areas(interfaces)` - Extract areas
- `get_ospf_interfaces_by_area(interfaces, area)` - Filter by area
- `validate_ospf_config(device, interfaces)` - Validate configuration

---

## By Use Case

### Idempotent Operations
- `get_vlans_needing_changes()` - VLAN idempotency
- `get_interfaces_needing_changes()` - Interface idempotency
- `compare_interface_vlans()` - VLAN comparison
- `select_interfaces_to_configure()` - Interface selection

### Data Extraction
- `extract_vlan_ids()` - VLAN IDs
- `extract_interface_vrfs()` - VRF names
- `extract_ospf_areas()` - OSPF areas
- `get_interface_ip_addresses()` - Interface/IP matching

### Filtering
- `filter_vlans_in_use()` - Active VLANs
- `filter_vrfs_in_use()` - Active VRFs
- `filter_configurable_vrfs()` - Safe VRFs
- `select_ospf_interfaces()` - OSPF interfaces
- `get_ospf_interfaces_by_area()` - Area filtering

### Categorization
- `categorize_l2_interfaces()` - L2 by mode/type
- `categorize_l3_interfaces()` - L3 by type/VRF

### EVPN/VXLAN
- `extract_evpn_vlans()` - EVPN VLANs
- `extract_vxlan_mappings()` - VNI mappings
- `parse_evpn_evi_output()` - Parse show output

### Validation
- `validate_ospf_config()` - OSPF validation

---

## Design Principles

1. **Single Responsibility**: Each filter does one thing well
2. **Composability**: Filters can be chained together
3. **Idempotency**: Comparison filters enable idempotent playbooks
4. **Debugging**: Built-in debug logging via `DEBUG_ANSIBLE` env var
5. **Safety**: Automatic exclusion of built-in/system resources
6. **Backward Compatibility**: Deprecated filters maintained for compatibility

---

## Performance Considerations

- Filters designed for datasets of 100-1,000 interfaces
- Debug output controlled by environment variable (zero overhead when disabled)
- Set operations used for efficient lookups
- Comparison filters optimize via early exit

---

## Development

### Adding New Filters

1. Choose appropriate module (or create new one)
2. Write function with proper docstring
3. Use `_debug()` for troubleshooting output
4. Export in `__init__.py`
5. Register in `netbox_filters.py`
6. Document in this guide

### Testing

```bash
# Enable debug mode
export DEBUG_ANSIBLE=true

# Run playbook
ansible-playbook site.yml

# Check filter loading
python3 << 'EOF'
from filter_plugins.netbox_filters import FilterModule
fm = FilterModule()
print(f'Loaded {len(fm.filters())} filters')
EOF
```

---

## See Also

- [Main Filter Plugins Overview](../FILTER_PLUGINS.md) - Overview document
- [Development Guide](../DEVELOPMENT.md) - Contributing guidelines
- [NetBox Integration](../NETBOX_INTEGRATION.md) - NetBox setup
- [L2 Interface Modes](../L2_INTERFACE_MODES.md) - VLAN mode reference
- [EVPN/VXLAN Configuration](../EVPN_VXLAN_CONFIGURATION.md) - EVPN/VXLAN guide
- [Interface Idempotent Implementation](../INTERFACE_IDEMPOTENT_IMPLEMENTATION.md) - Idempotent mode

---

## Statistics

| Module | Filters | Lines | Description |
|--------|---------|-------|-------------|
| **utils.py** | 3 | 100 | Helper functions and utilities |
| **vlan_filters.py** | 9 | 455 | VLAN lifecycle management |
| **vrf_filters.py** | 4 | 192 | VRF operations |
| **interface_filters.py** | 4 | 802 | Interface categorization |
| **comparison.py** | 2 | 279 | State comparison logic |
| **ospf_filters.py** | 4 | 112 | OSPF configuration |
| **Total** | **26** | **~1,940** | 6 modules + utilities |

---

## Support

- **Repository**: https://github.com/aopdal/ansible-role-aruba-cx-switch
- **Issues**: GitHub Issues
- **Documentation**: [docs/](../) folder
