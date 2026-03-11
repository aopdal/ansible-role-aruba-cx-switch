# Filter Plugins - Detailed Reference

Comprehensive documentation for the filter plugins used with Aruba AOS-CX switches.

## What Are Filter Plugins? (For Non-Python Experts)

In Ansible, a **filter** is a small function that transforms data. You use it in your playbook with the pipe (`|`) symbol, like this:

```yaml
# Take a list of interfaces, pipe it through a filter, get categorized results
- set_fact:
    l2: "{{ my_interfaces | categorize_l2_interfaces }}"
```

Think of filters like functions in a spreadsheet: data goes in, transformed data comes out. The filters in this role take raw data from NetBox (your network source of truth) and transform it into structures that Ansible can use to configure Aruba AOS-CX switches.

**You don't need to know Python to use these filters.** You just need to know:
1. What data to pass in (the input)
2. What you get back (the output)
3. Where to use the filter in your playbook

Each filter's documentation below tells you exactly that.

---

## Overview

The filter plugins library provides **38 custom Ansible filters** organized across **11 modules** in two filter plugin files.

- **`netbox_filters.py`** - Main plugin with 34 filters (NetBox data transformation)
- **`rest_api_transforms.py`** - Separate plugin with 4 filters (REST API format conversion)

---

## Module Documentation

### Core Utilities

**[Utils Module](utils.md)** - Helper functions and debugging
**Functions**: 5 (2 exposed as Ansible filters, 3 internal helpers)

Foundation module providing:
- Debug message printing with environment variable control
- VLAN list range formatting (e.g., `10-12,20-21`)
- Interface selection for idempotent mode
- IP address extraction and categorization (IPv4/IPv6)
- IP changes population for idempotent checks

---

### L3 Configuration

**[L3 Config Helpers](l3_config_helpers.md)** - L3 interface configuration optimization
**Filters**: 6

Configuration building and helper functions:
- Interface IP grouping (flat per-IP list → per-interface with all addresses)
- Interface name formatting for AOS-CX
- IP version detection (IPv4/IPv6)
- VRF extraction with safe fallback
- Complete L3 config line generation (all IPs, VRF, MTU, OSPF — once per interface)
- Supports physical, LAG, VLAN, and sub-interfaces

**Key Filters:**
- `group_interface_ips()` - Group per-IP list into per-interface items
- `format_interface_name()` - Format interface names
- `is_ipv4_address()` / `is_ipv6_address()` - IP version detection
- `get_interface_vrf()` - Extract VRF with fallback
- `build_l3_config_lines()` - Build all config commands for an interface

---

### VLAN Operations

**[VLAN Filters](vlan_filters.md)** - Complete VLAN lifecycle management
**Filters**: 8

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

**[VRF Filters](vrf_filters.md)** - VRF extraction, filtering, and route target management
**Filters**: 6

Manages VRF identification and filtering:
- VRF extraction from interfaces and IP addresses
- Automatic exclusion of built-in VRFs (mgmt, Global, default)
- Multi-tenant VRF filtering
- Route target name extraction
- Address-family-aware route target configuration building

**Key Filters:**
- `extract_interface_vrfs()` - Get VRF names from interfaces
- `filter_vrfs_in_use()` - Filter with tenant support
- `get_vrfs_in_use()` - Comprehensive VRF details
- `filter_configurable_vrfs()` - Safety filter for built-in VRFs
- `get_all_rt_names()` - Extract all route target names
- `build_vrf_rt_config()` - Build per-VRF, per-address-family RT config

---

### Interface Processing

Interface processing is split into three focused modules:

**Interface Categorization** (`interface_categorization.py`)
**Filters**: 2

- L2 interface categorization (15 categories)
- L3 interface categorization (9 categories)
- Key filters: `categorize_l2_interfaces()`, `categorize_l3_interfaces()`

**IP Address Processing** (`interface_ip_processing.py`)
**Filters**: 1

- Interface/IP address matching with anycast gateway support
- Key filter: `get_interface_ip_addresses()`

**Change Detection** (`interface_change_detection.py`)
**Filters**: 1

- Idempotent change detection for interfaces
- Key filter: `get_interfaces_needing_config_changes()`

See **[Interface Filters](interface_filters.md)** for detailed documentation.

---

### State Comparison

**[Comparison Module](comparison.md)** - NetBox vs device state comparison
**Filters**: 2

Enables idempotent operations:
- VLAN configuration comparison
- Interface change detection
- VLAN cleanup identification
- Two-phase update support (cleanup then configure)

**Key Filters:**
- `compare_interface_vlans()` - Single interface VLAN comparison
- `get_interfaces_needing_changes()` - Batch interface analysis

---

### OSPF Configuration

