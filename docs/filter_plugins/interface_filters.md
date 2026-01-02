# Interface Filters Documentation

Part of the NetBox Filters Library for Aruba AOS-CX switches.

## Overview

Interface processing functionality is split into three focused modules that handle categorization, IP address matching, and change detection.

### Module Structure

| Module | Filters | Lines | Description |
|--------|---------|-------|-------------|
| `interface_categorization.py` | 2 | 294 | L2/L3 interface categorization |
| `interface_ip_processing.py` | 1 | 106 | IP address to interface matching |
| `interface_change_detection.py` | 1 | 814 | Idempotent change detection |
| **Total** | **4** | **1,214** | |

**Dependencies**: All modules depend on [utils.py](utils.md) (`_debug`)

---

## Filters

### 1. `categorize_l2_interfaces(interfaces)`

Categorizes Layer 2 interfaces by their VLAN configuration mode and interface type.

#### Purpose

Different L2 interface configurations require different Ansible module parameters. This filter sorts interfaces into 15 categories based on:
- **VLAN Mode**: access, tagged, tagged-all
- **Native VLAN**: with or without untagged VLAN
- **Interface Type**: physical, LAG, MCLAG

#### Parameters

- **interfaces** (list): List of interface objects from NetBox

#### Returns

- **dict**: Dictionary with 15 categorized interface lists:

**Regular Interfaces:**
- `access` - Access mode with untagged VLAN
- `tagged_with_untagged` - Trunk mode with native VLAN
- `tagged_no_untagged` - Trunk mode without native VLAN
- `tagged_all_with_untagged` - Trunk all VLANs with native
- `tagged_all_no_untagged` - Trunk all VLANs without native

**LAG Interfaces:**
- `lag_access` - LAG in access mode
- `lag_tagged_with_untagged` - LAG trunk with native VLAN
- `lag_tagged_no_untagged` - LAG trunk without native VLAN
- `lag_tagged_all_with_untagged` - LAG trunk all with native
- `lag_tagged_all_no_untagged` - LAG trunk all without native

**MCLAG Interfaces:**
- `mclag_access` - MCLAG in access mode
- `mclag_tagged_with_untagged` - MCLAG trunk with native
- `mclag_tagged_no_untagged` - MCLAG trunk without native
- `mclag_tagged_all_with_untagged` - MCLAG trunk all with native
- `mclag_tagged_all_no_untagged` - MCLAG trunk all without native

#### Algorithm

1. Initialize 15 empty category lists
2. For each interface:
   - Skip if None, management, or no mode
   - Skip virtual interfaces
   - Determine interface type (physical/LAG/MCLAG)
   - Check for untagged VLAN
   - Check for tagged VLANs
   - Categorize based on mode + VLAN config + type
3. Return categorized dict

#### Usage Examples

**Basic Categorization:**
```yaml
- name: Categorize L2 interfaces
  set_fact:
    l2_interfaces: "{{ netbox_interfaces | categorize_l2_interfaces }}"

- name: Display categories
  debug:
    msg: |
      Access ports: {{ l2_interfaces.access | length }}
      Trunk ports (with native): {{ l2_interfaces.tagged_with_untagged | length }}
      Trunk ports (no native): {{ l2_interfaces.tagged_no_untagged | length }}
      LAGs: {{ l2_interfaces.lag_access | length + l2_interfaces.lag_tagged_with_untagged | length }}
```

**Configure Access Ports:**
```yaml
- name: Categorize interfaces
  set_fact:
    l2_intfs: "{{ interfaces | categorize_l2_interfaces }}"

- name: Configure access ports
  arubanetworks.aoscx.aoscx_l2_interface:
    interface: "{{ item.name }}"
    vlan_mode: access
    vlan_access: "{{ item.untagged_vlan.vid }}"
  loop: "{{ l2_intfs.access }}"
```

**Configure Trunk Ports with Native VLAN:**
```yaml
- name: Configure trunk ports with native VLAN
  arubanetworks.aoscx.aoscx_l2_interface:
    interface: "{{ item.name }}"
    vlan_mode: trunk
    vlan_trunk_native_id: "{{ item.untagged_vlan.vid }}"
    vlan_trunk_allowed: "{{ item.tagged_vlans | map(attribute='vid') | list }}"
  loop: "{{ l2_intfs.tagged_with_untagged }}"
```

