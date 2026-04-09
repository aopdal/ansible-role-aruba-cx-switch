# OSPF Filters Module

Part of the NetBox Filters Library for Aruba AOS-CX switches.

## What This Module Does (Plain English)

**OSPF** (Open Shortest Path First) is a routing protocol that lets switches and routers automatically discover and share network routes with each other. It organizes the network into "areas" - think of areas as neighborhoods in a city. Each interface on a switch can be assigned to one OSPF area.

In NetBox, OSPF configuration is stored as **custom fields** on interfaces (e.g., `if_ip_ospf_1_area = "0.0.0.0"` means "this interface is in OSPF area 0"). This module provides filters to:

- **Find which interfaces have OSPF configured** in NetBox
- **Extract the list of OSPF areas** in use
- **Group interfaces by area** for targeted configuration
- **Validate the OSPF setup** before deploying (e.g., check that the router has a router-id defined)

---

## Overview

The `ospf_filters.py` module provides OSPF (Open Shortest Path First) interface selection and validation functionality. It extracts OSPF configuration from NetBox custom fields and validates OSPF area consistency.

**File Location**: `filter_plugins/netbox_filters_lib/ospf_filters.py`

**Lines of Code**: 112 lines

**Dependencies**: None (standalone module)

**Filter Count**: 4 filters

## NetBox Custom Fields

OSPF configuration is stored in NetBox custom fields:

### Interface Custom Fields
- **`if_ip_ospf_1_area`** (text): OSPF area ID for the interface (e.g., "0.0.0.0", "0.0.0.1")

### Device Custom Fields
- **`device_ospf_1_routerid`** (text): OSPF router ID for the device
- **Config Context**: `ospf_areas` list with area configurations

---

## Filters

### 1. `select_ospf_interfaces(interfaces)`

Filters interfaces that have OSPF configuration defined.

#### Purpose

Identifies which interfaces should participate in OSPF routing by checking for the `if_ip_ospf_1_area` custom field.

#### Parameters

- **interfaces** (list): List of interface objects from NetBox

#### Returns

- **list**: Filtered list of interfaces with OSPF configuration

#### Custom Field Check

An interface is considered OSPF-enabled if:
- `custom_fields.if_ip_ospf_1_area` is set
- Value is not `None`, `""`, or `"null"`

#### Usage Examples

**Basic Selection:**
```yaml
- name: Get OSPF interfaces
  set_fact:
    ospf_interfaces: "{{ netbox_interfaces | select_ospf_interfaces }}"

- name: Display OSPF interface count
  debug:
    msg: "{{ ospf_interfaces | length }} interfaces configured for OSPF"
```

**Configure OSPF on Interfaces:**
```yaml
- name: Select OSPF interfaces
  set_fact:
    ospf_intfs: "{{ interfaces | select_ospf_interfaces }}"

- name: Configure OSPF on interfaces
  arubanetworks.aoscx.aoscx_ospf_interface:
    interface: "{{ item.name }}"
    area: "{{ item.custom_fields.if_ip_ospf_1_area }}"
    state: present
  loop: "{{ ospf_intfs }}"
```

**Filter and Configure by Area:**
```yaml
- name: Get all OSPF interfaces
  set_fact:
    all_ospf_intfs: "{{ netbox_interfaces | select_ospf_interfaces }}"

- name: Configure Area 0 interfaces
  arubanetworks.aoscx.aoscx_ospf_interface:
    interface: "{{ item.name }}"
    area: "{{ item.custom_fields.if_ip_ospf_1_area }}"
    state: present
  loop: "{{ all_ospf_intfs }}"
  when: item.custom_fields.if_ip_ospf_1_area == '0.0.0.0'
```

**Complete OSPF Workflow:**
```yaml
---
- name: Configure OSPF
  hosts: routers
  tasks:
    # Select interfaces
    - name: Get OSPF-enabled interfaces
      set_fact:
        ospf_interfaces: "{{ netbox_interfaces | select_ospf_interfaces }}"

    # Validate configuration
    - name: Ensure OSPF interfaces exist
      assert:
        that: ospf_interfaces | length > 0
        fail_msg: "No OSPF interfaces found in NetBox"

    # Configure OSPF process
    - name: Configure OSPF router
      arubanetworks.aoscx.aoscx_ospf:
        router_id: "{{ device.custom_fields.device_ospf_1_routerid }}"
        state: present

    # Configure interfaces
    - name: Enable OSPF on interfaces
      arubanetworks.aoscx.aoscx_ospf_interface:
        interface: "{{ item.name }}"
        area: "{{ item.custom_fields.if_ip_ospf_1_area }}"
        state: present
      loop: "{{ ospf_interfaces }}"
```