**[OSPF Filters](ospf_filters.md)** - OSPF interface selection and validation
**Filters**: 4

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

### BGP Session Enrichment

**[BGP Filters](bgp_filters.md)** - BGP session VRF and address-family resolution
**Filters**: 1

Enriches BGP session data from the NetBox BGP plugin:
- Cross-references BGP session local addresses with interface IPs
- Determines VRF membership (global vs. per-tenant)
- Identifies address family (IPv4 vs. IPv6)

**Key Filter:**
- `get_bgp_session_vrf_info()` - Enrich sessions with VRF and AF metadata

---

### REST API Transforms

**[REST API Transforms](rest_api_transforms.md)** - REST API response normalization
**Filters**: 4 *(separate plugin file: `rest_api_transforms.py`)*

Converts raw Aruba AOS-CX REST API responses into the format expected by `aoscx_facts`-based logic:
- Interface data normalization (admin state, IPv6 URL-decoding)
- VLAN data normalization
- EVPN VLAN data extraction
- VNI data extraction

**Key Filters:**
- `rest_api_to_aoscx_interfaces()` - Normalize interface data
- `rest_api_to_aoscx_vlans()` - Normalize VLAN data
- `rest_api_to_aoscx_evpn_vlans()` - Extract EVPN VLAN config
- `rest_api_to_aoscx_vnis()` - Extract VNI config

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

#### BGP Configuration
```yaml
# Enrich BGP sessions with VRF info
- set_fact:
    bgp_sessions: "{{ nb_bgp_sessions | get_bgp_session_vrf_info(netbox_interfaces) }}"

# Configure global sessions (underlay/EVPN)
- arubanetworks.aoscx.aoscx_bgp_neighbor:
    vrf: default
    neighbor: "{{ item.remote_address.address | ansible.utils.ipaddr('address') }}"
    remote_as: "{{ item.remote_as.asn }}"
  loop: "{{ bgp_sessions | selectattr('_vrf', 'equalto', 'default') | list }}"
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

#### Utils (2 filters + 3 internal)
- `collapse_vlan_list(vlan_list)` - Format VLAN ranges
- `select_interfaces_to_configure(interfaces, idempotent_mode, changes)` - Idempotent selection
- *Internal*: `_debug()`, `extract_ip_addresses()`, `populate_ip_changes()`

#### L3 Config Helpers (6 filters)
- `group_interface_ips(interface_ip_list)` - Group per-IP list into per-interface items
- `format_interface_name(name, type)` - Format interface names
- `is_ipv4_address(address)` - IPv4 detection
- `is_ipv6_address(address)` - IPv6 detection
- `get_interface_vrf(interface)` - Extract VRF name
- `build_l3_config_lines(item, type, vrf_type, l3_counters_enable, ospf_process_id)` - Build all config commands for an interface

#### VLAN Filters (8)
- `extract_vlan_ids(interfaces)` - Extract VLAN IDs
- `filter_vlans_in_use(vlans, interfaces)` - Filter to used VLANs
- `extract_evpn_vlans(vlans, interfaces, check_noevpn)` - EVPN VLANs
- `extract_vxlan_mappings(vlans, interfaces, use_l2vpn_id)` - VXLAN mappings
- `get_vlans_in_use(interfaces, vlan_interfaces)` - Comprehensive VLAN data
- `get_vlans_needing_changes(device_vlans, vlans_in_use, facts)` - Change detection
- `get_vlan_interfaces(interfaces)` - Extract SVIs
- `parse_evpn_evi_output(output)` - Parse show command

#### VRF Filters (6)
- `extract_interface_vrfs(interfaces)` - Extract VRF names
- `filter_vrfs_in_use(vrfs, interfaces, tenant)` - Filter VRFs
- `get_vrfs_in_use(interfaces, ip_addresses)` - Comprehensive VRF data
- `filter_configurable_vrfs(vrfs)` - Remove built-in VRFs
- `get_all_rt_names(vrf_details)` - Extract all route target names
- `build_vrf_rt_config(vrf_details)` - Build address-family RT config per VRF

#### Interface Categorization (2 filters)
- `categorize_l2_interfaces(interfaces)` - 15 L2 categories
- `categorize_l3_interfaces(interfaces)` - 9 L3 categories

#### Interface IP Processing (1 filter)
- `get_interface_ip_addresses(interfaces, ip_addresses)` - Match IPs to interfaces

#### Interface Change Detection (1 filter)
- `get_interfaces_needing_config_changes(interfaces, facts, enhanced_facts)` - Change detection

#### Comparison (2 filters)
- `compare_interface_vlans(nb_intf, device_intf)` - Single interface comparison
- `get_interfaces_needing_changes(interfaces, facts)` - Batch comparison

#### OSPF Filters (4)
- `select_ospf_interfaces(interfaces)` - Get OSPF interfaces
- `extract_ospf_areas(interfaces)` - Extract areas
- `get_ospf_interfaces_by_area(interfaces, area)` - Filter by area
- `validate_ospf_config(device, interfaces)` - Validate configuration

#### BGP Filters (1)
- `get_bgp_session_vrf_info(sessions, interfaces)` - Enrich BGP sessions with VRF/AF info

#### REST API Transforms (4) *(separate plugin)*
- `rest_api_to_aoscx_interfaces(rest_data)` - Normalize interface data
- `rest_api_to_aoscx_vlans(rest_data)` - Normalize VLAN data
- `rest_api_to_aoscx_evpn_vlans(rest_data)` - Extract EVPN VLAN config
- `rest_api_to_aoscx_vnis(rest_data)` - Extract VNI config

---

## By Use Case

### Idempotent Operations
- `get_vlans_needing_changes()` - VLAN idempotency
- `get_interfaces_needing_changes()` - Interface idempotency
- `get_interfaces_needing_config_changes()` - Granular interface change detection
- `compare_interface_vlans()` - VLAN comparison
- `select_interfaces_to_configure()` - Interface selection

### Data Extraction
- `extract_vlan_ids()` - VLAN IDs
- `extract_interface_vrfs()` - VRF names
- `extract_ospf_areas()` - OSPF areas
- `get_interface_ip_addresses()` - Interface/IP matching
- `get_all_rt_names()` - Route target names

### Filtering
- `filter_vlans_in_use()` - Active VLANs
- `filter_vrfs_in_use()` - Active VRFs
- `filter_configurable_vrfs()` - Safe VRFs
- `select_ospf_interfaces()` - OSPF interfaces
- `get_ospf_interfaces_by_area()` - Area filtering

### Categorization
- `categorize_l2_interfaces()` - L2 by mode/type (15 categories)
- `categorize_l3_interfaces()` - L3 by type/VRF (9 categories)

### BGP
- `get_bgp_session_vrf_info()` - Enrich sessions with VRF and address family

### EVPN/VXLAN
- `extract_evpn_vlans()` - EVPN VLANs
- `extract_vxlan_mappings()` - VNI mappings
- `parse_evpn_evi_output()` - Parse show output

### Route Target Management
- `get_all_rt_names()` - Collect all RT names
- `build_vrf_rt_config()` - Build per-VRF, per-AF RT structure

### REST API Normalization
- `rest_api_to_aoscx_interfaces()` - Interface data
- `rest_api_to_aoscx_vlans()` - VLAN data
- `rest_api_to_aoscx_evpn_vlans()` - EVPN data
- `rest_api_to_aoscx_vnis()` - VNI data

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
5. Register in `netbox_filters.py` (or create own `FilterModule` for separate plugin)
6. Document in this guide and create/update module doc

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
print(f'Loaded {len(fm.filters())} filters from netbox_filters')

from filter_plugins.rest_api_transforms import FilterModule as RestFM
rfm = RestFM()
print(f'Loaded {len(rfm.filters())} filters from rest_api_transforms')
EOF
```

