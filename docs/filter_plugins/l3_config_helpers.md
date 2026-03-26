# L3 Configuration Helpers

**Module**: `l3_config_helpers.py`
**Filters**: 6
**Purpose**: L3 interface configuration optimization and code reuse

## What This Module Does (Plain English)

When you assign IP addresses to a switch interface, you need to run several configuration commands: set the IPs, maybe attach a VRF, enable L3 counters, configure the MTU, configure OSPF, etc. The exact commands vary slightly depending on whether it's a physical port, a LAG, a VLAN interface, or a sub-interface.

This module provides two key filters that work together:

1. **`group_interface_ips`** — groups a flat per-IP list (one item per address) into a per-interface list (one item per interface, with all its addresses). This is the crucial pre-processing step.

2. **`build_l3_config_lines`** — takes a grouped interface item and generates **all** correct configuration commands for that interface in one pass: VRF attachment, all IPv4/IPv6 addresses, anycast gateways, MTU, L3 counters, and OSPF — each emitted exactly once, no matter how many IPs the interface has.

It also provides small helper filters for common L3 tasks:
- Formatting interface names (e.g., `lag1` needs to become `lag 1` on AOS-CX)
- Checking whether an IP address is IPv4 or IPv6
- Extracting the VRF name from interface data with a safe fallback

---

## Overview

The L3 Configuration Helpers module provides specialized filter functions for building Layer 3 interface configurations. This module was created to eliminate code duplication across physical, LAG, VLAN, and sub-interface configuration tasks while providing a clean, testable API for L3 operations.

### Key Benefits

- **Single source of truth** for L3 configuration logic
- **Eliminates ~200+ lines** of duplicated task code
- **No redundant commands** — VRF attach, MTU, L3-counters, OSPF emitted once per interface regardless of how many IPs
- **OSPF inline** — OSPF interface config included in L3 config lines; no separate OSPF interface task needed
- **Unit tested** Python functions vs complex Jinja2 templates
- **Reusable** across all interface types (physical, LAG, VLAN, sub-interface)
- **Supports** IPv4, IPv6, VRFs, anycast gateways, and OSPF

---

## Filters

### 1. `group_interface_ips`

**Purpose**: Group a flat per-IP list into a per-interface list with all addresses combined

**Signature**:
```python
group_interface_ips(interface_ip_list: list) -> list
```

**Parameters**:
- `interface_ip_list` - Flat list of per-IP dicts (output of `get_interface_ip_addresses | categorize_l3_interfaces`), each with keys:
  - `interface_name` - Interface name
  - `interface` - Full interface object from NetBox
  - `address` - IP address with CIDR (e.g., `"10.0.0.1/24"`)
  - `ip_role` - IP role (e.g., `'anycast'`) or `None`
  - `anycast_mac` - MAC for anycast gateway or `None`
  - `_needs_add` - Whether this IP needs to be configured

**Returns**: List of per-interface dicts, each with:
- `interface_name` - Interface name
- `interface` - Full interface object
- `addresses` - List of address dicts, each with `address`, `ip_role`, `anycast_mac`

Only items where `_needs_add` is truthy are included. Addresses are sorted: anycast before regular, IPv4 before IPv6.

**Example**:
```yaml
- set_fact:
    grouped: "{{ l3_interfaces.vlan_default_vrf | group_interface_ips }}"
# Input (3 IPs on vlan108):
# [{interface_name: vlan108, address: 10.0.0.1/24, ip_role: anycast, anycast_mac: 00:..., _needs_add: true},
#  {interface_name: vlan108, address: 2001:db8::1/64, ip_role: anycast, anycast_mac: 00:..., _needs_add: true},
#  {interface_name: vlan108, address: 10.0.0.2/24, ip_role: null, _needs_add: true}]
#
# Output (1 item for vlan108):
# [{interface_name: vlan108, interface: {...},
#   addresses: [
#     {address: 10.0.0.1/24, ip_role: anycast, anycast_mac: 00:...},  # anycast IPv4 first
#     {address: 10.0.0.2/24, ip_role: null, anycast_mac: null},         # regular IPv4
#     {address: 2001:db8::1/64, ip_role: anycast, anycast_mac: 00:...}  # anycast IPv6 last
#   ]}]
```

---

### 2. `format_interface_name`

**Purpose**: Format interface names for AOS-CX CLI context

**Signature**:
```python
format_interface_name(interface_name: str, interface_type: str) -> str
```

