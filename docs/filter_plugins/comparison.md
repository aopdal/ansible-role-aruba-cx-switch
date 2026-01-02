# Comparison Module

Part of the NetBox Filters Library for Aruba AOS-CX switches.

## Overview

The `comparison.py` module provides state comparison logic for determining configuration changes between NetBox (source of truth) and device facts (current state). This enables idempotent playbook execution by only making necessary changes.

**File Location**: [filter_plugins/netbox_filters_lib/comparison.py](../../filter_plugins/netbox_filters_lib/comparison.py)

**Lines of Code**: 279 lines

**Dependencies**: [utils.py](utils.md) (`_debug`)

**Filter Count**: 2 filters

## Purpose

Idempotent infrastructure-as-code requires comparing desired state (NetBox) with current state (device) to determine:
- What needs to be created/added
- What needs to be deleted/removed
- What's already correct (skip)

This module handles VLAN configuration comparison for L2 interfaces on AOS-CX switches.

---

## Filters

### 1. `compare_interface_vlans(netbox_interface, device_facts_interface)`

Compares VLAN configuration between a single NetBox interface and its device facts counterpart.

#### Purpose

Determines exactly what VLAN changes are needed for one interface by comparing:
- VLAN mode (access vs. trunk)
- Access/native VLAN
- Trunk VLAN list

#### Parameters

- **netbox_interface** (dict): Interface object from NetBox
- **device_facts_interface** (dict): Interface object from device facts

#### Returns

- **dict**: Comparison result with:
  - `vlans_to_add` (list): VLAN IDs to add to trunk
  - `vlans_to_remove` (list): VLAN IDs to remove from trunk
  - `needs_change` (bool): Whether any changes are needed
  - `mode_change` (bool): Whether VLAN mode needs to change

#### AOS-CX VLAN Data Structure

Device facts store VLANs in a specific format:

**Access/Native VLAN:**
```python
"vlan_tag": {
    "10": "/rest/v10.09/system/vlans/10"
}
```

**Trunk VLANs:**
```python
"vlan_trunks": {
    "20": "/rest/v10.09/system/vlans/20",
    "30": "/rest/v10.09/system/vlans/30"
}
```

The filter extracts VLAN IDs from the dictionary keys.

#### VLAN Mode Mapping

| NetBox Mode | AOS-CX Mode |
|-------------|-------------|
| `access` | `access` |
| `tagged` | `native-tagged` or `native-untagged` |
| `tagged-all` | `native-tagged` or `native-untagged` |

#### Algorithm

1. Extract NetBox configuration:
   - VLAN mode
   - Untagged VLAN
   - Tagged VLANs
2. Extract device configuration:
   - VLAN mode
   - Native/access VLAN from `vlan_tag` dict
   - Trunk VLANs from `vlan_trunks` dict
3. Compare mode:
   - Check if mode change needed
4. Compare VLANs based on mode:
   - **Access mode**: Compare access VLAN
   - **Tagged mode**: Compare native + trunk VLANs
   - **Tagged-all**: Compare native VLAN only
5. Calculate additions and removals
6. Return comparison dict

#### Usage Examples

**Basic Comparison:**
```yaml
- name: Compare single interface
  set_fact:
    changes: "{{
      netbox_interface |
      compare_interface_vlans(device_interface)
    }}"

- name: Display changes
  debug:
    msg: |
      Needs change: {{ changes.needs_change }}
      Mode change: {{ changes.mode_change }}
      VLANs to add: {{ changes.vlans_to_add }}
      VLANs to remove: {{ changes.vlans_to_remove }}
```

**Conditional Update:**
```yaml
- name: Check if interface needs update
  set_fact:
    comparison: "{{
      netbox_intf |
      compare_interface_vlans(facts_intf)
    }}"

- name: Update only if needed
  arubanetworks.aoscx.aoscx_l2_interface:
    interface: "{{ netbox_intf.name }}"
    # ... configuration ...
  when: comparison.needs_change
```

