# BGP Filters Module

Part of the NetBox Filters Library for Aruba AOS-CX switches.

## What This Module Does (Plain English)

When you configure BGP (Border Gateway Protocol) on a switch, each BGP session needs to know two things:

1. **Which VRF it belongs to** - Is this a global/underlay session or a per-tenant VRF session?
2. **Which address family it uses** - Is the session using IPv4 or IPv6?

NetBox stores BGP sessions (via the NetBox BGP plugin) separately from interfaces. This module bridges those gaps:

- **`get_bgp_session_vrf_info`** looks at each BGP session's local IP address, finds which interface has that IP, checks what VRF that interface is in, and tags the session with the VRF name and address family. This lets your playbook split sessions into global BGP (for EVPN/underlay) and VRF BGP (for L3VPN/tenant peering) without any manual tagging in NetBox.

- **`collect_ebgp_vrf_policy_config`** reads each eBGP VRF session's `import_policies` and `export_policies`, fetches the matching routing policy rules and prefix list rules from the NetBox BGP plugin API, and returns pre-built AOS-CX CLI commands ready to apply to the device. Prefix lists must be configured before route-maps, and both before BGP neighbor statements.

---

## Overview

The `bgp_filters.py` module provides BGP session enrichment functionality. It takes raw BGP session data from the NetBox BGP plugin and adds VRF and address-family metadata by cross-referencing interface IP assignments.

**File Location**: `netbox_filters_lib/bgp_filters.py`

**Lines of Code**: 899 lines

**Dependencies**: [utils.py](utils.md) (`_debug`)

