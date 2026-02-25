# VRF Filters Module

Part of the NetBox Filters Library for Aruba AOS-CX switches.

## What This Module Does (Plain English)

A **VRF** (Virtual Routing and Forwarding) is like having separate, isolated routing tables on a single switch. Think of it as virtual routers running inside one physical device. Each tenant or department can have its own VRF so their traffic stays separate.

This module helps you figure out:
- **Which VRFs are actually being used** on a device (not every VRF in NetBox is relevant to every switch)
- **Which VRFs are safe to configure** (built-in system VRFs like `mgmt` should never be touched by automation)
- **Which route targets belong to each VRF** (for L3VPN/MPLS/EVPN configurations)

Every Aruba AOS-CX switch has some built-in VRFs (`mgmt`, `default`, `Global`) that the switch creates automatically. This module's filters know about these and automatically skip them so your automation doesn't accidentally try to create or delete system VRFs.

---

## Overview

The `vrf_filters.py` module provides VRF (Virtual Routing and Forwarding) extraction and filtering functionality. It handles VRF identification, filtering by usage and tenant, route target extraction, and automatic exclusion of built-in system VRFs.

**File Location**: [filter_plugins/netbox_filters_lib/vrf_filters.py](../../filter_plugins/netbox_filters_lib/vrf_filters.py)

**Dependencies**: [utils.py](utils.md) (`_debug`)

**Filter Count**: 6 filters

## Built-in VRF Handling

Several VRFs are built into AOS-CX and should not be configured via automation:
- `mgmt` / `MGMT` - Management VRF
- `Global` / `global` - Global/default routing table
- `default` / `Default` - Default VRF

All filters in this module automatically exclude these VRFs unless explicitly requested.

---

## Filters

### 1. `extract_interface_vrfs(interfaces)`

Extracts unique VRF names from a list of interfaces.

#### Purpose

Scans interfaces to identify all VRFs in use. This is the foundation for other VRF filters.

#### Parameters

- **interfaces** (list): List of interface objects from NetBox

#### Returns

- **set**: Set of unique VRF names (strings)

#### Algorithm

1. Initialize empty set for VRF names
2. For each interface:
   - Extract VRF object
   - Get VRF name
   - Add to set if not None
3. Return set of VRF names

#### Implementation Details

```python
def extract_interface_vrfs(interfaces):
    """Extract unique VRF names from interfaces"""
    vrf_names = set()

    for interface in interfaces:
        vrf = interface.get("vrf")
        if vrf and vrf is not None:
            vrf_name = vrf.get("name")
            if vrf_name:
                _debug(f"Found VRF '{vrf_name}' on interface {interface.get('name')}")
                vrf_names.add(vrf_name)

    _debug(f"All VRFs found in interfaces: {vrf_names}")
    return vrf_names
```

#### Usage Examples

**Basic Extraction:**
```yaml
- name: Get VRF names in use
  set_fact:
    vrf_names: "{{ netbox_interfaces | extract_interface_vrfs }}"
  # Returns: {'customer-a', 'customer-b', 'mgmt'}
```

**Filter Out Built-in VRFs:**
```yaml
- name: Get only custom VRFs
  set_fact:
    vrf_names: "{{ netbox_interfaces | extract_interface_vrfs }}"
    custom_vrfs: "{{ vrf_names | difference(['mgmt', 'Global', 'default']) }}"
  # Returns: {'customer-a', 'customer-b'}
```

**Count VRFs:**
```yaml
- name: Extract VRFs
  set_fact:
    all_vrfs: "{{ netbox_interfaces | extract_interface_vrfs }}"

- name: Display VRF count
  debug:
    msg: "Found {{ all_vrfs | length }} unique VRFs: {{ all_vrfs | list | sort }}"
```

---

### 2. `filter_vrfs_in_use(vrfs, interfaces, tenant=None)`

Filters VRF objects to only those actually in use on interfaces, with optional tenant filtering.

#### Purpose

NetBox may have many VRFs defined, but only a subset are used on a specific device. This filter identifies the relevant VRFs and automatically excludes built-in VRFs.

#### Parameters

- **vrfs** (list): List of all VRF objects from NetBox
- **interfaces** (list): List of interface objects from NetBox
- **tenant** (str, optional): Tenant slug to filter by (includes VRFs with no tenant)

#### Returns

- **list**: Filtered list of VRF objects that are in use