**Configure LAG Trunk Ports:**
```yaml
- name: Configure LAG trunk ports
  arubanetworks.aoscx.aoscx_l2_interface:
    interface: "{{ item.name }}"
    vlan_mode: trunk
    vlan_trunk_allowed: "{{ item.tagged_vlans | map(attribute='vid') | list }}"
  loop: "{{ l2_intfs.lag_tagged_no_untagged }}"
```

**Complete L2 Workflow:**
```yaml
---
- name: Configure all L2 interfaces
  hosts: switches
  tasks:
    - name: Categorize L2 interfaces
      set_fact:
        l2: "{{ netbox_interfaces | categorize_l2_interfaces }}"

    # Access ports
    - name: Configure access ports
      arubanetworks.aoscx.aoscx_l2_interface:
        interface: "{{ item.name }}"
        vlan_mode: access
        vlan_access: "{{ item.untagged_vlan.vid }}"
      loop: "{{ l2.access }}"

    # Trunk ports with native VLAN
    - name: Configure trunk (with native)
      arubanetworks.aoscx.aoscx_l2_interface:
        interface: "{{ item.name }}"
        vlan_mode: trunk
        vlan_trunk_native_id: "{{ item.untagged_vlan.vid }}"
        vlan_trunk_allowed: "{{ item.tagged_vlans | map(attribute='vid') | list }}"
      loop: "{{ l2.tagged_with_untagged }}"

    # Trunk ports without native VLAN
    - name: Configure trunk (no native)
      arubanetworks.aoscx.aoscx_l2_interface:
        interface: "{{ item.name }}"
        vlan_mode: trunk
        vlan_trunk_allowed: "{{ item.tagged_vlans | map(attribute='vid') | list }}"
      loop: "{{ l2.tagged_no_untagged }}"

    # LAG access ports
    - name: Configure LAG access
      arubanetworks.aoscx.aoscx_l2_interface:
        interface: "{{ item.name }}"
        vlan_mode: access
        vlan_access: "{{ item.untagged_vlan.vid }}"
      loop: "{{ l2.lag_access }}"

    # MCLAG trunk ports
    - name: Configure MCLAG trunk
      arubanetworks.aoscx.aoscx_l2_interface:
        interface: "{{ item.name }}"
        vlan_mode: trunk
        vlan_trunk_native_id: "{{ item.untagged_vlan.vid | default(omit) }}"
        vlan_trunk_allowed: "{{ item.tagged_vlans | map(attribute='vid') | list }}"
      loop: "{{ l2.mclag_tagged_with_untagged + l2.mclag_tagged_no_untagged }}"
```

---

### 2. `categorize_l3_interfaces(interfaces)`

Categorizes Layer 3 interfaces by interface type and VRF membership.

#### Purpose

L3 interfaces need different configuration based on type and VRF. This filter categorizes interfaces for targeted configuration, distinguishing between default/built-in VRFs and custom VRFs.

#### Parameters

- **interfaces** (list): List of interface objects with IP addresses from NetBox

#### Returns

- **dict**: Dictionary with 7 categorized interface lists:
  - `physical_default_vrf` - Physical interfaces in default/Global/mgmt VRF
  - `physical_custom_vrf` - Physical interfaces in custom VRFs
  - `vlan_default_vrf` - VLAN interfaces (SVIs) in default VRF
  - `vlan_custom_vrf` - VLAN interfaces in custom VRFs
  - `lag_default_vrf` - LAG interfaces in default VRF
  - `lag_custom_vrf` - LAG interfaces in custom VRFs
  - `loopback` - Loopback interfaces

#### Built-in VRFs

The following are considered built-in (default) VRFs:
- `default`, `Default`
- `Global`, `global`
- `mgmt`, `MGMT`
- `None` (no VRF assigned)

#### Algorithm