**Parameters**:
- `interface_name` - Raw interface name from NetBox
- `interface_type` - Type of interface: `'physical'`, `'lag'`, `'vlan'`, or `'subinterface'`

**Returns**: Formatted interface name for configuration commands

**Behavior**:
- **Physical / VLAN / Sub-interface**: Returns name as-is
- **LAG**: Adds space after 'lag' (e.g., `"lag1"` → `"lag 1"`)

**Example**:
```yaml
- debug:
    msg: "{{ item.interface_name | format_interface_name('lag') }}"
  # Output for lag1: "lag 1"
```

---

### 3. `is_ipv4_address`

**Purpose**: Test if an IP address string is IPv4

**Signature**:
```python
is_ipv4_address(address: str) -> bool
```

**Parameters**:
- `address` - IP address with CIDR notation (e.g., `"192.168.1.1/24"`)

**Returns**: `True` if IPv4, `False` if IPv6

**Detection Method**: Checks for absence of colon (`:`) in address

**Example**:
```yaml
- debug:
    msg: "IPv4"
  when: item.address | is_ipv4_address
```

---

### 4. `is_ipv6_address`

**Purpose**: Test if an IP address string is IPv6

**Signature**:
```python
is_ipv6_address(address: str) -> bool
```

**Parameters**:
- `address` - IP address with CIDR notation (e.g., `"2001:db8::1/64"`)

**Returns**: `True` if IPv6, `False` if IPv4

**Detection Method**: Checks for presence of colon (`:`) in address

---

### 5. `get_interface_vrf`

**Purpose**: Extract VRF name from interface data with safe fallback

**Signature**:
```python
get_interface_vrf(interface_data: dict) -> str
```

**Parameters**:
- `interface_data` - Interface object from NetBox

**Returns**: VRF name, defaults to `'default'` if not specified or invalid

**Example**:
```yaml
- debug:
    msg: "VRF: {{ item.interface | get_interface_vrf }}"
  # Output: "VRF: CUSTOMER_A" or "VRF: default"
```

---

### 6. `build_l3_config_lines`

**Purpose**: Build complete L3 configuration command list for an interface (all IPs, OSPF, VRF, MTU, counters — each emitted once)

**Signature**:
```python
build_l3_config_lines(
    item: dict,
    interface_type: str,
    vrf_type: str,
    l3_counters_enable: bool = True,
    ospf_process_id: int = 1
) -> list[str]
```

**Parameters**:
- `item` - Grouped interface dict (output of `group_interface_ips`), with keys:
  - `interface` - Full interface object from NetBox
  - `interface_name` - Name of interface
  - `addresses` - List of address dicts, each with `address`, `ip_role`, `anycast_mac`
- `interface_type` - `'physical'`, `'lag'`, `'vlan'`, or `'subinterface'`
- `vrf_type` - `'default'` or `'custom'`
- `l3_counters_enable` - Enable L3 counters (default: `True`)
- `ospf_process_id` - OSPF process/instance ID (default: `1`)

**Returns**: List of configuration command strings for the entire interface

**Configuration Elements** (each emitted exactly once per interface):

1. **Encapsulation** (sub-interfaces only, from `interface.custom_fields.encapsulation`)
   ```
   encapsulation dot1q <vlan_id>
   ```

2. **VRF Attachment** (custom VRF only)
   ```
   vrf attach <vrf_name>
   ```

3. **All IPv4 addresses** (anycast first, then regular)
   ```
   active-gateway ip mac <mac>          # anycast
   active-gateway ip <address>          # anycast
   ip address <address>                 # regular
   ip address <address> secondary       # additional regular IPs
   ```

4. **All IPv6 addresses** (anycast first, then regular)
   ```
   ipv6 address link-local <addr>/<prefix>  # if anycast addr is link-local (fe80::)
   active-gateway ipv6 mac <mac>            # anycast
   active-gateway ipv6 <address>           # anycast
   ipv6 address <address>                  # regular
   ```
   > **HPE Aruba recommendation**: Use a link-local address (fe80::) as the IPv6
   > anycast gateway. When the anycast address is link-local, `ipv6 address link-local`
   > must be explicitly configured before the `active-gateway ipv6` command.
   > `build_l3_config_lines` emits this automatically when the anycast address
   > starts with `fe80:`. Global-unicast anycast addresses are unaffected.

5. **MTU** (if set on interface)
   ```
   ip mtu <mtu>
   ```

6. **L3 Counters** (if enabled)
   ```
   l3-counters
   ```

