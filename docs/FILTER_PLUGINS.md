# NetBox Filters Library

Custom Ansible filters for transforming NetBox data for use with Aruba AOS-CX switches.

## Overview

This library provides **32 custom filters** organized into 9 focused modules totaling ~2,161 lines of code. The filters handle VLAN management, VRF configuration, interface categorization, interface IP processing, L3 configuration optimization, change detection, OSPF setup, and state comparison between NetBox (source of truth) and device facts.

## ⚠️ Important: NetBox Data Interpretation

### Source of Truth Philosophy

These filters implement **intelligent interpretation** of NetBox data to handle common configuration patterns and edge cases. While this improves usability, it introduces a layer of logic between NetBox (the source of truth) and device configuration.

**Trade-off**: The filters compensate for certain NetBox configuration patterns, which means:
- ✅ **Benefit**: More forgiving of NetBox data modeling variations
- ⚠️ **Risk**: May mask incorrect NetBox configurations
- 📋 **Recommendation**: Maintain strict NetBox data hygiene to preserve true "source of truth" integrity

### Specific Interpretation Logic

#### Interface Mode Detection

**Filters**: `interface_categorization.py` and `interface_change_detection.py`

**Problem**: NetBox uses `mode: tagged` for both trunk ports and access ports with only a native VLAN.

**Filter Behavior**:
```python
# If NetBox has:
#   - mode: "tagged" (not "tagged-all")
#   - untagged_vlan: <vlan_id>
#   - tagged_vlans: [] (empty or missing)
#
# Filter interprets as: mode: "access"
#
# Note: mode: "tagged-all" is always treated as trunk,
# even with empty tagged_vlans list (allows all VLANs)
```

**Rationale**:
- A `mode: tagged` port with no tagged VLANs and only an untagged VLAN is functionally an access port
- A `mode: tagged-all` port allows all VLANs and is always a trunk, even if `tagged_vlans` list is empty

**Impact**:
- Prevents false positives when comparing NetBox `mode: tagged` (empty list) against device `vlan_mode: access`
- Correctly handles `mode: tagged-all` as trunk configuration
- Masks potential NetBox misconfiguration where user intended trunk but used `mode: tagged` with no VLANs

**Best Practice**:
- Use NetBox `mode: access` explicitly for access ports
- Use NetBox `mode: tagged` only when `tagged_vlans` list is populated
- Use NetBox `mode: tagged-all` for trunk ports that allow all VLANs (with or without native VLAN)
- Document your organization's NetBox modeling standards

#### Admin State Detection

**Filter**: `interface_change_detection.py`

**Problem**: AOS-CX devices expose multiple admin state fields with different meanings:
- `admin_state`: May show "down" for ports without physical link
- `forwarding_state.enablement`: Shows operational forwarding state
- `user_config.admin`: Shows configured admin intent (most reliable)

**Filter Behavior**:
```python
# Priority order:
# 1. user_config.admin (if exists)
# 2. forwarding_state.enablement (fallback)
# 3. admin_state (last resort)
```

**Impact**:
- Correctly handles ports configured as "up" but without physical link
- Prevents false positives where `admin_state: down` (no link) is compared against NetBox `enabled: true`

**Best Practice**:
- Trust that filter uses the most reliable state field
- Use `DEBUG_ANSIBLE=true` to see which state fields are being compared

### Recommendations

1. **Validate NetBox Data**: Regularly audit your NetBox configurations to ensure they accurately reflect intended state
2. **Use Debug Mode**: Set `DEBUG_ANSIBLE=true` to see filter decision-making in real-time
3. **Document Patterns**: Establish and document your organization's NetBox modeling patterns
4. **Test Changes**: When modifying filter logic, test against known-good configurations
5. **Consider Strictness**: For strict "source of truth" enforcement, consider removing interpretation logic and requiring exact NetBox data accuracy

### Performance Optimization

**Fact Gathering Strategy**: The role uses a centralized fact gathering approach to minimize API calls:

1. **Initial Gather** (`gather_facts.yml`): Collects interfaces + VLANs once at the start
2. **Analysis Phase**: Filters use existing facts from step 1 (no re-gathering)
   - `identify_vlan_changes.yml`: Uses existing `ansible_facts.network_resources`
   - `identify_interface_changes.yml`: Uses existing `ansible_facts.network_resources`
