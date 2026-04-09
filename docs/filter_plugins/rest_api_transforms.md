# REST API Transforms Module

Separate filter plugin for transforming Aruba AOS-CX REST API responses.

## What This Module Does (Plain English)

Aruba AOS-CX switches have a REST API that returns device state (interfaces, VLANs, EVPN, VNIs) in a specific format. This role's change detection logic, however, expects data in the format produced by `aoscx_facts` (the Ansible facts module). These filters bridge that gap.

**Why is this needed?** Sometimes you query the switch REST API directly (e.g., for enhanced facts at `depth=2`) instead of using `aoscx_facts`. The raw REST API response has different field names, URL-encoded IPv6 addresses, and different nesting. These filters normalize everything into the format the rest of the role already understands.

Think of it like a translator: the REST API speaks one dialect, the role's filters speak another, and these transforms translate between them.

---

## Overview

The `rest_api_transforms.py` module is a **standalone filter plugin** (separate from `netbox_filters.py`). It provides 4 filters that convert REST API responses into the format expected by `aoscx_facts`-based logic.

**File Location**: `filter_plugins/rest_api_transforms.py`

**Dependencies**: `urllib.parse` (Python standard library)

**Filter Count**: 4 filters

---

## Key Differences Between REST API and aoscx_facts Format

| Aspect | REST API Format | aoscx_facts Format |
|--------|----------------|-------------------|
| Admin state field | `admin` or `admin_state` | `admin` |
| IPv6 addresses | URL-encoded keys (e.g., `2001%3Adb8%3A%3A1%2F64`) | Plain text keys |
| Anycast/gateway IPs | `vsx_virtual_ip4`, `vsx_virtual_ip6` | Same fields, normalized |
| VLAN IDs | May be strings or integers | Consistent integers |
| EVPN VLAN data | Nested under `/system/evpn/evpn_vlans` | Flat dict by VLAN ID |
| VNI keys | `"type,id"` format (e.g., `"vxlan,100"`) | ID-based keys |

---

## Filters

### 1. `rest_api_to_aoscx_interfaces(rest_data)`

Converts REST API interface data into the format used by `aoscx_facts`.

#### How It Works

Takes the raw dict from a `GET /system/interfaces?depth=2` REST API call and normalizes each interface entry:

1. **Admin state**: Checks both `admin_state` and `admin` fields (the field name varies by firmware version), and stores it as `admin`.
2. **IPv6 addresses**: URL-decodes the address keys (the REST API URL-encodes colons and slashes in IPv6 addresses).
3. **VLAN config**: Passes through `vlan_mode`, `vlan_tag`, and `vlan_trunks` as-is.
4. **VSX/Anycast IPs**: Preserves `vsx_virtual_ip4/ip6` and gateway MAC fields for anycast gateway detection.

#### Parameters

- **rest_data** (dict): Raw response from `GET /rest/v10.xx/system/interfaces?depth=2`. Keys are interface names (e.g., `"1/1/1"`, `"vlan10"`), values are interface detail dicts.

#### Returns

- **dict**: Normalized interface data with consistent field names. Keys are interface names, values contain: `name`, `admin`, `description`, `mtu`, `type`, `ip4_address`, `ip4_address_secondary`, `ip6_addresses`, `vsx_virtual_ip4`, `vsx_virtual_ip6`, `vsx_virtual_gw_mac_v4`, `vsx_virtual_gw_mac_v6`, `vlan_mode`, `vlan_tag`, `vlan_trunks`, `lacp_status`, `bond_status`, `routing`, `vrf`, `other_config`.

#### Usage Example

```yaml
- name: Get interface data from REST API
  uri:
    url: "https://{{ ansible_host }}/rest/v10.16/system/interfaces?depth=2"
    headers:
      Cookie: "{{ login_cookie }}"
    validate_certs: false
  register: rest_interfaces

- name: Convert to aoscx_facts format
  set_fact:
    enhanced_facts: "{{ rest_interfaces.json | rest_api_to_aoscx_interfaces }}"

# Now use with change detection filters
- name: Detect changes using enhanced facts
  set_fact:
    changes: "{{ netbox_interfaces | get_interfaces_needing_config_changes(
                   ansible_facts, enhanced_facts) }}"
```

---

### 2. `rest_api_to_aoscx_vlans(rest_data)`

Converts REST API VLAN data into the format used by `aoscx_facts`.

#### How It Works

Takes the raw dict from `GET /system/vlans?depth=2` and normalizes each VLAN entry. Handles the fact that VLAN IDs can be strings or integers in the REST API and ensures consistent integer IDs in the output.

#### Parameters

- **rest_data** (dict): Raw response from `GET /rest/v10.xx/system/vlans?depth=2`. Keys are VLAN IDs (as strings), values are VLAN detail dicts.

#### Returns

- **dict**: Normalized VLAN data keyed by VLAN ID string. Each value contains: `id` (int), `name`, `description`, `admin`, `voice`, `type`, `oper_state`.

#### Usage Example

```yaml
- name: Get VLANs from REST API
  uri:
    url: "https://{{ ansible_host }}/rest/v10.16/system/vlans?depth=2"
    headers:
      Cookie: "{{ login_cookie }}"
    validate_certs: false
  register: rest_vlans

- name: Convert to standard format
  set_fact:
    current_vlans: "{{ rest_vlans.json | rest_api_to_aoscx_vlans }}"
```

---

### 3. `rest_api_to_aoscx_evpn_vlans(rest_data)`

