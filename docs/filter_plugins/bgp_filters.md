# BGP Filters Module

Part of the NetBox Filters Library for Aruba AOS-CX switches.

## What This Module Does (Plain English)

When you configure BGP (Border Gateway Protocol) on a switch, each BGP session needs to know two things:

1. **Which VRF it belongs to** - Is this a global/underlay session or a per-tenant VRF session?
2. **Which address family it uses** - Is the session using IPv4 or IPv6?

NetBox stores BGP sessions (via the NetBox BGP plugin) separately from interfaces. This filter bridges that gap: it looks at each BGP session's local IP address, finds which interface has that IP, checks what VRF that interface is in, and tags the session with the VRF name and address family.

This lets your playbook split sessions into global BGP (for EVPN/underlay) and VRF BGP (for L3VPN/tenant peering) without any manual tagging in NetBox.

---

## Overview

The `bgp_filters.py` module provides BGP session enrichment functionality. It takes raw BGP session data from the NetBox BGP plugin and adds VRF and address-family metadata by cross-referencing interface IP assignments.

**File Location**: [filter_plugins/netbox_filters_lib/bgp_filters.py](../../filter_plugins/netbox_filters_lib/bgp_filters.py)

**Dependencies**: [utils.py](utils.md) (`_debug`)

**Filter Count**: 1 filter

---

## Built-in VRF Handling

The following VRF names are normalized to `'default'`:

- `mgmt` / `MGMT` - Management VRF
- `Global` / `global` - Global routing table
- `default` / `Default` - Default VRF

If a BGP session's local address is on an interface in any of these VRFs, the session gets `_vrf = 'default'`.

---

## Filters

### `get_bgp_session_vrf_info(sessions, interfaces)`

Enriches BGP session objects with VRF and address-family information derived from interface IP assignments.

#### How It Works (Step by Step)

Think of this filter as doing a "lookup" for each BGP session:

1. **Build a lookup table**: Go through every interface on the device. For each IP address on each interface, record which VRF that interface belongs to. This creates a map like: `"10.0.0.1/31" → "customer-a"`.

