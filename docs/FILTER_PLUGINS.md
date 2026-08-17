# NetBox Filters Library

Custom Ansible filters for transforming NetBox data for use with Aruba AOS-CX switches.

## Overview

This library provides **67 custom filters** organized into 17 modules in `netbox_filters_lib/`, registered across 2 Ansible filter plugin files (`netbox_filters.py` and `rest_api_transforms.py`). The filters handle VLAN management, VRF configuration and route targets, interface categorization, interface IP processing, L3 configuration optimization, interface/VLAN/VRF/OSPF/BGP/port-access/STP/VSX/static-route change detection, REST API data normalization, and state comparison between NetBox (source of truth) and device facts.

For a full per-filter reference (parameters, return values, and one-line "what does this actually do" summaries) grouped the same way, see [docs/filter_plugins/index.md](filter_plugins/index.md) — that page is the better starting point if you don't already know which module you need.

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

These two filters handle this case differently:

**`interface_categorization.py` behavior** (used for L2 configuration):

```python
# mode: "access"  → access category (if untagged VLAN present)
# mode: "tagged"  + untagged + tagged VLANs → tagged_with_untagged
# mode: "tagged"  + tagged VLANs only       → tagged_no_untagged
# mode: "tagged"  + untagged VLAN only      → SKIPPED (not configured)
# mode: "tagged"  + no VLANs               → SKIPPED (not configured)
# mode: "tagged-all" + untagged VLAN        → tagged_all_with_untagged
# mode: "tagged-all" + no untagged VLAN     → tagged_all_no_untagged
```

Interfaces with `mode: tagged` but no tagged VLANs are silently skipped and will not be configured. Use NetBox `mode: access` explicitly for access ports.

**`interface_change_detection.py` behavior** (used for comparing against device state):

```python
# If NetBox has:
#   - mode: "tagged" (not "tagged-all")
#   - untagged_vlan: <vlan_id>
#   - tagged_vlans: [] (empty or missing)
#
# Effective mode for comparison is: "access"
#
# Note: mode: "tagged-all" is always treated as trunk,
# even with empty tagged_vlans list (allows all VLANs)
```

**Rationale for change detection**:

- A `mode: tagged` port with no tagged VLANs and only an untagged VLAN is functionally an access port
- Treating it as access prevents false positives when comparing against a device already configured as `vlan_mode: access`
- `mode: tagged-all` always stays as trunk (allows all VLANs), even if `tagged_vlans` is empty

**Impact**:

- Prevents false positives in change detection when NetBox has `mode: tagged` (empty list) and device has `vlan_mode: access`
- Interfaces with `mode: tagged` and only an untagged VLAN are **skipped during configuration** (not pushed to device) but **correctly compared** during change detection
- Masks potential NetBox misconfiguration where user intended trunk but used `mode: tagged` with no VLANs

**Best Practice**:

- Use NetBox `mode: access` explicitly for access ports — `mode: tagged` with only an untagged VLAN will be skipped during configuration
- Use NetBox `mode: tagged` only when `tagged_vlans` list is populated
- Use NetBox `mode: tagged-all` for trunk ports that allow all VLANs (with or without native VLAN)
- Document your organization's NetBox modeling standards