#### Filtering Logic

1. Extract VRF names in use (calls `extract_interface_vrfs()`)
2. For each VRF in NetBox:
   - Skip if not in use on any interface
   - Skip if name is `mgmt` or `Global`
   - If tenant specified:
     - Include if VRF has no tenant
     - Include if VRF tenant matches specified tenant
   - If no tenant specified:
     - Include all in-use VRFs
3. Return filtered list

#### Built-in VRFs Excluded

- `mgmt` - Management VRF (always excluded)
- `Global` - Global routing table (always excluded)

#### Tenant Filtering Behavior

| VRF Tenant | Filter Tenant | Included? |
|------------|---------------|-----------|
| None       | Any value     | Yes       |
| tenant-a   | tenant-a      | Yes       |
| tenant-a   | tenant-b      | No        |
| tenant-a   | None          | Yes       |

VRFs with no tenant are always included (considered shared infrastructure).

#### Usage Examples

**Basic Filtering:**
```yaml
- name: Get VRFs in use
  set_fact:
    active_vrfs: "{{ all_vrfs | filter_vrfs_in_use(netbox_interfaces) }}"
```

**With Tenant Filter:**
```yaml
- name: Get VRFs for specific tenant
  set_fact:
    tenant_vrfs: "{{
      all_vrfs |
      filter_vrfs_in_use(netbox_interfaces, 'customer-a')
    }}"
  # Only includes VRFs for 'customer-a' tenant or shared VRFs
```

**Create VRFs:**
```yaml
- name: Filter to VRFs in use
  set_fact:
    vrfs_to_create: "{{ device_vrfs | filter_vrfs_in_use(interfaces) }}"

- name: Create VRFs on switch
  arubanetworks.aoscx.aoscx_vrf:
    name: "{{ item.name }}"
    rd: "{{ item.rd | default(omit) }}"
    state: present
  loop: "{{ vrfs_to_create }}"
```

**Multi-Tenant Example:**
```yaml
---
- name: Configure VRFs per tenant
  hosts: switches
  tasks:
    - name: Get VRFs for tenant A
      set_fact:
        tenant_a_vrfs: "{{
          all_vrfs |
          filter_vrfs_in_use(netbox_interfaces, 'tenant-a')
        }}"

    - name: Get VRFs for tenant B
      set_fact:
        tenant_b_vrfs: "{{
          all_vrfs |
          filter_vrfs_in_use(netbox_interfaces, 'tenant-b')
        }}"

    - name: Create tenant A VRFs
      arubanetworks.aoscx.aoscx_vrf:
        name: "{{ item.name }}"
        state: present
      loop: "{{ tenant_a_vrfs }}"
      tags: tenant-a

    - name: Create tenant B VRFs
      arubanetworks.aoscx.aoscx_vrf:
        name: "{{ item.name }}"
        state: present
      loop: "{{ tenant_b_vrfs }}"
      tags: tenant-b
```

---

### 3. `get_vrfs_in_use(interfaces, ip_addresses=None)`

Extracts VRFs in use from both interfaces and IP addresses with full metadata.

#### Purpose

Provides comprehensive VRF information by checking both:
- Interface VRF assignments
- IP address VRF assignments

Automatically excludes built-in/non-configurable VRFs.

#### Parameters

- **interfaces** (list): List of interface objects from NetBox
- **ip_addresses** (list, optional): List of IP address objects from NetBox

#### Returns

- **dict**: Dictionary with:
  - `vrf_names` (list): Sorted list of configurable VRF names
  - `vrfs` (dict): Dict of VRF objects keyed by name

#### Built-in VRFs Filtered Out

- `mgmt`, `MGMT`
- `Global`, `global`
- `default`, `Default`

#### Algorithm

1. Initialize empty dicts/sets
2. Process interfaces:
   - Skip management interfaces
   - Extract VRF from interface
   - Add to dict if not built-in
3. Process IP addresses (if provided):
   - Extract VRF from IP object
   - Add to dict if not built-in
4. Return sorted VRF names and VRF objects

#### Usage Examples

**From Interfaces Only:**
```yaml
- name: Get VRFs in use
  set_fact:
    vrfs_in_use: "{{ netbox_interfaces | get_vrfs_in_use }}"

- name: Display VRF summary
  debug:
    msg: |
      VRFs in use: {{ vrfs_in_use.vrf_names }}
      VRF count: {{ vrfs_in_use.vrf_names | length }}
```