**Process VLAN Changes:**
```yaml
- name: Compare interface VLANs
  set_fact:
    vlan_changes: "{{
      netbox_intf |
      compare_interface_vlans(device_intf)
    }}"

# Remove VLANs first (if needed)
- name: Remove VLANs
  arubanetworks.aoscx.aoscx_l2_interface:
    interface: "{{ netbox_intf.name }}"
    vlan_trunk_allowed: "{{ device_trunk_vlans | difference(vlan_changes.vlans_to_remove) | list }}"
  when: vlan_changes.vlans_to_remove | length > 0

# Add VLANs
- name: Add VLANs
  arubanetworks.aoscx.aoscx_l2_interface:
    interface: "{{ netbox_intf.name }}"
    vlan_trunk_allowed: "{{ desired_vlans }}"
  when: vlan_changes.vlans_to_add | length > 0
```

#### Comparison Scenarios

**Scenario 1: Access Port (No Changes)**
```yaml
NetBox:
  mode: access
  untagged_vlan: 10

Device:
  vlan_mode: access
  vlan_tag: {"10": "/rest/.../vlans/10"}

Result:
  needs_change: false
  mode_change: false
```

**Scenario 2: Access Port (VLAN Change)**
```yaml
NetBox:
  mode: access
  untagged_vlan: 20

Device:
  vlan_mode: access
  vlan_tag: {"10": "/rest/.../vlans/10"}

Result:
  needs_change: true
  mode_change: false
```

**Scenario 3: Mode Change (Access to Trunk)**
```yaml
NetBox:
  mode: tagged
  untagged_vlan: 10
  tagged_vlans: [20, 30]

Device:
  vlan_mode: access
  vlan_tag: {"10": "/rest/.../vlans/10"}

Result:
  needs_change: true
  mode_change: true
  vlans_to_add: [20, 30]
```

**Scenario 4: Trunk VLANs Need Update**
```yaml
NetBox:
  mode: tagged
  untagged_vlan: 10
  tagged_vlans: [20, 30, 40]

Device:
  vlan_mode: native-untagged
  vlan_tag: {"10": "/rest/.../vlans/10"}
  vlan_trunks: {"20": "...", "30": "...", "50": "..."}

Result:
  needs_change: true
  mode_change: false
  vlans_to_add: [40]     # In NetBox, not on device
  vlans_to_remove: [50]  # On device, not in NetBox
```

---

### 2. `get_interfaces_needing_changes(interfaces, device_facts)`

Analyzes all interfaces to identify which need configuration changes.

#### Purpose

Processes all interfaces at once, returning categorized lists of interfaces that need VLAN cleanup or configuration changes.

#### Parameters

- **interfaces** (list): List of interface objects from NetBox
- **device_facts** (dict): Device facts from `ansible_facts`

#### Returns

- **dict**: Dictionary with:
  - `cleanup` (list): Interfaces needing VLAN removal
  - `configure` (list): Interfaces needing VLAN additions or changes

Each cleanup entry includes:
```python
{
    "interface": "1/1/10",
    "vlans_to_remove": [50, 60],
    "is_lag": false,
    "is_mclag": false
}
```

#### Device Facts Structure

The filter expects device facts in this structure:
```python
ansible_facts:
  network_resources:
    interfaces:
      "1/1/1": { ... }
      "1/1/2": { ... }
```

Or:
```python
network_resources:
  interfaces:
    "1/1/1": { ... }
```

#### Algorithm

1. Validate inputs
2. Extract device facts interfaces dict
3. For each NetBox interface:
   - Skip if None, no mode, or management
   - Find matching device interface
   - Call `compare_interface_vlans()`
   - If changes needed: add to `configure` list
   - If VLANs to remove: add to `cleanup` list
4. Return categorized dict

#### Usage Examples

**Basic Change Detection:**
```yaml
- name: Identify interface changes
  set_fact:
    changes: "{{
      netbox_interfaces |
      get_interfaces_needing_changes(ansible_facts)
    }}"

- name: Display summary
  debug:
    msg: |
      Interfaces needing cleanup: {{ changes.cleanup | length }}
      Interfaces needing configuration: {{ changes.configure | length }}
```

**Two-Phase Configuration:**
```yaml
- name: Get changes
  set_fact:
    intf_changes: "{{ interfaces | get_interfaces_needing_changes(ansible_facts) }}"

# Phase 1: Remove unwanted VLANs
- name: Cleanup VLAN assignments
  arubanetworks.aoscx.aoscx_l2_interface:
    interface: "{{ item.interface }}"
    vlan_trunks_remove: "{{ item.vlans_to_remove }}"
  loop: "{{ intf_changes.cleanup }}"
  when: intf_changes.cleanup | length > 0

# Phase 2: Configure interfaces
- name: Configure interfaces
  arubanetworks.aoscx.aoscx_l2_interface:
    interface: "{{ item.name }}"
    vlan_mode: "{{ item.mode.value }}"
    # ... full configuration ...
  loop: "{{ intf_changes.configure }}"
  when: intf_changes.configure | length > 0
```

