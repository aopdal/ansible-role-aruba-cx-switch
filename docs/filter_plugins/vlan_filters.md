# VLAN Filters Module

Part of the NetBox Filters Library for Aruba AOS-CX switches.

## What This Module Does (Plain English)

A **VLAN** (Virtual LAN) is a way to split a physical switch into multiple isolated networks. For example, VLAN 10 might be for office PCs and VLAN 20 for printers - even though they're plugged into the same switch, they can't talk to each other without a router.

This module handles everything VLAN-related when configuring a switch from NetBox:

- **Finding which VLANs are in use**: Not every VLAN defined in NetBox is needed on every switch. These filters figure out which VLANs are actually assigned to interfaces on a specific device.
- **Creating and removing VLANs**: Compares what VLANs should exist (from NetBox) with what VLANs currently exist (from device facts) and tells you which ones to create or delete.
- **EVPN/VXLAN support**: In overlay networks, VLANs are extended across data centers using EVPN and VXLAN. These filters extract which VLANs need EVPN configuration and what VNI (Virtual Network Identifier) maps to which VLAN.
- **Parsing show commands**: Can read the output of `show evpn evi` from the switch and extract structured data from it.

---

## Overview

The `vlan_filters.py` module provides comprehensive VLAN lifecycle management functionality. It handles extraction, filtering, EVPN/VXLAN configuration, and state comparison for VLANs across NetBox and device facts.

**File Location**: `filter_plugins/netbox_filters_lib/vlan_filters.py`

**Lines of Code**: 455 lines

**Dependencies**: [utils.py](utils.md) (`_debug`)

**Filter Count**: 8 filters + 1 parser

## Filters

### 1. `extract_vlan_ids(interfaces)`

Extracts all unique VLAN IDs in use from a list of interfaces.

#### Purpose

Scans interface configurations to build a comprehensive list of all VLANs that need to exist on the switch. This includes VLANs from:
- VLAN interfaces (SVIs) like `vlan100`
- Untagged (access/native) VLANs
- Tagged (trunk) VLANs

#### Parameters

- **interfaces** (list): List of interface objects from NetBox

#### Returns

- **list**: Sorted list of unique VLAN IDs (integers)

#### Algorithm

1. Initialize empty set for VLAN IDs
2. For each interface:
   - Extract VLAN ID from interface name if it starts with `vlan`
   - Add untagged VLAN ID if present
   - **Skip tagged VLANs if the interface is a subinterface** (type `virtual` with a parent)
   - Add all tagged VLAN IDs if present (physical/LAG interfaces only)
3. Sort and return as list

> **Note:** Tagged VLANs on subinterfaces (e.g. `1/1/3.100`) are intentionally excluded. A subinterface uses an encapsulation VLAN for L3 routing and does not require a standalone VLAN to be created on the switch.

#### Implementation Details

```python
def _is_subinterface(interface):
    """Return True when interface is a subinterface (virtual + parent)."""
    if not interface or not isinstance(interface, dict):
        return False
    type_obj = interface.get("type")
    type_value = type_obj.get("value") if isinstance(type_obj, dict) else None
    has_parent = interface.get("parent") is not None
    return type_value == "virtual" and has_parent


def extract_vlan_ids(interfaces):
    vlan_ids = set()

    for interface in interfaces:
        # VLAN interfaces (e.g., vlan100)
        if interface.get("name", "").startswith("vlan"):
            try:
                vid = int(interface["name"].replace("vlan", ""))
                vlan_ids.add(vid)
            except (ValueError, TypeError):
                pass

        # Untagged VLANs
        if interface.get("untagged_vlan") and interface["untagged_vlan"] is not None:
            vid = interface["untagged_vlan"].get("vid")
            if vid is not None:
                vlan_ids.add(vid)

        # Tagged VLANs on subinterfaces do not require standalone VLAN creation.
        if _is_subinterface(interface):
            continue

        # Tagged VLANs
        if interface.get("tagged_vlans") and interface["tagged_vlans"] is not None:
            for vlan in interface["tagged_vlans"]:
                vid = vlan.get("vid")
                if vid is not None:
                    vlan_ids.add(vid)

    _debug(f"Extracted VLAN IDs: {sorted(list(vlan_ids))}")
    return sorted(list(vlan_ids))
```