---

## See Also

- [Main Filter Plugins Overview](../FILTER_PLUGINS.md) - Overview document
- [Development Guide](../DEVELOPMENT.md) - Contributing guidelines
- [NetBox Integration](../NETBOX_INTEGRATION.md) - NetBox setup
- [L2 Interface Modes](../L2_INTERFACE_MODES.md) - VLAN mode reference
- [EVPN/VXLAN Configuration](../EVPN_VXLAN_CONFIGURATION.md) - EVPN/VXLAN guide

---

## Statistics

| Module | Filters | Description |
|--------|---------|-------------|
| **vlan_filters.py** | 8 | VLAN lifecycle management |
| **vrf_filters.py** | 6 | VRF operations and route targets |
| **l3_config_helpers.py** | 6 | L3 configuration optimization |
| **ospf_filters.py** | 4 | OSPF configuration |
| **rest_api_transforms.py** | 4 | REST API data normalization |
| **interface_categorization.py** | 2 | Interface categorization |
| **comparison.py** | 2 | State comparison logic |
| **utils.py** | 2 | Helper functions and utilities |
| **interface_change_detection.py** | 1 | Change detection and idempotency |
| **interface_ip_processing.py** | 1 | IP address matching |
| **bgp_filters.py** | 1 | BGP session enrichment |
| **Total** | **38** | 11 modules across 2 plugin files |

---

## Support

- **Repository**: https://github.com/aopdal/ansible-role-aruba-cx-switch
- **Issues**: GitHub Issues
- **Documentation**: [docs/](../) folder
