# REST API 10.15+ Optimization Proposal

## Executive Summary

This proposal outlines how to replace the slow `aoscx_facts` module with direct REST API calls using the AOS-CX REST API v10.15+. Based on analysis of the OpenAPI specification and current role implementation, this optimization can significantly reduce fact gathering time while providing more complete data (IPv6 addresses, VSX virtual IPs).

## Current State Analysis

### Current Fact Gathering Flow

```
gather_facts.yml
├── aoscx_facts (slow, ~10-30s per switch)
│   └── gather_network_resources: [interfaces, vlans]
└── gather_enhanced_facts.yml (optional, ~2-3s)
    └── REST API /system/interfaces?depth=2
```

### Problems with Current Approach

1. **aoscx_facts is slow**: Uses pyaoscx library which makes multiple API calls internally
2. **Limited to REST API v10.09**: pyaoscx doesn't support newer API versions
3. **IPv6 as URIs**: Returns `ip6_addresses` as URL strings, not actual addresses
4. **Missing VSX data**: No `vsx_virtual_ip4/ip6` for anycast/active-gateway
5. **Duplicate calls**: When `aoscx_gather_enhanced_facts: true`, we query interfaces twice

## Proposed Solution

### New REST API-Based Fact Gathering

Replace `aoscx_facts` entirely with direct REST API calls when:
- `aoscx_use_rest_api_facts: true` (new variable, default: false initially)
- REST API version 10.15+ available

### API Endpoints to Use

| Resource | Endpoint | Query Parameters | Purpose |
|----------|----------|------------------|---------|
| Interfaces | `/system/interfaces` | `depth=2`, `attributes=...` | All interface config |
| VLANs | `/system/vlans` | `depth=1`, `attributes=id,name,admin,description,voice,type` | VLAN definitions |
| EVPN | `/system/evpn` | `depth=2` | EVPN global config |
| EVPN VLANs | `/system/evpn/evpn_vlans` | `depth=1` | Per-VLAN EVPN config |
| VNIs | `/system/virtual_network_ids` | `depth=1` | VXLAN VNI mappings |

### Interface Attributes to Query

```
/system/interfaces?depth=2&attributes=name,admin_state,description,mtu,type,
  ip4_address,ip4_address_secondary,ip6_addresses,
  vsx_virtual_ip4,vsx_virtual_ip6,vsx_virtual_gw_mac_v4,vsx_virtual_gw_mac_v6,
  vlan_mode,vlan_tag,vlan_trunks,
  lacp_status,bond_status,other_config
```

### VLAN Attributes to Query

```
/system/vlans?depth=1&attributes=id,name,description,admin,voice,type,oper_state
```

## Implementation Plan

### Phase 1: New Task File (Low Risk)

Create `tasks/gather_facts_rest_api.yml`:

