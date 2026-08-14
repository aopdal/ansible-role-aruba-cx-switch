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

Each filter's documentation below tells you exactly that. Most filters fall into one of a small number of *shapes*, once you recognize the shape the details are easier to skim:

- **Extractors** (`extract_*`) — pull a simple list/set out of a bigger NetBox structure (e.g. "give me every VLAN ID currently in use").
- **Filters** (`filter_*`, `select_*`) — narrow a list down to the items that match some rule (e.g. "only the VRFs that aren't built-in").
- **Categorizers** (`categorize_*`, `get_*_in_use`) — sort a list into labeled buckets so playbook tasks can loop over just the bucket they care about.
- **Change-detectors** (`get_*_needing_*`, `get_*_changes`, `*_diff`) — compare what NetBox says should exist against what the device currently reports, and return only the difference. These are what makes the role *idempotent*: re-running the playbook doesn't push commands that would have no effect.
- **Builders** (`build_*`) — turn a decision ("this interface needs these IPs") into the actual list of AOS-CX CLI command strings to push.

---

## Overview

The filter plugins library provides **67 custom Ansible filters** organized across **17 modules** inside `netbox_filters_lib/`, split between two Ansible filter plugin files.

- **`netbox_filters.py`** - Main plugin, registers 62 filters (NetBox data transformation, change detection, config building)
- **`rest_api_transforms.py`** - Separate plugin, registers 5 filters (REST API response → `aoscx_facts`-shaped data)

---

## Module Documentation

### Core Utilities

**[Utils Module](utils.md)** - Helper functions and debugging
**Functions**: 10 (4 exposed as Ansible filters, 6 internal helpers)

Foundation module providing:
- Debug message printing with environment variable control
- VLAN list range formatting (e.g., `10-12,20-21`)
- Interface selection for idempotent mode
- IPv4/IPv6 address-string detection (`is_ipv4_address` / `is_ipv6_address`, filter names live under [L3 Config Helpers](l3_config_helpers.md))
- IP address extraction and categorization (IPv4/IPv6)
- IP changes population for idempotent checks
- Data-shape normalisation helpers (`interface.type` dict-vs-string, IPv6 canonical form, JSON-string-vs-dict facts)

---

### L3 Configuration

**[L3 Config Helpers](l3_config_helpers.md)** - L3 interface configuration optimization
**Filters**: 8

Configuration building and helper functions:
- Interface IP grouping (flat per-IP list → per-interface with all addresses)
- Interface name formatting for AOS-CX
- IP version detection (IPv4/IPv6)
- VRF extraction with safe fallback
- Per-address idempotency decision (`should_add_interface_ip`)
- Complete L3 config line generation (all IPs, VRF, MTU, OSPF, ip helper-address — once per interface)
- Debug-only config preview builder
- Supports physical, LAG, VLAN, and sub-interfaces

**Key Filters:**
- `group_interface_ips()` - Group per-IP list into per-interface items
- `format_interface_name()` - Format interface names
- `is_ipv4_address()` / `is_ipv6_address()` - IP version detection
- `get_interface_vrf()` - Extract VRF with fallback
- `should_add_interface_ip()` - Per-IP idempotency decision
- `build_l3_config_lines()` - Build all config commands for an interface
- `build_l3_config_preview()` - Debug/dry-run preview of config lines per interface

---

### VLAN Operations

**[VLAN Filters](vlan_filters.md)** - Complete VLAN lifecycle management
**Filters**: 14

Most comprehensive module handling:
- VLAN ID extraction from interfaces
- VLAN filtering and selection, including excluding whole NetBox VLAN groups
- EVPN/VXLAN configuration extraction
- Idempotent VLAN change detection (create/delete, IGMP snooping, voice VLAN, name/description)
- VLAN interface (SVI) identification
- EVPN EVI output parsing
- Port-access role VLAN extraction (config_context)

**Key Filters:**
- `extract_vlan_ids()` - Get all VLAN IDs in use
- `get_vlans_in_use()` - Comprehensive VLAN details (incl. port-access)
- `get_vlans_needing_changes()` - Idempotent create/delete detection
- `get_vlans_needing_igmp_update()` / `get_vlans_needing_voice_update()` / `get_vlans_needing_name_update()` - Idempotent per-setting change detection
- `extract_evpn_vlans()` - EVPN-enabled VLANs
- `extract_vxlan_mappings()` - VNI-to-VLAN mappings
- `extract_port_access_vlan_ids()` - VLANs referenced by port-access roles
- `filter_out_vlan_groups()` - Exclude VLANs belonging to given NetBox VLAN group slugs
- `parse_vlan_id_spec()` - Parse `"11-13"` / `"11,13,15-20"` syntax

