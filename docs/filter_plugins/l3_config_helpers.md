# L3 Configuration Helpers

**Module**: `l3_config_helpers.py`
**Filters**: 8
**Purpose**: L3 interface configuration optimization and code reuse

## What This Module Does (Plain English)

When you assign IP addresses to a switch interface, you need to run several configuration commands: set the IPs, maybe attach a VRF, enable L3 counters, configure the MTU, etc. The exact commands vary slightly depending on whether it's a physical port, a LAG, a VLAN interface, or a sub-interface.

This module provides two key filters that work together:

1. **`group_interface_ips`** — groups a flat per-IP list (one item per address) into a per-interface list (one item per interface, with all its addresses). This is the crucial pre-processing step.

2. **`build_l3_config_lines`** — takes a grouped interface item and generates **all** correct base L3 configuration commands for that interface in one pass: VRF attachment, all IPv4/IPv6 addresses, anycast gateways, MTU, and L3 counters — each emitted exactly once, no matter how many IPs the interface has.

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
- **No redundant commands** — VRF attach, MTU, and L3-counters emitted once per interface regardless of how many IPs
- **Clear separation of concerns** — OSPF interface config is handled in `tasks/configure_ospf.yml`
- **Unit tested** Python functions vs complex Jinja2 templates
- **Reusable** across all interface types (physical, LAG, VLAN, sub-interface)
- **Supports** IPv4, IPv6, VRFs, and anycast gateways

---

## Filters

### 1. `group_interface_ips`

**Purpose**: Group a flat per-IP list into a per-interface list with all addresses combined, and decide which interfaces need any L3 config pushed at all this run

**Signature**:
```python
group_interface_ips(
    interface_ip_list: list,
    ospf_facts: dict | None = None,
    ospf_process_id: int = 1,
) -> list
```

**Parameters**:
- `interface_ip_list` - Flat list of per-IP dicts (output of `get_interface_ip_addresses | categorize_l3_interfaces`), each with keys:
  - `interface_name` - Interface name
  - `interface` - Full interface object from NetBox
  - `address` - IP address with CIDR (e.g., `"10.0.0.1/24"`)
  - `ip_role` - IP role (e.g., `'anycast'`) or `None`
  - `anycast_mac` - MAC for anycast gateway or `None`
  - `_needs_add` - Whether this IP needs to be configured
- `ospf_facts` (optional) - `aoscx_ospf_interface_facts`-shaped dict:
  `{vrf: {process_id_str: {area: {intf_name: {ospf_if_type, ...}}}}}`. When
  provided, an interface whose OSPF area/network-type already matches the
  device is *not* pulled in just because it has OSPF configured. When
  `None`, every OSPF-configured interface is included (conservative — no
  device state to compare against).
- `ospf_process_id` (default `1`) - OSPF process ID to look up in `ospf_facts`.

**Returns**: List of per-interface dicts, each with:
- `interface_name` - Interface name
- `interface` - Full interface object
- `addresses` - List of address dicts, each with `address`, `ip_role`, `anycast_mac`

Only addresses where `_needs_add` is truthy are included in `addresses`.
Addresses are sorted: regular before anycast, IPv4 before IPv6.

**Why an interface with zero `_needs_add` addresses can still appear**:
this filter isn't purely "does this interface have a new IP" — it's "does
`build_l3_config_lines` need to run for this interface at all this run". An
interface with no IP changes is still included when any of these is true
(each is set by `get_interfaces_needing_config_changes` in
[interface_change_detection.py](interface_filters.md), so this filter never
inspects device facts itself for these three):

- The interface has `custom_fields.if_ip_ospf_1_area` set **and** either
  `ospf_facts` is `None`, the interface isn't registered in that OSPF area
  yet, or its network type doesn't match `if_ip_ospf_network`.
- `interface._ip_changes.dhcp_relay_change` is `True` (DHCP relay / `ip
  helper-address` servers differ from the device).
- `interface._ip_changes.description_change` is `True` (a VLAN SVI /
  loopback / sub-interface description differs from the device).