**Idempotent Workflow:**
```yaml
---
- name: Idempotent L2 interface configuration
  hosts: switches
  tasks:
    # Gather current state
    - name: Gather facts
      arubanetworks.aoscx.aoscx_facts:
        gather_subset:
          - interfaces

    # Determine changes
    - name: Identify changes
      set_fact:
        changes: "{{
          netbox_interfaces |
          get_interfaces_needing_changes(ansible_facts)
        }}"

    # Report
    - name: Change summary
      debug:
        msg: |
          Total interfaces: {{ netbox_interfaces | length }}
          Interfaces needing changes: {{ changes.configure | length }}
          Interfaces needing cleanup: {{ changes.cleanup | length }}

    # Cleanup first
    - name: Remove unwanted VLANs
      arubanetworks.aoscx.aoscx_l2_interface:
        interface: "{{ item.interface }}"
        vlan_mode: trunk
        vlan_trunk_allowed_remove: "{{ item.vlans_to_remove }}"
      loop: "{{ changes.cleanup }}"
      when: changes.cleanup | length > 0

    # Then configure
    - name: Categorize interfaces needing config
      set_fact:
        l2_intfs: "{{ changes.configure | categorize_l2_interfaces }}"

    - name: Configure access ports
      arubanetworks.aoscx.aoscx_l2_interface:
        interface: "{{ item.name }}"
        vlan_mode: access
        vlan_access: "{{ item.untagged_vlan.vid }}"
      loop: "{{ l2_intfs.access }}"

    - name: Configure trunk ports
      arubanetworks.aoscx.aoscx_l2_interface:
        interface: "{{ item.name }}"
        vlan_mode: trunk
        vlan_trunk_native_id: "{{ item.untagged_vlan.vid | default(omit) }}"
        vlan_trunk_allowed: "{{ item.tagged_vlans | map(attribute='vid') | list }}"
      loop: "{{ l2_intfs.tagged_with_untagged + l2_intfs.tagged_no_untagged }}"
```

**Selective Updates:**
```yaml
- name: Get interface changes
  set_fact:
    changes: "{{ interfaces | get_interfaces_needing_changes(ansible_facts) }}"

# Only configure if there are changes
- name: Configure L2 interfaces
  include_tasks: configure_l2.yml
  when: changes.configure | length > 0

# Only cleanup if needed
- name: Cleanup VLANs
  include_tasks: cleanup_vlans.yml
  when: changes.cleanup | length > 0
```

**Performance Optimization:**
```yaml
---
- name: Optimize with change detection
  hosts: switches
  tasks:
    - name: Gather facts
      arubanetworks.aoscx.aoscx_facts:
        gather_subset:
          - interfaces

    - name: Detect changes
      set_fact:
        changes: "{{ netbox_interfaces | get_interfaces_needing_changes(ansible_facts) }}"

    - name: Skip if no changes
      debug:
        msg: "No interface changes needed - skipping configuration"
      when: changes.configure | length == 0

    - name: Report change count
      debug:
        msg: "{{ changes.configure | length }} interfaces need updates"
      when: changes.configure | length > 0

    # Only run configuration if needed
    - name: Configure interfaces
      arubanetworks.aoscx.aoscx_l2_interface:
        # ... configuration ...
      loop: "{{ changes.configure }}"
      when: changes.configure | length > 0
```

---

## Complete Idempotent Workflow