7. **OSPF** (if `custom_fields.if_ip_ospf_1_area` is set on interface)
   ```
   ip ospf <process_id> area <area>
   ip ospf network <type>               # if if_ip_ospf_network is set
   ```

**Example Usage**:

```yaml
# In configure_l3_interface_common.yml
- name: "Configure {{ interface_type }} L3 interfaces ({{ vrf_type }} VRF)"
  arubanetworks.aoscx.aoscx_config:
    lines: "{{ item | build_l3_config_lines(interface_type, vrf_type, aoscx_l3_counters_enable | default(true), ospf_process_id | default(1)) }}"
    parents: "interface {{ item.interface_name | format_interface_name(interface_type) }}"
  loop: "{{ interface_list | group_interface_ips }}"
  loop_control:
    label: "Interface: {{ item.interface_name }}"
```

**Example Output**:

```python
# Dual-stack VLAN interface with link-local anycast gateway (HPE Aruba recommended)
[
  'active-gateway ip mac 00:00:5e:00:01:01',
  'active-gateway ip 10.0.0.1',
  'ip address 10.0.0.2/24',
  'ipv6 address link-local fe80::1/64',   # auto-added when anycast is link-local
  'active-gateway ipv6 mac 00:00:5e:00:01:01',
  'active-gateway ipv6 fe80::1',
  'ipv6 address 2001:db8::2/64',
  'ip mtu 9000',
  'l3-counters',
  'ip ospf 1 area 0.0.0.0',
  'ip ospf network point-to-point'
]

# Regular IPv4 in custom VRF, no OSPF
[
  'vrf attach CUSTOMER_A',
  'ip address 192.168.1.1/24',
  'ip mtu 1500',
  'l3-counters'
]

# LAG sub-interface with encapsulation
[
  'encapsulation dot1q 100',
  'vrf attach CUSTOMER_A',
  'ip address 10.1.1.1/30',
  'l3-counters'
]
```

---

---

## Integration with Role

### Unified Task File

The filters are used by `tasks/configure_l3_interface_common.yml`, a single reusable task that handles all interface types.

**Before refactoring** (12 tasks × ~20 lines each = 240+ lines, plus separate OSPF interface tasks):
```yaml
# Separate tasks for each combination of:
# - Interface type (physical, LAG, VLAN) × 3
# - IP version (IPv4, IPv6) × 2
# - VRF type (default, custom) × 2
# = 12 nearly identical tasks with slight variations
# Plus: separate aoscx_ospf_interface tasks in configure_ospf.yml
```

**After** (1 reusable task, ~20 lines):
```yaml
# tasks/configure_l3_interface_common.yml
- name: "Configure {{ interface_type }} L3 interfaces ({{ vrf_type }} VRF)"
  arubanetworks.aoscx.aoscx_config:
    lines: "{{ item | build_l3_config_lines(interface_type, vrf_type, aoscx_l3_counters_enable | default(true), ospf_process_id | default(1)) }}"
    parents: "interface {{ item.interface_name | format_interface_name(interface_type) }}"
  loop: "{{ _grouped_interfaces }}"
  loop_control:
    label: "Interface: {{ item.interface_name }}"
  when: _grouped_interfaces | length > 0
  vars:
    ansible_connection: "{{ aoscx_connection_type }}"
    _grouped_interfaces: "{{ interface_list | group_interface_ips }}"
```

### Usage in Interface-Specific Tasks

Each interface type file calls the common task once per VRF type:

```yaml
# tasks/configure_l3_physical.yml
- ansible.builtin.include_tasks:
    file: configure_l3_interface_common.yml
  vars:
    interface_list: "{{ l3_interfaces.physical_default_vrf }}"
    interface_type: physical
    vrf_type: default
  when: l3_interfaces.physical_default_vrf | default([]) | length > 0

- ansible.builtin.include_tasks:
    file: configure_l3_interface_common.yml
  vars:
    interface_list: "{{ l3_interfaces.physical_custom_vrf }}"
    interface_type: physical
    vrf_type: custom
  when: l3_interfaces.physical_custom_vrf | default([]) | length > 0
```

### OSPF Interface Config Eliminated

Previously, `configure_ospf.yml` contained two `aoscx_ospf_interface` tasks that configured OSPF area and network type per interface. Since `build_l3_config_lines` now reads `custom_fields.if_ip_ospf_1_area` and `if_ip_ospf_network` directly from the NetBox interface object and emits the OSPF lines inline, those separate tasks are no longer needed. `configure_ospf.yml` retains only the router-level and area-level tasks.

