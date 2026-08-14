# Port-Access Filters

Part of the NetBox Filters Library for Aruba AOS-CX switches.

**Modules**: `port_access.py` + `port_access_orphans.py`
**Filters**: 3 (2 in `port_access.py`, 1 in `port_access_orphans.py`)

## What This Module Does (Plain English)

AOS-CX **port-access** (device-profile) is Aruba's name for a bundle of
network-access-control config: which devices are allowed to identify
themselves over LLDP (`lldp_groups`), what a given device type is allowed to
do once connected (`roles` — VLANs, PoE priority, QoS trust), and which
role+LLDP-group combination gets auto-applied to a port when that kind of
device shows up (`device_profiles`). Think of it as "if something that looks
like an Aruba AP plugs in here, put it in the AP VLAN and trust its QoS
tags" — configured once, applied automatically.

This is one config_context tree with three kinds of objects inside it, and
this pair of modules gives you the idempotency and cleanup for the whole
tree:

- **`port_access.py`** answers "what needs to be *pushed*?" — it flattens
  the device's current REST API state into a comparable shape
  (`port_access_facts_from_device_profiles`) and then diffs it against what
  NetBox wants (`port_access_diff`), so only genuinely different LLDP
  groups, roles, and device-profile associations get configured.
- **`port_access_orphans.py`** answers "what needs to be *removed*?" — it
  finds device-profiles/roles/LLDP-groups that exist on the switch but were
  deleted from NetBox, for idempotent cleanup.

---

## Overview

**File Locations**: `netbox_filters_lib/port_access.py` (355 lines),
`netbox_filters_lib/port_access_orphans.py` (36 lines)

**Dependencies**: None (standalone modules)

**NetBox config_context shape** (top-level `port_access` key):

```yaml
port_access:
  lldp_groups:
    - name: Lab-IAP-group
      match:
        - { seq: 10, vendor-oui: "000b86" }
        - { seq: 20, sysname: "my-switch" }
  roles:
    - name: Lab-IAP-role
      description: Aruba IAP
      poe_priority: high
      trust_mode: dscp
      vlan_trunk_native: 11
      vlan_trunk_allowed: "11-13"
      extra_lines:              # optional: raw CLI appended verbatim
        - "reauth-period 3600"
  device_profiles:
    - name: Lab-IAP-prof
      enable: true
      associate_role: Lab-IAP-role
      associate_lldp_group: Lab-IAP-group
```

Configuration order matters — device-profiles reference roles and LLDP
groups, so `tasks/configure_port_access.yml` always pushes in the order
lldp-group → role → device-profile; cleanup runs the reverse order.

---

## Filters

### 1. `port_access_facts_from_device_profiles(profiles_payload)`

#### Purpose

`GET /system/device_profiles?depth=4` returns each profile with its
associated `role` and `lldp_groups` nested inline — one REST call covers
every object kind, instead of three separate ones. But that nested shape
isn't directly comparable to the flat, per-object-kind NetBox structure
above. This filter merges the nested dicts up to the top level so
`port_access_diff` can compare like-for-like.

#### Parameters

- **profiles_payload** (dict): Keyed by profile name, e.g. `{"LAB-SW": {"role": {"LAB-SW01": {...}}, "lldp_groups": {"AP-group": {...}}, ...}, ...}`. `None`/non-dict/empty input returns empty sub-dicts.

#### Returns

- **dict**: `{"device_profiles": {...}, "roles": {...}, "lldp_groups": {...}}`, each a flat dict keyed by object name. If the same role/group name appears under multiple profiles, the last one wins (a defensive merge — the device itself guarantees name uniqueness).

#### Usage Example

```yaml
# tasks/gather_facts_rest_api.yml
- name: Query port-access device-profiles via REST API
  ansible.builtin.uri:
    url: "https://{{ ansible_host }}/rest/v10.16/system/device_profiles?depth=4"
    headers:
      Cookie: "{{ login_cookie }}"
    validate_certs: false
  register: _rest_port_access_profiles
  when: (port_access | default({})) | length > 0

- name: Build aoscx_port_access_facts
  ansible.builtin.set_fact:
    aoscx_port_access_facts: >-
      {{ (_rest_port_access_profiles.json | default({}))
         | port_access_facts_from_device_profiles }}
  when: _rest_port_access_profiles is defined
```