**Including IP Addresses:**
```yaml
- name: Get VRFs from interfaces and IPs
  set_fact:
    vrfs_in_use: "{{ netbox_interfaces | get_vrfs_in_use(ip_addresses) }}"

- name: Create VRFs
  arubanetworks.aoscx.aoscx_vrf:
    name: "{{ item }}"
    state: present
  loop: "{{ vrfs_in_use.vrf_names }}"
```

**Access VRF Objects:**
```yaml
- name: Get VRFs in use
  set_fact:
    vrfs_data: "{{ interfaces | get_vrfs_in_use(ip_addresses) }}"

- name: Configure VRFs with metadata
  arubanetworks.aoscx.aoscx_vrf:
    name: "{{ vrfs_data.vrfs[item].name }}"
    rd: "{{ vrfs_data.vrfs[item].rd | default(omit) }}"
    description: "{{ vrfs_data.vrfs[item].description | default(omit) }}"
  loop: "{{ vrfs_data.vrf_names }}"
```

**Complete Workflow:**
```yaml
---
- name: VRF and L3 interface configuration
  hosts: switches
  tasks:
    # Get VRFs in use
    - name: Extract VRFs
      set_fact:
        vrfs_in_use: "{{ netbox_interfaces | get_vrfs_in_use(ip_addresses) }}"

    # Display summary
    - name: VRF summary
      debug:
        msg: |
          Configurable VRFs: {{ vrfs_in_use.vrf_names }}
          (Built-in VRFs mgmt/Global/default are automatically excluded)

    # Create VRFs
    - name: Create VRFs
      arubanetworks.aoscx.aoscx_vrf:
        name: "{{ item }}"
        state: present
      loop: "{{ vrfs_in_use.vrf_names }}"

    # Configure L3 interfaces in VRFs
    - name: Categorize L3 interfaces
      set_fact:
        l3_interfaces: "{{ netbox_interfaces | categorize_l3_interfaces }}"

    - name: Configure L3 interfaces in custom VRFs
      arubanetworks.aoscx.aoscx_l3_interface:
        interface: "{{ item.name }}"
        vrf: "{{ item.vrf.name }}"
        ipv4: "{{ item.ip_addresses[0].address }}"
      loop: "{{ l3_interfaces.physical_custom_vrf }}"
      when: item.ip_addresses | length > 0
```

---

### 4. `filter_configurable_vrfs(vrfs)`

Filters out built-in/non-configurable VRFs from a list.

#### Purpose

Ensures automation doesn't attempt to configure system VRFs. Useful when you have a list of VRF names or objects and need to remove built-in VRFs.

#### Parameters

- **vrfs** (list): List of VRF objects or VRF names (strings)

#### Returns

- **list**: List of configurable VRFs (same type as input)

#### Built-in VRFs Removed

- `mgmt`, `MGMT`
- `Global`, `global`
- `default`, `Default`

#### Input Type Handling

Accepts both:
- **VRF objects** (dicts with 'name' key)
- **VRF names** (strings)

Returns the same type as input.

#### Implementation Details

```python
def filter_configurable_vrfs(vrfs):
    """Filter out VRFs that should not be configured (built-in VRFs)"""
    if not vrfs:
        return []

    # Built-in, non-configurable VRFs
    builtin_vrfs = {"mgmt", "MGMT", "Global", "global", "default", "Default"}
    configurable = []

    for vrf in vrfs:
        if isinstance(vrf, dict):
            vrf_name = vrf.get("name")
        elif isinstance(vrf, str):
            vrf_name = vrf
        else:
            continue

        if vrf_name and vrf_name not in builtin_vrfs:
            configurable.append(vrf)
            _debug(f"VRF {vrf_name} is configurable")
        else:
            _debug(f"VRF {vrf_name} is built-in/non-configurable - skipping")

    return configurable
```

#### Usage Examples

**Filter VRF Objects:**
```yaml
- name: Remove built-in VRFs from list
  set_fact:
    configurable_vrfs: "{{ all_vrfs | filter_configurable_vrfs }}"
```

**Filter VRF Names:**
```yaml
- name: Get VRF names
  set_fact:
    all_vrf_names: "{{ device.vrfs | map(attribute='name') | list }}"

- name: Filter to configurable names
  set_fact:
    vrf_names_to_config: "{{ all_vrf_names | filter_configurable_vrfs }}"
  # Input: ['customer-a', 'mgmt', 'customer-b', 'Global']
  # Output: ['customer-a', 'customer-b']
```

