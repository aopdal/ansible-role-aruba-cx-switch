# Static Route Filters Module

Part of the NetBox Filters Library for Aruba AOS-CX switches.

**Module**: `static_route_filters.py`
**Filters**: 1

## What This Module Does (Plain English)

A static route is a manually-defined "to reach this network, send traffic
here" rule — as opposed to routes learned dynamically via OSPF/BGP. The
tricky part with AOS-CX static routes isn't the routing logic, it's that the
Ansible module for them (`aoscx_static_route`, via the underlying `pyaoscx`
library) **isn't idempotent on its own**: every time you tell it to "create"
a route, it deletes and recreates that route's next-hop entry, even if the
route is already exactly correct. Left unchecked, that means every playbook
run reports "changed" for every static route, every time — which makes
"changed: 0" (the normal signal that nothing needed fixing) useless for
static routes.

This filter is the fix: it pre-compares the routes NetBox wants against
what the device's REST API facts say is actually configured, and only hands
back the routes that genuinely differ. Routes that already match aren't
touched, so a stable config produces a real "no changes" run.

---

## Overview

**File Location**: `netbox_filters_lib/static_route_filters.py`

**Lines of Code**: 136 lines

**Dependencies**: None (standalone module)

**NetBox config_context shape** (top-level `static_routes` key, per VRF):

```yaml
static_routes:
  default:
    - prefix: "0.0.0.0/0"
      type: forward          # forward (default) | blackhole | reject
      next_hop: "172.18.17.33"
      distance: 1             # optional, default 1
  lab-blue:
    - prefix: "10.99.0.0/24"
      type: forward
      next_hop_interface: "1/1/5"
```

Only a single next-hop per prefix is supported (no ECMP). See
[STATIC_ROUTES_CONFIGURATION.md](../STATIC_ROUTES_CONFIGURATION.md) for the
full data model and role behavior.

---

## Filters

### `get_static_route_changes(static_routes, static_route_facts=None)`

#### Purpose

Compute which static routes actually need to be created/updated on the
device, and which ones exist on the device but should be deleted because
they're no longer in NetBox.

#### Parameters

- **static_routes** (dict): The NetBox config_context `static_routes` value — keyed by VRF name, each a list of route dicts with keys `prefix` (required), `type` (`forward`/`blackhole`/`reject`, default `forward`), `next_hop` (IP address, optional), `next_hop_interface` (optional), `distance` (default `1`).
- **static_route_facts** (dict, optional): Current device state, keyed by VRF name then prefix:
  ```python
  {
    "default": {
      "0.0.0.0/0": {
        "type": "forward",
        "distance": 1,
        "next_hop_ip_address": "172.18.17.33",
        "next_hop_interface": None,
      }
    }
  }
  ```
  When `None` (`aoscx_gather_facts_rest_api: false`, or facts unavailable for
  this device), there's no reliable device state to diff against — every
  desired route is returned for push, and **no** deletions are computed
  (deleting requires knowing what's actually there).

#### Returns

- **dict**: `{"routes_to_apply": [...], "routes_to_delete": [...]}`
  - Each entry in `routes_to_apply` contains the full set of `aoscx_static_route` module parameters: `vrf_name`, `destination_address_prefix`, `type`, `distance`, `next_hop_ip_address`, `next_hop_interface`.
  - Each entry in `routes_to_delete` contains `vrf_name` and `destination_address_prefix`.

#### Usage Example

```yaml
- name: Compute static route changes
  ansible.builtin.set_fact:
    _static_route_changes: >-
      {{ static_routes | default({}) | get_static_route_changes(aoscx_static_route_facts | default(None)) }}

- name: Create/update static routes
  arubanetworks.aoscx.aoscx_static_route:
    vrf_name: "{{ item.vrf_name }}"
    destination_address_prefix: "{{ item.destination_address_prefix }}"
    type: "{{ item.type }}"
    distance: "{{ item.distance }}"
    next_hop_interface: "{{ item.next_hop_interface | default(omit, true) }}"
    next_hop_ip_address: "{{ item.next_hop_ip_address | default(omit, true) }}"
    state: create
  loop: "{{ _static_route_changes.routes_to_apply }}"
  loop_control:
    label: "VRF {{ item.vrf_name }} {{ item.destination_address_prefix }} ({{ item.type }})"
  when: _static_route_changes.routes_to_apply | length > 0

- name: Remove static routes no longer present in NetBox
  arubanetworks.aoscx.aoscx_static_route:
    vrf_name: "{{ item.vrf_name }}"
    destination_address_prefix: "{{ item.destination_address_prefix }}"
    state: delete
  loop: "{{ _static_route_changes.routes_to_delete }}"
  when:
    - aoscx_idempotent_mode | bool
    - _static_route_changes.routes_to_delete | length > 0
```

#### Debug Output

```yaml
- name: Debug - Show static route changes
  ansible.builtin.debug:
    msg:
      - "Routes to create/update: {{ _static_route_changes.routes_to_apply | length }}"
      - "Routes to delete: {{ _static_route_changes.routes_to_delete | length }}"
  when: aoscx_debug | bool or ansible_verbosity >= 1
```

---

## Dependencies (Task Ordering)

Static routes depend on VRFs (a route can't attach to a VRF that doesn't
exist yet) and L3 interfaces (`next_hop_interface` targets must already
exist on the device). Route deletion is gated the same way as other
cleanup tasks: only in `aoscx_idempotent_mode`, and only when REST API
facts are actually available. See
[docs/TAG_DEPENDENT_INCLUDES.md](../TAG_DEPENDENT_INCLUDES.md) for how
`tasks/configure_static_routes.yml` is included relative to OSPF/BGP.

---

## See Also

- [Filter Plugins Overview](../FILTER_PLUGINS.md)
- [Detailed Filter Reference](index.md)
- [Static Routes Configuration](../STATIC_ROUTES_CONFIGURATION.md) - Full data model and role behavior
- [VRF Filters](vrf_filters.md) - VRFs a static route can be attached to
- `tasks/configure_static_routes.yml`, `tasks/gather_facts_rest_api.yml`