Without this, an interface that only needs its OSPF area, DHCP relay
servers, or description updated — with no IP address change at all — would
never be handed to `build_l3_config_lines`, and that update would silently
never get pushed.

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

**Purpose**: Build complete L3 configuration command list for an interface (description, encapsulation, routing, VRF, all IPs, ip helper-address, MTU, counters — each emitted once). **OSPF interface config (`ip ospf ...`) is NOT included here** — that's pushed separately by `tasks/configure_ospf.yml`, using `get_ospf_interface_changes()` (see [OSPF Filters](ospf_filters.md)). `group_interface_ips`'s OSPF-awareness only decides *whether an interface needs to appear in this loop at all*; it doesn't hand OSPF lines to this function.

**Signature**:
```python
build_l3_config_lines(
    item: dict,
    interface_type: str,
    vrf_type: str,
    l3_counters_enable: bool = True,
    ip_helper_addresses: dict | None = None,
) -> list[str]
```

**Parameters**:
- `item` - Grouped interface dict (output of `group_interface_ips`), with keys:
  - `interface` - Full interface object from NetBox (provides `mtu`, `vrf`, `description`, `tagged_vlans` for sub-interfaces, and `_ip_changes` set by change detection)
  - `interface_name` - Name of interface
  - `addresses` - List of address dicts, each with `address`, `ip_role`, `anycast_mac`
- `interface_type` - `'physical'`, `'lag'`, `'vlan'`, `'subinterface'`, or `'loopback'`
- `vrf_type` - `'default'` or `'custom'`
- `l3_counters_enable` - Enable L3 counters (default: `True`)
- `ip_helper_addresses` (optional) - Dict keyed by VRF name, values are `{str_index: ip_address}` (e.g. `{"lab-blue": {"0": "172.16.3.10", "1": "172.16.3.11"}}`, from the `ip_helper_addresses` config_context). When provided **and** the interface has `custom_fields.if_ip_helper: true`, emits one `ip helper-address <ip>` line per server in the interface's VRF, ordered by string index key. Omit (default `None`) when calling from a context that never needs DHCP relay lines (e.g. `build_l3_config_preview`).

**Returns**: List of configuration command strings for the entire interface

**Configuration Elements** (each emitted exactly once per interface, in this order):

1. **Description** (`interface_type` is `'vlan'`, `'loopback'`, or `'subinterface'` only, when `interface.description` is set)
   ```
   description <text>
   ```
   `physical` and `lag` are deliberately excluded here — those already get
   description pushed unconditionally by
   `configure_physical_interfaces.yml`/`configure_lag_interfaces.yml`/
   `configure_mclag_interfaces.yml` whenever the interface has any pending
   change, regardless of L2/L3 role. Emitting it here too would duplicate
   the command.

2. **Encapsulation** (sub-interfaces only, from the first `tagged_vlans[].vid` on the NetBox interface)
   ```
   encapsulation dot1q <vlan_id>
   ```

3. **Routing mode** (`interface_type` is `'physical'` or `'lag'` only)
   ```
   routing
   ```
   Some AOS-CX hardware/firmware defaults physical and LAG ports to L2
   (switching) mode, so routed mode is explicitly enabled whenever the
   interface carries L3 config. VLAN SVIs and loopbacks are always L3 by
   nature and never emit this line; sub-interface parents are handled
   separately in `tasks/configure_physical_interfaces.yml` (not by this
   function).

4. **VRF Attachment** — two cases:
   ```
   vrf attach <vrf_name>
   ```
   - `vrf_type == 'custom'`: attach the named VRF, as before.
   - `vrf_type == 'default'` **and** `interface._ip_changes.vrf_change` is
     `True`: the interface is being moved back from a custom VRF to
     `default`. AOS-CX requires `vrf attach default` explicitly to clear
     the old VRF — simply omitting the command does not revert it.

5. **All IPv4 addresses** (regular first, then anycast)
   ```
   ip address <address>                 # regular
   ip address <address> secondary       # additional regular IPs
   active-gateway ip mac <mac>          # anycast
   active-gateway ip <address>          # anycast
   ```