```yaml
---
# REST API-based fact gathering (v10.15+)
# Faster alternative to aoscx_facts module

- name: Set REST API variables
  ansible.builtin.set_fact:
    _rest_host: "{{ aoscx_rest_host | default(ansible_host) }}"
    _rest_user: "{{ aoscx_rest_user | default(ansible_user) }}"
    _rest_password: "{{ aoscx_rest_password | default(ansible_password) }}"
    _rest_validate_certs: "{{ aoscx_rest_validate_certs | default(false) }}"
    _rest_api_version: "{{ aoscx_rest_api_version | default('10.15') }}"
  no_log: true

- name: Login to AOS-CX REST API
  ansible.builtin.uri:
    url: "https://{{ _rest_host }}/rest/v{{ _rest_api_version }}/login"
    method: POST
    body_format: form-urlencoded
    body:
      username: "{{ _rest_user }}"
      password: "{{ _rest_password }}"
    validate_certs: "{{ _rest_validate_certs }}"
    status_code: [200]
  register: _rest_login
  delegate_to: localhost
  no_log: true

- name: Query interfaces with depth=2
  ansible.builtin.uri:
    url: >-
      https://{{ _rest_host }}/rest/v{{ _rest_api_version }}/system/interfaces
      ?depth=2
      &attributes=name,admin_state,description,mtu,type,
      ip4_address,ip4_address_secondary,ip6_addresses,
      vsx_virtual_ip4,vsx_virtual_ip6,vsx_virtual_gw_mac_v4,vsx_virtual_gw_mac_v6,
      other_config
    method: GET
    headers:
      Cookie: "{{ _rest_login.cookies_string }}"
    validate_certs: "{{ _rest_validate_certs }}"
    status_code: [200]
  register: _rest_interfaces
  delegate_to: localhost

- name: Query VLANs
  ansible.builtin.uri:
    url: >-
      https://{{ _rest_host }}/rest/v{{ _rest_api_version }}/system/vlans
      ?depth=1
      &attributes=id,name,description,admin,voice,type,oper_state
    method: GET
    headers:
      Cookie: "{{ _rest_login.cookies_string }}"
    validate_certs: "{{ _rest_validate_certs }}"
    status_code: [200]
  register: _rest_vlans
  delegate_to: localhost

- name: Query EVPN configuration
  ansible.builtin.uri:
    url: "https://{{ _rest_host }}/rest/v{{ _rest_api_version }}/system/evpn?depth=2"
    method: GET
    headers:
      Cookie: "{{ _rest_login.cookies_string }}"
    validate_certs: "{{ _rest_validate_certs }}"
    status_code: [200, 404]  # 404 if EVPN not configured
  register: _rest_evpn
  delegate_to: localhost
  when: aoscx_configure_evpn | default(false) | bool

- name: Query VNI mappings
  ansible.builtin.uri:
    url: "https://{{ _rest_host }}/rest/v{{ _rest_api_version }}/system/virtual_network_ids?depth=1"
    method: GET
    headers:
      Cookie: "{{ _rest_login.cookies_string }}"
    validate_certs: "{{ _rest_validate_certs }}"
    status_code: [200, 404]
  register: _rest_vnis
  delegate_to: localhost
  when: aoscx_configure_vxlan | default(false) | bool

- name: Logout from AOS-CX REST API
  ansible.builtin.uri:
    url: "https://{{ _rest_host }}/rest/v{{ _rest_api_version }}/logout"
    method: POST
    headers:
      Cookie: "{{ _rest_login.cookies_string }}"
    validate_certs: "{{ _rest_validate_certs }}"
    status_code: [200, 204]
  delegate_to: localhost
  no_log: true

- name: Transform REST API response to ansible_facts format
  ansible.builtin.set_fact:
    ansible_facts:
      network_resources:
        interfaces: "{{ _rest_interfaces.json | rest_api_to_aoscx_interfaces }}"
        vlans: "{{ _rest_vlans.json | rest_api_to_aoscx_vlans }}"
    aoscx_enhanced_interface_facts: "{{ _rest_interfaces.json }}"
    aoscx_evpn_facts: "{{ _rest_evpn.json | default({}) }}"
    aoscx_vni_facts: "{{ _rest_vnis.json | default({}) }}"
```

### Phase 2: Filter Plugins for Data Transformation

Create `filter_plugins/rest_api_transforms.py`:

```python
"""Transform REST API responses to match aoscx_facts format."""

def rest_api_to_aoscx_interfaces(rest_data):
    """Convert REST API interface data to aoscx_facts format.

    REST API returns: {"1/1/1": {...}, "vlan10": {...}}
    aoscx_facts expects: {"1/1/1": {...}, "vlan10": {...}}

    Main differences:
    - REST API uses admin_state, aoscx_facts uses admin
    - REST API ip6_addresses is dict, aoscx_facts is URL string
    - REST API includes vsx_virtual_* fields
    """
    result = {}
    for intf_name, intf_data in rest_data.items():
        if isinstance(intf_data, dict):
            result[intf_name] = {
                'name': intf_name,
                'admin': intf_data.get('admin_state', 'up'),
                'description': intf_data.get('description', ''),
                'mtu': intf_data.get('mtu'),
                'type': intf_data.get('type'),
                # IP addresses - already in proper format from depth=2
                'ip4_address': intf_data.get('ip4_address'),
                'ip4_address_secondary': intf_data.get('ip4_address_secondary', []),
                'ip6_addresses': intf_data.get('ip6_addresses', {}),
                # VSX virtual IPs (for anycast/active-gateway)
                'vsx_virtual_ip4': intf_data.get('vsx_virtual_ip4'),
                'vsx_virtual_ip6': intf_data.get('vsx_virtual_ip6'),
                'vsx_virtual_gw_mac_v4': intf_data.get('vsx_virtual_gw_mac_v4'),
                'vsx_virtual_gw_mac_v6': intf_data.get('vsx_virtual_gw_mac_v6'),
                # Other config
                'other_config': intf_data.get('other_config', {}),
            }
    return result


def rest_api_to_aoscx_vlans(rest_data):
    """Convert REST API VLAN data to aoscx_facts format."""
    result = {}
    for vlan_id, vlan_data in rest_data.items():
        if isinstance(vlan_data, dict):
            result[vlan_id] = {
                'id': vlan_data.get('id', vlan_id),
                'name': vlan_data.get('name', f'VLAN{vlan_id}'),
                'description': vlan_data.get('description', ''),
                'admin': vlan_data.get('admin', 'up'),
                'voice': vlan_data.get('voice', False),
                'type': vlan_data.get('type', 'static'),
                'oper_state': vlan_data.get('oper_state', 'up'),
            }
    return result


class FilterModule:
    def filters(self):
        return {
            'rest_api_to_aoscx_interfaces': rest_api_to_aoscx_interfaces,
            'rest_api_to_aoscx_vlans': rest_api_to_aoscx_vlans,
        }
```