---

### VRF Operations

**[VRF Filters](vrf_filters.md)** - VRF extraction, filtering, and route target management
**Filters**: 8

Manages VRF identification and filtering:
- VRF extraction from interfaces and IP addresses
- Automatic exclusion of built-in VRFs (mgmt, Global, default)
- Multi-tenant VRF filtering
- Route target name extraction
- Address-family-aware route target configuration building
- Idempotent detection of stale route targets and VRF/RD/RT changes vs. device state

**Key Filters:**
- `extract_interface_vrfs()` - Get VRF names from interfaces
- `filter_vrfs_in_use()` - Filter with tenant support
- `get_vrfs_in_use()` - Comprehensive VRF details
- `filter_configurable_vrfs()` - Safety filter for built-in VRFs
- `get_all_rt_names()` - Extract all route target names
- `build_vrf_rt_config()` - Build per-VRF, per-address-family RT config
- `get_vrf_rt_removals()` - Find route targets on the device no longer in NetBox
- `get_vrf_changes()` - Categorize VRF create / RD-change / RT-add / RT-remove vs. device facts

---

### Interface Processing

Interface processing is split into several focused modules:

**Interface Categorization** (`interface_categorization.py`)
**Filters**: 2

- L2 interface categorization (15 categories)
- L3 interface categorization (9 categories)
- Key filters: `categorize_l2_interfaces()`, `categorize_l3_interfaces()`

**IP Address Processing** (`interface_ip_processing.py`)
**Filters**: 1

- Interface/IP address matching with anycast gateway support
- Key filter: `get_interface_ip_addresses()`

**Change Detection** (`interface_change_detection.py` + `interface_ip_comparisons.py`)
**Filters**: 1

- Idempotent change detection for interfaces
- Key filter: `get_interfaces_needing_config_changes()`
- IPv4/IPv6/VRF/encapsulation/anycast/DHCP-relay comparison lives in
  `interface_ip_comparisons.py` as internal helpers (`compute_l3_ip_changes()`,
  `compute_dhcp_relay_changes()`), called by `get_interfaces_needing_config_changes()`
  per interface — not separately registered as Ansible filters

**Virtual Interface Cleanup** (`interface_orphans.py`)
**Filters**: 1

- Finds VLAN SVIs / loopbacks / sub-interfaces present on the device but no longer in NetBox, so idempotent cleanup can delete them
- Key filter: `get_virtual_interfaces_to_delete()`

See **[Interface Filters](interface_filters.md)** for detailed documentation of all four modules above.

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

**[OSPF Filters](ospf_filters.md)** - OSPF interface/area selection, validation, and change detection
**Filters**: 8

OSPF-specific operations:
- OSPF interface identification from custom fields
- OSPF area extraction
- Area-based interface filtering
- Multi-VRF / legacy single-VRF config_context normalisation
- Dropping OSPF config for VRFs not actually in use on this device
- Configuration validation
- Idempotent router-id/area and per-interface (area, network type, MD5 auth, passive) change detection vs. device REST facts

**Key Filters:**
- `select_ospf_interfaces()` - Get OSPF-enabled interfaces
- `extract_ospf_areas()` - List all areas in use
- `get_ospf_interfaces_by_area()` - Filter by area
- `normalize_ospf_vrfs()` - Collapse multi-VRF/legacy config_context shapes into one
- `filter_ospf_vrfs_in_use()` - Drop OSPF config for unused VRFs
- `validate_ospf_config()` - Pre-deployment validation
- `get_ospf_router_changes()` - Router-id/area diff vs. device facts
- `get_ospf_interface_changes()` - Per-interface OSPF settings diff vs. device facts

---

### BGP Configuration

**[BGP Filters](bgp_filters.md)** - BGP session enrichment, policy config, redistribution, and neighbor options
**Filters**: 8