---

### 2. `extract_ospf_areas(interfaces)`

Extracts unique OSPF area IDs from interfaces.

#### Purpose

Builds a list of all OSPF areas in use, which can be used for area-level configuration or validation.

#### Parameters

- **interfaces** (list): List of interface objects from NetBox

#### Returns

- **list**: Sorted list of unique OSPF area IDs (strings)

#### Usage Examples

**Basic Extraction:**
```yaml
- name: Get OSPF areas in use
  set_fact:
    ospf_areas: "{{ netbox_interfaces | extract_ospf_areas }}"
  # Returns: ['0.0.0.0', '0.0.0.1', '0.0.0.10']

- name: Display areas
  debug:
    msg: "OSPF areas configured: {{ ospf_areas }}"
```

**Configure OSPF Areas:**
```yaml
- name: Extract areas
  set_fact:
    areas: "{{ interfaces | extract_ospf_areas }}"

- name: Configure OSPF areas
  arubanetworks.aoscx.aoscx_ospf_area:
    area_id: "{{ item }}"
    state: present
  loop: "{{ areas }}"
```

**Area-Based Configuration:**
```yaml
---
- name: Configure OSPF with multiple areas
  hosts: routers
  tasks:
    # Get areas
    - name: Extract OSPF areas
      set_fact:
        ospf_areas: "{{ netbox_interfaces | extract_ospf_areas }}"

    # Configure each area
    - name: Configure OSPF areas
      arubanetworks.aoscx.aoscx_ospf_area:
        area_id: "{{ item }}"
        authentication: "{{ ospf_area_auth[item] | default(omit) }}"
        state: present
      loop: "{{ ospf_areas }}"

    # Get interfaces for each area
    - name: Process each area
      include_tasks: configure_ospf_area.yml
      loop: "{{ ospf_areas }}"
      loop_control:
        loop_var: area_id
```

**Count Interfaces per Area:**
```yaml
- name: Get OSPF areas
  set_fact:
    areas: "{{ interfaces | extract_ospf_areas }}"

- name: Count interfaces per area
  set_fact:
    area_counts: |
      {% set counts = {} %}
      {% for area in areas %}
      {% set area_intfs = interfaces | get_ospf_interfaces_by_area(area) %}
      {% set _ = counts.update({area: area_intfs | length}) %}
      {% endfor %}
      {{ counts }}

- name: Display area summary
  debug:
    msg: "Area {{ item.key }}: {{ item.value }} interfaces"
  loop: "{{ area_counts | dict2items }}"
```

---

### 3. `get_ospf_interfaces_by_area(interfaces, area_id)`

Gets all interfaces belonging to a specific OSPF area.

#### Purpose

Filters interfaces to those in a specific OSPF area, useful for area-specific configuration or validation.

#### Parameters

- **interfaces** (list): List of interface objects from NetBox
- **area_id** (str): OSPF area ID to filter by (e.g., "0.0.0.0")

#### Returns

- **list**: List of interfaces in the specified area

#### Usage Examples

**Get Interfaces for Area:**
```yaml
- name: Get Area 0 interfaces
  set_fact:
    area0_interfaces: "{{ interfaces | get_ospf_interfaces_by_area('0.0.0.0') }}"

- name: Display Area 0 interfaces
  debug:
    msg: "{{ item.name }} is in Area 0"
  loop: "{{ area0_interfaces }}"
```

**Configure Area-Specific Settings:**
```yaml
- name: Get backbone area interfaces
  set_fact:
    backbone_intfs: "{{ netbox_interfaces | get_ospf_interfaces_by_area('0.0.0.0') }}"

- name: Configure backbone interfaces
  arubanetworks.aoscx.aoscx_ospf_interface:
    interface: "{{ item.name }}"
    area: "0.0.0.0"
    cost: 10
    priority: 100
  loop: "{{ backbone_intfs }}"
```

**Multi-Area Configuration:**
```yaml
---
- name: Configure OSPF areas with different settings
  hosts: routers
  vars:
    area_configs:
      "0.0.0.0":
        cost: 10
        hello_interval: 10
      "0.0.0.1":
        cost: 100
        hello_interval: 30
  tasks:
    # Configure each area
    - name: Configure OSPF by area
      include_tasks: configure_area.yml
      loop: "{{ area_configs | dict2items }}"
      loop_control:
        loop_var: area_config

# configure_area.yml
- name: Get interfaces for area {{ area_config.key }}
  set_fact:
    area_interfaces: "{{
      netbox_interfaces |
      get_ospf_interfaces_by_area(area_config.key)
    }}"

- name: Configure interfaces in area {{ area_config.key }}
  arubanetworks.aoscx.aoscx_ospf_interface:
    interface: "{{ item.name }}"
    area: "{{ area_config.key }}"
    cost: "{{ area_config.value.cost }}"
    hello_interval: "{{ area_config.value.hello_interval }}"
  loop: "{{ area_interfaces }}"
```