3. **Cleanup Phase** (idempotent mode only): Re-gathers facts after configuration to detect what needs cleanup

**Why This Matters**:
- Gathering facts makes REST API calls to the device (slow, especially for large configs)
- Original implementation gathered facts twice before any configuration (wasteful)
- Optimized version gathers once initially, then only re-gathers before cleanup when state has changed

**Debug Mode**: Use `DEBUG_ANSIBLE=true` to see filter decisions without debug output from fact gathering overhead

## L3 Interface IP Address Idempotency

### Overview

The role implements intelligent comparison of L3 interface IP addresses to minimize configuration time. The `get_interfaces_needing_config_changes()` filter (in `interface_filters.py`) compares NetBox's intended IP configuration with device facts and tracks which specific IP addresses need to be added.

### IPv4 Address Optimization

**Implementation**: Full comparison and granular change tracking

IPv4 addresses are compared between NetBox and device facts:
- Only IP addresses that **actually need to be added** are marked for configuration
- Tasks filter interfaces using `selectattr('_needs_add', 'equalto', true)`
- Significantly reduces configuration time by skipping unnecessary device connections
- IP version filtering uses simple colon check: IPv6 has `:`, IPv4 doesn't

**Example**:
```yaml
# Filter IPv4 addresses that need configuration
filtered_interfaces: >-
  {{
    interface_list
    | rejectattr('address', 'search', ':')
    | selectattr('_needs_add', 'equalto', true)
    | list
  }}
```

**Performance Impact**:
- Typical environment: 50+ interfaces with 2-5 IPs each
- Without filtering: 100-250 unnecessary configuration tasks
- With filtering: Only tasks for actual changes
- Time saved: Significant reduction in L3 configuration phase

### IPv6 Address Performance Trade-off

**Implementation**: Always configure, suppress false positives

IPv6 addresses in AOS-CX device facts are returned as REST API URL references:
```json
{
  "ip6_addresses": "/rest/v10.09/system/interfaces/vlan11/ip6_addresses"
}
```

**Challenge**: The actual IPv6 addresses are not available in facts, only URL references to where they can be fetched.

**Why Not Fetch IPv6 Data?**

Testing confirmed that fetching IPv6 addresses for comparison is **slower** than just applying configuration:

| Approach | Time Cost | Benefit |
|----------|-----------|---------|
| Fetch IPv6 via CLI | ~2-3s per interface | Skip config only if no changes |
| Apply idempotent config | ~0.5s per interface | Always correct, no overhead |

**Decision**: For 20+ interfaces, checking would take 40-60 seconds, while applying takes 10-15 seconds.

**Current Implementation**:
- IPv6 tasks **always execute** (no pre-comparison performed)
- Configuration remains idempotent at CLI level (duplicate commands have no effect)

**Example**:
```yaml
- name: Configure IPv6 address on VLAN interface
  arubanetworks.aoscx.aoscx_config:
    lines:
      - ipv6 address {{ item.address }}
    parents: interface {{ item.interface_name | format_interface_name('vlan') }}
  loop: "{{ filtered_interfaces }}"
  vars:
    filtered_interfaces: >-
      {{ interface_list | selectattr('address', 'search', ':') | list }}
```

### Filter Implementation Details

The `get_interfaces_needing_config_changes()` filter returns:
```python
{
    '_ip_changes': {
        'ipv4_to_add': ['10.1.1.1/24', '10.1.2.1/24'],  # Only IPs needing addition
        'ipv6_addresses': ['2001:db8::1/64']  # All IPv6 addresses (for reference)
    }
}
```

Tasks in `configure_l3_*.yml` files then:
1. Filter by IP version using colon check: `rejectattr('address', 'search', ':')` for IPv4
2. Use `aoscx_config` module which is inherently idempotent
3. Loopback tasks still use `_needs_add` with `aoscx_l3_interface` module

### Best Practices

**IPv4 Configuration**:
- ✅ Filter ensures only necessary changes are applied
- ✅ Dramatically reduces configuration time in large environments
- ✅ Maintains accurate "changed" status in Ansible output