1. Initialize 7 empty category lists
2. For each interface:
   - Skip if None or management interface
   - Determine interface type (physical/LAG/virtual)
   - Get VRF name from interface object
   - Check if VRF is built-in
   - Categorize based on type + VRF category
3. Return categorized dict

#### VRF Determination

**IMPORTANT**: Only checks the **interface VRF**, not the IP address VRF. This is correct because:
- Interface VRF determines routing table
- IP address VRF is for IPAM organization only

#### Usage Examples

**Basic Categorization:**
```yaml
- name: Categorize L3 interfaces
  set_fact:
    l3_interfaces: "{{ netbox_interfaces | categorize_l3_interfaces }}"

- name: Display L3 summary
  debug:
    msg: |
      Physical (default VRF): {{ l3_interfaces.physical_default_vrf | length }}
      Physical (custom VRF): {{ l3_interfaces.physical_custom_vrf | length }}
      VLAN SVIs (default VRF): {{ l3_interfaces.vlan_default_vrf | length }}
      VLAN SVIs (custom VRF): {{ l3_interfaces.vlan_custom_vrf | length }}
      Loopbacks: {{ l3_interfaces.loopback | length }}
```

**Configure Physical L3 Interfaces in Default VRF:**
```yaml
- name: Categorize interfaces
  set_fact:
    l3: "{{ interface_ips | categorize_l3_interfaces }}"

- name: Configure physical L3 (default VRF)
  arubanetworks.aoscx.aoscx_l3_interface:
    interface: "{{ item.interface_name }}"
    ipv4: "{{ item.address }}"
    description: "{{ item.description | default(omit) }}"
  loop: "{{ l3.physical_default_vrf }}"
```

**Configure Interfaces in Custom VRFs:**
```yaml
- name: Configure physical L3 (custom VRF)
  arubanetworks.aoscx.aoscx_l3_interface:
    interface: "{{ item.interface_name }}"
    vrf: "{{ item.interface.vrf.name }}"
    ipv4: "{{ item.address }}"
  loop: "{{ l3.physical_custom_vrf }}"
```

**Configure VLAN SVIs:**
```yaml
- name: Configure VLAN SVIs in default VRF
  arubanetworks.aoscx.aoscx_l3_interface:
    interface: "{{ item.interface_name }}"
    ipv4: "{{ item.address }}"
  loop: "{{ l3.vlan_default_vrf }}"

- name: Configure VLAN SVIs in custom VRFs
  arubanetworks.aoscx.aoscx_l3_interface:
    interface: "{{ item.interface_name }}"
    vrf: "{{ item.interface.vrf.name }}"
    ipv4: "{{ item.address }}"
  loop: "{{ l3.vlan_custom_vrf }}"
```

**Configure Loopbacks:**
```yaml
- name: Configure loopback interfaces
  arubanetworks.aoscx.aoscx_l3_interface:
    interface: "{{ item.interface_name }}"
    ipv4: "{{ item.address }}"
  loop: "{{ l3.loopback }}"
```

**Complete L3 Workflow:**
```yaml
---
- name: Configure L3 interfaces
  hosts: switches
  tasks:
    # Get interface/IP mappings
    - name: Match IPs to interfaces
      set_fact:
        interface_ips: "{{ netbox_interfaces | get_interface_ip_addresses(ip_addresses) }}"

    # Categorize
    - name: Categorize L3 interfaces
      set_fact:
        l3: "{{ interface_ips | categorize_l3_interfaces }}"

    # Configure by category
    - name: Configure physical L3 (default VRF)
      arubanetworks.aoscx.aoscx_l3_interface:
        interface: "{{ item.interface_name }}"
        ipv4: "{{ item.address }}"
        description: "{{ item.description }}"
      loop: "{{ l3.physical_default_vrf }}"

    - name: Configure physical L3 (custom VRF)
      arubanetworks.aoscx.aoscx_l3_interface:
        interface: "{{ item.interface_name }}"
        vrf: "{{ item.interface.vrf.name }}"
        ipv4: "{{ item.address }}"
        description: "{{ item.description }}"
      loop: "{{ l3.physical_custom_vrf }}"

    - name: Configure VLAN SVIs (default VRF)
      arubanetworks.aoscx.aoscx_l3_interface:
        interface: "{{ item.interface_name }}"
        ipv4: "{{ item.address }}"
      loop: "{{ l3.vlan_default_vrf }}"

    - name: Configure VLAN SVIs (custom VRF)
      arubanetworks.aoscx.aoscx_l3_interface:
        interface: "{{ item.interface_name }}"
        vrf: "{{ item.interface.vrf.name }}"
        ipv4: "{{ item.address }}"
      loop: "{{ l3.vlan_custom_vrf }}"

    - name: Configure loopbacks
      arubanetworks.aoscx.aoscx_l3_interface:
        interface: "{{ item.interface_name }}"
        ipv4: "{{ item.address }}"
      loop: "{{ l3.loopback }}"
```