**Validation Example:**
```yaml
- name: Extract areas
  set_fact:
    areas: "{{ interfaces | extract_ospf_areas }}"

- name: Validate each area has interfaces
  block:
    - name: Check area {{ item }}
      set_fact:
        area_intfs: "{{ interfaces | get_ospf_interfaces_by_area(item) }}"

    - name: Ensure area has interfaces
      assert:
        that: area_intfs | length > 0
        fail_msg: "Area {{ item }} has no interfaces configured"

  loop: "{{ areas }}"
```

---

### 4. `validate_ospf_config(device_config, interfaces)`

Validates OSPF configuration consistency between device and interfaces.

#### Purpose

Performs sanity checks on OSPF configuration to catch common configuration errors:
- Missing router ID when OSPF interfaces exist
- Interface references to undefined areas

#### Parameters

- **device_config** (dict): Device configuration object from NetBox
- **interfaces** (list): List of interface objects from NetBox

#### Returns

- **dict**: Validation results:
  - `valid` (bool): Overall validation status (currently always True, only warnings)
  - `warnings` (list): List of warning messages
  - `errors` (list): List of error messages (currently unused)

#### Validation Checks

**Check 1: Router ID**
- If OSPF interfaces exist, router ID should be defined
- Custom field: `device_ospf_1_routerid`

**Check 2: Area Consistency**
- All interface areas should be defined in device config context
- Config context: `ospf_areas` list

#### Usage Examples

**Basic Validation:**
```yaml
- name: Validate OSPF configuration
  set_fact:
    ospf_validation: "{{ device | validate_ospf_config(interfaces) }}"

- name: Display validation results
  debug:
    msg: |
      Valid: {{ ospf_validation.valid }}
      Warnings: {{ ospf_validation.warnings }}
      Errors: {{ ospf_validation.errors }}
```

**Fail on Warnings:**
```yaml
- name: Validate OSPF
  set_fact:
    validation: "{{ device | validate_ospf_config(netbox_interfaces) }}"

- name: Ensure no warnings
  assert:
    that: validation.warnings | length == 0
    fail_msg: "OSPF configuration has warnings: {{ validation.warnings }}"
```

**Pre-Deployment Validation:**
```yaml
---
- name: Pre-deployment OSPF validation
  hosts: routers
  gather_facts: false
  tasks:
    # Validate configuration
    - name: Check OSPF configuration
      set_fact:
        ospf_check: "{{ device | validate_ospf_config(netbox_interfaces) }}"

    # Report warnings
    - name: Display warnings
      debug:
        msg: "WARNING: {{ item }}"
      loop: "{{ ospf_check.warnings }}"
      when: ospf_check.warnings | length > 0

    # Stop if warnings exist (optional)
    - name: Halt on configuration issues
      fail:
        msg: "OSPF configuration has {{ ospf_check.warnings | length }} warnings. Fix before deployment."
      when:
        - ospf_check.warnings | length > 0
        - strict_validation | default(false)

    # Proceed with deployment
    - name: Configure OSPF
      include_tasks: deploy_ospf.yml
      when: ospf_check.warnings | length == 0 or not (strict_validation | default(false))
```

**Detailed Validation Report:**
```yaml
- name: Run OSPF validation
  set_fact:
    validation: "{{ device | validate_ospf_config(interfaces) }}"

- name: Generate validation report
  debug:
    msg: |
      ===== OSPF Configuration Validation =====
      Device: {{ device.name }}
      Router ID: {{ device.custom_fields.device_ospf_1_routerid | default('NOT SET') }}

      OSPF Interfaces: {{ interfaces | select_ospf_interfaces | length }}
      OSPF Areas: {{ interfaces | extract_ospf_areas }}

      Validation Status: {{ 'PASS' if validation.valid else 'FAIL' }}

      {% if validation.warnings | length > 0 %}
      Warnings:
      {% for warning in validation.warnings %}
      - {{ warning }}
      {% endfor %}
      {% endif %}

      {% if validation.errors | length > 0 %}
      Errors:
      {% for error in validation.errors %}
      - {{ error }}
      {% endfor %}
      {% endif %}
```