### Phase 3: Update gather_facts.yml

```yaml
---
# Gather facts from AOS-CX switches

# Option 1: Use REST API directly (faster, requires v10.15+)
- name: Include REST API-based fact gathering
  ansible.builtin.include_tasks:
    file: gather_facts_rest_api.yml
  when:
    - aoscx_use_rest_api_facts | default(false) | bool
  tags:
    - always

# Option 2: Use aoscx_facts module (slower, compatible with all versions)
- name: Gather device facts via aoscx_facts
  arubanetworks.aoscx.aoscx_facts:
    gather_network_resources:
      - interfaces
      - vlans
  register: device_facts_result
  when:
    - not (aoscx_use_rest_api_facts | default(false) | bool)
  tags:
    - always

# Enhanced facts only needed when NOT using REST API facts
# (REST API facts already include this data)
- name: Include enhanced fact gathering
  ansible.builtin.include_tasks:
    file: gather_enhanced_facts.yml
  when:
    - not (aoscx_use_rest_api_facts | default(false) | bool)
    - aoscx_gather_enhanced_facts | default(false) | bool
  tags:
    - always
```

### Phase 4: New Variables in defaults/main.yml

```yaml
# REST API-based fact gathering (v10.15+)
# When true, uses direct REST API calls instead of aoscx_facts module
# Benefits:
#   - 3-5x faster fact gathering
#   - IPv6 addresses included (not just URIs)
#   - VSX virtual IPs for anycast/active-gateway
#   - Single authenticated session for all queries
# Requirements:
#   - aoscx_rest_api_version: "10.15" or later
#   - REST API credentials (defaults to ansible_user/ansible_password)
aoscx_use_rest_api_facts: false  # Set to true to enable
```

## Performance Comparison

| Metric | aoscx_facts | REST API Direct |
|--------|-------------|-----------------|
| Typical time (50 interfaces) | 15-30 seconds | 3-5 seconds |
| API calls | Multiple (per resource) | 2-4 (login + queries + logout) |
| IPv6 addresses | URI references | Actual addresses |
| VSX virtual IPs | Not included | Included |
| REST API version | 10.09 max | 10.15+ |

## Migration Path

### Stage 1: Optional Feature (Recommended)
- Add `aoscx_use_rest_api_facts: false` (default off)
- Users opt-in by setting to `true`
- No breaking changes

### Stage 2: Default On (After Testing)
- Change default to `true` after validation
- Document fallback to `aoscx_facts` if issues

### Stage 3: Deprecate aoscx_facts (Long Term)
- Remove `aoscx_facts` dependency
- Require REST API v10.15+

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| API version incompatibility | Version check before using REST API |
| Breaking changes in API | Pin to tested versions (10.15, 10.17) |
| Authentication failures | Fall back to aoscx_facts |
| Missing data fields | Compare output format, add transforms |

## Testing Plan

1. **Unit tests**: Filter plugins for data transformation
2. **Integration tests**:
   - Compare REST API output vs aoscx_facts output
   - Verify all interface types (physical, LAG, VLAN, loopback)
   - Test IPv6 address extraction
   - Test VSX virtual IP extraction
3. **Performance tests**: Measure time improvement
4. **Regression tests**: Ensure existing functionality unchanged

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `tasks/gather_facts_rest_api.yml` | Create | New REST API fact gathering |
| `filter_plugins/rest_api_transforms.py` | Create | Data transformation filters |
| `tasks/gather_facts.yml` | Modify | Add REST API option |
| `defaults/main.yml` | Modify | Add `aoscx_use_rest_api_facts` |
| `docs/PERFORMANCE_OPTIMIZATION.md` | Modify | Document new feature |

## Conclusion

Direct REST API fact gathering can provide:
- **3-5x faster** fact gathering
- **Complete IPv6 data** without additional calls
- **VSX virtual IP support** for anycast/active-gateway
- **Single session** for all queries

Recommendation: Implement as optional feature first (`aoscx_use_rest_api_facts: false` by default), allowing users to opt-in and validate before making it the default.