**Virtual interfaces are excluded entirely**: NetBox also uses `mode`/
`tagged_vlans` to describe a sub-interface's 802.1Q encapsulation tag (see
[VIRTUAL_INTERFACE_CLEANUP.md](VIRTUAL_INTERFACE_CLEANUP.md#sub-interfaces-are-not-l2-trunk-ports)),
even though AOS-CX configures that via `encapsulation dot1q`, not L2
`vlan_mode`. `interface_change_detection.py` skips this entire L2 VLAN
mode/membership comparison for any interface with `type.value == "virtual"`
(VLAN SVIs, loopbacks, sub-interfaces) — none of them ever populate
`vlan_mode`/`vlan_tag`/`vlan_trunks` on the device, so without this
exclusion every virtual interface with a `mode`/`tagged_vlans` set in
NetBox would be incorrectly flagged as needing L2 changes.

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

The role implements intelligent comparison of L3 interface IP addresses to minimize configuration time. The `get_interfaces_needing_config_changes()` filter (in `interface_change_detection.py`) compares NetBox's intended IP configuration with device facts and tracks which specific IP addresses need to be added.

### IPv4 Address Optimization

**Implementation**: Full comparison and granular change tracking

IPv4 addresses are compared between NetBox and device facts:

- Only IP addresses that **actually need to be added** are marked for configuration
- Tasks filter interfaces using `selectattr('_needs_add', 'equalto', true)`
- Significantly reduces configuration time by skipping unnecessary device connections
- IP version filtering uses simple colon check: IPv6 has `:`, IPv4 doesn't

**Example**:

```yaml
# Group per-IP items into per-interface items and apply all L3 config in one call
- name: Configure physical L3 interfaces
  arubanetworks.aoscx.aoscx_config:
    lines: "{{ item | build_l3_config_lines('physical', vrf_type, aoscx_l3_counters_enable | default(true)) }}"
    parents: "interface {{ item.interface_name | format_interface_name('physical') }}"
  loop: "{{ interface_list | group_interface_ips }}"
  # group_interface_ips groups by interface, filters _needs_add=True,
  # sorts addresses (anycast-first, IPv4-before-IPv6)
```

**Performance Impact**:

- Typical environment: 50+ interfaces with 2-5 IPs each
- Without filtering: 100-250 unnecessary configuration tasks
- With filtering: Only tasks for actual changes
- Time saved: Significant reduction in L3 configuration phase

### IPv6 Address Handling

IPv6 addresses are a special case because the `aoscx_facts` module (the
default fact-gathering path) only returns them as REST API URL
references, not the actual addresses:

```json
{
  "ip6_addresses": "/rest/v10.09/system/interfaces/vlan11/ip6_addresses"
}
```

Without real addresses to compare against, the role has no way to know
whether a given IPv6 address is already configured. **Without REST API
fact gathering enabled, IPv6 configuration is therefore always pushed
unconditionally** - still idempotent at the CLI level (duplicate commands
have no effect), but every run reports `changed: true` for these tasks
even when nothing actually changed.

**Fix — REST API fact gathering** (`aoscx_gather_facts_rest_api: true`):
`tasks/gather_facts_rest_api.yml` queries the REST API at `depth=2`, which
returns actual IPv6 addresses (and VSX virtual IPs) instead of URL
references. The result is stored in `aoscx_enhanced_interface_facts` and
passed to `get_interfaces_needing_config_changes()` as the
`enhanced_facts` argument. When present, the filter performs full IPv6
comparison against NetBox's intended state and only configures addresses
that are actually missing - the same compare-device-facts-to-NetBox
approach used for IPv4 and everywhere else in the role. See
[FACT_GATHERING.md](FACT_GATHERING.md) for why REST API fact gathering
exists and how it works.

```yaml
# Enable in host_vars or group_vars:
aoscx_gather_facts_rest_api: true
```

**Without enhanced facts (default)**:

- IPv6 tasks **always execute** (no pre-comparison possible - the base
  facts module simply doesn't have the data)
- Configuration remains idempotent at CLI level (duplicate commands have
  no effect)

**With enhanced facts enabled**:

- One REST API call retrieves actual IPv6 addresses for all interfaces
- Filter compares and only configures missing addresses
- Also enables proper VSX virtual IP comparison for anycast/active-gateway

**Example**:

```yaml
# IPv4 and IPv6 are now configured in the same call via build_l3_config_lines.
# group_interface_ips groups all IPs per interface and sorts IPv4 before IPv6.
- name: Configure VLAN L3 interfaces
  arubanetworks.aoscx.aoscx_config:
    lines: "{{ item | build_l3_config_lines('vlan', vrf_type, aoscx_l3_counters_enable | default(true)) }}"
    parents: "interface {{ item.interface_name | format_interface_name('vlan') }}"
  loop: "{{ interface_list | group_interface_ips }}"
```

### Filter Implementation Details

The `get_interfaces_needing_config_changes()` filter returns:

```python
{
    "_ip_changes": {
        "ipv4_to_add": ["10.1.1.1/24", "10.1.2.1/24"],  # Only IPs needing addition
        "ipv6_addresses": ["2001:db8::1/64"],  # All IPv6 addresses (for reference)
        "ipv6_to_add": ["fe80::1/64"],  # IPv6 anycast/addresses to add
        "anycast_ipv4_to_remove": ["10.1.3.1"],  # Stale active-gateway IPv4
        "anycast_ipv6_to_remove": ["2001:db8::1"],  # Stale active-gateway IPv6
        "link_local_ipv6_to_add": ["fe80::1/64"],  # Missing 'ipv6 address link-local'
    }
}
```

`link_local_ipv6_to_add` is populated when a link-local address (`fe80::`) is used as the IPv6 anycast gateway (HPE Aruba recommendation) but `ipv6 address link-local <addr>` has not been explicitly configured on the device. Detected via the `ip6_address_link_local` REST API field (requires `aoscx_gather_facts_rest_api: true`).

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

- ✅ Without `aoscx_gather_facts_rest_api: true`: the `aoscx_facts` module
  can't provide real IPv6 addresses to compare against, so configuration
  is applied unconditionally every run (idempotent at the CLI level, but
  always reports `changed`)
- ✅ With `aoscx_gather_facts_rest_api: true`: full IPv6 comparison
  against NetBox via one REST API call - the recommended setting; see
  [FACT_GATHERING.md](FACT_GATHERING.md)

**Debugging**:

```bash
# See which IPs are marked for addition
export DEBUG_ANSIBLE=true
ansible-playbook your-playbook.yml

# Output shows:
# "Interface vlan11: IPv4 changes needed: ['10.1.1.1/24']"
# "Interface vlan11: IPv6 addresses present: ['2001:db8::1/64']"
```

## Structure

```
filter_plugins/
├── netbox_filters.py                    # Main entry point (FilterModule class, 62 filters)
├── rest_api_transforms.py               # Separate FilterModule (5 filters)
└── netbox_filters_lib/                  # Package directory (role root, not inside filter_plugins/)
    ├── __init__.py                      # Package initialization
    ├── utils.py                         # Helper functions (246 lines)
    ├── l3_config_helpers.py             # L3 configuration optimization (583 lines)
    ├── vlan_filters.py                  # VLAN operations (952 lines)
    ├── vrf_filters.py                   # VRF operations (428 lines)
    ├── bgp_filters.py                   # BGP session enrichment, policy, redistribute, neighbor options, BFD (899 lines)
    ├── interface_categorization.py      # L2/L3 interface categorization (325 lines)
    ├── interface_ip_processing.py       # IP address matching (103 lines)
    ├── interface_change_detection.py    # Change detection orchestration (760 lines)
    ├── interface_ip_comparisons.py      # IPv4/IPv6/VRF/anycast/DHCP relay comparison (681 lines)
    ├── interface_orphans.py             # Orphaned virtual interface (SVI/loopback/sub-if) cleanup (56 lines)
    ├── comparison.py                    # State comparison (291 lines)
    ├── ospf_filters.py                  # OSPF operations (438 lines)
    ├── port_access.py                   # Port-access (device-profile) idempotency (355 lines)
    ├── port_access_orphans.py           # Orphaned port-access object cleanup (36 lines)
    ├── static_route_filters.py          # Static route change detection (136 lines)
    ├── stp.py                           # Global + per-interface STP change detection (134 lines)
    └── vsx.py                           # VSX config change detection (80 lines)
```

**Recent Updates** (January 2025):
- Added `l3_config_helpers.py` module for L3 configuration optimization (5 filters)
- Enhanced `utils.py` with IP address extraction helpers (2 new functions)
- Updated `interface_change_detection.py` with bug fix for VLAN IPv4 address configuration

**Recent Updates** (May 2026):
- Added `stp.py` module: `stp_interface_changes` filter compares NetBox interface STP custom fields against REST API `stp_config` facts and returns only the interfaces and CLI commands that need to change

**Recent Updates** (August 2026):
- Split `interface_change_detection.py` (was 1,369 lines, a single ~1,180-line
  function): the IPv4/IPv6/VRF/encapsulation/anycast/DHCP-relay comparison
  logic moved to a new `interface_ip_comparisons.py` module as two functions,
  `compute_l3_ip_changes()` and `compute_dhcp_relay_changes()`, leaving
  `get_interfaces_needing_config_changes()` focused on orchestration
  (existence checks, physical/L2 property checks, categorization). Both new
  functions are pure — they return `(needs_change, change_reasons,
  ip_changes)` instead of writing `_ip_changes` onto the interface dict —
  and `get_interfaces_needing_config_changes()` now shallow-copies each
  interface at the top of its loop so it no longer mutates the `interfaces`
  list passed in by the caller (see docs/CODE_AUDIT.md findings F4/F5). No
  behavior change; the public filter's signature and output are unchanged.

**Note**: The `interface_filters.py` module was split into three focused modules in November 2025:
- `interface_categorization.py` - Interface type and VLAN mode categorization
- `interface_ip_processing.py` - IP address to interface matching and anycast gateway processing
- `interface_change_detection.py` - NetBox vs device comparison and change detection

## Modules

### `utils.py` - Helper Functions

Core utilities used across all modules (5 functions, 2 exposed as filters, 176 lines):

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

Configuration building and helper functions for L3 interfaces (5 filters, 181 lines):

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

- **`group_interface_ips(interface_ip_list, ospf_facts=None, ospf_process_id=1)`**
    - Group flat per-IP items into per-interface items for use with `build_l3_config_lines`
    - Filters to `_needs_add=True`, sorts addresses (regular-before-anycast, IPv4 before IPv6)
    - Includes an interface with no `_needs_add` IPs when any of the following is true:
        - The interface has `if_ip_ospf_1_area` set AND it is not yet in the correct OSPF area (or `ospf_facts` is `None`)
        - `_ip_changes.dhcp_relay_change` is `True` (set by change detection when DHCP relay servers differ)
        - `_ip_changes.description_change` is `True` (set by change detection for virtual interfaces — VLAN SVIs, loopbacks, sub-interfaces — when the NetBox description differs from the device description)
    - Returns: List of `{interface_name, interface, addresses}` dicts

- **`build_l3_config_lines(item, interface_type, vrf_type, l3_counters_enable=True, ip_helper_addresses=None)`**
    - Build complete L3 configuration command list for a single interface
    - `item` is a per-interface grouped dict from `group_interface_ips()` with an `addresses` list
    - Handles all IPs (IPv4 + IPv6, anycast gateways) in a single call — each per-interface command (vrf attach, ip mtu, l3-counters) emitted exactly once
    - For `interface_type` `vlan`, `loopback`, or `subinterface`, emits a `description <text>` line when `item.interface.description` is set. `physical` and `lag` are deliberately excluded — those are already pushed unconditionally by `configure_physical_interfaces.yml`/`configure_lag_interfaces.yml`/`configure_mclag_interfaces.yml` regardless of L2/L3 role, so emitting it here too would duplicate the command.
    - OSPF interface config is handled separately in `tasks/configure_ospf.yml`
    - When `ip_helper_addresses` is provided and the interface has `custom_fields.if_ip_helper=True`, emits `ip helper-address <ip>` lines (one per server, ordered by string index key) after all IP/anycast lines and before `l3-counters`
    - Servers are looked up by the interface VRF name in `ip_helper_addresses` (a dict keyed by VRF, values are `{"0": "ip", "1": "ip", ...}`)
    - Returns: List of configuration commands

- **`should_add_interface_ip(interface, address)`**
    - Decide whether a single IP address on an interface must be pushed. Used by `tasks/configure_l3_interfaces.yml` to set the per-combo `_needs_add` flag consumed downstream by `group_interface_ips`.
    - VRF-change short-circuit: when `interface._ip_changes.vrf_change` is `True`, always returns `True` (the switch wipes all L3 config on a VRF move, so every address — including anycast — must be re-applied).
    - IPv4 (no colon in `address`): returns membership in `_ip_changes.ipv4_to_add` when present; if `_ip_changes` exists but has no `ipv4_to_add`, returns `False`; if no `_ip_changes` at all, returns `True` (new interface).
    - IPv6 (colon in `address`): returns membership in `_ip_changes.ipv6_to_add` when present; if `_ip_changes` exists but has no `ipv6_to_add`, returns `True` (no enhanced facts — configure all IPv6 addresses); if no `_ip_changes` at all, returns `True`.
    - Returns: Boolean

- **`build_l3_config_preview(l3_interfaces, aoscx_builtin_vrfs, l3_counters_enable=True)`**
    - Debug-only preview mapping formatted interface name → list of L3 config lines. Iterates every `(interface_type, VRF)` category in `l3_interfaces`, calls `group_interface_ips` + `build_l3_config_lines`, and keys the result by `format_interface_name`. Loopbacks (a single unsplit list in `categorize_l3_interfaces` output) are split by VRF here — loopbacks with `vrf in aoscx_builtin_vrfs + [None]` go to the default bucket, the rest to custom.
    - `ip_helper_addresses` is intentionally not exposed: the preview is a lightweight summary; helper-address lines are only added in the live `configure_l3_interface_common.yml` push.
    - Returns: Dict of `{formatted_interface_name: [config_line, ...]}`

**Key Benefits**:
- Eliminates duplicated task code across interface type files
- Replaces complex Jinja2 with testable Python
- Single source of truth for all L3 interface configuration logic

### `vlan_filters.py` - VLAN Operations

Complete VLAN lifecycle management (8 filters, 454 lines):

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

- **`get_vlans_in_use(interfaces, vlan_interfaces=None, port_access=None)`**
    - Get comprehensive VLAN details with full metadata
    - Optional `port_access` argument: a `port_access` dict from NetBox
      config_context. VLAN IDs referenced by `port_access.roles[*]` via
      `vlan_trunk_native`, `vlan_trunk_allowed`, or `vlan_access` are merged
      into `vids` so the VLANs get created on the device and protected from
      idempotent cleanup. Range/list syntax is supported (e.g. `"11-13"`,
      `"11,13,15-20"`).
    - Returns: Dict with `vids` (sorted list of VLAN IDs) and `vlans` (list of VLAN objects)

- **`extract_port_access_vlan_ids(port_access)`**
    - Extract every VLAN ID referenced by port-access roles in a
      `port_access` config_context dict (`vlan_trunk_native`,
      `vlan_trunk_allowed`, `vlan_access`).
    - Returns: Sorted list of unique VLAN IDs (1-4094)

- **`parse_vlan_id_spec(spec)`**
    - Parse a VLAN-ID specification into a sorted list of unique integers.
    - Accepts `int`, `str` (`"11"`, `"11,13"`, `"11-13"`,
      `"11,13,15-20"`), or list/tuple of these. Whitespace tolerated;
      reverse ranges normalised; out-of-range and non-numeric tokens skipped.
    - Returns: Sorted list of unique VLAN IDs (1-4094)

- **`get_vlans_needing_changes(device_vlans, vlans_in_use_dict, device_facts=None)`**
    - Determine which VLANs need to be added or removed
    - Compares NetBox with current device state
    - Returns: Dict with `vlans_to_create` and `vlans_to_delete` lists

- **`get_vlans_needing_igmp_update(device_vlans, vlans_in_use_dict, enhanced_vlan_facts=None)`**
    - Determine which VLANs need IGMP snooping configuration updates
    - Filters to VLANs in use with `vlan_ip_igmp_snooping` custom field defined
    - Compares desired NetBox state vs current device state (when enhanced facts available)
    - Only returns VLANs where IGMP setting differs from device
    - Returns: List of VLAN objects needing IGMP snooping updates

- **`get_vlans_needing_voice_update(device_vlans, vlans_in_use_dict, enhanced_vlan_facts=None)`**
    - Determine which VLANs need voice VLAN configuration updates
    - Filters to VLANs in use with `vlan_voice_vlan` custom field defined
    - Compares desired NetBox state vs current device state (when enhanced facts available)
    - Only returns VLANs where voice setting differs from device
    - Returns: List of VLAN objects needing voice VLAN updates

- **`get_vlans_needing_name_update(device_vlans, vlans_in_use_dict, enhanced_vlan_facts=None)`**
    - Determine which VLANs need name or description configuration updates
    - Filters to VLANs in use on this device
    - Compares desired NetBox `name`/`description` vs current device state (when enhanced facts available)
    - Only returns VLANs where name or description differs from device
    - Returns: List of VLAN objects needing name/description updates

- **`get_vlan_interfaces(interfaces)`**
    - Extract VLAN/SVI interfaces (e.g., vlan100, vlan200)
    - Returns: List of VLAN interface objects

### `vrf_filters.py` - VRF Operations

VRF extraction and filtering (8 filters):

- **`extract_interface_vrfs(interfaces)`**
    - Extract unique VRF names from interfaces
    - Returns: Set of VRF names

- **`filter_vrfs_in_use(vrfs, interfaces, tenant=None)`**
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

- **`get_all_rt_names(vrf_details)`**
    - Extract all unique route target names from VRF export/import target lists
    - Returns: Sorted list of unique RT name strings

- **`build_vrf_rt_config(vrf_details)`**
    - Build address-family-aware route target config grouped per VRF
    - Reads `address_family` custom field from RT objects; defaults to `ipv4`
    - Returns: Dict keyed by VRF name → `{ipv4: {export: [], import: []}, ipv6: {...}}`

- **`get_vrf_rt_removals(vrf_rt_config, vrf_rt_facts=None)`**
    - Compare desired route targets (`build_vrf_rt_config` output) against device state
      (`aoscx_vrf_rt_facts`, gathered via REST API) to find route targets present on the
      device but no longer in NetBox
    - RT *additions* stay idempotent via `aoscx_config`'s `match: line`; this filter only
      closes the "stale RT" gap for `aoscx_idempotent_mode` cleanup
    - Returns `[]` when `vrf_rt_facts` is `None` (no reliable device state to diff against)
    - Returns: List of `{vrf, address_family, direction, rt}` dicts

- **`get_vrf_changes(vrfs_in_use, vrf_rt_config, vrf_facts=None, vrf_rt_facts=None)`**
    - Single source of truth for VRF change detection, used by
      `tasks/identify_vrf_changes.yml` so `configure_vrfs.yml` only pushes
      VRF creation / RD / route-target diffs that actually differ from device
      state (mirrors the interface/VLAN change-identification pattern)
    - Compares NetBox desired state (`vrfs_in_use`, `vrf_rt_config`) against
      device REST facts (`aoscx_vrf_facts`, `aoscx_vrf_rt_facts`)
    - When facts are `None` (REST API fact gathering disabled), returns every
      VRF/RD/RT for push - same "push everything" fallback convention as
      `get_static_route_changes` and `get_vrf_rt_removals`
    - Returns: Dict with `to_create`, `rd_changes`, `rt_additions`,
      `rt_removals`, and `no_changes` keys

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
    - Returns dict with 9 categories:
    - `physical_default_vrf`: Physical interfaces in default/Global/mgmt VRF
    - `physical_custom_vrf`: Physical interfaces in custom VRFs
    - `vlan_default_vrf`: VLAN/SVI interfaces in default VRF
    - `vlan_custom_vrf`: VLAN/SVI interfaces in custom VRFs
    - `lag_default_vrf`: LAG interfaces in default VRF
    - `lag_custom_vrf`: LAG interfaces in custom VRFs
    - `subinterface_default_vrf`: Sub-interfaces in default VRF
    - `subinterface_custom_vrf`: Sub-interfaces in custom VRFs
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

NetBox vs device comparison and idempotency logic (1 filter, 761 lines).
The IPv4/IPv6/VRF/encapsulation/anycast/DHCP-relay comparison itself lives
in `interface_ip_comparisons.py` (682 lines, internal helpers
`compute_l3_ip_changes()` and `compute_dhcp_relay_changes()` — not
separately exposed as Ansible filters); this module handles the
orchestration described below and calls into those helpers per interface.

- **`get_interfaces_needing_config_changes(interfaces, device_facts, enhanced_facts=None, dhcp_relay_facts=None, ip_helper_addresses=None)`**
    - Compare NetBox interface configuration with device state
    - Implements granular change detection for:
      - Physical properties (enabled/disabled, description, MTU) — physical, LAG, and MCLAG interfaces
      - Description — virtual interfaces (VLAN SVIs, loopbacks, sub-interfaces; NetBox `type.value == "virtual"`), which skip the admin-state/MTU checks above but are still compared on `description`
      - Encapsulation VLAN — sub-interfaces only (NetBox `type.value == "virtual"` with `parent` set). Compares the device's `subintf_vlan` (REST API, requires `enhanced_facts`) against the first `tagged_vlans[].vid` on the NetBox interface, so a re-tagged sub-interface is detected as drift instead of silently passing when its IP/description are otherwise unchanged
      - LAG membership
      - L2 VLAN configuration
      - L3 IP addresses (IPv4 with specific address tracking; IPv6 with full comparison when `enhanced_facts` is provided, otherwise reference only)
      - DHCP relay / ip helper-address (when `dhcp_relay_facts` and `ip_helper_addresses` are both provided; otherwise conservative — always marks as needing change when `if_ip_helper=True`)
    - Parameters:
      - `interfaces`: List of NetBox interface objects
      - `device_facts`: Device facts dict (from `aoscx_facts` / `ansible_facts`)
      - `enhanced_facts`: Optional dict of enhanced interface data from `aoscx_enhanced_interface_facts` (populated by `tasks/gather_facts_rest_api.yml` when `aoscx_gather_facts_rest_api: true`). Provides actual IPv6 addresses and VSX virtual IPs for accurate comparison instead of URL references.
      - `dhcp_relay_facts`: Optional dict keyed by interface name with a sorted list of currently configured relay server IPs. Produced by `rest_api_to_aoscx_dhcp_relays` from `GET /system/dhcp_relays?depth=2`. When provided (with `ip_helper_addresses`), enables idempotent DHCP relay comparison.
      - `ip_helper_addresses`: Optional dict keyed by VRF name with `{str_index: ip}` dicts (from `ip_helper_addresses` config context). Used together with `dhcp_relay_facts`.
    - Returns: Dict with categorized interfaces:
      - `physical`: Physical interfaces needing changes
      - `lag`: LAG interfaces needing changes
      - `mclag`: MCLAG interfaces needing changes
      - `l2`: L2 interfaces needing VLAN changes
      - `l3`: L3 interfaces needing IP address or DHCP relay changes (also includes VLAN SVI / loopback / sub-interface entries that only need a description update)
      - `lag_members`: Physical interfaces needing LAG assignment changes
      - `no_changes`: Interfaces that don't need any changes
    - Adds `_ip_changes` dict to L3 interfaces containing:
      - `ipv4_to_add`: List of specific IPv4 addresses needing configuration
      - `ipv6_addresses`: List of IPv6 addresses needing configuration (all when enhanced facts are absent; only additions when enhanced facts are available)
      - `dhcp_relay_change`: `True` when DHCP relay configuration needs to be pushed (set in all relay-change branches so `group_interface_ips` includes the interface even when no IPs need adding)
      - `dhcp_relay_to_remove`: Sorted list of relay server IPs present on the device but absent from NetBox (requires `dhcp_relay_facts`). Used by the "Remove stale ip helper-address entries" task.
      - `dhcp_relay_expected`/`dhcp_relay_actual`: Sorted lists of the desired (from `ip_helper_addresses`) and currently-configured (from `dhcp_relay_facts`) relay servers. Always populated for any interface with `if_ip_helper=True` when both `dhcp_relay_facts` and `ip_helper_addresses` are provided — including interfaces that land in `no_changes` because the servers already match — so verification/reporting tooling can display current ip helper state without re-deriving it.
      - `description_change`: `True` when a virtual interface's (VLAN SVI/loopback/sub-interface) description differs from the device, so `group_interface_ips` includes the interface even when no IPs need adding and `build_l3_config_lines` emits a `description` line. Physical/LAG/MCLAG description changes are handled separately by `configure_physical_interfaces.yml`/`configure_lag_interfaces.yml`/`configure_mclag_interfaces.yml`, which push description unconditionally whenever the interface has any pending change.
      - `encapsulation_change`: `True` when a sub-interface's device-side `subintf_vlan` (REST API, requires `enhanced_facts`) differs from NetBox's `tagged_vlans[0].vid`, so `group_interface_ips` includes the interface even when no IPs need adding and `build_l3_config_lines` re-emits the `encapsulation dot1q <vid>` line. Without `enhanced_facts` this comparison is skipped (no false positives, but also no drift detection) since standard `aoscx_facts` does not expose `subintf_vlan`.
    - See "L3 Interface IP Address Idempotency" section for performance details

### `bgp_filters.py` - BGP Session Enrichment, Policy, Redistribution, Neighbor Options, BFD

BGP session enrichment and config-building against the NetBox BGP plugin
(8 filters, 899 lines):

- **`get_bgp_session_vrf_info(sessions, interfaces)`**
    - Enrich BGP session objects with VRF and address-family by cross-referencing interface IP assignments
    - Normalises built-in VRF names (mgmt, Global, default) to `'default'`
    - Returns: List of session dicts, each with added `_vrf` (str) and `_af` (`'ipv4'`/`'ipv6'`) fields

- **`collect_ebgp_vrf_policy_config(sessions, all_policy_rules, all_prefix_list_rules)`**
    - Build AOS-CX CLI commands for route-maps and prefix lists from NetBox BGP plugin data
    - Route-map entries use `route-map NAME permit seq INDEX` syntax
    - Returns: Dict with `prefix_lists` and `route_map_rules` lists

- **`get_bgp_redistribute_config(bgp_redistribute)`**
    - Flattens the `bgp_redistribute` config_context (keyed by VRF name, each
      mapping an address family to a list of protocols) into a list of
      per-VRF, per-AF, per-protocol entries
    - Unknown/invalid address families or protocols are skipped rather than raised
    - Returns: `[{"vrf": str, "af": "ipv4"|"ipv6", "protocol": str}, ...]`

- **`get_stale_bgp_redistribute(bgp_redistribute, running_config, local_asn)`**
    - `aoscx_config` (used to push the entries from `get_bgp_redistribute_config`)
      only ever adds missing lines — it never removes ones deleted from
      config_context. Diffs `show running-config` text against the desired
      state to find explicit `no redistribute` candidates for idempotent cleanup
    - Returns: `[{"vrf": str, "af": str, "protocol": str}, ...]` to remove

- **`get_bgp_neighbor_options_config(bgp_neighbor_options, sessions)`**
    - Flattens the `bgp_neighbor_options` config_context (keyed by neighbor
      IP, each mapping a scope `ipv4`/`ipv6`/`general` to a list of raw CLI
      option strings) into per-VRF, per-scope, per-neighbor entries
    - Matches each neighbor IP against live session data (`_vrf`/`_af` from
      `get_bgp_session_vrf_info`) so only IPs actually peered are pushed;
      lines already managed by other BGP tasks (`remote-as`, `route-map`,
      `activate`, ...) are skipped so this can't fight those tasks
    - Returns: `[{"vrf": str, "af": str|None, "neighbor_ip": str, "command": str}, ...]`

- **`get_stale_bgp_neighbor_options(bgp_neighbor_options, sessions, running_config, local_asn)`**
    - Cleanup counterpart to `get_bgp_neighbor_options_config`: diffs
      `show running-config` against the desired neighbor options to find
      lines that were removed from config_context and must be un-configured
    - Returns: Same shape as `get_bgp_neighbor_options_config`, entries to remove

- **`get_bgp_bfd_enabled(bgp_neighbor_options, sessions)`**
    - AOS-CX's `bfd` command is a single global, top-level toggle — not
      per-VRF/neighbor — and must be enabled before any neighbor's
      `fall-over bfd` has effect. Derives whether it's needed from any
      neighbor declaring `fall-over bfd` in the `general` scope of
      `bgp_neighbor_options`, rather than requiring a second config_context entry
    - **Note**: `bfd` is also usable by OSPF/static routes — if those start
      managing it too, this and `get_stale_bgp_bfd()` must be combined with
      their equivalent checks before pushing `no bfd`
    - Returns: `bool` — `True` if the global `bfd` line must be present

- **`get_stale_bgp_bfd(bgp_neighbor_options, sessions, running_config)`**
    - Cleanup counterpart: `True` when `bfd` is currently configured on the
      device but no neighbor declares `fall-over bfd` anymore, so `no bfd`
      should be pushed

### `port_access.py` - Port-Access Diff

Idempotency comparison for port-access (device-profile) configuration
(2 filters, 355 lines):

- **`port_access_facts_from_device_profiles(profiles_payload)`**
    - Flattens the `/system/device_profiles?depth=4` REST payload (which
      nests each profile's `role` and `lldp_groups` inline) into the
      `aoscx_port_access_facts` shape expected by `port_access_diff` —
      `{device_profiles, roles, lldp_groups}`, each a flat dict keyed by
      object name
    - Returns: Dict with keys `device_profiles`, `roles`, `lldp_groups`

- **`port_access_diff(desired, current)`**
    - Compare the desired `port_access` config_context against
      `aoscx_port_access_facts` (REST API fact gathering) and return only
      the items that need to be configured.
    - Compares LLDP group match-sets (sequence-number agnostic), role
      attributes (`description`, `poe_priority`, `trust_mode` vs REST
      `qos_trust_mode`, `vlan_trunk_native`/`vlan_access` vs `vlan_tag`,
      `vlan_trunk_allowed` range expansion vs `vlan_trunks` list), and
      device-profile associations (`enable`, `associate_role`,
      `associate_lldp_group`).
    - Returns: Dict with `lldp_groups`, `roles`, `device_profiles` lists.
      When current facts are missing, returns every desired item (safe
      fallback).

### `port_access_orphans.py` - Port-Access Cleanup

Identifies orphaned port-access objects for idempotent cleanup (1 filter,
36 lines):

- **`port_access_orphans(desired, current)`**
    - Compares `aoscx_port_access_facts` (`current`) against the desired
      `port_access` config_context (`desired`) per object kind
      (`device_profiles`, `roles`, `lldp_groups`) and returns names present
      on the device but no longer in NetBox — orphan = present on device but
      not in NetBox
    - Returns: `{"device_profiles": [...], "roles": [...], "lldp_groups": [...]}`
      (sorted name lists); `current` missing/not-a-dict returns all-empty lists

### `vsx.py` - VSX Config Change Detection

Idempotency comparison for VSX (MCLAG peer-switch) configuration (1 filter,
80 lines):

- **`vsx_config_diff(desired, facts)`**
    - Compares desired VSX settings from config_context (`vsx_role`,
      `vsx_system_mac`, `vsx_isl_lag`, `vsx_keepalive_vrf`,
      `vsx_keepalive_src`, `vsx_keepalive_peer`) against `aoscx_vsx_facts`
      (REST API; may be empty/`None`)
    - Returns: `{"changed": bool, "changes": [{"field": str, "expected": ..., "actual": ...}, ...]}`

### `interface_orphans.py` - Virtual Interface Cleanup

Identifies orphaned virtual interfaces for idempotent cleanup (1 filter, 56
lines):

- **`get_virtual_interfaces_to_delete(desired_interfaces, device_interfaces)`**
    - Unlike physical/LAG/MCLAG interfaces (which always exist in hardware
      regardless of NetBox), VLAN SVIs, loopbacks, and sub-interfaces are
      logical objects this role creates and destroys. If NetBox is
      misconfigured — e.g. an interface renamed or reparented — the stale
      device-side object is never referenced again and can hold the same IP
      as its replacement, breaking L3 configuration with a duplicate-IP error
    - Matches device interface names against a `vlan<N>` / `loopback<N>` /
      `<parent>.<N>` regex to identify which device interfaces are virtual,
      then returns those present on the device but absent from NetBox
    - Returns: Sorted list of virtual interface names to delete. Physical
      and LAG/MCLAG interfaces are never included (they can't be deleted)

### `stp.py` - Global and Per-Interface STP Change Detection

STP configuration change detection (2 filters, 134 lines):

- **`stp_global_config_diff(desired, facts)`**
    - Compares desired global MSTP config (`mstp_config_name`,
      `mstp_config_revision`, `mstp_priority` from config_context) against
      `aoscx_stp_global_facts` (the `stp_config` object from
      `/system?attributes=stp_config&depth=1`)
    - Returns: `{"changed": bool, "changes": [{"field", "expected", "actual"}, ...], "lines": [str, ...]}`

- **`stp_interface_changes(interfaces, enhanced_facts)`**
    - Compare NetBox interface STP custom fields against device `stp_config` facts
      from `aoscx_enhanced_interface_facts` (populated by `gather_facts_rest_api.yml`
      when `aoscx_gather_facts_rest_api: true` and `aoscx_configure_stp: true`).
    - Only L2 interfaces (mode defined) are considered; routed interfaces are ignored.
    - Custom field values of `None` (not set in NetBox) are skipped — the device
      setting is left unchanged for that field.
    - NetBox custom field → `stp_config` device field → AOS-CX CLI command mapping:

      | Custom field | Device field | Enable command |
      |---|---|---|
      | `if_stp_bpdu_filter` | `bpdu_filter_enable` | `spanning-tree bpdu-filter` |
      | `if_stp_bpdu_guard` | `bpdu_guard_enable` | `spanning-tree bpdu-guard` |
      | `if_stp_edge_port` | `admin_edge_port_enable` | `spanning-tree port-type admin-edge` |
      | `if_stp_root_guard` | `root_guard_enable` | `spanning-tree root-guard` |

    - When desired differs from current, the enable command or its `no` prefix is added.
    - When `enhanced_facts` is empty or the interface is absent, all device fields
      default to `False` — any NetBox `True` value produces the enable command.
    - Parameters:
        - `interfaces`: List of NetBox interface dicts
        - `enhanced_facts`: `aoscx_enhanced_interface_facts` dict (keyed by interface name)
    - Returns: List of `{"name": str, "lines": [str]}` — only interfaces with changes.

### `comparison.py` - State Comparison
NetBox vs device state comparison (2 filters, 295 lines):

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
OSPF interface selection and validation:

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

- **`normalize_ospf_vrfs(ospf_vrfs, ospf_1_vrf=None, ospf_areas=None)`**
    - Collapses the multi-VRF (`ospf_vrfs`) and legacy single-VRF
      (`ospf_1_vrf` + `ospf_areas`) config context formats into one shape
    - Returns: `[{'vrf': str, 'areas': [{'area': str}, ...]}, ...]`

- **`filter_ospf_vrfs_in_use(ospf_vrfs, vrf_names_in_use)`**
    - Drops OSPF VRF/area entries for VRFs with no interfaces assigned on
      this device (the built-in `default` VRF is always kept)
    - Returns: Filtered `ospf_vrfs` list

- **`validate_ospf_config(device_config, interfaces)`**
    - Validate OSPF configuration consistency
    - Checks router ID and area definitions
    - Returns: Dict with `valid` boolean, `warnings`, and `errors` lists

- **`get_ospf_router_changes(ospf_config, ospf_router_facts=None)`**
    - Compares desired OSPF router-id/areas per VRF against device REST
      facts (`aoscx_ospf_router_facts`)
    - When `ospf_router_facts` is `None` (REST facts unavailable), every
      desired router-id/area is returned for push
    - Returns: `{"router_changes": [...], "area_additions": [...],
      "no_changes": [...]}`

- **`get_ospf_interface_changes(ospf_interface_items, ospf_interface_facts=None, ospf_router_facts=None, process_id=1)`**
    - Compares desired per-interface OSPF settings (area, network type,
      MD5 authentication, passive) against device REST facts
      (`aoscx_ospf_interface_facts`, `aoscx_ospf_router_facts`)
    - Reuses the same network-type enum mapping and MD5-auth-presence
      semantics as `l3_config_helpers.group_interface_ips`
    - When facts are unavailable, every item is returned for push
    - Returns: `{"config_changes": [...], "passive_set": [...],
      "passive_clear": [...], "no_changes": [...]}`

### `static_route_filters.py` - Static Route Change Detection

Pre-compares desired static routes (NetBox `static_routes` config context,
per VRF) against device REST API facts (`aoscx_static_route_facts`),
since `aoscx_static_route` is not idempotent (pyaoscx always deletes and
recreates the route's next-hop).

- **`get_static_route_changes(static_routes, static_route_facts=None)`**
    - Compares desired routes (type, distance, next-hop IP/interface)
      against current device state per VRF/prefix
    - When `static_route_facts` is `None` (REST facts unavailable), all
      desired routes are returned for push and none for deletion
    - Returns: `{"routes_to_apply": [...], "routes_to_delete": [...]}`
      — see [STATIC_ROUTES_CONFIGURATION.md](STATIC_ROUTES_CONFIGURATION.md)

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
    # Returns: { vids: [...], vlans: [...] }

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
    # Returns dict with 9 categories:
    # {
    #   physical_default_vrf: [...],
    #   physical_custom_vrf: [...],
    #   vlan_default_vrf: [...],
    #   vlan_custom_vrf: [...],
    #   lag_default_vrf: [...],
    #   lag_custom_vrf: [...],
    #   subinterface_default_vrf: [...],
    #   subinterface_custom_vrf: [...],
    #   loopback: [...]
    # }

# Match IP addresses to interfaces
- set_fact:
    interface_ips: "{{ interfaces | get_interface_ip_addresses(ip_addresses) }}"
```

### L3 Configuration Helpers

```yaml
# Group per-IP items into per-interface items (filters to _needs_add=True)
- set_fact:
    grouped: "{{ l3_interfaces.physical_custom_vrf | group_interface_ips }}"
    # Returns: [{interface_name: '1/1/1', interface: {...}, addresses: [{address, ip_role, anycast_mac}]}]
    # Interfaces with _ip_changes.dhcp_relay_change=True are also included even with no IPs to add

# Build all L3 configuration lines for a grouped interface item
- set_fact:
    config_lines: "{{ item | build_l3_config_lines('physical', 'custom', true) }}"
    # Returns: ['vrf attach CUST-A', 'ip address 10.1.1.1/24', 'ip mtu 9000', 'l3-counters']
    # OSPF interface lines are emitted by tasks/configure_ospf.yml, not here

# Build config with DHCP relay (ip helper-address)
- set_fact:
    config_lines: "{{ item | build_l3_config_lines('vlan', 'custom', true, ip_helper_addresses) }}"
    # When item.interface.custom_fields.if_ip_helper=True and ip_helper_addresses has
    # an entry for the interface VRF, emits lines such as:
    # ['vrf attach lab-blue', 'ip address 172.27.4.1/27', 'ip helper-address 172.16.3.10',
    #  'ip helper-address 172.16.3.11', 'l3-counters']

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

### STP Interface Configuration

```yaml
# Build list of L2 interfaces that need STP changes
# (compares NetBox custom fields against aoscx_enhanced_interface_facts[name].stp_config)
- set_fact:
    stp_changes: "{{ interfaces | stp_interface_changes(aoscx_enhanced_interface_facts | default({})) }}"
    # Returns: [{"name": "1/1/5", "lines": ["spanning-tree bpdu-guard", "spanning-tree port-type admin-edge"]}, ...]
    # Only interfaces where at least one field differs are included.

# Apply commands (used by configure_stp.yml)
- arubanetworks.aoscx.aoscx_config:
    lines: "{{ item.lines }}"
    parents: "interface {{ item.name }}"
  loop: "{{ stp_changes }}"
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
    - BGP operations → `bgp_filters.py`
    - L3 configuration helpers → `l3_config_helpers.py`
    - General utilities → `utils.py`
    - STP operations → `stp.py`
    - Port-access (device-profile) operations → `port_access.py` / `port_access_orphans.py`
    - VSX operations → `vsx.py`
    - Static route operations → `static_route_filters.py`
    - Virtual interface (SVI/loopback/sub-interface) cleanup → `interface_orphans.py`

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
                        netbox_filters_lib/*.py

# Run specific checks
pylint netbox_filters_lib/*.py
black --check netbox_filters_lib/*.py
flake8 netbox_filters_lib/*.py
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
netbox_filters.py (main entry point, 62 filters)
    ├── utils.py (no dependencies)
    ├── vlan_filters.py → utils
    ├── vrf_filters.py → utils
    ├── bgp_filters.py → utils
    ├── interface_categorization.py → utils
    ├── interface_ip_processing.py → utils
    ├── interface_change_detection.py → utils, interface_ip_comparisons
    ├── interface_ip_comparisons.py → utils
    ├── interface_orphans.py (no dependencies)
    ├── l3_config_helpers.py → utils
    ├── comparison.py → utils
    ├── ospf_filters.py → utils
    ├── port_access.py (no dependencies)
    ├── port_access_orphans.py (no dependencies)
    ├── static_route_filters.py (no dependencies)
    ├── stp.py (no dependencies)
    └── vsx.py (no dependencies)

rest_api_transforms.py (separate entry point, 5 filters — no dependency on netbox_filters_lib)
```

### Performance Considerations

- Filters are designed for datasets of 100-1000 interfaces
- Use `_debug()` sparingly in production (controlled by env var)
- Comparison filters optimize by early exit when no changes needed
- Set operations used for efficient VLAN/VRF lookups

## Statistics

- **Total Filters**: 67 (62 in `netbox_filters.py` + 5 in `rest_api_transforms.py`)
- **Total Lines**: ~6,500 in `netbox_filters_lib/` (including docstrings and comments), plus ~460 across the two plugin entry-point files
- **Modules**: 17 in `netbox_filters_lib/`, across 2 plugin files
- **Test Coverage**: Unit-tested per module under `tests/unit/`; used in production for 100+ switches
- **Code Quality**: Pylint-checked via pre-commit

### Filter Distribution

| Module | Filters | Lines | Description |
|--------|---------|-------|-------------|
| `vlan_filters.py` | 14 | 952 | VLAN lifecycle management (incl. IGMP/voice/name change detection, VLAN-group exclusion) |
| `bgp_filters.py` | 8 | 899 | BGP session enrichment, policy, redistribute, neighbor options, BFD |
| `interface_change_detection.py` | 1 | 760 | Change detection orchestration & idempotency |
| `interface_ip_comparisons.py` | 0 (internal) | 681 | IPv4/IPv6/VRF/anycast/DHCP relay comparison |
| `l3_config_helpers.py` | 8 | 583 | L3 configuration optimization (incl. ip helper-address) |
| `port_access.py` | 2 | 355 | Port-access (device-profile) idempotency |
| `interface_categorization.py` | 2 | 325 | Interface categorization |
| `comparison.py` | 2 | 291 | State comparison logic |
| `vrf_filters.py` | 8 | 428 | VRF operations, route targets, change detection |
| `ospf_filters.py` | 8 | 438 | OSPF configuration and change detection |
| `utils.py` | 4 | 246 | Helper functions (incl. IP version detection, data-shape normalisation) |
| `static_route_filters.py` | 1 | 136 | Static route change detection |
| `stp.py` | 2 | 134 | Global + per-interface STP change detection |
| `interface_ip_processing.py` | 1 | 103 | IP address matching |
| `vsx.py` | 1 | 80 | VSX config change detection |
| `interface_orphans.py` | 1 | 56 | Orphaned virtual interface cleanup |
| `port_access_orphans.py` | 1 | 36 | Orphaned port-access object cleanup |
| **Subtotal (`netbox_filters_lib/`, 17 modules)** | **62 unique** *(rows above sum to 64 — `is_ipv4_address`/`is_ipv6_address` appear in both `utils.py`'s row and `l3_config_helpers.py`'s row, see note)* | **~6,500** | |
| `rest_api_transforms.py` *(separate plugin)* | 5 | 275 | REST API → `aoscx_facts` format normalization |
| **Total** | **67** | **~6,960** | **17 lib modules + 1 separate plugin** |

Note: `is_ipv4_address` / `is_ipv6_address` are implemented in `utils.py` but
their Ansible filter names are registered from `l3_config_helpers.py` (which
imports and re-exports them). They're listed under both rows above because
both are true depending on what you're looking for ("where's the code" vs.
"where's the filter name registered") — count them once when totaling.

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
- **[Filter Plugin Reuse Guide](FILTER_PLUGINS_REUSE.md)** - Which filters work with other vendor devices
- **[Development Guide](DEVELOPMENT.md)** - Contributing guidelines
- **[NetBox Integration](NETBOX_INTEGRATION.md)** - NetBox setup and configuration