#### Validation Scenarios

**Scenario 1: Missing Router ID**
```yaml
Device:
  custom_fields:
    device_ospf_1_routerid: null

Interfaces:
  - name: "1/1/1"
    custom_fields:
      if_ip_ospf_1_area: "0.0.0.0"

Result:
  valid: true
  warnings:
    - "OSPF interfaces configured but no router ID defined"
  errors: []
```

**Scenario 2: Undefined Area**
```yaml
Device:
  config_context:
    ospf_areas:
      - ospf_1_area: "0.0.0.0"

Interfaces:
  - name: "1/1/1"
    custom_fields:
      if_ip_ospf_1_area: "0.0.0.1"

Result:
  valid: true
  warnings:
    - "Interface references OSPF area 0.0.0.1 but area not defined in device config"
  errors: []
```

**Scenario 3: Valid Configuration**
```yaml
Device:
  custom_fields:
    device_ospf_1_routerid: "10.0.0.1"
  config_context:
    ospf_areas:
      - ospf_1_area: "0.0.0.0"

Interfaces:
  - name: "1/1/1"
    custom_fields:
      if_ip_ospf_1_area: "0.0.0.0"

Result:
  valid: true
  warnings: []
  errors: []
```

---

## Complete OSPF Deployment Workflow

```yaml
---
- name: Deploy OSPF configuration
  hosts: routers
  gather_facts: false
  vars:
    strict_validation: true
  tasks:
    # === VALIDATION ===
    - name: Validate OSPF configuration
      set_fact:
        ospf_validation: "{{ device | validate_ospf_config(netbox_interfaces) }}"

    - name: Report validation results
      debug:
        msg: |
          OSPF Validation: {{ 'PASS' if ospf_validation.warnings | length == 0 else 'WARNING' }}
          Warnings: {{ ospf_validation.warnings | length }}
          {% for warning in ospf_validation.warnings %}
          - {{ warning }}
          {% endfor %}

    - name: Fail on validation warnings
      fail:
        msg: "OSPF configuration validation failed"
      when:
        - strict_validation
        - ospf_validation.warnings | length > 0

    # === EXTRACT OSPF DATA ===
    - name: Get OSPF interfaces
      set_fact:
        ospf_interfaces: "{{ netbox_interfaces | select_ospf_interfaces }}"

    - name: Get OSPF areas
      set_fact:
        ospf_areas: "{{ netbox_interfaces | extract_ospf_areas }}"

    - name: Display OSPF summary
      debug:
        msg: |
          Router ID: {{ device.custom_fields.device_ospf_1_routerid }}
          OSPF Interfaces: {{ ospf_interfaces | length }}
          OSPF Areas: {{ ospf_areas }}

    # === CONFIGURE OSPF PROCESS ===
    - name: Configure OSPF router
      arubanetworks.aoscx.aoscx_ospf:
        router_id: "{{ device.custom_fields.device_ospf_1_routerid }}"
        state: present

    # === CONFIGURE AREAS ===
    - name: Configure OSPF areas
      arubanetworks.aoscx.aoscx_ospf_area:
        area_id: "{{ item }}"
        state: present
      loop: "{{ ospf_areas }}"

    # === CONFIGURE INTERFACES ===
    - name: Enable OSPF on interfaces
      arubanetworks.aoscx.aoscx_ospf_interface:
        interface: "{{ item.name }}"
        area: "{{ item.custom_fields.if_ip_ospf_1_area }}"
        state: present
      loop: "{{ ospf_interfaces }}"

    # === VERIFICATION ===
    - name: Verify OSPF neighbors
      arubanetworks.aoscx.aoscx_command:
        commands:
          - show ip ospf neighbor
      register: ospf_neighbors

    - name: Display OSPF neighbors
      debug:
        var: ospf_neighbors.stdout_lines
```

---

## Best Practices

1. **Always Validate First**: Use `validate_ospf_config()` before deployment
2. **Check Router ID**: Ensure router ID is set before configuring OSPF
3. **Define All Areas**: Document all areas in device config context
4. **Use Area Filtering**: Configure area-specific settings with `get_ospf_interfaces_by_area()`
5. **Verify After**: Check OSPF neighbors after configuration

---

## See Also

- [Filter Plugins Overview](../FILTER_PLUGINS.md)
- [Utils Module](utils.md)
- [Interface Filters](interface_filters.md)
- [VRF Filters](vrf_filters.md)
- [NetBox Integration](../NETBOX_INTEGRATION.md)