**IPv6 Configuration**:
- ✅ Fastest approach: Apply idempotent configuration without pre-checking
- ⚠️ Accept that IPv6 tasks always run (performance-optimal trade-off)

**Debugging**:
```bash
# See which IPs are marked for addition
export DEBUG_ANSIBLE=true
ansible-playbook your-playbook.yml

# Output shows:
# "Interface vlan11: IPv4 changes needed: ['10.1.1.1/24']"
# "Interface vlan11: IPv6 addresses present: ['2001:db8::1/64']"
```

### Technical Background

**Why IPv6 is a URL Reference**:
- AOS-CX REST API structure: IPv6 addresses stored in separate endpoint
- Device facts use httpapi connection: Only returns URL references
- Retrieving actual data requires:
  - Switching to network_cli connection (SSH)
  - Executing CLI commands (`show ipv6 interface`)
  - Parsing unstructured output
  - Connection overhead: 2-3 seconds per interface

**Architecture Decision**:
- Primary connection: `arubanetworks.aoscx.aoscx` (REST API) for facts
- CLI tasks: Temporary switch to `network_cli` for configuration
- Performance: Checking would require connection switching for every interface
- Conclusion: Direct configuration is faster than check + configure

## Structure

```
filter_plugins/
├── netbox_filters.py                    # Main entry point (FilterModule class)
└── netbox_filters_lib/                  # Package directory
    ├── __init__.py                      # Package initialization
    ├── utils.py                         # Helper functions (159 lines)
    ├── l3_config_helpers.py             # L3 configuration optimization (162 lines)
    ├── vlan_filters.py                  # VLAN operations (455 lines)
    ├── vrf_filters.py                   # VRF operations (192 lines)
    ├── interface_categorization.py      # L2/L3 interface categorization (294 lines)
    ├── interface_ip_processing.py       # IP address matching (106 lines)
    ├── interface_change_detection.py    # Change detection & idempotency (621 lines)
    ├── comparison.py                    # State comparison (279 lines)
    └── ospf_filters.py                  # OSPF operations (112 lines)
```

**Recent Updates** (January 2025):
- Added `l3_config_helpers.py` module for L3 configuration optimization (5 filters)
- Enhanced `utils.py` with IP address extraction helpers (2 new functions)
- Updated `interface_change_detection.py` with bug fix for VLAN IPv4 address configuration

**Note**: The `interface_filters.py` module was split into three focused modules in November 2025:
- `interface_categorization.py` - Interface type and VLAN mode categorization
- `interface_ip_processing.py` - IP address to interface matching and anycast gateway processing
- `interface_change_detection.py` - NetBox vs device comparison and change detection

## Modules

### `utils.py` - Helper Functions

Core utilities used across all modules (5 functions, 159 lines):

- **`_debug(message)`**
    - Print debug messages when `DEBUG_ANSIBLE=true` environment variable is set

- **`collapse_vlan_list(vlan_list)`**
    - Format VLAN IDs as compact ranges
    - Example: `[10, 11, 12, 20, 21]` → `"10-12,20-21"`

- **`select_interfaces_to_configure(interfaces, idempotent_mode, changes)`**
    - Select which interfaces to configure based on idempotent mode
    - Used for smart interface filtering in change detection

- **`extract_ip_addresses(nb_intf, exclude_anycast=False)`** *(Added January 2025)*
    - Extract and categorize IPv4 and IPv6 addresses from interface objects
    - `exclude_anycast`: If True, skip IPs with role="anycast" (for change detection)
    - Returns tuple: `(ipv4_list, ipv6_list)`

- **`populate_ip_changes(nb_intf, nb_ipv4, nb_ipv6)`** *(Added January 2025)*
    - Populate `_ip_changes` dict for idempotent IP address configuration
    - Supports anycast gateway IP address handling

### `l3_config_helpers.py` - L3 Configuration Optimization *(New in January 2025)*

Configuration building and helper functions for L3 interfaces (5 filters, 162 lines):

- **`format_interface_name(interface_name, interface_type)`**
    - Format interface names for AOS-CX CLI
    - Handles LAG interface name formatting (adds space: "lag1" → "lag 1")