---

## Code Reduction

| Component | Before | After | Reduction |
|-----------|--------|-------|-----------|
| configure_l3_physical.yml | 85 lines (4 includes) | 20 lines (2 includes) | **-76%** |
| configure_l3_lag.yml | 85 lines (4 includes) | 20 lines (2 includes) | **-76%** |
| configure_l3_vlan.yml | 105 lines (4 includes) | 20 lines (2 includes) | **-81%** |
| configure_l3_subinterface.yml | 85 lines (4 includes) | 20 lines (2 includes) | **-76%** |
| configure_ospf.yml (interface tasks) | 30 lines removed | 0 | **-100%** |
| **Total task duplication** | **390 lines** | **80 lines** | **-79%** |

**Added**: `configure_l3_interface_common.yml`: ~20 lines (reusable task)

**Net Result**: Eliminated ~310 lines of duplicated/scattered logic, centralized configuration in testable Python code, no more redundant per-IP command repetition.

---

## Testing

### Unit Tests

All helper functions have comprehensive unit tests in `tests/unit/test_l3_config_helpers.py`:

```python
# Test grouping
result = group_interface_ips([
    {"interface_name": "vlan108", "interface": {}, "address": "10.0.0.1/24",
     "ip_role": "anycast", "anycast_mac": "00:00:5e:00:01:01", "_needs_add": True},
    {"interface_name": "vlan108", "interface": {}, "address": "2001:db8::1/64",
     "ip_role": None, "anycast_mac": None, "_needs_add": True},
])
assert len(result) == 1
assert result[0]["interface_name"] == "vlan108"
assert len(result[0]["addresses"]) == 2

# Test config line building (new grouped API)
item = {"interface_name": "vlan108", "interface": {"mtu": 9000}, "addresses": [
    {"address": "10.0.0.1/24", "ip_role": "anycast", "anycast_mac": "00:00:5e:00:01:01"},
]}
lines = build_l3_config_lines(item, "vlan", "default", True)
assert "active-gateway ip mac 00:00:5e:00:01:01" in lines
assert "active-gateway ip 10.0.0.1" in lines
assert "ip mtu 9000" in lines
assert "l3-counters" in lines
# No redundant vrf attach, no redundant mtu
assert lines.count("l3-counters") == 1
```

### Integration Testing

```bash
# Validate Python syntax
python3 -m py_compile filter_plugins/netbox_filters_lib/l3_config_helpers.py

# Test filter loading
python3 << 'EOF'
from filter_plugins.netbox_filters import FilterModule
fm = FilterModule()
assert 'group_interface_ips' in fm.filters()
assert 'build_l3_config_lines' in fm.filters()
assert 'format_interface_name' in fm.filters()
print("All L3 filters loaded")
EOF

# Run unit tests
python3 -m pytest tests/unit/test_l3_config_helpers.py -v
```

---

## Design Decisions

### Why Group First, Then Build?

The old approach called `build_l3_config_lines` once per IP address (the input list was flat, one item per IP). For an interface with 3 IPs (anycast IPv4, regular IPv4, anycast IPv6), this produced:
```
# Interface vlan108 configured 3 times:
vrf attach TENANT_A     ← repeated
ip address 10.0.0.1/24
ip mtu 9000             ← repeated
l3-counters             ← repeated

vrf attach TENANT_A     ← repeated
ip address 10.0.0.2/24
ip mtu 9000             ← repeated
l3-counters             ← repeated

vrf attach TENANT_A     ← repeated
ipv6 address 2001:db8::1/64
ip mtu 9000             ← repeated
l3-counters             ← repeated
```

The new approach groups first, then builds once per interface:
```
# Interface vlan108 configured once:
vrf attach TENANT_A
ip address 10.0.0.1/24
ip address 10.0.0.2/24 secondary
ipv6 address 2001:db8::1/64
ip mtu 9000
l3-counters
ip ospf 1 area 0.0.0.0
```

### Why Python Over Jinja2?

The config-building logic involves conditionals, loops over address lists, IP version detection, and OSPF field lookups. In Python this is readable and testable. In Jinja2 it would be a maintenance nightmare.

### Address Ordering

AOS-CX CLI requires the active-gateway (anycast) command before the `ip address` command for a given address family. The sort key ensures:
1. Anycast IPv4 addresses
2. Regular IPv4 addresses
3. Anycast IPv6 addresses
4. Regular IPv6 addresses

### OSPF Inline