6. **All IPv6 addresses** (regular first, then anycast)
   ```
   ipv6 address <address>                  # regular
   ipv6 address link-local <addr>/<prefix>  # if anycast addr is link-local (fe80::)
   active-gateway ipv6 mac <mac>            # anycast
   active-gateway ipv6 <address>           # anycast
   ```
   > **HPE Aruba recommendation**: Use a link-local address (fe80::) as the IPv6
   > anycast gateway. When the anycast address is link-local, `ipv6 address link-local`
   > must be explicitly configured before the `active-gateway ipv6` command.
   > `build_l3_config_lines` emits this automatically when the anycast address
   > starts with `fe80:`. Global-unicast anycast addresses are unaffected.

7. **ip helper-address** (only when `ip_helper_addresses` is passed and the interface has `custom_fields.if_ip_helper: true`)
   ```
   ip helper-address <ip>   # one line per configured DHCP relay server
   ```

8. **MTU** (if set on interface)
   ```
   ip mtu <mtu>
   ```

9. **L3 Counters** (if enabled)
   ```
   l3-counters
   ```

**Example Usage**:

```yaml
# In configure_l3_interface_common.yml
- name: "Configure {{ interface_type }} L3 interfaces ({{ vrf_type }} VRF)"
  arubanetworks.aoscx.aoscx_config:
    lines: "{{ item | build_l3_config_lines(interface_type, vrf_type, aoscx_l3_counters_enable | default(true), ip_helper_addresses | default(None)) }}"
    parents: "interface {{ item.interface_name | format_interface_name(interface_type) }}"
  loop: "{{ interface_list | group_interface_ips(aoscx_ospf_interface_facts | default(None), ospf_config.process_id | default(1)) }}"
  loop_control:
    label: "Interface: {{ item.interface_name }}"
```

**Example Output**:

```python
# Dual-stack VLAN interface with link-local anycast gateway (HPE Aruba recommended)
[
    "description Server VLAN",
    "ip address 10.0.0.2/24",
    "active-gateway ip mac 00:00:5e:00:01:01",
    "active-gateway ip 10.0.0.1",
    "ipv6 address 2001:db8::2/64",
    "ipv6 address link-local fe80::1/64",  # auto-added when anycast is link-local
    "active-gateway ipv6 mac 00:00:5e:00:01:01",
    "active-gateway ipv6 fe80::1",
    "ip mtu 9000",
    "l3-counters",
]
# OSPF ("ip ospf 1 area 0.0.0.0", "ip ospf network point-to-point") is pushed
# separately by tasks/configure_ospf.yml, not by this call.

# Regular IPv4 in custom VRF, with DHCP relay
[
    "vrf attach CUSTOMER_A",
    "ip address 192.168.1.1/24",
    "ip helper-address 172.16.3.10",
    "ip mtu 1500",
    "l3-counters",
]

# LAG sub-interface with encapsulation
[
    "encapsulation dot1q 100",
    "vrf attach CUSTOMER_A",
    "ip address 10.1.1.1/30",
    "l3-counters",
]
```

---

### 7. `should_add_interface_ip`

**Purpose**: Decide whether one specific IP address on one interface needs to be pushed to the device this run — the per-address idempotency decision that feeds `group_interface_ips`'s `_needs_add` filtering.

**Signature**:
```python
should_add_interface_ip(interface: dict, address: str) -> bool
```

**Parameters**:
- `interface` - NetBox interface object, expected to carry `_ip_changes` (set by `get_interfaces_needing_config_changes`) when change detection has run.
- `address` - A single IP address string (with or without CIDR) belonging to this interface.

**Returns**: `bool`

**Decision logic** (used by `tasks/configure_l3_interfaces.yml` to set the per-combo `_needs_add` flag before calling `group_interface_ips`):