- **`is_ipv4_address(address)`**
    - Check if an address is IPv4
    - Returns: Boolean

- **`is_ipv6_address(address)`**
    - Check if an address is IPv6
    - Returns: Boolean

- **`get_interface_vrf(interface)`**
    - Extract VRF name from interface object with safe fallback
    - Returns: VRF name or "default"

- **`build_l3_config_lines(item, interface_type, ip_version, vrf_type, l3_counters_enable=True)`**
    - Build complete L3 configuration command list
    - Handles: VRF attachment, IP addressing, MTU, L3 counters, anycast gateway
    - Supports: Physical, LAG, and VLAN interfaces
    - Returns: List of configuration commands

**Key Benefits**:
- Eliminates 146 lines of duplicated task code
- Replaces complex Jinja2 with testable Python
- Single source of truth for L3 configuration logic

### `vlan_filters.py` - VLAN Operations

Complete VLAN lifecycle management (9 filters, 455 lines):

- **`extract_vlan_ids(interfaces)`**
    - Extract all VLAN IDs in use from interfaces
    - Returns: Sorted list of unique VLAN IDs

- **`filter_vlans_in_use(vlans, interfaces)`**
    - Filter VLAN objects to only those actually in use on interfaces
    - Returns: List of VLAN objects

- **`extract_evpn_vlans(vlans, interfaces, check_noevpn=True)`**
    - Get VLANs that should be configured for EVPN
    - Checks `vlan_noevpn` custom field and L2VPN termination
    - Returns: List of EVPN-enabled VLAN objects

- **`extract_vxlan_mappings(vlans, interfaces, use_l2vpn_id=True)`**
    - Extract VXLAN VNI to VLAN mappings for VXLAN configuration
    - Returns: List of dicts with `vni` and `vlan` keys

- **`get_vlans_in_use(interfaces, vlan_interfaces=None)`**
    - Get comprehensive VLAN details with full metadata
    - Returns: Dict with `vlan_ids`, `vlans`, and detailed VLAN info

- **`get_vlans_needing_changes(device_vlans, vlans_in_use_dict, device_facts=None)`**
    - Determine which VLANs need to be added or removed
    - Compares NetBox with current device state
    - Returns: Dict with `vlans_to_create` and `vlans_to_delete` lists

- **`get_vlan_interfaces(interfaces)`**
    - Extract VLAN/SVI interfaces (e.g., vlan100, vlan200)
    - Returns: List of VLAN interface objects

### `vrf_filters.py` - VRF Operations

VRF extraction and filtering (4 filters, 192 lines):

- **`extract_interface_vrfs(interfaces)`**
    - Extract unique VRF names from interfaces
    - Returns: Set of VRF names