#### Usage Examples

**Basic Extraction:**
```yaml
- name: Get all VLAN IDs in use
  set_fact:
    vlan_ids: "{{ netbox_interfaces | extract_vlan_ids }}"
  # Returns: [10, 20, 100, 200]
```

**With Debug Output:**
```bash
export DEBUG_ANSIBLE=true
# Output: DEBUG: Extracted VLAN IDs: [10, 20, 100, 200]
```

**Complete Workflow:**
```yaml
---
- name: Ensure all required VLANs exist
  hosts: switches
  tasks:
    - name: Get VLANs from interfaces
      set_fact:
        required_vlans: "{{ netbox_interfaces | extract_vlan_ids }}"

    - name: Display VLAN count
      debug:
        msg: "Switch requires {{ required_vlans | length }} VLANs: {{ required_vlans }}"

    - name: Create VLANs
      arubanetworks.aoscx.aoscx_vlan:
        vlan_id: "{{ item }}"
        state: present
      loop: "{{ required_vlans }}"
```

---

### 2. `filter_vlans_in_use(vlans, interfaces)`

Filters a list of VLAN objects to include only those actually in use on interfaces.

#### Purpose

NetBox may have many VLANs defined for a site/tenant, but only a subset are used on a specific switch. This filter extracts just the relevant VLANs.

#### Parameters

- **vlans** (list): List of all VLAN objects from NetBox
- **interfaces** (list): List of interface objects from NetBox

#### Returns

- **list**: Filtered list of VLAN objects that are in use

#### Algorithm

1. Extract VLAN IDs in use (calls `extract_vlan_ids()`)
2. Filter VLAN objects to only those with VIDs in the in-use set
3. Return filtered list

#### Usage Examples

**Filter VLANs:**
```yaml
- name: Get only VLANs actually used
  set_fact:
    active_vlans: "{{ all_device_vlans | filter_vlans_in_use(netbox_interfaces) }}"
```

**Create Only Used VLANs:**
```yaml
- name: Filter to VLANs in use
  set_fact:
    vlans_to_create: "{{ device_vlans | filter_vlans_in_use(interfaces) }}"

- name: Create VLANs with metadata
  arubanetworks.aoscx.aoscx_vlan:
    vlan_id: "{{ item.vid }}"
    name: "{{ item.name }}"
    description: "{{ item.description | default(omit) }}"
    state: present
  loop: "{{ vlans_to_create }}"
```

---

### 3. `extract_evpn_vlans(vlans, interfaces, check_noevpn=True)`

Extracts VLANs that should be configured for EVPN based on L2VPN terminations and custom fields.

#### Purpose

In EVPN-VXLAN environments, not all VLANs participate in the fabric. This filter identifies which VLANs should be configured for EVPN based on:
- L2VPN termination configuration
- `vlan_noevpn` custom field flag

#### Parameters

- **vlans** (list): List of all VLAN objects from NetBox
- **interfaces** (list): List of interface objects from NetBox
- **check_noevpn** (bool, default=True): Whether to check `vlan_noevpn` custom field

#### Returns

- **list**: List of VLAN objects for EVPN configuration

#### Algorithm

1. Get VLANs in use (calls `filter_vlans_in_use()`)
2. For each VLAN:
   - Skip if `vlan_noevpn` custom field is set (optional check)
   - Include if L2VPN termination exists
3. Return EVPN-enabled VLANs

#### Custom Fields

**vlan_noevpn** (boolean): Set to `true` in NetBox to exclude a VLAN from EVPN configuration. Useful for:
- Management VLANs
- Local-only VLANs
- Troubleshooting/testing VLANs

#### Usage Examples

**Get EVPN VLANs:**
```yaml
- name: Get VLANs for EVPN configuration
  set_fact:
    evpn_vlans: "{{ device_vlans | extract_evpn_vlans(interfaces) }}"
```

**Configure EVPN:**
```yaml
- name: Configure EVPN for VLANs
  arubanetworks.aoscx.aoscx_evpn:
    vlan_id: "{{ item.vid }}"
    rd: "auto"
    route_target_export: "{{ item.l2vpn_termination.l2vpn.identifier }}:{{ item.vid }}"
    route_target_import: "{{ item.l2vpn_termination.l2vpn.identifier }}:{{ item.vid }}"
  loop: "{{ evpn_vlans }}"
```