```yaml
---
- name: Idempotent L2 interface management
  hosts: leaf_switches
  gather_facts: false
  tasks:
    # === GATHER CURRENT STATE ===
    - name: Gather device facts
      arubanetworks.aoscx.aoscx_facts:
        gather_subset:
          - interfaces
          - vlans
      register: device_facts

    # === IDENTIFY CHANGES ===
    - name: Determine interface changes needed
      set_fact:
        interface_changes: "{{
          netbox_interfaces |
          get_interfaces_needing_changes(ansible_facts)
        }}"

    # === REPORT ===
    - name: Display change summary
      debug:
        msg: |
          ===== Interface Change Summary =====
          Total interfaces in NetBox: {{ netbox_interfaces | length }}
          Interfaces needing changes: {{ interface_changes.configure | length }}
          Interfaces needing cleanup: {{ interface_changes.cleanup | length }}
          Interfaces already correct: {{
            (netbox_interfaces | length) - (interface_changes.configure | length)
          }}

    # === CLEANUP PHASE ===
    - name: Remove unwanted VLANs (Phase 1)
      block:
        - name: Report cleanup
          debug:
            msg: "Removing VLANs from {{ item.interface }}: {{ item.vlans_to_remove }}"
          loop: "{{ interface_changes.cleanup }}"

        - name: Execute VLAN removal
          arubanetworks.aoscx.aoscx_l2_interface:
            interface: "{{ item.interface }}"
            vlan_mode: trunk
            vlan_trunk_allowed_remove: "{{ item.vlans_to_remove }}"
          loop: "{{ interface_changes.cleanup }}"
      when: interface_changes.cleanup | length > 0

    # === CONFIGURATION PHASE ===
    - name: Configure interfaces (Phase 2)
      block:
        # Categorize interfaces needing changes
        - name: Categorize L2 interfaces
          set_fact:
            l2_categories: "{{ interface_changes.configure | categorize_l2_interfaces }}"

        # Configure access ports
        - name: Configure access ports
          arubanetworks.aoscx.aoscx_l2_interface:
            interface: "{{ item.name }}"
            vlan_mode: access
            vlan_access: "{{ item.untagged_vlan.vid }}"
          loop: "{{ l2_categories.access }}"

        # Configure trunk ports with native VLAN
        - name: Configure trunk ports (with native)
          arubanetworks.aoscx.aoscx_l2_interface:
            interface: "{{ item.name }}"
            vlan_mode: trunk
            vlan_trunk_native_id: "{{ item.untagged_vlan.vid }}"
            vlan_trunk_allowed: "{{ item.tagged_vlans | map(attribute='vid') | list }}"
          loop: "{{ l2_categories.tagged_with_untagged }}"

        # Configure trunk ports without native VLAN
        - name: Configure trunk ports (no native)
          arubanetworks.aoscx.aoscx_l2_interface:
            interface: "{{ item.name }}"
            vlan_mode: trunk
            vlan_trunk_allowed: "{{ item.tagged_vlans | map(attribute='vid') | list }}"
          loop: "{{ l2_categories.tagged_no_untagged }}"

      when: interface_changes.configure | length > 0

    # === VERIFICATION ===
    - name: Verify changes
      arubanetworks.aoscx.aoscx_facts:
        gather_subset:
          - interfaces
      when: interface_changes.configure | length > 0

    - name: Final status
      debug:
        msg: "Interface configuration complete - all interfaces now match NetBox"
```

---

## Debug Output Examples

With `DEBUG_ANSIBLE=true`:

```
DEBUG: Found 48 interfaces in device facts
DEBUG: Sample interface keys: ['1/1/1', '1/1/2', '1/1/3', '1/1/4', '1/1/5']
DEBUG: Interface 1/1/10: NB mode=tagged, untagged=10, tagged={20, 30, 40}
DEBUG: Interface 1/1/10: Device mode=native-untagged, native=10, trunks={20, 30, 50}
DEBUG: Interface 1/1/10 comparison: {'vlans_to_add': [40], 'vlans_to_remove': [50], 'needs_change': True, 'mode_change': False}
DEBUG: Interface 1/1/10 needs configuration changes
DEBUG: Interface 1/1/10 needs cleanup: remove VLANs [50]
DEBUG: Interfaces needing cleanup: 1
DEBUG: Interfaces needing configuration: 1
DEBUG: Interfaces skipped (no changes): 46
```

---

## Best Practices

1. **Always Gather Facts First**: Use `aoscx_facts` before comparison
2. **Two-Phase Updates**: Remove VLANs before adding (cleanup first)
3. **Check for Changes**: Skip configuration if `changes.configure` is empty
4. **Use Categorization**: Combine with `categorize_l2_interfaces()` for cleaner code
5. **Report Changes**: Log what's being changed for auditing
6. **Verify After**: Re-gather facts to confirm changes

---

## See Also

- [Filter Plugins Overview](../FILTER_PLUGINS.md)
- [Utils Module](utils.md)
- [VLAN Filters](vlan_filters.md)
- [Interface Filters](interface_filters.md)
- [L2 Interface Modes](../L2_INTERFACE_MODES.md)