---

### 2. `port_access_diff(desired, current)`

#### Purpose

Compare the `port_access` config_context against `aoscx_port_access_facts`
and return only the objects that actually need to be pushed, so
unconfigured LLDP groups/roles/device-profiles don't trigger an SSH
round-trip and CLI push every single run.

#### How It Works (Plain English)

For each of the three object kinds, every desired item is compared field-by-field
against the matching current object (if any exists):

- **LLDP groups**: match-sets are compared sequence-number-agnostic — reordering the same match criteria doesn't count as a change, only actual criteria differences do.
- **Roles**: compares `description`, `poe_priority`, `trust_mode` (against the device's `qos_trust_mode`), `vlan_trunk_native`/`vlan_access` (against `vlan_tag`), and `vlan_trunk_allowed` — with NetBox's range/list syntax (`"11-13"`) expanded before comparing against the device's `vlan_trunks` list. Roles using `extra_lines` always push (raw CLI content bypasses the REST diff — there's no reliable way to compare arbitrary CLI lines against structured facts).
- **Device-profiles**: compares `enable`, `associate_role`, `associate_lldp_group`.

#### Parameters

- **desired** (dict): The `port_access` config_context, with any of the keys `lldp_groups`, `roles`, `device_profiles` (each a list of object dicts).
- **current** (dict): `aoscx_port_access_facts` (output of `port_access_facts_from_device_profiles`). May be `None`/empty.

#### Returns

- **dict**: Same three keys as the input. Each value is the list of desired items that differ from the device or are missing entirely — items that already match are omitted. When `current` is missing/empty/the wrong shape, every desired object is returned (safe default: never silently skip work that can't be verified).

#### Usage Example

```yaml
- name: Compute diff vs device state
  set_fact:
    port_access_changes: >-
      {{ (port_access | default({}))
         | port_access_diff(aoscx_port_access_facts | default({})) }}
  when: port_access is defined and port_access | length > 0

- name: Configure each port-access lldp-group that changed
  ansible.builtin.include_tasks: configure_port_access_lldp_group.yml
  loop: "{{ port_access_changes.lldp_groups }}"
  loop_control:
    loop_var: pa_lldp_group
  when: port_access_changes.lldp_groups | length > 0
```

---

### 3. `port_access_orphans(desired, current)`

*(module: `port_access_orphans.py`)*

#### Purpose

Find device-profiles, roles, and LLDP groups that exist on the switch but
were removed from NetBox, so `tasks/cleanup_port_access.yml` can un-configure
them when running in idempotent mode. Orphan = present on device but not in
NetBox.

#### Parameters

- **desired** (dict): The `port_access` config_context.
- **current** (dict): `aoscx_port_access_facts`.

#### Returns

- **dict**: `{"device_profiles": [...], "roles": [...], "lldp_groups": [...]}` — sorted lists of *names* (not full objects) to remove. When `current` is missing/not a dict, all three lists are empty (nothing to compare against, so nothing is assumed orphaned).

#### Usage Example

```yaml
# tasks/cleanup_port_access.yml — removal order is the reverse of config:
# device-profiles first (they reference roles/groups), then roles, then lldp-groups.
- name: Identify orphaned port-access objects
  ansible.builtin.set_fact:
    aoscx_port_access_orphans: "{{ port_access | port_access_orphans(aoscx_port_access_facts) }}"
  when:
    - aoscx_idempotent_mode | bool
    - aoscx_configure_port_access | bool
    - port_access is defined
    - aoscx_port_access_facts is defined

- name: Remove orphaned device-profiles
  arubanetworks.aoscx.aoscx_config:
    lines:
      - "no port-access device-profile {{ item }}"
  loop: "{{ aoscx_port_access_orphans.device_profiles | default([]) }}"
  when: aoscx_port_access_orphans.device_profiles | length > 0
  vars:
    ansible_connection: network_cli
```

---

## See Also

- [Filter Plugins Overview](../FILTER_PLUGINS.md)
- [Detailed Filter Reference](index.md)
- [STP Filters](stp.md) - Same diff-against-REST-facts pattern for spanning tree
- [VSX Filters](vsx.md) - Same diff-against-REST-facts pattern for VSX
- `tasks/configure_port_access.yml`, `tasks/cleanup_port_access.yml`, `tasks/gather_facts_rest_api.yml`