---

### 3. `get_interface_ip_addresses(interfaces, ip_addresses)`

Matches IP addresses to their assigned interfaces, creating a combined data structure.

#### Purpose

NetBox stores interfaces and IP addresses separately. This filter combines them for easier processing.

#### Parameters

- **interfaces** (list): List of interface objects from NetBox
- **ip_addresses** (list): List of IP address objects from NetBox

#### Returns

- **list**: List of dicts with combined interface/IP information:
  ```python
  {
      "interface": <interface_object>,
      "interface_name": "1/1/10",
      "interface_type": "1000base-t",
      "address": "192.168.1.1/24",
      "vrf": "customer-a",
      "description": "Server uplink",
      "enabled": true
  }
  ```

#### Algorithm

1. Build dict of interfaces by ID for quick lookup
2. For each IP address:
   - Get assigned object (interface) ID
   - Lookup interface by ID
   - Skip management interfaces
   - Extract VRF from IP object
   - Create combined dict
3. Return list of combined objects

#### Usage Examples

**Basic Matching:**
```yaml
- name: Match IPs to interfaces
  set_fact:
    interface_ips: "{{ interfaces | get_interface_ip_addresses(ip_addresses) }}"

- name: Display matches
  debug:
    msg: "{{ item.interface_name }}: {{ item.address }} (VRF: {{ item.vrf }})"
  loop: "{{ interface_ips }}"
```

**Configure L3 Interfaces:**
```yaml
- name: Get interface/IP mappings
  set_fact:
    intf_ips: "{{ netbox_interfaces | get_interface_ip_addresses(ip_addresses) }}"

- name: Configure L3 interfaces
  arubanetworks.aoscx.aoscx_l3_interface:
    interface: "{{ item.interface_name }}"
    ipv4: "{{ item.address }}"
    vrf: "{{ item.vrf if item.vrf != 'default' else omit }}"
    description: "{{ item.description }}"
  loop: "{{ intf_ips }}"
```

**Filter by VRF:**
```yaml
- name: Get all interface/IP mappings
  set_fact:
    all_intf_ips: "{{ interfaces | get_interface_ip_addresses(ip_addresses) }}"

- name: Filter to specific VRF
  set_fact:
    customer_intf_ips: "{{
      all_intf_ips |
      selectattr('vrf', 'equalto', 'customer-a') |
      list
    }}"
```

**Use with Categorization:**
```yaml
- name: Get interface/IP mappings
  set_fact:
    intf_ips: "{{ interfaces | get_interface_ip_addresses(ip_addresses) }}"

- name: Categorize L3 interfaces
  set_fact:
    l3_categories: "{{ intf_ips | categorize_l3_interfaces }}"

- name: Configure each category appropriately
  # ... (see categorize_l3_interfaces examples)
```

---

### 4. `get_interfaces_needing_config_changes(interfaces, device_facts)`

Compares NetBox interfaces with device facts to identify which interfaces need configuration changes.

#### Purpose

Enables idempotent interface configuration by detecting:
- Enabled/disabled state changes
- Description changes
- MTU changes
- LAG membership changes
- VLAN configuration changes

#### Parameters

- **interfaces** (list): List of interface objects from NetBox
- **device_facts** (dict): Device facts from `ansible_facts`

#### Returns