- **filter_vrfs_in_use(vrfs, interfaces, tenant=None)`**
    - Filter VRF objects to only those in use on interfaces
    - Excludes built-in VRFs (mgmt, Global)
    - Optional tenant filtering
    - Returns: List of VRF objects

- **`get_vrfs_in_use(interfaces, ip_addresses=None)`**
    - Get comprehensive VRF details with full metadata
    - Excludes built-in/non-configurable VRFs
    - Returns: Dict with `vrf_names` list and `vrfs` dict

- **`filter_configurable_vrfs(vrfs)`**
    - Remove built-in VRFs that should not be configured
    - Filters out: mgmt, MGMT, Global, global, default, Default
    - Returns: List of configurable VRF objects

### `interface_categorization.py` - Interface Categorization

L2 and L3 interface categorization by type and configuration (2 filters, 294 lines):

- **`categorize_l2_interfaces(interfaces)`**
    - Categorize L2 interfaces by VLAN mode and type
    - Returns dict with 15 categories:
    - Regular interfaces: `access`, `tagged_with_untagged`, `tagged_no_untagged`, `tagged_all_with_untagged`, `tagged_all_no_untagged`
    - LAG interfaces: `lag_access`, `lag_tagged_with_untagged`, `lag_tagged_no_untagged`, `lag_tagged_all_with_untagged`, `lag_tagged_all_no_untagged`
    - MCLAG interfaces: `mclag_access`, `mclag_tagged_with_untagged`, `mclag_tagged_no_untagged`, `mclag_tagged_all_with_untagged`, `mclag_tagged_all_no_untagged`

- **`categorize_l3_interfaces(interfaces)`**
    - Categorize L3 interfaces by type and VRF
    - Returns dict with 7 categories:
    - `physical_default_vrf`: Physical interfaces in default/Global/mgmt VRF
    - `physical_custom_vrf`: Physical interfaces in custom VRFs
    - `vlan_default_vrf`: VLAN/SVI interfaces in default VRF
    - `vlan_custom_vrf`: VLAN/SVI interfaces in custom VRFs
    - `lag_default_vrf`: LAG interfaces in default VRF
    - `lag_custom_vrf`: LAG interfaces in custom VRFs
    - `loopback`: Loopback interfaces

### `interface_ip_processing.py` - IP Address Processing

IP address to interface matching and anycast gateway processing (1 filter, 106 lines):

- **`get_interface_ip_addresses(interfaces, ip_addresses)`**
    - Match IP addresses to their interfaces
    - Extracts IP role (e.g., "anycast") from NetBox IP address objects
    - Extracts anycast gateway MAC from interface custom field `if_anycast_gateway_mac`
    - Returns: List of dicts with interface and IP information including:
      - `interface`: Full interface object
      - `interface_name`: Interface name
      - `address`: IP address with prefix (e.g., "192.168.1.1/24")
      - `vrf`: VRF name
      - `ip_role`: IP address role (e.g., "anycast", None for regular IPs)
      - `anycast_mac`: MAC address for anycast gateway (e.g., "02:01:00:00:01:00")
    - Used for L3 configuration including anycast gateway setup

### `interface_change_detection.py` - Change Detection

NetBox vs device comparison and idempotency logic (2 filters, 621 lines):

- **`get_interfaces_needing_config_changes(interfaces, device_facts)`**
    - Compare NetBox interface configuration with device state
    - Implements granular change detection for:
      - Physical properties (enabled/disabled, description, MTU)
      - LAG membership
      - L2 VLAN configuration
      - L3 IP addresses (IPv4 with specific address tracking, IPv6 reference only)
    - Returns: Dict with categorized interfaces:
      - `physical`: Physical interfaces needing changes
      - `lag`: LAG interfaces needing changes
      - `mclag`: MCLAG interfaces needing changes
      - `l2`: L2 interfaces needing VLAN changes
      - `l3`: L3 interfaces needing IP address changes
      - `lag_members`: Physical interfaces needing LAG assignment changes
      - `no_changes`: Interfaces that don't need any changes
    - Adds `_ip_changes` dict to L3 interfaces containing:
      - `ipv4_to_add`: List of specific IPv4 addresses needing configuration
      - `ipv6_addresses`: List of all IPv6 addresses (for reference, not filtered)
    - See "L3 Interface IP Address Idempotency" section for performance details

- **`_categorize_interface_for_changes(intf, result_dict, needs_change=True)`**
    - Helper function to categorize interfaces into appropriate change categories
    - Handles multi-category assignment (e.g., LAG member in both `lag_members` and `physical`)
    - Internal use only

### `comparison.py` - State Comparison
NetBox vs device state comparison (2 filters):

- **`compare_interface_vlans(netbox_interface, device_facts_interface)`**
    - Compare VLAN configuration between NetBox and device
    - Returns dict with:
    - `vlans_to_add`: VLANs to add to interface
    - `vlans_to_remove`: VLANs to remove from interface
    - `needs_change`: Boolean if changes needed
    - `mode_change`: Boolean if VLAN mode needs to change

- **`get_interfaces_needing_changes(interfaces, device_facts)`**
    - Identify interfaces requiring configuration updates
    - Returns dict with:
    - `cleanup`: Interfaces needing VLAN removal
    - `configure`: Interfaces needing VLAN additions

### `ospf_filters.py` - OSPF Configuration
OSPF interface selection and validation (4 filters):

- **`select_ospf_interfaces(interfaces)`**
    - Filter interfaces that have OSPF configuration defined
    - Checks `if_ip_ospf_1_area` custom field
    - Returns: List of OSPF-enabled interfaces

- **`extract_ospf_areas(interfaces)`**
    - Extract unique OSPF area IDs from interfaces
    - Returns: Sorted list of area IDs

- **`get_ospf_interfaces_by_area(interfaces, area_id)`**
    - Get all interfaces belonging to a specific OSPF area
    - Returns: List of interfaces in the specified area

- **`validate_ospf_config(device_config, interfaces)`**
    - Validate OSPF configuration consistency
    - Checks router ID and area definitions
    - Returns: Dict with `valid` boolean, `warnings`, and `errors` lists

## Usage in Playbooks

All filters are available through the standard Ansible filter syntax:

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

### L3 Configuration Helpers

```yaml
# Build L3 configuration lines
- set_fact:
    config_lines: "{{ item | build_l3_config_lines('physical', 'ipv4', 'custom', true) }}"
    # Returns: ['vrf attach CUST-A', 'ip address 10.1.1.1/24', 'ip mtu 9000', 'l3-counters']