**Skip noevpn Check:**
```yaml
# Include all VLANs with L2VPN, ignoring vlan_noevpn flag
- name: Get all L2VPN VLANs
  set_fact:
    all_l2vpn_vlans: "{{ device_vlans | extract_evpn_vlans(interfaces, false) }}"
```

---

### 4. `extract_vxlan_mappings(vlans, interfaces, use_l2vpn_id=True)`

Extracts VXLAN VNI-to-VLAN mappings for VXLAN configuration.

#### Purpose

VXLAN requires mapping VLAN IDs to VNI (VXLAN Network Identifier) values. This filter generates those mappings from NetBox L2VPN configuration.

#### Parameters

- **vlans** (list): List of all VLAN objects from NetBox
- **interfaces** (list): List of interface objects from NetBox
- **use_l2vpn_id** (bool, default=True): Use L2VPN identifier as VNI (true), or use VLAN ID (false)

#### Returns

- **list**: List of dicts with `vni` and `vlan` keys
  ```python
  [
    {"vni": 10010, "vlan": 10},
    {"vni": 10020, "vlan": 20},
    # ...
  ]
  ```

#### Algorithm

1. Get VLANs in use
2. For each VLAN:
   - Skip if `vlan_noevpn` is set
   - If `use_l2vpn_id=True`: Extract VNI from L2VPN identifier
   - If `use_l2vpn_id=False`: Use VLAN ID as VNI
3. Return list of mappings

#### Usage Examples

**L2VPN-Based VNI Mapping:**
```yaml
- name: Get VXLAN mappings from L2VPN identifiers
  set_fact:
    vxlan_mappings: "{{ device_vlans | extract_vxlan_mappings(interfaces) }}"
  # Returns: [{"vni": 10010, "vlan": 10}, {"vni": 10020, "vlan": 20}]

- name: Configure VXLAN
  arubanetworks.aoscx.aoscx_vxlan:
    source_ip: "{{ loopback_ip }}"
    vni_mappings: "{{ vxlan_mappings }}"
```

**VLAN ID as VNI:**
```yaml
# Simple 1:1 mapping (VNI = VLAN ID)
- name: Use VLAN IDs as VNIs
  set_fact:
    vxlan_mappings: "{{ device_vlans | extract_vxlan_mappings(interfaces, false) }}"
  # Returns: [{"vni": 10, "vlan": 10}, {"vni": 20, "vlan": 20}]
```

**Complete VXLAN Configuration:**
```yaml
---
- name: Configure VXLAN on leaf switches
  hosts: leaf_switches
  tasks:
    - name: Get VXLAN VNI mappings
      set_fact:
        vni_mappings: "{{ device_vlans | extract_vxlan_mappings(interfaces, true) }}"

    - name: Display mappings
      debug:
        msg: "VNI {{ item.vni }} -> VLAN {{ item.vlan }}"
      loop: "{{ vni_mappings }}"

    - name: Configure VXLAN VNI mappings
      arubanetworks.aoscx.aoscx_vxlan:
        vni: "{{ item.vni }}"
        vlan: "{{ item.vlan }}"
      loop: "{{ vni_mappings }}"
```

---

### 5. `get_vlans_in_use(interfaces, vlan_interfaces=None, port_access=None)`

Extracts comprehensive VLAN details with full metadata from interfaces.

#### Purpose

Provides detailed VLAN information including both IDs and full VLAN objects with all NetBox metadata (name, description, tenant, etc.).

#### Parameters

- **interfaces** (list): List of interface objects from NetBox
- **vlan_interfaces** (list, optional): List of VLAN/SVI interfaces to also process
- **port_access** (dict, optional): `port_access` dict from NetBox
  config_context. VLAN IDs referenced by `port_access.roles[*]`
  (`vlan_trunk_native`, `vlan_trunk_allowed`, `vlan_access`) are added to
  the in-use set so the VLANs get created on the device and are protected
  from idempotent cleanup. Range/list syntax is supported (e.g.
  `"11-13"`, `"11,13,15-20"`).

#### Returns