**Safety Filter:**
```yaml
- name: Ensure we don't touch built-in VRFs
  set_fact:
    safe_vrfs: "{{ user_provided_vrfs | filter_configurable_vrfs }}"

- name: Configure only safe VRFs
  arubanetworks.aoscx.aoscx_vrf:
    name: "{{ item.name }}"
    state: present
  loop: "{{ safe_vrfs }}"
```

---

### 5. `get_all_rt_names(vrf_details)`

Extracts all unique route target names from VRF export and import target lists.

#### How It Works (Plain English)

**Route targets (RTs)** tell the switch which VRF routes to share and with whom. Each VRF can export routes (advertise them) and import routes (accept them from other VRFs). This filter collects all the unique RT names from all your VRFs into a single flat list.

This is useful when you need to create the route target objects on the switch *before* assigning them to VRFs.

#### Parameters

- **vrf_details** (dict): Dict of VRF name to VRF object, as returned by a NetBox `nb_lookup` for VRFs. Each VRF object should contain `export_targets` and `import_targets` lists, where each target has a `name` field.

#### Returns

- **list**: Sorted list of unique route target name strings (e.g., `["65000:100", "65000:200"]`)

#### Usage Examples

**Get All Route Targets:**
```yaml
- name: Look up VRF details from NetBox
  set_fact:
    vrf_details: "{{ query('netbox.netbox.nb_lookup', 'vrfs',
                      api_filter='name__in=' + vrfs_in_use.vrf_names | join(',')) }}"

- name: Extract all route target names
  set_fact:
    all_rt_names: "{{ vrf_details | get_all_rt_names }}"
  # Result: ["65000:100", "65000:200", "65000:300"]

- name: Create route targets on switch
  arubanetworks.aoscx.aoscx_config:
    lines:
      - "route-target {{ item }}"
  loop: "{{ all_rt_names }}"
```

---

### 6. `build_vrf_rt_config(vrf_details)`

Builds an address-family-aware route target configuration grouped per VRF.

#### How It Works (Plain English)

In modern networks with both IPv4 and IPv6, route targets can be specific to an address family. For example, a VRF might export IPv4 routes with one RT and IPv6 routes with a different RT.

This filter reads the `address_family` custom field from each route target object in NetBox and organizes them into a nested structure: VRF → address family (ipv4/ipv6) → direction (export/import) → list of RT names.

If a route target doesn't have an `address_family` custom field, it defaults to `ipv4`.

#### Parameters

- **vrf_details** (dict): Dict of VRF name to VRF object from NetBox `nb_lookup`. Each VRF should have `export_targets` and `import_targets` lists containing full RT objects (including `custom_fields` with optional `address_family` field).

#### Returns

- **dict**: Nested dict keyed by VRF name:

```yaml
customer-a:
  ipv4:
    export: ["65000:100"]
    import: ["65000:100"]
  ipv6:
    export: ["65000:600"]
    import: ["65000:600"]
customer-b:
  ipv4:
    export: ["65000:200"]
    import: ["65000:200"]
  ipv6:
    export: []
    import: []
```

#### Usage Examples

**Build and Apply RT Config:**
```yaml
- name: Look up VRF details from NetBox
  set_fact:
    vrf_details: "{{ query('netbox.netbox.nb_lookup', 'vrfs',
                      api_filter='name__in=' + vrfs_in_use.vrf_names | join(',')) }}"

- name: Build address-family RT config
  set_fact:
    vrf_rt_config: "{{ vrf_details | build_vrf_rt_config }}"

- name: Configure VRF route targets
  arubanetworks.aoscx.aoscx_config:
    lines:
      - "vrf {{ item.key }}"
      - "  address-family ipv4 unicast"
      - "    route-target export {{ rt }}"
  loop: "{{ vrf_rt_config | dict2items }}"
  vars:
    rt: "{{ item.value.ipv4.export | first }}"
  when: item.value.ipv4.export | length > 0
```