Converts REST API EVPN VLAN data into a usable format for EVPN configuration checks.

#### How It Works

Takes the raw dict from `GET /system/evpn/evpn_vlans?depth=1` and extracts the EVPN-specific fields for each VLAN: route distinguisher, route targets, and redistribution settings.

#### Parameters

- **rest_data** (dict): Raw response from `GET /rest/v10.xx/system/evpn/evpn_vlans?depth=1`. Keys are VLAN IDs, values are EVPN config dicts.

#### Returns

- **dict**: EVPN VLAN config keyed by VLAN ID string. Each value contains: `vlan` (int), `rd`, `export_route_targets`, `import_route_targets`, `redistribute`.

#### Usage Example

```yaml
- name: Get EVPN VLAN config from REST API
  uri:
    url: "https://{{ ansible_host }}/rest/v10.16/system/evpn/evpn_vlans?depth=1"
    headers:
      Cookie: "{{ login_cookie }}"
    validate_certs: false
  register: rest_evpn_vlans

- name: Convert EVPN VLAN data
  set_fact:
    current_evpn_vlans: "{{ rest_evpn_vlans.json | rest_api_to_aoscx_evpn_vlans }}"
```

---

### 4. `rest_api_to_aoscx_vnis(rest_data)`

Converts REST API VNI (Virtual Network Identifier) data into a usable format.

#### How It Works

Takes the raw dict from `GET /system/virtual_network_ids?depth=1` where keys are in `"type,id"` format (e.g., `"vxlan,100"`) and extracts VNI details into a clean dict keyed by VNI ID.

#### Parameters

- **rest_data** (dict): Raw response from `GET /rest/v10.xx/system/virtual_network_ids?depth=1`. Keys are `"type,id"` strings, values are VNI detail dicts.

#### Returns

- **dict**: VNI config keyed by VNI ID string. Each value contains: `id`, `type`, `vlan`, `vrf`, `routing`, `state`, `interface`.

#### Usage Example

```yaml
- name: Get VNI config from REST API
  uri:
    url: "https://{{ ansible_host }}/rest/v10.16/system/virtual_network_ids?depth=1"
    headers:
      Cookie: "{{ login_cookie }}"
    validate_certs: false
  register: rest_vnis

- name: Convert VNI data
  set_fact:
    current_vnis: "{{ rest_vnis.json | rest_api_to_aoscx_vnis }}"

- name: Show current VNI-to-VLAN mappings
  debug:
    msg: "VNI {{ item.value.id }} → VLAN {{ item.value.vlan }}"
  loop: "{{ current_vnis | dict2items }}"
```

---

## Complete Enhanced Facts Workflow

This example shows how all four transforms work together to provide full device state for idempotent change detection:

```yaml
---
- name: Gather enhanced device facts via REST API
  hosts: switches
  tasks:
    # Login to REST API
    - name: Authenticate
      uri:
        url: "https://{{ ansible_host }}/rest/v10.16/login"
        method: POST
        body_format: form-urlencoded
        body:
          username: "{{ ansible_user }}"
          password: "{{ ansible_password }}"
        validate_certs: false
        status_code: 200
      register: login

    # Gather all enhanced facts
    - name: Get interfaces (depth=2 for full IPv6 data)
      uri:
        url: "https://{{ ansible_host }}/rest/v10.16/system/interfaces?depth=2"
        headers:
          Cookie: "{{ login.cookies_string }}"
        validate_certs: false
      register: rest_interfaces

    - name: Get VLANs
      uri:
        url: "https://{{ ansible_host }}/rest/v10.16/system/vlans?depth=2"
        headers:
          Cookie: "{{ login.cookies_string }}"
        validate_certs: false
      register: rest_vlans

    # Transform to standard format
    - name: Normalize interface data
      set_fact:
        enhanced_interfaces: "{{ rest_interfaces.json | rest_api_to_aoscx_interfaces }}"
        enhanced_vlans: "{{ rest_vlans.json | rest_api_to_aoscx_vlans }}"

    # Use with change detection
    - name: Detect interface changes (with full IPv6 comparison)
      set_fact:
        changes: "{{ netbox_interfaces | get_interfaces_needing_config_changes(
                       ansible_facts, enhanced_interfaces) }}"
```

---

## When to Use These Filters

| Scenario | Use This? |
|----------|-----------|
| Standard playbook using `aoscx_facts` | No - data is already in the right format |
| Enhanced facts for full IPv6 comparison | Yes - `rest_api_to_aoscx_interfaces` |
| Checking current VLAN state via REST API | Yes - `rest_api_to_aoscx_vlans` |
| EVPN idempotent checks | Yes - `rest_api_to_aoscx_evpn_vlans` |
| VXLAN VNI idempotent checks | Yes - `rest_api_to_aoscx_vnis` |

---

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Input is not a dict | Returns empty dict `{}` |
| VLAN data entries are URI strings (depth < 2) | Skipped |
| IPv6 keys are URL-encoded | Automatically decoded |
| VLAN ID is a string like `"10"` | Converted to integer `10` |
| VNI key format `"vxlan,100"` | ID extracted from data, not from key |
| `admin_state` vs `admin` field | Both checked, `admin_state` preferred |

---

## See Also

- [Filter Plugins Overview](../FILTER_PLUGINS.md)
- [Interface Filters](interface_filters.md) - Change detection that consumes this data
- [VLAN Filters](vlan_filters.md) - VLAN management
- [EVPN/VXLAN Configuration](../EVPN_VXLAN_CONFIGURATION.md) - EVPN setup guide