- **dict**: Dictionary with:
  - `vids` (list): Sorted list of VLAN IDs in use
  - `vlans` (list): List of unique VLAN objects with full metadata

#### Algorithm

1. Initialize empty dicts/sets for tracking VLANs
2. Process physical/LAG interfaces:
   - Extract untagged VLAN
   - Skip management interfaces
   - **Skip tagged VLANs if the interface is a subinterface** (type `virtual` with a parent)
   - Extract tagged VLANs (physical/LAG interfaces only)
3. Process VLAN/SVI interfaces (if provided):
   - Extract VLAN from interface
4. Return dict with VIDs and VLAN objects

> **Note:** Tagged VLANs on subinterfaces are excluded because a subinterface uses an encapsulation VLAN for L3 routing and does not require a standalone VLAN to be created on the switch.

#### Usage Examples

**Get Comprehensive VLAN Data:**
```yaml
- name: Get detailed VLAN information
  set_fact:
    vlans_in_use: "{{ interfaces | get_vlans_in_use }}"

- name: Display VLAN summary
  debug:
    msg: |
      VLANs in use: {{ vlans_in_use.vids }}
      VLAN details: {{ vlans_in_use.vlans | length }} objects
```

**Include VLAN Interfaces:**
```yaml
- name: Get VLAN interfaces
  set_fact:
    vlan_intfs: "{{ interfaces | get_vlan_interfaces }}"

- name: Get all VLANs including from SVIs
  set_fact:
    all_vlans: "{{ interfaces | get_vlans_in_use(vlan_intfs) }}"
```

**Include VLANs referenced by port-access roles (config_context):**
```yaml
- name: Get all VLANs including those referenced by port-access roles
  set_fact:
    all_vlans: "{{ interfaces | get_vlans_in_use(
                    vlan_intfs | default([]),
                    port_access | default({})
                  ) }}"
```

Given the following `port_access` config_context:

```json
{
  "port_access": {
    "roles": [
      {
        "name": "Lab-IAP-role",
        "vlan_trunk_native": 11,
        "vlan_trunk_allowed": "11-13"
      }
    ]
  }
}
```

VLAN IDs `11`, `12`, and `13` are added to `vids` and resolved against the
NetBox-provided VLAN list, so they are auto-created on the device and
protected from deletion in idempotent mode.

**Use VLAN Metadata:**
```yaml
- name: Get VLANs in use
  set_fact:
    vlans_data: "{{ interfaces | get_vlans_in_use }}"

- name: Create VLANs with full metadata
  arubanetworks.aoscx.aoscx_vlan:
    vlan_id: "{{ item.vid }}"
    name: "{{ item.name }}"
    description: "{{ item.description | default('') }}"
  loop: "{{ vlans_data.vlans }}"

- name: Report VLAN usage
  debug:
    msg: "VLAN {{ item.vid }} ({{ item.name }}) - Tenant: {{ item.tenant.name | default('None') }}"
  loop: "{{ vlans_data.vlans }}"
```

---

### 6. `get_vlans_needing_changes(device_vlans, vlans_in_use_dict, device_facts=None)`

Determines which VLANs need to be added or removed by comparing NetBox with device state.

#### Purpose