**Complete RT Workflow:**
```yaml
---
- name: Configure VRF route targets from NetBox
  hosts: pe_routers
  tasks:
    # Get VRFs in use
    - name: Extract VRFs
      set_fact:
        vrfs_in_use: "{{ netbox_interfaces | get_vrfs_in_use(ip_addresses) }}"

    # Look up full VRF details (including RT objects)
    - name: Get VRF details from NetBox
      set_fact:
        vrf_lookup: "{{ query('netbox.netbox.nb_lookup', 'vrfs',
                         api_filter='name__in=' + vrfs_in_use.vrf_names | join(',')) }}"

    # Build RT config
    - name: Build RT config
      set_fact:
        vrf_rt_config: "{{ vrf_lookup | build_vrf_rt_config }}"

    # First create all route targets
    - name: Get unique RT names
      set_fact:
        all_rts: "{{ vrf_lookup | get_all_rt_names }}"

    # Then apply per-VRF
    - name: Configure IPv4 export RTs
      arubanetworks.aoscx.aoscx_config:
        lines: >-
          vrf {{ item.0.key }}
            address-family ipv4 unicast
              route-target export {{ item.1 }}
      with_subelements:
        - "{{ vrf_rt_config | dict2items }}"
        - value.ipv4.export
```

---

## Complete Workflow Examples

### Multi-Tenant VRF Management

```yaml
---
- name: Multi-tenant VRF configuration
  hosts: core_switches
  tasks:
    # Get all VRFs in use
    - name: Extract VRFs from interfaces and IPs
      set_fact:
        vrfs_in_use: "{{ netbox_interfaces | get_vrfs_in_use(ip_addresses) }}"

    # Safety check - remove built-in VRFs
    - name: Filter to configurable VRFs
      set_fact:
        configurable_vrfs: "{{ vrfs_in_use.vrf_names | filter_configurable_vrfs }}"

    # Display summary
    - name: VRF configuration summary
      debug:
        msg: |
          Total VRFs found: {{ vrfs_in_use.vrf_names | length }}
          Configurable VRFs: {{ configurable_vrfs | length }}
          VRFs: {{ configurable_vrfs }}

    # Create VRFs
    - name: Create customer VRFs
      arubanetworks.aoscx.aoscx_vrf:
        name: "{{ item }}"
        state: present
      loop: "{{ configurable_vrfs }}"
```

### Tenant-Specific VRF Deployment

```yaml
---
- name: Deploy VRFs for specific tenant
  hosts: pe_routers
  vars:
    target_tenant: "customer-a"
  tasks:
    # Get VRFs for specific tenant
    - name: Filter VRFs for tenant
      set_fact:
        tenant_vrfs: "{{
          all_vrfs |
          filter_vrfs_in_use(netbox_interfaces, target_tenant)
        }}"

    # Ensure they're configurable
    - name: Double-check configurability
      set_fact:
        safe_tenant_vrfs: "{{ tenant_vrfs | filter_configurable_vrfs }}"

    # Report
    - name: Tenant VRF report
      debug:
        msg: |
          Tenant: {{ target_tenant }}
          VRFs to configure: {{ safe_tenant_vrfs | map(attribute='name') | list }}

    # Create VRFs with full metadata
    - name: Create tenant VRFs
      arubanetworks.aoscx.aoscx_vrf:
        name: "{{ item.name }}"
        rd: "{{ item.rd | default(omit) }}"
        description: "{{ item.description | default('Tenant ' + target_tenant) }}"
        state: present
      loop: "{{ safe_tenant_vrfs }}"

    # Configure BGP for VRFs
    - name: Configure BGP for VRFs
      arubanetworks.aoscx.aoscx_bgp:
        vrf_name: "{{ item.name }}"
        asn: "{{ device.custom_fields.bgp_asn }}"
        router_id: "{{ item.rd.split(':')[0] | default(loopback_ip) }}"
      loop: "{{ safe_tenant_vrfs }}"
      when: enable_bgp | default(false)
```

### VRF Validation and Cleanup

