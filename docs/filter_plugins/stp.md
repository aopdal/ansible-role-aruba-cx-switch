# STP Filters Module

Part of the NetBox Filters Library for Aruba AOS-CX switches.

**Module**: `stp.py`
**Filters**: 2

## What This Module Does (Plain English)

**STP** (Spanning Tree Protocol, specifically MSTP — Multiple Spanning Tree
Protocol — on AOS-CX) prevents Layer 2 loops by electing a "root" switch and
blocking redundant paths. There are two levels of STP settings this role
manages from NetBox:

- **Global** settings that apply to the whole switch: the MST config name,
  revision number, and this switch's bridge priority (lower priority = more
  likely to become root).
- **Per-interface** settings: BPDU filter/guard, root guard, and admin-edge
  (portfast-equivalent) — each is a security/stability knob you'd typically
  enable on access ports facing end devices, not on inter-switch links.

Both filters follow the same shape: compare what NetBox wants against what
the device's REST API facts currently report, and return only the CLI lines
needed to close the gap — so a switch that's already correctly configured
shows zero changes on a re-run instead of unconditionally re-pushing every
STP setting every time.

---

## Overview

**File Location**: `netbox_filters_lib/stp.py`

**Lines of Code**: 134 lines

**Dependencies**: None (standalone module)

**Requires**: `aoscx_gather_facts_rest_api: true` for device-state
comparison. Global STP additionally requires `mstp_config_name` to be
defined in config_context; interface STP additionally requires
`aoscx_configure_stp: true`. Without REST facts, both filters default every
device-side value to its "not configured" state, so any NetBox `True`/set
value is treated as a change and gets pushed.

---

## Filters

### 1. `stp_global_config_diff(desired, facts)`

#### Purpose

Compare the switch's global MSTP settings (from NetBox config_context)
against `aoscx_stp_global_facts` and return the specific CLI lines needed to
bring the device in line — nothing when they already match.

#### Parameters

- **desired** (dict): `{"mstp_config_name": str, "mstp_config_revision": int, "mstp_priority": int}`, built from the `mstp_config_name`, `mstp_config_revision`, and `mstp_priority` config_context values.
- **facts** (dict): `aoscx_stp_global_facts` — the `stp_config` object from `GET /system?attributes=stp_config&depth=1`.

#### Returns

- **dict**:
  - `changed` (bool): `True` when at least one field differs.
  - `changes` (list of dicts): Per-field diffs, each `{"field": str, "expected": ..., "actual": ...}`.
  - `lines` (list of str): The CLI lines needed to apply the changes.

#### Usage Example

```yaml
- name: Compare global MSTP configuration against device facts
  ansible.builtin.set_fact:
    _stp_global_diff: >-
      {{ {
        'mstp_config_name': mstp_config_name | default(None),
        'mstp_config_revision': mstp_config_revision | default(0),
        'mstp_priority': mstp_priority | default(8),
      } | stp_global_config_diff(aoscx_stp_global_facts | default({})) }}
  when: mstp_config_name is defined

- name: Apply global STP (MSTP) configuration
  arubanetworks.aoscx.aoscx_config:
    lines: "{{ _stp_global_diff.lines }}"
  when:
    - mstp_config_name is defined
    - _stp_global_diff.changed | bool
  vars:
    ansible_connection: network_cli
```

---

### 2. `stp_interface_changes(interfaces, enhanced_facts)`

#### Purpose

Per-interface counterpart to `stp_global_config_diff` — compares each L2
interface's NetBox STP custom fields against the device's `stp_config`
facts and returns only the interfaces (and only the specific CLI lines)
that actually need to change.

#### Parameters

- **interfaces** (list): NetBox interface dicts. Only interfaces with an L2 `mode` defined are considered — routed (L3-only) interfaces are skipped, since STP settings don't apply to them.
- **enhanced_facts** (dict): `aoscx_enhanced_interface_facts`, keyed by interface name (populated by `tasks/gather_facts_rest_api.yml` when `aoscx_gather_facts_rest_api: true` **and** `aoscx_configure_stp: true`). Each interface's `.stp_config` sub-object holds the current device state.

#### Custom field → device field → CLI command mapping

| NetBox custom field | Device field (`stp_config`) | Command when enabling |
|---|---|---|
| `if_stp_bpdu_filter` | `bpdu_filter_enable` | `spanning-tree bpdu-filter` |
| `if_stp_bpdu_guard` | `bpdu_guard_enable` | `spanning-tree bpdu-guard` |
| `if_stp_edge_port` | `admin_edge_port_enable` | `spanning-tree port-type admin-edge` |
| `if_stp_root_guard` | `root_guard_enable` | `spanning-tree root-guard` |

- A custom field left as `None` (not set in NetBox) is skipped entirely — the device's existing setting for that field is left alone, it is neither enabled nor disabled.
- When desired differs from current, the enable command (or its `no` prefix, to disable) is added to that interface's `lines`.
- When `enhanced_facts` is empty, or the interface isn't present in it, all four device fields are treated as `False` — so any NetBox field set to `True` produces an enable command (nothing is silently skipped just because facts are missing).

#### Returns

- **list**: `[{"name": str, "lines": [str, ...]}, ...]` — only interfaces that actually have at least one changed field are included.

#### Usage Example

```yaml
- name: Build STP interface change list
  ansible.builtin.set_fact:
    _stp_interface_changes: >-
      {{ interfaces | default([]) |
         stp_interface_changes(aoscx_enhanced_interface_facts | default({})) }}

- name: Apply STP configuration to interfaces
  arubanetworks.aoscx.aoscx_config:
    lines: "{{ item.lines }}"
    parents: "interface {{ item.name | replace('lag', 'lag ') }}"
  loop: "{{ _stp_interface_changes }}"
  loop_control:
    label: "Interface {{ item.name }}: {{ item.lines | join(', ') }}"
  when: _stp_interface_changes | length > 0
  vars:
    ansible_connection: network_cli
```

---

## See Also

- [Filter Plugins Overview](../FILTER_PLUGINS.md)
- [Detailed Filter Reference](index.md)
- [Port-Access Filters](port_access.md) - Same diff-against-REST-facts pattern
- [VSX Filters](vsx.md) - Same diff-against-REST-facts pattern
- `tasks/configure_stp.yml`, `tasks/gather_facts_rest_api.yml`