Enriches and builds config for BGP, using the NetBox BGP plugin:
- Cross-references BGP session local addresses with interface IPs to determine VRF/address-family
- Builds route-map and prefix-list CLI commands from NetBox routing-policy objects
- Flattens `bgp_redistribute` config_context into per-VRF/AF redistribution entries, with stale-entry detection
- Flattens `bgp_neighbor_options` config_context into per-neighbor CLI option lines, with stale-entry detection
- Derives whether the global `bfd` toggle needs to be enabled/disabled from neighbor BFD usage

**Key Filters:**
- `get_bgp_session_vrf_info()` - Enrich sessions with VRF and AF metadata
- `collect_ebgp_vrf_policy_config()` - Build route-map/prefix-list CLI commands
- `get_bgp_redistribute_config()` / `get_stale_bgp_redistribute()` - Redistribute config + cleanup
- `get_bgp_neighbor_options_config()` / `get_stale_bgp_neighbor_options()` - Per-neighbor CLI options + cleanup
- `get_bgp_bfd_enabled()` / `get_stale_bgp_bfd()` - Global BFD toggle decision + cleanup

---

### Port-Access (Device Profiles)

**[Port-Access Filters](port_access.md)** - Port-access (device-profile) idempotency and cleanup
**Filters**: 3 *(2 in `port_access.py` + 1 in `port_access_orphans.py`)*

Compares the NetBox `port_access` config_context (LLDP groups, roles, device-profile associations) against REST API facts:
- Flattens the nested REST payload into a comparable shape
- Returns only the LLDP groups / roles / device-profile associations that actually differ, so unchanged ones are skipped
- Identifies device-profile objects present on the device but no longer in NetBox, for idempotent cleanup

**Key Filters:**
- `port_access_facts_from_device_profiles()` - Flatten REST payload for comparison
- `port_access_diff()` - Desired-vs-current diff (what to configure)
- `port_access_orphans()` - Present-on-device-but-not-in-NetBox (what to remove)

---

### STP Configuration

**[STP Filters](stp.md)** - Spanning-tree global and per-interface change detection
**Filters**: 2

Compares NetBox's global and per-interface STP settings against device REST facts, so `configure_stp.yml` only pushes the CLI lines that actually differ:
- Global MSTP config name/revision/priority
- Per-interface BPDU filter/guard, root guard, edge-port settings

**Key Filters:**
- `stp_global_config_diff()` - Global MSTP config diff
- `stp_interface_changes()` - Per-interface STP settings diff

---

### VSX Configuration

**[VSX Filters](vsx.md)** - VSX (MCLAG peer-switch) configuration change detection
**Filters**: 1

Compares the desired VSX role, system MAC, ISL, and keepalive settings (from NetBox config_context) against `aoscx_vsx_facts`, returning only the fields that differ.

**Key Filter:**
- `vsx_config_diff()` - Desired-vs-current VSX config diff

---

### Static Routes

**[Static Route Filters](static_route_filters.md)** - Static route change detection
**Filters**: 1