```yaml
---
- name: Validate and clean up VRFs
  hosts: switches
  tasks:
    # Get expected VRFs from NetBox
    - name: Get VRFs that should exist
      set_fact:
        expected_vrfs: "{{ netbox_interfaces | get_vrfs_in_use(ip_addresses) }}"

    # Get current VRFs from device
    - name: Gather VRF facts
      arubanetworks.aoscx.aoscx_facts:
        gather_subset:
          - vrfs
      register: device_facts

    # Extract current VRF names (filter out built-in)
    - name: Get current VRFs
      set_fact:
        current_vrfs: "{{
          device_facts.ansible_network_resources.vrfs.keys() | list |
          filter_configurable_vrfs
        }}"

    # Find discrepancies
    - name: Compare expected vs actual
      set_fact:
        vrfs_to_add: "{{ expected_vrfs.vrf_names | difference(current_vrfs) }}"
        vrfs_to_remove: "{{ current_vrfs | difference(expected_vrfs.vrf_names) }}"

    # Report
    - name: VRF audit report
      debug:
        msg: |
          Expected VRFs: {{ expected_vrfs.vrf_names }}
          Current VRFs: {{ current_vrfs }}
          VRFs to add: {{ vrfs_to_add }}
          VRFs to remove: {{ vrfs_to_remove }}

    # Create missing VRFs
    - name: Create missing VRFs
      arubanetworks.aoscx.aoscx_vrf:
        name: "{{ item }}"
        state: present
      loop: "{{ vrfs_to_add }}"
      when: vrfs_to_add | length > 0

    # Optionally remove extra VRFs
    - name: Remove extra VRFs
      arubanetworks.aoscx.aoscx_vrf:
        name: "{{ item }}"
        state: absent
      loop: "{{ vrfs_to_remove }}"
      when:
        - vrfs_to_remove | length > 0
        - allow_vrf_deletion | default(false)
```

---

## Debug Output Examples

With `DEBUG_ANSIBLE=true`:

```
DEBUG: Found VRF 'customer-a' on interface 1/1/10
DEBUG: Found VRF 'customer-b' on interface 1/1/20
DEBUG: All VRFs found in interfaces: {'customer-a', 'customer-b', 'mgmt'}
DEBUG: VRFs in use from interfaces: {'customer-a', 'customer-b', 'mgmt'}
DEBUG: Total VRFs from NetBox: 5
DEBUG: Tenant filter: None
DEBUG: Checking VRF: customer-a, tenant: None
DEBUG: VRF 'customer-a' passed initial checks
DEBUG: Including 'customer-a' - no tenant filter
DEBUG: Checking VRF: mgmt, tenant: None
DEBUG: Skipping 'mgmt' - mgmt or Global
DEBUG: Final filtered VRFs: ['customer-a', 'customer-b']
DEBUG: Found 2 configurable VRFs in use: ['customer-a', 'customer-b']
DEBUG: Built-in VRFs filtered out: {'mgmt', 'MGMT', 'Global', 'global', 'default', 'Default'}
```

---

## Best Practices

1. **Always Filter Built-in VRFs**: Use `filter_configurable_vrfs()` or `get_vrfs_in_use()` to avoid touching system VRFs
2. **Include IP Addresses**: Call `get_vrfs_in_use(interfaces, ip_addresses)` to catch all VRF usage
3. **Tenant Filtering**: Use tenant parameter when deploying multi-tenant configurations
4. **Safety Checks**: Always validate VRF lists before delete operations
5. **Metadata Preservation**: Use full VRF objects (not just names) to preserve NetBox metadata

---

## Common Patterns

### Pattern 1: Simple VRF Creation
```yaml
- set_fact:
    vrfs: "{{ interfaces | get_vrfs_in_use }}"
- arubanetworks.aoscx.aoscx_vrf:
    name: "{{ item }}"
    state: present
  loop: "{{ vrfs.vrf_names }}"
```

### Pattern 2: Tenant-Filtered VRF Creation
```yaml
- set_fact:
    vrfs: "{{ all_vrfs | filter_vrfs_in_use(interfaces, tenant_slug) }}"
- arubanetworks.aoscx.aoscx_vrf:
    name: "{{ item.name }}"
    state: present
  loop: "{{ vrfs }}"
```

### Pattern 3: Safety-First VRF Management
```yaml
- set_fact:
    all_vrfs: "{{ interfaces | get_vrfs_in_use(ip_addresses) }}"
    safe_vrfs: "{{ all_vrfs.vrf_names | filter_configurable_vrfs }}"
- arubanetworks.aoscx.aoscx_vrf:
    name: "{{ item }}"
    state: present
  loop: "{{ safe_vrfs }}"
```

---

## See Also

- [Filter Plugins Overview](../FILTER_PLUGINS.md)
- [Utils Module](utils.md) - Debug functions
- [Interface Filters](interface_filters.md) - L3 interface categorization by VRF
- [VLAN Filters](vlan_filters.md) - VLAN operations
- [NetBox Integration](../NETBOX_INTEGRATION.md)