2. **Enrich each BGP session**: For each session, take its `local_address` field, look it up in the map, and add two new fields:

    - `_vrf`: The VRF name (or `'default'` if it's a global/built-in VRF)
    - `_af`: `'ipv4'` or `'ipv6'` based on the address format

3. **Return the enriched sessions**: Each session dict now has the extra fields your playbook can use for conditional logic.

#### Parameters

- **sessions** (list): List of BGP session objects from the NetBox BGP plugin. Each session should have a `local_address` dict with an `address` field (in CIDR notation, e.g., `"10.0.0.1/31"`).
- **interfaces** (list): List of interface objects from NetBox inventory (with `ip_addresses` lists and optional `vrf` dicts).

#### Returns

- **list**: The same session dicts, each with two added fields:
    - `_vrf` (str): VRF name, or `'default'` for global/built-in VRFs
    - `_af` (str): `'ipv4'` or `'ipv6'`

#### Usage Examples

**Basic Usage:**
```yaml
- name: Enrich BGP sessions with VRF info
  set_fact:
    bgp_sessions: "{{ nb_bgp_sessions | get_bgp_session_vrf_info(netbox_interfaces) }}"
```

**Split Sessions by VRF Type:**
```yaml
- name: Enrich BGP sessions
  set_fact:
    bgp_sessions: "{{ nb_bgp_sessions | get_bgp_session_vrf_info(netbox_interfaces) }}"

# Global/underlay sessions (EVPN, spine-leaf fabric)
- name: Configure global BGP sessions
  arubanetworks.aoscx.aoscx_bgp_neighbor:
    vrf: default
    neighbor: "{{ item.remote_address.address | ansible.utils.ipaddr('address') }}"
    remote_as: "{{ item.remote_as.asn }}"
  loop: "{{ bgp_sessions | selectattr('_vrf', 'equalto', 'default') | list }}"

# VRF sessions (tenant peering, L3VPN)
- name: Configure VRF BGP sessions
  arubanetworks.aoscx.aoscx_bgp_neighbor:
    vrf: "{{ item._vrf }}"
    neighbor: "{{ item.remote_address.address | ansible.utils.ipaddr('address') }}"
    remote_as: "{{ item.remote_as.asn }}"
  loop: "{{ bgp_sessions | rejectattr('_vrf', 'equalto', 'default') | list }}"
```

**Filter by Address Family:**
```yaml
- name: Enrich BGP sessions
  set_fact:
    bgp_sessions: "{{ nb_bgp_sessions | get_bgp_session_vrf_info(netbox_interfaces) }}"

- name: Get IPv4 sessions only
  set_fact:
    ipv4_sessions: "{{ bgp_sessions | selectattr('_af', 'equalto', 'ipv4') | list }}"
    ipv6_sessions: "{{ bgp_sessions | selectattr('_af', 'equalto', 'ipv6') | list }}"
```

**Complete BGP Workflow:**
```yaml
---
- name: Configure BGP from NetBox
  hosts: switches
  tasks:
    # Get BGP sessions from NetBox BGP plugin
    - name: Lookup BGP sessions
      set_fact:
        nb_bgp_sessions: "{{ query('netbox.netbox.nb_lookup', 'bgp_sessions',
                              api_filter='device=' + inventory_hostname) }}"

    # Enrich with VRF and address-family info
    - name: Add VRF context to sessions
      set_fact:
        bgp_sessions: "{{ nb_bgp_sessions | get_bgp_session_vrf_info(netbox_interfaces) }}"

    # Show what we found
    - name: Display BGP summary
      debug:
        msg: |
          Total sessions: {{ bgp_sessions | length }}
          Global sessions: {{ bgp_sessions | selectattr('_vrf', 'equalto', 'default') | list | length }}
          VRF sessions: {{ bgp_sessions | rejectattr('_vrf', 'equalto', 'default') | list | length }}
          IPv4 sessions: {{ bgp_sessions | selectattr('_af', 'equalto', 'ipv4') | list | length }}
          IPv6 sessions: {{ bgp_sessions | selectattr('_af', 'equalto', 'ipv6') | list | length }}
```

#### Input/Output Example

**Input session (from NetBox BGP plugin):**
```json
{
  "name": "spine1-leaf1",
  "local_address": {"address": "10.0.0.1/31"},
  "remote_address": {"address": "10.0.0.0/31"},
  "remote_as": {"asn": 65001}
}
```

**Input interface (from NetBox inventory):**
```json
{
  "name": "1/1/1",
  "vrf": {"name": "customer-a"},
  "ip_addresses": [{"address": "10.0.0.1/31"}]
}
```

**Output (enriched session):**
```json
{
  "name": "spine1-leaf1",
  "local_address": {"address": "10.0.0.1/31"},
  "remote_address": {"address": "10.0.0.0/31"},
  "remote_as": {"asn": 65001},
  "_vrf": "customer-a",
  "_af": "ipv4"
}
```

---

## Debug Output Examples

With `DEBUG_ANSIBLE=true`:

```
DEBUG: IP→VRF map: 10.0.0.1/31 → 'customer-a' (interface '1/1/1')
DEBUG: IP→VRF map: 10.0.1.1/31 → 'default' (interface '1/1/2')
DEBUG: IP→VRF map built with 2 entries
DEBUG: Session 'spine1-leaf1': local_address=10.0.0.1/31 → VRF='customer-a', AF='ipv4'
DEBUG: Session 'spine2-leaf1': local_address=10.0.1.1/31 → VRF='default', AF='ipv4'
```

---

## Edge Cases

| Scenario | Result |
|----------|--------|
| Session local_address not found on any interface | `_vrf = 'default'` |
| Interface has no VRF assigned | `_vrf = 'default'` |
| Interface VRF is `mgmt` or `Global` | Normalized to `_vrf = 'default'` |
| Local address contains `:` (IPv6) | `_af = 'ipv6'` |
| Management interface (`mgmt_only: true`) | Skipped during map building |
| Empty sessions list | Returns empty list |
| Empty interfaces list | All sessions get `_vrf = 'default'` |

---

## Prerequisites

This filter requires:
- **NetBox BGP plugin** installed and configured in NetBox
- BGP sessions defined with `local_address` fields
- Device interfaces with IP addresses assigned in NetBox

---

## See Also

- [Filter Plugins Overview](../FILTER_PLUGINS.md)
- [VRF Filters](vrf_filters.md) - VRF extraction and management
- [Interface Filters](interface_filters.md) - Interface categorization
- [BGP Configuration Guide](../BGP_CONFIGURATION.md) - Full BGP setup guide
- [NetBox BGP Plugin](../NETBOX_BGP_PLUGIN.md) - NetBox BGP plugin integration