- **VRF-change short-circuit**: if `interface._ip_changes.vrf_change` is `True`, always returns `True` — moving an interface to a different VRF wipes all its L3 config on the switch, so every address (including anycast) must be re-applied regardless of whether that specific address was already correct.
- **IPv4** (no colon in `address`): returns whether the address is in `_ip_changes.ipv4_to_add`. If `_ip_changes` exists but has no `ipv4_to_add` key, returns `False` (nothing to add). If there's no `_ip_changes` at all, returns `True` (new interface — configure everything).
- **IPv6** (colon in `address`): returns whether the address is in `_ip_changes.ipv6_to_add` when present. If `_ip_changes` exists but has no `ipv6_to_add`, returns `True` — this is the "no enhanced facts" case (see [L3 Interface IP Address Idempotency](../FILTER_PLUGINS.md#l3-interface-ip-address-idempotency) in FILTER_PLUGINS.md): without `aoscx_gather_facts_rest_api: true`, IPv6 can't be compared, so it's always (idempotently, at the CLI level) re-applied. If there's no `_ip_changes` at all, also returns `True`.

**Example**:
```yaml
- name: Mark which IPs actually need adding
  set_fact:
    interface_list: "{{ interface_list | map('combine', {'_needs_add': item | should_add_interface_ip(item.address)}) | list }}"
```

---

### 8. `build_l3_config_preview`

**Purpose**: Debug/dry-run helper — build a `{formatted_interface_name: [config_line, ...]}` mapping across an entire `categorize_l3_interfaces()` output, without pushing anything to a device. Useful in a `debug:` task or `ansible-playbook --check` run to see exactly what L3 config *would* be sent.

**Signature**:
```python
build_l3_config_preview(
    l3_interfaces: dict,
    aoscx_builtin_vrfs: list,
    l3_counters_enable: bool = True,
) -> dict
```

**Parameters**:
- `l3_interfaces` - Output of `categorize_l3_interfaces()` (9 categories: `physical_default_vrf`, `physical_custom_vrf`, `vlan_default_vrf`, `vlan_custom_vrf`, `lag_default_vrf`, `lag_custom_vrf`, `subinterface_default_vrf`, `subinterface_custom_vrf`, `loopback`).
- `aoscx_builtin_vrfs` - List of built-in VRF names (e.g. `["default", "mgmt", "Global"]`). Because `categorize_l3_interfaces` returns `loopback` as a single unsplit list (not separated by VRF like the other categories), this filter splits loopbacks itself: any loopback whose VRF is in `aoscx_builtin_vrfs` (or has no VRF) goes to the default-VRF bucket, the rest go to custom-VRF.
- `l3_counters_enable` - Same meaning as in `build_l3_config_lines` (default `True`).

**Returns**: `dict` — `{formatted_interface_name: [config_line, ...], ...}`, one entry per interface that has any config to show, keyed by the same name `format_interface_name` would produce for that interface.

**Note**: `ip_helper_addresses` is intentionally not exposed as a parameter —
this is meant as a lightweight summary, and the DHCP-relay lines are only
meaningful in the live `configure_l3_interface_common.yml` push where the
real `ip_helper_addresses` config_context is available.

**Example**:
```yaml
- name: Preview all L3 config that would be pushed (debug only)
  debug:
    msg: "{{ l3_interfaces | build_l3_config_preview(aoscx_builtin_vrfs, aoscx_l3_counters_enable | default(true)) }}"
  when: aoscx_debug_l3_preview | default(false)
```

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
    lines: "{{ item | build_l3_config_lines(interface_type, vrf_type, aoscx_l3_counters_enable | default(true), ip_helper_addresses | default(None)) }}"
    parents: "interface {{ item.interface_name | format_interface_name(interface_type) }}"
  loop: "{{ _grouped_interfaces }}"
  loop_control:
    label: "Interface: {{ item.interface_name }}"
  when: _grouped_interfaces | length > 0
  vars:
    ansible_connection: network_cli
    _grouped_interfaces: "{{ interface_list | group_interface_ips }}"
```

### Usage in Interface-Specific Tasks

`tasks/configure_l3_interfaces.yml` iterates over every
`(interface_list, interface_type, vrf_type)` category and calls the common
task once per non-empty category:

```yaml
# tasks/configure_l3_interfaces.yml
- name: Configure L3 interfaces by category
  ansible.builtin.include_tasks:
    file: configure_l3_interface_common.yml
  vars:
    interface_list: "{{ item.list }}"
    interface_type: "{{ item.itype }}"
    vrf_type: "{{ item.vrf_type }}"
  loop:
    - list: "{{ l3_interfaces.physical_default_vrf }}"
      itype: physical
      vrf_type: default
    - list: "{{ l3_interfaces.physical_custom_vrf }}"
      itype: physical
      vrf_type: custom
    # ... subinterface / vlan / lag / loopback × default|custom ...
  when: item.list | length > 0
```

### OSPF Interface Config Eliminated

Previously, `configure_ospf.yml` contained two `aoscx_ospf_interface` tasks that configured OSPF area and network type per interface. Since `build_l3_config_lines` now reads `custom_fields.if_ip_ospf_1_area` and `if_ip_ospf_network` directly from the NetBox interface object and emits the OSPF lines inline, those separate tasks are no longer needed. `configure_ospf.yml` retains only the router-level and area-level tasks.

---

## Code Reduction

| Component | Before | After | Reduction |
|-----------|--------|-------|-----------|
| configure_l3_physical.yml | 85 lines (4 includes) | (deleted, folded into loop) | **-100%** |
| configure_l3_lag.yml | 85 lines (4 includes) | (deleted, folded into loop) | **-100%** |
| configure_l3_vlan.yml | 105 lines (4 includes) | (deleted, folded into loop) | **-100%** |
| configure_l3_subinterface.yml | 85 lines (4 includes) | (deleted, folded into loop) | **-100%** |
| configure_ospf.yml (interface tasks) | 30 lines removed | 0 | **-100%** |
| **Total task duplication** | **390 lines** | **~45 lines (one loop)** | **-88%** |

**Added**: `configure_l3_interface_common.yml`: ~20 lines (reusable task)

**Net Result**: Eliminated ~310 lines of duplicated/scattered logic, centralized configuration in testable Python code, no more redundant per-IP command repetition.

---

## Testing

### Unit Tests

All helper functions have comprehensive unit tests in `tests/unit/test_l3_config_helpers.py`:

```python
# Test grouping
result = group_interface_ips(
    [
        {
            "interface_name": "vlan108",
            "interface": {},
            "address": "10.0.0.1/24",
            "ip_role": "anycast",
            "anycast_mac": "00:00:5e:00:01:01",
            "_needs_add": True,
        },
        {
            "interface_name": "vlan108",
            "interface": {},
            "address": "2001:db8::1/64",
            "ip_role": None,
            "anycast_mac": None,
            "_needs_add": True,
        },
    ]
)
assert len(result) == 1
assert result[0]["interface_name"] == "vlan108"
assert len(result[0]["addresses"]) == 2

# Test config line building (new grouped API)
item = {
    "interface_name": "vlan108",
    "interface": {"mtu": 9000},
    "addresses": [
        {
            "address": "10.0.0.1/24",
            "ip_role": "anycast",
            "anycast_mac": "00:00:5e:00:01:01",
        },
    ],
}
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
python3 -m py_compile netbox_filters_lib/l3_config_helpers.py

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

OSPF configuration is driven by NetBox interface custom fields, but the
actual `ip ospf ...` CLI lines are **not** produced here — they're built
by `get_ospf_interface_changes()` and pushed by `tasks/configure_ospf.yml`
(see [OSPF Filters](ospf_filters.md)). What this module *does* use these
fields for is `group_interface_ips()`'s decision to include an interface in
the L3 loop even when it has no IP changes (see filter 1 above):

| Custom Field | Purpose |
|---|---|
| `if_ip_ospf_1_area` | OSPF area ID (e.g., `"0.0.0.0"`). If set, the interface is pulled into `group_interface_ips()`'s output whenever its OSPF state doesn't yet match the device. |
| `if_ip_ospf_network` | OSPF network type (e.g., `"point-to-point"`). Optional; also considered when deciding whether OSPF state matches the device. |

The suffix `_1` represents OSPF instance/process 1. If you run multiple OSPF
processes, pass a different `ospf_process_id` to `group_interface_ips` (not
to `build_l3_config_lines`, which no longer takes that parameter).

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