Instead of a separate `aoscx_ospf_interface` task loop (which requires the same NetBox interface data to be passed separately), `build_l3_config_lines` reads the OSPF custom fields from the interface object already present in the grouped item. This eliminates a complete task category while keeping the data flow simple.

---

## Variables

### Role Defaults

```yaml
# defaults/main.yml

# Enable L3 counters on all L3 interfaces
aoscx_l3_counters_enable: true
```

### OSPF Custom Fields

OSPF configuration is driven by NetBox interface custom fields:

| Custom Field | Purpose |
|---|---|
| `if_ip_ospf_1_area` | OSPF area ID (e.g., `"0.0.0.0"`). If set, OSPF lines are emitted. |
| `if_ip_ospf_network` | OSPF network type (e.g., `"point-to-point"`). Optional. |

The suffix `_1` represents OSPF instance/process 1. If you run multiple OSPF processes, pass a different `ospf_process_id` to `build_l3_config_lines`.

---

## Common Patterns

### Configure Physical L3 Interfaces

```yaml
- ansible.builtin.include_tasks:
    file: configure_l3_interface_common.yml
  vars:
    interface_list: "{{ l3_interfaces.physical_default_vrf }}"
    interface_type: physical
    vrf_type: default
  when: l3_interfaces.physical_default_vrf | default([]) | length > 0
```

### Configure VLAN Interfaces with Anycast and OSPF

```yaml
- ansible.builtin.include_tasks:
    file: configure_l3_interface_common.yml
  vars:
    interface_list: "{{ l3_interfaces.vlan_default_vrf }}"
    interface_type: vlan
    vrf_type: default
  # Anycast gateways and OSPF config automatically included
  # if the NetBox interface has the relevant custom fields
```

### Debug Config Lines Before Applying

```yaml
# In configure_l3_interfaces.yml (guarded by aoscx_debug or verbosity)
- name: Build L3 config lines preview
  set_fact:
    _l3_config_preview: >-
      {%- set result = {} -%}
      {%- set categories = [
        (l3_interfaces.physical_default_vrf, 'physical', 'default'),
        (l3_interfaces.vlan_default_vrf, 'vlan', 'default'),
      ] -%}
      {%- for items, itype, vrf in categories -%}
        {%- for item in items | group_interface_ips -%}
          {%- set lines = item | build_l3_config_lines(itype, vrf, aoscx_l3_counters_enable | default(true)) -%}
          {%- set iname = item.interface_name | format_interface_name(itype) -%}
          {%- set _ = result.update({iname: lines}) -%}
        {%- endfor -%}
      {%- endfor -%}
      {{ result }}
  when: aoscx_debug | bool or ansible_verbosity >= 1
```

---

## Troubleshooting

### Debug Mode

```bash
export DEBUG_ANSIBLE=true
ansible-playbook site.yml
```

### Common Issues

**Issue**: Commands repeated multiple times for the same interface
**Solution**: Ensure you are using `group_interface_ips` before `build_l3_config_lines`. The old per-IP call pattern is no longer used.

**Issue**: LAG interface name not formatted correctly
**Solution**: Ensure `interface_type: lag` is passed

**Issue**: VRF not attached
**Solution**: Verify `vrf_type: custom` and interface has `vrf.name` field in NetBox

**Issue**: Anycast gateway not configured
**Solution**: Check that IP has `role.value: 'anycast'` and interface has `custom_fields.if_anycast_gateway_mac`

**Issue**: `ipv6 address link-local` missing on interfaces that already have `active-gateway ipv6 fe80::1`
**Solution**: This is detected automatically via the `ip6_address_link_local` REST API field (requires `aoscx_gather_facts_rest_api: true`). The role compares the device's active link-local address against the expected link-local anycast from NetBox and stores any missing address in `_ip_changes.link_local_ipv6_to_add`. A dedicated task in `configure_l3_interfaces.yml` then applies `ipv6 address link-local <addr>` before the regular L3 config runs.

**Issue**: OSPF not configured on interface
**Solution**: Check that interface has `custom_fields.if_ip_ospf_1_area` set in NetBox

---

## Related Documentation

- [Filter Plugins Index](index.md) - All available filters
- [Filter Plugins Overview](../FILTER_PLUGINS.md) - Overview with examples
- [Filter Plugins Reuse](../FILTER_PLUGINS_REUSE.md) - Portability guide
- [Interface Filters](interface_filters.md) - Interface categorization
- [OSPF Filters](ospf_filters.md) - Router/area-level OSPF configuration