- **dict**: Dictionary with categorized interfaces:
  - `physical` - Physical interfaces needing changes
  - `lag` - LAG interfaces needing changes
  - `mclag` - MCLAG interfaces needing changes
  - `l2` - L2 interfaces needing VLAN changes
  - `l3` - L3 interfaces needing IP changes
  - `lag_members` - Physical interfaces needing LAG assignment
  - `no_changes` - Interfaces that don't need changes

#### Checks Performed

**Basic Interface Properties:**
- Enabled/disabled state (`admin` state)
- Description (with special handling for `AP_Aruba`)
- MTU (if specified in NetBox)

**LAG Membership:**
- Current LAG assignment vs. NetBox

**L2 Configuration (for non-SVI interfaces):**
- VLAN mode (access/trunk)
- Access VLAN
- Native VLAN
- Trunk VLANs

**Special Cases:**
- VLAN 1 is never deleted
- Management interfaces are skipped
- VLAN/SVI interfaces skip L2 checks
- Interfaces not on device are marked as needing creation

#### AP_Aruba Description Handling

For interfaces with description `AP_Aruba`, the expected device description is:
```
<interface_name> AP_Aruba
```

Example: Interface `1/1/10` with description `AP_Aruba` expects device description `1/1/10 AP_Aruba`.

#### Algorithm

1. Validate inputs
2. Extract device interface facts
3. Build LAG membership map (reverse lookup)
4. For each NetBox interface:
   - Skip management interfaces
   - Find matching device interface
   - Compare properties
   - Categorize based on changes needed
5. Return categorized dict

#### Usage Examples

**Basic Change Detection:**
```yaml
- name: Gather facts
  arubanetworks.aoscx.aoscx_facts:
    gather_subset:
      - interfaces

- name: Detect interface changes
  set_fact:
    interface_changes: "{{
      netbox_interfaces |
      get_interfaces_needing_config_changes(ansible_facts)
    }}"

- name: Display summary
  debug:
    msg: |
      Physical interfaces needing changes: {{ interface_changes.physical | length }}
      LAG interfaces needing changes: {{ interface_changes.lag | length }}
      L2 interfaces needing changes: {{ interface_changes.l2 | length }}
      Interfaces OK: {{ interface_changes.no_changes | length }}
```

**Idempotent Configuration:**
```yaml
- name: Detect changes
  set_fact:
    changes: "{{ interfaces | get_interfaces_needing_config_changes(ansible_facts) }}"

- name: Configure only interfaces that need changes
  arubanetworks.aoscx.aoscx_interface:
    name: "{{ item.name }}"
    enabled: "{{ item.enabled | default(true) }}"
    description: "{{ item.description | default(omit) }}"
    mtu: "{{ item.mtu | default(omit) }}"
  loop: "{{ changes.physical }}"
```

**Selective Configuration:**
```yaml
- name: Get changes
  set_fact:
    changes: "{{ interfaces | get_interfaces_needing_config_changes(ansible_facts) }}"

- name: Configure L2 changes only
  arubanetworks.aoscx.aoscx_l2_interface:
    interface: "{{ item.name }}"
    vlan_mode: "{{ item.mode.value }}"
    # ... VLAN configuration ...
  loop: "{{ changes.l2 }}"
  when: changes.l2 | length > 0

- name: Configure LAG membership changes
  arubanetworks.aoscx.aoscx_lag_interface:
    lag: "{{ item.lag.name }}"
    interfaces: ["{{ item.name }}"]
  loop: "{{ changes.lag_members }}"
  when: changes.lag_members | length > 0
```