Idempotent VLAN management - only create or delete VLANs when necessary. Compares:
- NetBox source of truth (what should exist)
- Device facts (what currently exists)
- Interface configuration (what's actually in use)

#### Parameters

- **device_vlans** (list): List of VLAN objects available for this device from NetBox
- **vlans_in_use_dict** (dict): Dict from `get_vlans_in_use()` with `vids` and `vlans` keys
- **device_facts** (dict, optional): Device facts from `ansible_facts` for current state

#### Returns

- **dict**: Dictionary with:
  - `vlans_to_create` (list): VLAN objects to create
  - `vlans_to_delete` (list): VLAN IDs to delete
  - `vlans_in_use` (list): VLAN objects currently in use

#### Algorithm

1. Validate inputs
2. Extract VLANs in use from `vlans_in_use_dict`
3. If device facts provided:
   - Extract current VLANs on device from `network_resources.vlans`
4. Build dict of available VLANs from NetBox
5. Determine VLANs to create:
   - In use AND (not on device OR no facts provided)
6. Determine VLANs to delete:
   - On device AND not in use AND not VLAN 1
7. Return results dict

#### Special Cases

- **VLAN 1**: Never deleted (default VLAN on switches)
- **No Facts**: All in-use VLANs marked for creation
- **Orphaned VLANs**: VLANs on device but not in NetBox are deleted

#### Usage Examples

**Basic Idempotent VLAN Management:**
```yaml
- name: Gather facts
  arubanetworks.aoscx.aoscx_facts:
    gather_subset:
      - vlans

- name: Get VLANs in use
  set_fact:
    vlans_in_use: "{{ interfaces | get_vlans_in_use }}"

- name: Determine VLAN changes
  set_fact:
    vlan_changes: "{{
      device_vlans |
      get_vlans_needing_changes(vlans_in_use, ansible_facts)
    }}"

- name: Display change summary
  debug:
    msg: |
      VLANs to create: {{ vlan_changes.vlans_to_create | length }}
      VLANs to delete: {{ vlan_changes.vlans_to_delete | length }}
```

**Create and Delete VLANs:**
```yaml
- name: Create missing VLANs
  arubanetworks.aoscx.aoscx_vlan:
    vlan_id: "{{ item.vid }}"
    name: "{{ item.name }}"
    state: present
  loop: "{{ vlan_changes.vlans_to_create }}"
  when: vlan_changes.vlans_to_create | length > 0

- name: Delete unused VLANs
  arubanetworks.aoscx.aoscx_vlan:
    vlan_id: "{{ item }}"
    state: absent
  loop: "{{ vlan_changes.vlans_to_delete }}"
  when: vlan_changes.vlans_to_delete | length > 0
```

**Detailed Reporting:**
```yaml
- name: Generate VLAN change report
  debug:
    msg: |
      === VLAN Change Report ===
      Total VLANs in NetBox: {{ device_vlans | length }}
      VLANs in use: {{ vlan_changes.vlans_in_use | map(attribute='vid') | list }}

      VLANs to create ({{ vlan_changes.vlans_to_create | length }}):
      {% for vlan in vlan_changes.vlans_to_create %}
      - VLAN {{ vlan.vid }}: {{ vlan.name }}
      {% endfor %}

      VLANs to delete ({{ vlan_changes.vlans_to_delete | length }}):
      {{ vlan_changes.vlans_to_delete }}
```

---

### 7. `get_vlan_interfaces(interfaces)`

Extracts VLAN/SVI (Switched Virtual Interface) interfaces from interface list.

#### Purpose

Identifies virtual interfaces that provide Layer 3 routing for VLANs. These are interfaces like `vlan100`, `vlan200`, etc.

#### Parameters

- **interfaces** (list): List of interface objects from NetBox

#### Returns

- **list**: List of VLAN interface objects

#### Algorithm

1. Iterate through interfaces
2. Check if interface is type "virtual"
3. Check if name contains "vlan"
4. Add matching interfaces to result
5. Return VLAN interface list

#### Usage Examples

**Get VLAN Interfaces:**
```yaml
- name: Extract VLAN/SVI interfaces
  set_fact:
    svi_interfaces: "{{ interfaces | get_vlan_interfaces }}"
```

**Configure SVIs:**
```yaml
- name: Get VLAN interfaces
  set_fact:
    vlan_intfs: "{{ netbox_interfaces | get_vlan_interfaces }}"

- name: Configure IP addresses on SVIs
  arubanetworks.aoscx.aoscx_l3_interface:
    interface: "{{ item.name }}"
    ipv4: "{{ item.ip_addresses[0].address }}"
    vrf: "{{ item.vrf.name | default(omit) }}"
  loop: "{{ vlan_intfs }}"
  when: item.ip_addresses | length > 0
```

**Combine with get_vlans_in_use:**
```yaml
- name: Get VLAN interfaces
  set_fact:
    vlan_intfs: "{{ interfaces | get_vlan_interfaces }}"

- name: Get all VLANs including from SVIs
  set_fact:
    all_vlans: "{{ interfaces | get_vlans_in_use(vlan_intfs) }}"
```

---

### 8. `parse_evpn_evi_output(output)`

Parses `show evpn evi` command output to extract EVPN and VXLAN configuration from the device.

#### Purpose

Extracts EVPN/VXLAN configuration from show command output for validation and comparison. Useful for:
- Verifying EVPN configuration
- Comparing NetBox vs. device state
- Troubleshooting EVPN issues

#### Parameters

- **output** (str): String output from `show evpn evi` command

#### Returns

- **dict**: Dictionary with:
  - `evpn_vlans` (list): VLAN IDs configured with EVPN
  - `vxlan_mappings` (list): `[VNI, VLAN]` pairs
  - `vxlan_vnis` (list): VNI values
  - `vxlan_vlans` (list): VLAN IDs configured with VXLAN

#### Command Output Format

```
L2VNI : 10100010
    Route Distinguisher        : 172.20.1.33:10
    VLAN                       : 10
    Status                     : up
    RT Import                  : 65005:10
    RT Export                  : 65005:10

L2VNI : 10100020
    Route Distinguisher        : 172.20.1.33:20
    VLAN                       : 20
    Status                     : up
    RT Import                  : 65005:20
    RT Export                  : 65005:20
```

#### Usage Examples

**Parse Show Command Output:**
```yaml
- name: Get EVPN EVI configuration
  arubanetworks.aoscx.aoscx_command:
    commands:
      - show evpn evi
  register: evpn_output

- name: Parse EVPN configuration
  set_fact:
    evpn_config: "{{ evpn_output.stdout[0] | parse_evpn_evi_output }}"

- name: Display parsed config
  debug:
    var: evpn_config
  # Output:
  # evpn_vlans: [10, 20]
  # vxlan_mappings: [[10100010, 10], [10100020, 20]]
  # vxlan_vnis: [10100010, 10100020]
  # vxlan_vlans: [10, 20]
```

**Validate EVPN Configuration:**
```yaml
- name: Get expected EVPN VLANs from NetBox
  set_fact:
    expected_evpn_vlans: "{{ device_vlans | extract_evpn_vlans(interfaces) | map(attribute='vid') | list }}"

- name: Get actual EVPN VLANs from device
  arubanetworks.aoscx.aoscx_command:
    commands:
      - show evpn evi
  register: evpn_show

- name: Parse device EVPN config
  set_fact:
    actual_evpn_config: "{{ evpn_show.stdout[0] | parse_evpn_evi_output }}"

- name: Compare expected vs actual
  set_fact:
    evpn_missing: "{{ expected_evpn_vlans | difference(actual_evpn_config.evpn_vlans) }}"
    evpn_extra: "{{ actual_evpn_config.evpn_vlans | difference(expected_evpn_vlans) }}"

- name: Report discrepancies
  debug:
    msg: |
      EVPN VLANs missing from device: {{ evpn_missing }}
      EVPN VLANs not in NetBox: {{ evpn_extra }}
  when: (evpn_missing | length > 0) or (evpn_extra | length > 0)
```

---

## Complete Workflow Example

```yaml
---
- name: Complete VLAN lifecycle management
  hosts: leaf_switches
  tasks:
    # 1. Gather current device state
    - name: Gather VLAN facts
      arubanetworks.aoscx.aoscx_facts:
        gather_subset:
          - vlans
          - interfaces

    # 2. Get VLANs in use from NetBox
    - name: Determine VLANs in use
      set_fact:
        vlans_in_use: "{{ netbox_interfaces | get_vlans_in_use }}"

    # 3. Compare NetBox with device and determine changes
    - name: Calculate VLAN changes needed
      set_fact:
        vlan_changes: "{{
          device_vlans |
          get_vlans_needing_changes(vlans_in_use, ansible_facts)
        }}"

    # 4. Report planned changes
    - name: Display change summary
      debug:
        msg: |
          VLANs in use: {{ vlans_in_use.vids }}
          VLANs to create: {{ vlan_changes.vlans_to_create | map(attribute='vid') | list }}
          VLANs to delete: {{ vlan_changes.vlans_to_delete }}

    # 5. Create missing VLANs
    - name: Create VLANs
      arubanetworks.aoscx.aoscx_vlan:
        vlan_id: "{{ item.vid }}"
        name: "{{ item.name }}"
        description: "{{ item.description | default(omit) }}"
        state: present
      loop: "{{ vlan_changes.vlans_to_create }}"

    # 6. Configure EVPN for VLANs (if applicable)
    - name: Get EVPN VLANs
      set_fact:
        evpn_vlans: "{{ device_vlans | extract_evpn_vlans(netbox_interfaces) }}"
      when: enable_evpn | default(false)

    - name: Configure EVPN
      arubanetworks.aoscx.aoscx_evpn:
        vlan_id: "{{ item.vid }}"
        rd: "auto"
        state: present
      loop: "{{ evpn_vlans }}"
      when: enable_evpn | default(false)

    # 7. Configure VXLAN mappings (if applicable)
    - name: Get VXLAN mappings
      set_fact:
        vxlan_mappings: "{{ device_vlans | extract_vxlan_mappings(netbox_interfaces) }}"
      when: enable_vxlan | default(false)

    - name: Configure VXLAN
      arubanetworks.aoscx.aoscx_vxlan:
        vni: "{{ item.vni }}"
        vlan: "{{ item.vlan }}"
        state: present
      loop: "{{ vxlan_mappings }}"
      when: enable_vxlan | default(false)

    # 8. Delete unused VLANs (after interface cleanup in other tasks)
    - name: Remove unused VLANs
      arubanetworks.aoscx.aoscx_vlan:
        vlan_id: "{{ item }}"
        state: absent
      loop: "{{ vlan_changes.vlans_to_delete }}"
      when: allow_vlan_deletion | default(false)
```

---

## Port-Access Helpers

Two helpers expose the VLAN-ID parsing/extraction logic that backs
`get_vlans_in_use`'s `port_access` argument. They are useful when building
diffs, validation rules, or render filters for the port-access feature.

### `extract_port_access_vlan_ids(port_access)`

Extracts every VLAN ID referenced by port-access roles in a `port_access`
config_context dict.

#### Parameters

- **port_access** (dict | None): `port_access` dict from NetBox
  config_context. Walks `port_access.roles[*]` and reads
  `vlan_trunk_native`, `vlan_trunk_allowed`, and `vlan_access`.

#### Returns

Sorted list of unique VLAN IDs (1-4094). Returns `[]` for `None`, missing
`roles`, or roles without VLAN fields.

#### Example

```yaml
- name: Show VLANs referenced by port-access roles
  ansible.builtin.debug:
    msg: "{{ port_access | default({}) | extract_port_access_vlan_ids }}"
```

Given:

```json
{
  "port_access": {
    "roles": [
      { "name": "Lab-IAP-role", "vlan_trunk_native": 11, "vlan_trunk_allowed": "11-13" },
      { "name": "Printer-role", "vlan_access": 50 }
    ]
  }
}
```

Returns: `[11, 12, 13, 50]`

---

### `parse_vlan_id_spec(spec)`

Parses a VLAN-ID specification into a sorted list of unique integers.

#### Parameters

- **spec** (int | str | list | tuple | None): Accepts:
    - `int` (e.g. `11`)
    - `str`: comma-separated list with optional ranges
      (`"11"`, `"11,13"`, `"11-13"`, `"11,13,15-20"`). Whitespace is tolerated.
    - `list`/`tuple` of any of the above (recursed)

#### Returns

Sorted list of unique VLAN IDs (1-4094). Reverse ranges are normalised
(`"15-13"` → `[13, 14, 15]`). Out-of-range and non-numeric tokens are
skipped silently (with debug output).

#### Examples

| Input | Output |
|---|---|
| `11` | `[11]` |
| `"11,13,15"` | `[11, 13, 15]` |
| `"11-13"` | `[11, 12, 13]` |
| `"11,13,15-20"` | `[11, 13, 15, 16, 17, 18, 19, 20]` |
| `[11, "13-14"]` | `[11, 13, 14]` |
| `"0,1,4094,4095"` | `[1, 4094]` |

---



- [Filter Plugins Overview](../FILTER_PLUGINS.md)
- [Utils Module](utils.md) - Debug and utility functions
- [Interface Filters](interface_filters.md) - Interface categorization
- [Comparison Module](comparison.md) - State comparison logic
- [EVPN/VXLAN Configuration Guide](../EVPN_VXLAN_CONFIGURATION.md)
- [L2 Interface Modes](../L2_INTERFACE_MODES.md)