# Format interface names
- set_fact:
    formatted_name: "{{ 'lag1' | format_interface_name('lag') }}"
    # Returns: "lag 1"

# Check IP version
- set_fact:
    is_v4: "{{ '192.168.1.1/24' | is_ipv4_address }}"
    is_v6: "{{ '2001:db8::1/64' | is_ipv6_address }}"
    # Returns: true, true

# Get VRF name with fallback
- set_fact:
    vrf_name: "{{ interface | get_interface_vrf }}"
    # Returns: VRF name or "default"
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
    - Interface categorization → `interface_categorization.py`
    - IP address processing → `interface_ip_processing.py`
    - Change detection → `interface_change_detection.py`
    - State comparison → `comparison.py`
    - OSPF operations → `ospf_filters.py`
    - L3 configuration helpers → `l3_config_helpers.py`
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
    ├── interface_categorization.py → utils
    ├── interface_ip_processing.py → utils
    ├── interface_change_detection.py → utils
    ├── l3_config_helpers.py → utils
    ├── comparison.py → utils
    └── ospf_filters.py → utils
```

### Performance Considerations

- Filters are designed for datasets of 100-1000 interfaces
- Use `_debug()` sparingly in production (controlled by env var)
- Comparison filters optimize by early exit when no changes needed
- Set operations used for efficient VLAN/VRF lookups

## Statistics

- **Total Filters**: 32
- **Total Lines**: ~2,161 (including docstrings and comments)
- **Modules**: 9 (8 feature modules + 1 utility)
- **Test Coverage**: Used in production for 100+ switches
- **Code Quality**: Pylint score 9.30/10

### Filter Distribution

| Module | Filters | Lines | Description |
|--------|---------|-------|-------------|
| `interface_change_detection.py` | 2 | 621 | Change detection & idempotency |
| `vlan_filters.py` | 9 | 455 | VLAN lifecycle management |
| `interface_categorization.py` | 2 | 294 | Interface categorization |
| `comparison.py` | 2 | 279 | State comparison logic |
| `vrf_filters.py` | 4 | 192 | VRF operations |
| `l3_config_helpers.py` | 5 | 162 | L3 configuration optimization |
| `utils.py` | 5 | 159 | Helper functions |
| `ospf_filters.py` | 4 | 112 | OSPF configuration |
| `interface_ip_processing.py` | 1 | 106 | IP address matching |
| **Total** | **32** | **~2,161** | **9 modules** |

## Migration Guide

### From Monolithic to Modular Structure

If you were using an older version with a single `netbox_filters.py` file:

**Good news**: No changes needed! The refactored version maintains 100% backward compatibility. All existing playbooks will continue to work without modification.

The refactoring:

- ✅ Preserves all filter names and signatures
- ✅ Maintains identical return values
- ✅ Keeps the same FilterModule interface
- ✅ Supports all existing playbooks

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

## See Also

- **[Detailed Filter Reference](filter_plugins/index.md)** - Complete module and filter documentation
- **[L3 Config Helpers](filter_plugins/l3_config_helpers.md)** - L3 configuration optimization details
- **[Development Guide](DEVELOPMENT.md)** - Contributing guidelines
- **[NetBox Integration](NETBOX_INTEGRATION.md)** - NetBox setup and configuration
