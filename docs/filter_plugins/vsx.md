# VSX Filters Module

Part of the NetBox Filters Library for Aruba AOS-CX switches.

**Module**: `vsx.py`
**Filters**: 1

## What This Module Does (Plain English)

**VSX** (Virtual Switching Extension) is Aruba's answer to "what if two
physical switches acted like one logical switch, for redundancy?" Two
switches are paired over an ISL (Inter-Switch Link, usually a LAG) and a
keepalive connection, and downstream devices see them as a single MCLAG
peer. Getting VSX config wrong (mismatched system MAC, wrong role, wrong
keepalive settings) breaks that pairing, so this role treats it carefully:
compare what NetBox wants against what the device currently reports, and
only push the fields that actually differ.

This mirrors the same "diff, don't blindly push" pattern used for
[STP](stp.md) and [Port-Access](port_access.md) — one filter, one job:
tell you which of the handful of VSX settings changed.

---

## Overview

**File Location**: `netbox_filters_lib/vsx.py`

**Lines of Code**: 80 lines

**Dependencies**: None (standalone module)

**Requires**: `aoscx_gather_facts_rest_api: true` for device-state
comparison (`aoscx_vsx_facts`); `custom_fields.device_vsx: true` on the
device to enable VSX configuration at all (checked in
`tasks/configure_vsx.yml`, not by this filter).

---

## Filters

### `vsx_config_diff(desired, facts)`

#### Purpose

Compare the VSX settings this role wants to configure against
`aoscx_vsx_facts` and report exactly which fields differ, so
`tasks/configure_vsx.yml` only calls `aoscx_vsx` (which pushes every
parameter at once) when there's an actual change to make.

#### Parameters

- **desired** (dict): VSX settings sourced from config_context —
  `{"vsx_role": str, "vsx_system_mac": str, "vsx_isl_lag": str|None, "vsx_keepalive_vrf": str, "vsx_keepalive_src": str, "vsx_keepalive_peer": str}`.
- **facts** (dict): `aoscx_vsx_facts` from the REST API. May be empty/`None` (e.g. `aoscx_gather_facts_rest_api: false`, or VSX facts weren't gathered for this device).

#### Returns

- **dict**:
  - `changed` (bool): `True` when at least one field differs.
  - `changes` (list of dicts): Per-field diffs, each `{"field": str, "expected": ..., "actual": ...}`.

#### Usage Example

```yaml
- name: Compare VSX configuration against device facts
  ansible.builtin.set_fact:
    vsx_diff: >-
      {{ {
        'vsx_role': vsx_role | default(None),
        'vsx_system_mac': vsx_system_mac | default(None),
        'vsx_isl_lag': vsx_isl_lag | default(None),
        'vsx_keepalive_vrf': vsx_keepalive_vrf | default(None),
        'vsx_keepalive_src': vsx_keepalive_src | default(None),
        'vsx_keepalive_peer': vsx_keepalive_peer | default(None),
      } | vsx_config_diff(aoscx_vsx_facts | default({})) }}
  when:
    - vsx_enabled | bool
    - vsx_system_mac is defined
    - vsx_role is defined

- name: Apply VSX configuration
  arubanetworks.aoscx.aoscx_vsx:
    system_mac: "{{ vsx_system_mac }}"
    keepalive_vrf: "{{ vsx_keepalive_vrf | default('mgmt') }}"
    keepalive_src_ip: "{{ vsx_keepalive_src | default('mgmt') }}"
    keepalive_peer_ip: "{{ vsx_keepalive_peer | default('not set') }}"
    device_role: "{{ vsx_role | default('not set') }}"
    isl_port: "{{ vsx_isl_lag | default('lag256') }}"
  when: vsx_diff.changed | bool
```

#### Debug Output

```yaml
- name: Display VSX diff results
  ansible.builtin.debug:
    msg:
      - "VSX changes needed: {{ vsx_diff.changed }}"
      - "Changes: {{ vsx_diff.changes }}"
  when: aoscx_debug | bool or ansible_verbosity >= 1
```

```
VSX changes needed: True
Changes: [{"field": "vsx_role", "expected": "primary", "actual": "secondary"}]
```

---

## See Also

- [Filter Plugins Overview](../FILTER_PLUGINS.md)
- [Detailed Filter Reference](index.md)
- [STP Filters](stp.md) - Same diff-against-REST-facts pattern
- [Port-Access Filters](port_access.md) - Same diff-against-REST-facts pattern
- `tasks/configure_vsx.yml`, `tasks/gather_facts_rest_api.yml`