**Complete Idempotent Workflow:**
```yaml
---
- name: Idempotent interface configuration
  hosts: switches
  vars:
    enable_idempotent: true
  tasks:
    # Gather current state
    - name: Gather facts
      arubanetworks.aoscx.aoscx_facts:
        gather_subset:
          - interfaces
          - vlans

    # Detect changes
    - name: Identify interfaces needing changes
      set_fact:
        changes: "{{
          netbox_interfaces |
          get_interfaces_needing_config_changes(ansible_facts)
        }}"

    # Report
    - name: Display change summary
      debug:
        msg: |
          Total interfaces: {{ netbox_interfaces | length }}
          Interfaces needing changes: {{
            (changes.physical | length) +
            (changes.lag | length) +
            (changes.l2 | length) +
            (changes.l3 | length)
          }}
          Interfaces already correct: {{ changes.no_changes | length }}

    # Configure physical interfaces
    - name: Update physical interfaces
      arubanetworks.aoscx.aoscx_interface:
        name: "{{ item.name }}"
        enabled: "{{ item.enabled | default(true) }}"
        description: "{{ item.description | default(omit) }}"
        mtu: "{{ item.mtu | default(omit) }}"
      loop: "{{ changes.physical }}"
      when: enable_idempotent

    # Configure LAG interfaces
    - name: Update LAG interfaces
      arubanetworks.aoscx.aoscx_lag_interface:
        name: "{{ item.name }}"
        enabled: "{{ item.enabled | default(true) }}"
      loop: "{{ changes.lag }}"
      when: enable_idempotent

    # Configure L2 interfaces
    - name: Update L2 interfaces
      arubanetworks.aoscx.aoscx_l2_interface:
        interface: "{{ item.name }}"
        # ... L2 configuration ...
      loop: "{{ changes.l2 }}"
      when: enable_idempotent
```

---

## Complete Multi-Layer Workflow

```yaml
---
- name: Complete interface configuration with categorization
  hosts: switches
  tasks:
    # === DATA GATHERING ===
    - name: Get interface/IP mappings
      set_fact:
        interface_ips: "{{ netbox_interfaces | get_interface_ip_addresses(ip_addresses) }}"

    # === L2 CONFIGURATION ===
    - name: Categorize L2 interfaces
      set_fact:
        l2: "{{ netbox_interfaces | categorize_l2_interfaces }}"

    - name: Configure access ports
      arubanetworks.aoscx.aoscx_l2_interface:
        interface: "{{ item.name }}"
        vlan_mode: access
        vlan_access: "{{ item.untagged_vlan.vid }}"
      loop: "{{ l2.access }}"

    - name: Configure trunk ports
      arubanetworks.aoscx.aoscx_l2_interface:
        interface: "{{ item.name }}"
        vlan_mode: trunk
        vlan_trunk_native_id: "{{ item.untagged_vlan.vid | default(omit) }}"
        vlan_trunk_allowed: "{{ item.tagged_vlans | map(attribute='vid') | list }}"
      loop: "{{ l2.tagged_with_untagged + l2.tagged_no_untagged }}"

    # === L3 CONFIGURATION ===
    - name: Categorize L3 interfaces
      set_fact:
        l3: "{{ interface_ips | categorize_l3_interfaces }}"

    - name: Configure physical L3 (default VRF)
      arubanetworks.aoscx.aoscx_l3_interface:
        interface: "{{ item.interface_name }}"
        ipv4: "{{ item.address }}"
      loop: "{{ l3.physical_default_vrf }}"

    - name: Configure physical L3 (custom VRF)
      arubanetworks.aoscx.aoscx_l3_interface:
        interface: "{{ item.interface_name }}"
        vrf: "{{ item.interface.vrf.name }}"
        ipv4: "{{ item.address }}"
      loop: "{{ l3.physical_custom_vrf }}"

    - name: Configure VLAN SVIs
      arubanetworks.aoscx.aoscx_l3_interface:
        interface: "{{ item.interface_name }}"
        vrf: "{{ item.interface.vrf.name if item.interface.vrf else omit }}"
        ipv4: "{{ item.address }}"
      loop: "{{ l3.vlan_default_vrf + l3.vlan_custom_vrf }}"

    - name: Configure loopbacks
      arubanetworks.aoscx.aoscx_l3_interface:
        interface: "{{ item.interface_name }}"
        ipv4: "{{ item.address }}"
      loop: "{{ l3.loopback }}"
```

---

## See Also

- [Filter Plugins Overview](../FILTER_PLUGINS.md)
- [Utils Module](utils.md)
- [VLAN Filters](vlan_filters.md)
- [VRF Filters](vrf_filters.md)
- [Comparison Module](comparison.md)
- [L2 Interface Modes](../L2_INTERFACE_MODES.md)