`aoscx_static_route` is not idempotent on its own (pyaoscx deletes and recreates the route's next-hop on every run), so this filter pre-compares desired routes (NetBox `static_routes` config_context, per VRF) against `aoscx_static_route_facts` and returns only the routes that actually need to be pushed or deleted.

**Key Filter:**
- `get_static_route_changes()` - Routes to apply / routes to delete

---

### REST API Transforms

**[REST API Transforms](rest_api_transforms.md)** - REST API response normalization
**Filters**: 5 *(separate plugin file: `rest_api_transforms.py`)*

Converts raw Aruba AOS-CX REST API responses into the format expected by `aoscx_facts`-based logic:
- Interface data normalization (admin state, IPv6 URL-decoding)
- VLAN data normalization
- EVPN VLAN data extraction
- VNI data extraction
- DHCP relay (`ip helper-address`) server list, flattened per interface

**Key Filters:**
- `rest_api_to_aoscx_interfaces()` - Normalize interface data
- `rest_api_to_aoscx_vlans()` - Normalize VLAN data
- `rest_api_to_aoscx_evpn_vlans()` - Extract EVPN VLAN config
- `rest_api_to_aoscx_vnis()` - Extract VNI config
- `rest_api_to_aoscx_dhcp_relays()` - Flatten DHCP relay servers per interface

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

#### Utils (4 filters + 6 internal)
- `collapse_vlan_list(vlan_list)` - Format VLAN ranges
- `select_interfaces_to_configure(interfaces, idempotent_mode, changes)` - Idempotent selection
- `is_ipv4_address(address)` / `is_ipv6_address(address)` - IP version detection *(implemented here, filter name registered via `l3_config_helpers`)*
- *Internal*: `_debug()`, `extract_ip_addresses()`, `populate_ip_changes()`, `get_interface_type_value()`, `normalize_ipv6()`, `_to_dict()`

#### L3 Config Helpers (8 filters)
- `group_interface_ips(interface_ip_list)` - Group per-IP list into per-interface items
- `format_interface_name(name, type)` - Format interface names
- `is_ipv4_address(address)` - IPv4 detection
- `is_ipv6_address(address)` - IPv6 detection
- `get_interface_vrf(interface)` - Extract VRF name
- `should_add_interface_ip(interface, address)` - Per-IP idempotency decision
- `build_l3_config_lines(item, type, vrf_type, l3_counters_enable, ip_helper_addresses)` - Build all config commands for an interface
- `build_l3_config_preview(l3_interfaces, aoscx_builtin_vrfs, l3_counters_enable)` - Debug preview of config lines

#### VLAN Filters (14)
- `extract_vlan_ids(interfaces)` - Extract VLAN IDs
- `filter_vlans_in_use(vlans, interfaces)` - Filter to used VLANs
- `filter_out_vlan_groups(vlans, group_slugs)` - Exclude VLAN group members
- `extract_evpn_vlans(vlans, interfaces, check_noevpn)` - EVPN VLANs
- `extract_vxlan_mappings(vlans, interfaces, use_l2vpn_id)` - VXLAN mappings
- `get_vlans_in_use(interfaces, vlan_interfaces, port_access)` - Comprehensive VLAN data (includes port-access role VLANs)
- `get_vlans_needing_changes(device_vlans, vlans_in_use, facts)` - Create/delete detection
- `get_vlans_needing_igmp_update(device_vlans, vlans_in_use, enhanced_vlan_facts)` - IGMP snooping change detection
- `get_vlans_needing_voice_update(device_vlans, vlans_in_use, enhanced_vlan_facts)` - Voice VLAN change detection
- `get_vlans_needing_name_update(device_vlans, vlans_in_use, enhanced_vlan_facts)` - Name/description change detection
- `get_vlan_interfaces(interfaces)` - Extract SVIs
- `parse_evpn_evi_output(output)` - Parse show command
- `extract_port_access_vlan_ids(port_access)` - VLANs from port-access roles
- `parse_vlan_id_spec(spec)` - Parse VLAN range/list syntax

#### VRF Filters (8)
- `extract_interface_vrfs(interfaces)` - Extract VRF names
- `filter_vrfs_in_use(vrfs, interfaces, tenant)` - Filter VRFs
- `get_vrfs_in_use(interfaces, ip_addresses)` - Comprehensive VRF data
- `filter_configurable_vrfs(vrfs)` - Remove built-in VRFs
- `get_all_rt_names(vrf_details)` - Extract all route target names
- `build_vrf_rt_config(vrf_details)` - Build address-family RT config per VRF
- `get_vrf_rt_removals(vrf_rt_config, vrf_rt_facts)` - Stale route targets vs. device
- `get_vrf_changes(vrfs_in_use, vrf_rt_config, vrf_facts, vrf_rt_facts)` - Create/RD/RT diff vs. device

#### Interface Categorization (2 filters)
- `categorize_l2_interfaces(interfaces)` - 15 L2 categories
- `categorize_l3_interfaces(interfaces)` - 9 L3 categories

#### Interface IP Processing (1 filter)
- `get_interface_ip_addresses(interfaces, ip_addresses)` - Match IPs to interfaces

#### Interface Change Detection (1 filter)
- `get_interfaces_needing_config_changes(interfaces, device_facts, enhanced_facts, dhcp_relay_facts, ip_helper_addresses)` - Change detection

#### Interface Cleanup (1 filter)
- `get_virtual_interfaces_to_delete(desired_interfaces, device_interfaces)` - Orphaned VLAN SVI/loopback/sub-interface detection

#### Comparison (2 filters)
- `compare_interface_vlans(nb_intf, device_intf)` - Single interface comparison
- `get_interfaces_needing_changes(interfaces, facts)` - Batch comparison

#### OSPF Filters (8)
- `select_ospf_interfaces(interfaces)` - Get OSPF interfaces
- `extract_ospf_areas(interfaces)` - Extract areas
- `get_ospf_interfaces_by_area(interfaces, area)` - Filter by area
- `normalize_ospf_vrfs(ospf_vrfs, ospf_1_vrf, ospf_areas)` - Normalize config_context shapes
- `filter_ospf_vrfs_in_use(ospf_vrfs, vrf_names_in_use)` - Drop unused-VRF entries
- `validate_ospf_config(device, interfaces)` - Validate configuration
- `get_ospf_router_changes(ospf_config, ospf_router_facts)` - Router-id/area diff vs. device
- `get_ospf_interface_changes(ospf_interface_items, ospf_interface_facts, ospf_router_facts, process_id)` - Per-interface diff vs. device

#### BGP Filters (8)
- `get_bgp_session_vrf_info(sessions, interfaces)` - Enrich BGP sessions with VRF/AF info
- `collect_ebgp_vrf_policy_config(sessions, all_policy_rules, all_prefix_list_rules)` - Route-map/prefix-list CLI commands
- `get_bgp_redistribute_config(bgp_redistribute)` - Redistribute entries from config_context
- `get_stale_bgp_redistribute(bgp_redistribute, running_config, local_asn)` - Redistribute cleanup
- `get_bgp_neighbor_options_config(bgp_neighbor_options, sessions)` - Per-neighbor CLI options
- `get_stale_bgp_neighbor_options(bgp_neighbor_options, sessions, running_config, local_asn)` - Neighbor option cleanup
- `get_bgp_bfd_enabled(bgp_neighbor_options, sessions)` - Whether global `bfd` must be enabled
- `get_stale_bgp_bfd(bgp_neighbor_options, sessions, running_config)` - Whether global `bfd` must be disabled

#### Port-Access Filters (3)
- `port_access_facts_from_device_profiles(profiles_payload)` - Flatten REST payload
- `port_access_diff(desired, current)` - Desired-vs-current diff
- `port_access_orphans(desired, current)` - Present-on-device-but-not-in-NetBox

#### STP Filters (2)
- `stp_global_config_diff(desired, facts)` - Global MSTP config diff
- `stp_interface_changes(interfaces, enhanced_facts)` - Per-interface STP diff

#### VSX Filters (1)
- `vsx_config_diff(desired, facts)` - VSX config diff

#### Static Route Filters (1)
- `get_static_route_changes(static_routes, static_route_facts)` - Routes to apply / delete

#### REST API Transforms (5) *(separate plugin)*
- `rest_api_to_aoscx_interfaces(rest_data)` - Normalize interface data
- `rest_api_to_aoscx_vlans(rest_data)` - Normalize VLAN data
- `rest_api_to_aoscx_evpn_vlans(rest_data)` - Extract EVPN VLAN config
- `rest_api_to_aoscx_vnis(rest_data)` - Extract VNI config
- `rest_api_to_aoscx_dhcp_relays(rest_data)` - Flatten DHCP relay servers per interface

---

## By Use Case

### Idempotent Operations
- `get_vlans_needing_changes()`, `get_vlans_needing_igmp_update()`, `get_vlans_needing_voice_update()`, `get_vlans_needing_name_update()` - VLAN idempotency
- `get_interfaces_needing_changes()` - Interface VLAN idempotency (comparison.py)
- `get_interfaces_needing_config_changes()` - Granular interface change detection
- `get_virtual_interfaces_to_delete()` - Orphaned virtual interface cleanup
- `compare_interface_vlans()` - VLAN comparison
- `select_interfaces_to_configure()` - Interface selection
- `get_vrf_rt_removals()`, `get_vrf_changes()` - VRF/RT idempotency
- `get_ospf_router_changes()`, `get_ospf_interface_changes()` - OSPF idempotency
- `get_stale_bgp_redistribute()`, `get_stale_bgp_neighbor_options()`, `get_bgp_bfd_enabled()`, `get_stale_bgp_bfd()` - BGP idempotency
- `port_access_diff()`, `port_access_orphans()` - Port-access idempotency
- `stp_global_config_diff()`, `stp_interface_changes()` - STP idempotency
- `vsx_config_diff()` - VSX idempotency
- `get_static_route_changes()` - Static route idempotency

### Data Extraction
- `extract_vlan_ids()` - VLAN IDs
- `extract_interface_vrfs()` - VRF names
- `extract_ospf_areas()` - OSPF areas
- `get_interface_ip_addresses()` - Interface/IP matching
- `get_all_rt_names()` - Route target names

### Filtering
- `filter_vlans_in_use()`, `filter_out_vlan_groups()` - Active/allowed VLANs
- `filter_vrfs_in_use()` - Active VRFs
- `filter_configurable_vrfs()` - Safe VRFs
- `select_ospf_interfaces()` - OSPF interfaces
- `get_ospf_interfaces_by_area()`, `filter_ospf_vrfs_in_use()` - Area/VRF filtering

### Categorization
- `categorize_l2_interfaces()` - L2 by mode/type (15 categories)
- `categorize_l3_interfaces()` - L3 by type/VRF (9 categories)

### BGP
- `get_bgp_session_vrf_info()` - Enrich sessions with VRF and address family
- `collect_ebgp_vrf_policy_config()`, `get_bgp_redistribute_config()`, `get_bgp_neighbor_options_config()`, `get_bgp_bfd_enabled()` - Build BGP-related CLI config

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
- `rest_api_to_aoscx_dhcp_relays()` - DHCP relay servers

### Validation
- `validate_ospf_config()` - OSPF validation

---

## Design Principles

1. **Single Responsibility**: Each filter does one thing well
2. **Composability**: Filters can be chained together
3. **Idempotency**: Comparison/diff filters enable idempotent playbooks — see [§4.7 in CLAUDE.md](../../CLAUDE.md#47-write-only--hashed-secret-fields-idempotency) for the one category (write-only secrets) where true idempotency isn't possible
4. **Debugging**: Built-in debug logging via `DEBUG_ANSIBLE` env var
5. **Safety**: Automatic exclusion of built-in/system resources; "facts unavailable" always falls back to "push everything" rather than silently skipping work
6. **Backward Compatibility**: Filter names and signatures are not renamed/removed without a deprecation cycle

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
4. Register in `netbox_filters.py` (import + add to the `filters()` dict), or create your own `FilterModule` for a separate plugin
5. Add a unit test under `tests/unit/`
6. Document in this guide and create/update the module doc

### Testing

```bash
# Enable debug mode
export DEBUG_ANSIBLE=true

# Run playbook
ansible-playbook site.yml

# Check filter loading
cd /workspaces/ansible-role-aruba-cx-switch
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
| **vlan_filters.py** | 14 | VLAN lifecycle management (incl. port-access, IGMP/voice/name change detection) |
| **vrf_filters.py** | 8 | VRF operations, route targets, and idempotent change detection |
| **l3_config_helpers.py** | 8 | L3 configuration optimization (incl. ip helper-address) |
| **ospf_filters.py** | 8 | OSPF configuration, validation, and idempotent change detection |
| **bgp_filters.py** | 8 | BGP session enrichment, policy config, redistribution, neighbor options, BFD |
| **rest_api_transforms.py** | 5 | REST API data normalization *(separate plugin file)* |
| **utils.py** | 4 | Helper functions and utilities (`is_ipv4/6_address` implemented here, registered via l3_config_helpers) |
| **interface_categorization.py** | 2 | Interface categorization |
| **comparison.py** | 2 | State comparison logic |
| **port_access.py** | 2 | Port-access (device-profile) idempotency |
| **stp.py** | 2 | Global + per-interface STP change detection |
| **interface_change_detection.py** | 1 | Change detection orchestration and idempotency |
| **interface_ip_processing.py** | 1 | IP address matching |
| **interface_orphans.py** | 1 | Orphaned virtual interface cleanup |
| **port_access_orphans.py** | 1 | Orphaned port-access object cleanup |
| **vsx.py** | 1 | VSX config change detection |
| **static_route_filters.py** | 1 | Static route idempotency |
| **interface_ip_comparisons.py** | 0 *(internal)* | IPv4/IPv6/VRF/encapsulation/anycast/DHCP relay comparison, called by `interface_change_detection.py` |
| **Total** | **67** | 17 modules in `netbox_filters_lib/` + 1 separate plugin file |

---

## Support

- **Repository**: https://github.com/aopdal/ansible-role-aruba-cx-switch
- **Issues**: GitHub Issues
- **Documentation**: [docs/](../) folder