**Filter Count**: 8 filters — `get_bgp_session_vrf_info` and `collect_ebgp_vrf_policy_config` are documented in detail below; the other six (redistribute, neighbor-options, and BFD config-building/cleanup) are documented in [Redistribution, Neighbor Options, and BFD](#redistribution-neighbor-options-and-bfd) further down.

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

---

## `collect_ebgp_vrf_policy_config(sessions, policy_rules, prefix_list_rules)`

Collects routing policies and prefix lists referenced by BGP VRF sessions'
`import_policies` and `export_policies` fields, and returns pre-built AOS-CX
CLI commands ready to apply to the device.

### How It Works (Step by Step)

1. **Collect referenced policies**: Scan every session's `import_policies` and
   `export_policies` lists to build a map of `{policy_id → policy_name}`.

2. **Match routing policy rules**: Filter `all_policy_rules` to those whose
   `routing_policy.id` is in the collected map. For each matched rule, build a
   list of AOS-CX CLI commands:
   - Entry command: `route-map NAME permit seq INDEX`
   - Match commands: `match ip address prefix-list NAME` (from `match_ip_address` list)
   - Set commands from `set_actions` dict:
     - `"local-preference": 300` → `set local-preference 300`
     - `"as-path prepend": [65015]` → `set as-path prepend 65015`

3. **Collect prefix list rules**: For each prefix list referenced in step 2,
   filter `all_prefix_list_rules` to matching entries. Extract the prefix from
   the IPAM FK object (`prefix.prefix`) or fall back to `prefix_custom` (plain
   string) when the FK is null.

4. **Sort and return**: Prefix list rules sorted by `index`; route-map rules
   sorted by `(name, index)`.

### Parameters

- **sessions** (list): BGP session objects enriched with `_vrf`/`_af` by
  `get_bgp_session_vrf_info`. Each session must have `import_policies` and
  `export_policies` as lists of `{id, name}` dicts.
- **policy_rules** (list): All routing policy rule objects from
  `/api/plugins/bgp/routing-policy-rule/`.
- **prefix_list_rules** (list): All prefix list rule objects from
  `/api/plugins/bgp/prefix-list-rule/`.

### Returns

```python
{
  "prefix_lists": [
    {
      "name": "LAB-BLUE-IPV4",
      "rules": [
        {"index": 10, "action": "permit", "prefix": "172.27.4.0/24"}
      ]
    }
  ],
  "route_map_rules": [
    {
      "name": "LAB-BLUE-IPV4-OUT-01",
      "index": 10,
      "action": "permit",
      "commands": [
        "route-map LAB-BLUE-IPV4-OUT-01 permit seq 10",
        "match ip address prefix-list LAB-BLUE-IPV4",
        "set as-path prepend 65015"
      ]
    }
  ]
}
```

### Usage in Playbooks

```yaml
# 1. Fetch the device's sessions, routing policy rules and prefix list rules:
#    one GraphQL query, converted to REST shapes by netbox_bgp_graphql_to_rest
#    (see tasks/configure_bgp.yml and the section below). Any source in the
#    REST shapes works, e.g. the REST endpoints with limit=0.
# 2. Collect policy config data for this device's eBGP VRF sessions
- name: Collect routing policy config
  ansible.builtin.set_fact:
    bgp_policy_data: >-
      {{ bgp_vrf_sessions |
         collect_ebgp_vrf_policy_config(
           netbox_policy_rules_all,
           netbox_prefix_list_rules_all
         ) }}

# 3. Configure prefix lists (must come before route-maps)
- name: Configure IPv4 prefix lists
  arubanetworks.aoscx.aoscx_command:
    commands:
      - configure terminal
      - >-
        ip prefix-list {{ item.0.name }}
        seq {{ item.1.index }}
        {{ item.1.action }}
        {{ item.1.prefix }}
      - end
  loop: "{{ bgp_policy_data.prefix_lists | subelements('rules') }}"

# 4. Configure route-map rules (using aoscx_config for proper sub-mode handling)
- name: Configure route-map rules
  arubanetworks.aoscx.aoscx_config:
    lines: "{{ item.commands[1:] }}"
    parents: "{{ item.commands[0] }}"
    match: line
  loop: "{{ bgp_policy_data.route_map_rules }}"
```

### Real NetBox BGP API Field Shapes

**Routing policy rule** (`/api/plugins/bgp/routing-policy-rule/`):
```json
{
  "id": 2,
  "routing_policy": {"id": 2, "name": "LAB-BLUE-IPV4-OUT-01"},
  "index": 10,
  "action": "permit",
  "match_ip_address": [{"id": 2, "name": "LAB-BLUE-IPV4"}],
  "set_actions": {"as-path prepend": [65015]}
}
```

**Prefix list rule** (`/api/plugins/bgp/prefix-list-rule/`):
```json
{
  "id": 2,
  "prefix_list": {"id": 2, "name": "LAB-BLUE-IPV4"},
  "index": 10,
  "action": "permit",
  "prefix": {"id": 756, "prefix": "172.27.4.0/24", "display": "172.27.4.0/24"},
  "prefix_custom": null
}
```

When `prefix` is `null` (no IPAM object assigned), the filter falls back to the
`prefix_custom` plain-string field.

### AOS-CX Route-Map Syntax Note

AOS-CX requires `seq` before the sequence number:

```
route-map LAB-BLUE-IPV4-OUT-01 permit seq 10
  match ip address prefix-list LAB-BLUE-IPV4
  set as-path prepend 65015
```

The route-map configuration task must use `aoscx_config` (not `aoscx_command`)
because `aoscx_command` does not correctly handle CLI sub-mode entry for
route-map contexts.

### Edge Cases

| Scenario | Result |
|----------|--------|
| No sessions with `import_policies`/`export_policies` | Returns empty lists |
| Policy referenced by multiple sessions | Deduplicated (one route-map set) |
| Rule's `prefix` FK is null | Falls back to `prefix_custom` string |
| `match_ip_address` is empty | Route-map entry generated without match command |
| `set_actions` dict is empty | Route-map entry generated without set commands |

---

## `netbox_bgp_graphql_to_rest(response)`

Converts the netbox-bgp GraphQL answer for one device into the shapes the
REST endpoints return, so `get_bgp_session_vrf_info`,
`collect_ebgp_vrf_policy_config` and the change-detection filters work
unchanged.

`tasks/configure_bgp.yml` sends one query per device to `/graphql/`:
`netbox_bgp_session_list` filtered on the device name, with
`import_policies` / `export_policies` → `rules` → `match_ip_address` /
`match_ipv6_address` → `prefrules` nested. Over REST this took a session
query plus one query per routing policy and per prefix list, because
netbox-bgp's `routing_policy_id` / `prefix_list_id` filters take a single
value (a repeated parameter keeps only the last; `__in` is ignored).

What the conversion does:

- `id`, `index` and ASN values become ints (GraphQL returns `ID` and
  `BigInt` as strings).
- `status` becomes `{"value": ...}`, as REST returns it.
- Session policies become `{id, name}` references; their rules go to
  `policy_rules`, each with `routing_policy: {id, name}`.
- Prefix lists matched by those rules go to `prefix_list_rules`, each with
  `prefix_list: {id, name}`.
- Policies and prefix lists used by several sessions appear once. They are
  ordered by name, with rules in index order, matching the REST endpoints.

Returns `{available, errors, sessions, policy_rules, prefix_list_rules}`:

- `available` is false when the schema has no `netbox_bgp_session_list`,
  which means the plugin is not installed. The old REST query treated a 404
  the same way.
- `errors` holds any other GraphQL error messages. GraphQL reports errors
  with HTTP 200, so the task fails on them rather than treating the device
  as having no BGP.

NetBox caps every GraphQL list at `MAX_PAGE_SIZE` (default 1000), the same
cap REST applies with `limit=0`.

---

## Redistribution, Neighbor Options, and BFD

The netbox-bgp plugin's session model covers neighbors, remote-AS, and
policies, but not everything an AOS-CX BGP config can express. These six
filters let three more things be driven from NetBox `config_context`
instead: route redistribution, arbitrary per-neighbor CLI options, and the
BFD toggle that per-neighbor `fall-over bfd` depends on. Each "get the
config" filter has a matching "get the stale entries" filter, because
`aoscx_config` only ever *adds* missing lines — something removed from
config_context is never un-configured unless one of these cleanup filters
finds it in `show running-config` and explicitly issues the `no` form.

### `get_bgp_redistribute_config(bgp_redistribute)`

#### How It Works (Plain English)

Flattens the `bgp_redistribute` config_context — keyed by VRF name (`default` for the global `router bgp` instance), each mapping an address family (`ipv4`/`ipv6`) to a list of protocols to redistribute (e.g. `connected`, `static`) — into one entry per (VRF, address-family, protocol) combination, ready to loop over. Unknown/invalid address families or protocols are skipped rather than raised, matching this role's tolerant handling of malformed config_context elsewhere.

#### Parameters

- **bgp_redistribute** (dict): The `bgp_redistribute` config_context value.

#### Returns

- **list**: `[{"vrf": "default", "af": "ipv4", "protocol": "connected"}, ...]`, sorted for deterministic ordering.

#### Usage Example

```yaml
- name: Build redistribute entries
  set_fact:
    bgp_redistribute_entries: "{{ bgp_redistribute | default({}) | get_bgp_redistribute_config }}"

- name: Push redistribute config
  arubanetworks.aoscx.aoscx_config:
    lines: ["redistribute {{ item.protocol }}"]
    parents: >-
      {{ ['router bgp ' ~ local_asn] if item.vrf == 'default'
         else ['router bgp ' ~ local_asn, 'vrf ' ~ item.vrf] }}
  loop: "{{ bgp_redistribute_entries | selectattr('af', 'equalto', 'ipv4') | list }}"
  vars:
    ansible_connection: network_cli
```

### `get_stale_bgp_redistribute(bgp_redistribute, running_config, local_asn)`

Cleanup counterpart to `get_bgp_redistribute_config`. Diffs the actual `show running-config` text against the desired state to find `redistribute` lines present on the device but no longer in `bgp_redistribute`, for use in idempotent cleanup.

- **Parameters**: `bgp_redistribute` (same as above), `running_config` (full `show running-config` text from the device), `local_asn` (the device's BGP ASN, e.g. `device_bgp_sessions[0].local_as.asn`).
- **Returns**: `list` of `{"vrf": str, "af": str, "protocol": str}` entries to remove.

---

### `get_bgp_neighbor_options_config(bgp_neighbor_options, sessions)`

#### How It Works (Plain English)

For CLI options the netbox-bgp plugin's session model has no field for (e.g. `soft-reconfiguration inbound`, `fall-over bfd`), this lets you list them per-neighbor in a `bgp_neighbor_options` config_context entry instead of extending the plugin. Two scopes are supported per neighbor: `ipv4`/`ipv6` (options that go inside the matching `address-family ... unicast` block, resolved against sessions matching that address family) and `general` (options that go directly under `router bgp`/`vrf <name>`, resolved against every VRF the neighbor is peered under, regardless of address family). Each neighbor IP is matched against live session data — enriched with `_vrf`/`_af` by `get_bgp_session_vrf_info` — so an IP with no matching session is skipped rather than blindly pushed to a VRF it isn't actually peered in. Lines starting with a keyword already managed elsewhere in `tasks/configure_bgp.yml` (`remote-as`, `route-map`, `activate`, ...) are also skipped, so this can't fight those tasks.

#### Parameters

- **bgp_neighbor_options** (dict): Keyed by neighbor IP (no CIDR), each mapping a scope (`ipv4`/`ipv6`/`general`) to a list of CLI option strings — everything after `neighbor <ip> `.
- **sessions** (list): BGP session objects, already enriched with `_vrf`/`_af` by `get_bgp_session_vrf_info`.

#### Returns

- **list**: `[{"vrf": str, "af": str|None, "neighbor_ip": str, "command": str}, ...]`, sorted for deterministic ordering. `af` is `None` for `general`-scope entries.

#### Usage Example

```yaml
bgp_neighbor_options:
  172.27.250.32:
    general:
      - "fall-over bfd"
    ipv4:
      - "soft-reconfiguration inbound"
```

```yaml
- name: Build per-neighbor CLI option lines
  set_fact:
    neighbor_option_lines: "{{ bgp_neighbor_options | default({}) | get_bgp_neighbor_options_config(bgp_sessions) }}"
```

### `get_stale_bgp_neighbor_options(bgp_neighbor_options, sessions, running_config, local_asn)`

Cleanup counterpart to `get_bgp_neighbor_options_config`: diffs `show running-config` against the desired neighbor options to find lines that were removed from config_context and must be un-configured.

- **Returns**: Same shape as `get_bgp_neighbor_options_config`, entries to remove.

---

### `get_bgp_bfd_enabled(bgp_neighbor_options, sessions)`

#### How It Works (Plain English)

AOS-CX's `bfd` command is global — a single top-level line (alongside things like `clock timezone`), not nested under `router bgp`/`vrf` and not per-VRF. It has to be enabled before any neighbor's `fall-over bfd` has any effect. Rather than requiring a second, easy-to-forget `config_context` entry that could drift out of sync with the neighbor options, this filter derives whether `bfd` is needed directly from whether any neighbor declares `fall-over bfd` in the `general` scope of `bgp_neighbor_options`.

> **Note**: `bfd` is a switch-wide toggle also usable by OSPF and static routes. If those features start managing it too, this filter and `get_stale_bgp_bfd()` must be combined with their equivalent checks before deciding to push `no bfd`, so BGP's cleanup logic doesn't disable BFD for a feature it has no visibility into.

#### Parameters

- **bgp_neighbor_options** (dict): Same shape as `get_bgp_neighbor_options_config`.
- **sessions** (list): BGP session objects, enriched with `_vrf`/`_af`.

#### Returns

- **bool**: `True` if any neighbor declares `fall-over bfd`, meaning the global `bfd` line must be present.

### `get_stale_bgp_bfd(bgp_neighbor_options, sessions, running_config)`

Determine whether the global `bfd` line is currently configured on the device but no BGP neighbor declares `fall-over bfd` anymore, so `no bfd` should be pushed.

- **Returns**: `bool` — `True` if `no bfd` should be pushed.

---

## Change Detection Against REST Facts

These three filters compare NetBox with `aoscx_bgp_facts` (built by
`rest_api_to_aoscx_bgp`, see [REST API Transforms](rest_api_transforms.md)).
AF names are `ipv4`, `ipv6` (unicast) and `evpn` (l2vpn evpn).

### `build_bgp_desired_neighbors(sessions, device_vxlan=False, route_reflector=False, evpn_ipv4_unicast=False)`

Turns sessions enriched by `get_bgp_session_vrf_info` into the per-neighbor
state `configure_bgp.yml` sets:

| Neighbor | Settings |
| --- | --- |
| EVPN (default VRF, `device_vxlan`) | remote-as, update-source local address, `evpn` activate + send-community extended, `ipv4` activate when `evpn_ipv4_unicast` |
| iBGP, address-family | update-source local address, next-hop-self, activate |
| eBGP, address-family | activate, route-map from the first import/export policy |
| IPv6 (iBGP or eBGP) | send-community extended |
| iBGP on a route reflector | route-reflector-client |

- **Returns**: `{vrf: {ip: {"name", "remote_as", "update_source", "ibgp", "afs": {af: {"activate", "next_hop_self", "route_reflector_client", "send_community", "route_map_in", "route_map_out"}}}}}`.
  IPs are canonical (`2a02::0:3` becomes `2a02::3`), so they match the
  device's keys.

### `get_bgp_neighbor_changes(desired, bgp_facts, local_asn, idempotent=False)`

Diffs `build_bgp_desired_neighbors` against `aoscx_bgp_facts`.

- **Returns**: `{"push": [{vrf, ip, name, commands}], "remove": [{vrf, ip, commands}], "source": "rest"|"none"}`.
  `commands` is a complete `aoscx_command` sequence (`configure terminal`,
  `router bgp`, `vrf` when not default, only the missing lines, `end`).
  `send-community both` on the device satisfies `extended`.
- **Idempotent**: also removes IP neighbors that NetBox does not list (any
  VRF with a BGP router), route-reflector-client from iBGP neighbors that
  should not have it, and route-maps from eBGP neighbors without a policy.
- **Without facts** (`bgp_facts` None): every desired neighbor is pushed in
  full and nothing is removed.

```yaml
_bgp_neighbor_changes: >-
  {{ device_bgp_sessions_enriched
     | build_bgp_desired_neighbors(device_vxlan, is_rr, bgp_ipv4_enabled)
     | get_bgp_neighbor_changes(aoscx_bgp_facts | default(None), asn, aoscx_idempotent_mode) }}
```

### `get_bgp_redistribute_changes(bgp_redistribute, bgp_facts, idempotent=False)`

Diffs `bgp_redistribute` (see `get_bgp_redistribute_config`) against the
`redistribute` attribute of each router in `aoscx_bgp_facts`.

- **Returns**: `{"add": [{vrf, af, protocol}], "remove": [...], "source"}`.
  `remove` (idempotent only) holds every entry on the device, any protocol,
  that the config_context does not list. Without facts, `add` is every
  desired entry and `remove` is empty.

### `get_bgp_policy_changes(policy_data, bgp_facts)`

Reduces the output of `collect_ebgp_vrf_policy_config` to what the device
is missing, using `aoscx_bgp_facts.prefix_lists` / `route_maps`
(`/system/prefix_lists` and `/system/route_maps` at depth 4).

- A prefix-list entry is in sync when the list has the same address
  family and the same sequence with the same action and prefix, and no
  `ge`/`le` (prefixes are normalized, so IPv6 notation differences do not
  matter).
- A route-map rule is in sync when the same sequence exists with the same
  action and every match/set line. Extra lines or entries on the device
  are not reported.
- **Returns**: `{"prefix_lists": [{name, af, rules: [missing rules]}],
  "route_map_rules": [rules with anything missing], "source":
  "rest"|"none"}`. Without these facts everything is returned.

## Change Detection Against the Running-Config

`bgp_neighbor_options` lines are free-form CLI that REST has no general
field for, so they are compared against a single `show running-config`
fetch.

### `get_missing_bgp_neighbor_options(bgp_neighbor_options, sessions, running_config, local_asn)`

The desired entries from `get_bgp_neighbor_options_config` that are not
yet in the `router bgp <asn>` block (counterpart of
`get_stale_bgp_neighbor_options`).

- **Returns**: List of `{vrf, af, neighbor_ip, command}` dicts. Without
  running-config text every desired entry is returned.

---

## See Also

- [Filter Plugins Overview](../FILTER_PLUGINS.md)
- [VRF Filters](vrf_filters.md) - VRF extraction and management
- [Interface Filters](interface_filters.md) - Interface categorization
- [BGP Configuration Guide](../BGP_CONFIGURATION.md) - NetBox BGP plugin integration and full BGP setup
