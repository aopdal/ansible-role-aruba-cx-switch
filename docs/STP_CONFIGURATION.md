# STP (Spanning Tree) Configuration

This page is the single reference for spanning-tree configuration with this
role. It covers:

1. [How STP is modelled in NetBox](#how-stp-is-modelled-in-netbox)
2. [Global MSTP settings](#global-mstp-settings)
3. [Per-interface STP settings](#per-interface-stp-settings)
4. [Complete config_context example](#complete-config_context-example)
5. [Change detection and idempotency](#change-detection-and-idempotency)
6. [Task ordering and tags](#task-ordering-and-tags)
7. [Operational notes](#operational-notes)

## How STP is modelled in NetBox

AOS-CX runs **MSTP** (Multiple Spanning Tree Protocol). This role manages
two independent layers of MSTP settings, both optional:

| Layer | Source | Applies to |
|-------|--------|------------|
| Global | Device config_context (`mstp_config_name`, `mstp_config_revision`, `mstp_priority`) | The whole switch's MST region identity and bridge priority |
| Per-interface | Interface custom fields (`if_stp_bpdu_filter`, `if_stp_bpdu_guard`, `if_stp_edge_port`, `if_stp_root_guard`) | Individual L2 interfaces (access/trunk ports) |

Both layers are gated by `aoscx_configure_stp` (default `true`). Neither
requires the other — you can set only the global region name, only
per-interface guards, or both. Task file:
[`tasks/configure_stp.yml`](../tasks/configure_stp.yml).

## Global MSTP settings

Read from the device's config_context (not a custom field):

| Key | Type | Default | CLI command |
|-----|------|---------|-------------|
| `mstp_config_name` | String | — (required to enable global STP config) | `spanning-tree config-name <name>` |
| `mstp_config_revision` | Integer | `0` (role default when unset) | `spanning-tree config-revision <n>` |
| `mstp_priority` | Integer | `8` (role default when unset) | `spanning-tree priority <n>` |

**Global STP config is only pushed when `mstp_config_name` is defined** — an
unset `mstp_config_name` means "don't touch global STP settings on this
device," not "clear them." All switches that participate in the same MST
region must share the same `mstp_config_name` and `mstp_config_revision`
(this is an MSTP protocol requirement, not something the role enforces) —
mismatched values put switches in different regions and break the shared
spanning-tree topology across them.

`mstp_priority` must be a multiple of 4096 (AOS-CX/802.1s requirement) —
the role does not validate this; an invalid value will be rejected by the
device at push time.

## Per-interface STP settings

Four boolean custom fields on the **interface** object, each independently
optional — a field left unset (`null`/not defined) in NetBox leaves the
device's current setting for that field alone, it is neither enabled nor
disabled:

| Custom field | CLI command (when `true`) | Typical use |
|---|---|---|
| `if_stp_bpdu_filter` | `spanning-tree bpdu-filter` | Suppress BPDUs entirely on a port (rare — usually edge ports where no switch should ever appear) |
| `if_stp_bpdu_guard` | `spanning-tree bpdu-guard` | Shut the port down if a BPDU is received — protects against an accidentally-connected switch/hub on an access port |
| `if_stp_edge_port` | `spanning-tree port-type admin-edge` | PortFast-equivalent: skip the listening/learning delay on ports connected to end devices, not other switches |
| `if_stp_root_guard` | `spanning-tree root-guard` | Prevent a downstream device from becoming root — use on ports facing untrusted/downstream switches, never on uplinks toward the real root |

**Only L2 interfaces are considered** — a routed (L3-only) interface never
gets STP config regardless of these fields, since spanning-tree only
applies to bridged ports.

`if_stp_bpdu_guard` and `if_stp_edge_port` are commonly set together on
access ports facing end devices (fast to forwarding, and shuts down if
something unexpected shows up). `if_stp_root_guard` is typically set on
downstream-facing ports of a distribution/core switch, never on the uplink
toward the actual STP root.

## Complete config_context example

```json
{
  "mstp_config_name": "DC1-REGION",
  "mstp_config_revision": 1,
  "mstp_priority": 4096
}
```

Interface custom fields (set per-interface in NetBox, not in
config_context):

```yaml
# Access port facing an end-user device
if_stp_bpdu_guard: true
if_stp_edge_port: true

# Uplink to another switch — leave both unset (device default = disabled)

# Downstream port on a distribution switch
if_stp_root_guard: true
```

## Change detection and idempotency

Both layers are idempotent — pushed only when device state actually
differs from NetBox — but **both require
[REST API fact gathering](FACT_GATHERING.md)**
(`aoscx_gather_facts_rest_api: true`). Without it, every enabled setting is
pushed unconditionally on every run (still functionally correct — the CLI
commands are themselves idempotent — but every run reports `changed: true`
instead of `changed: 0` when nothing actually changed).

- **Global**: [`stp_global_config_diff`](filter_plugins/stp.md#1-stp_global_config_diffdesired-facts)
  compares the three config_context values against `aoscx_stp_global_facts`
  (from `GET /system?attributes=stp_config&depth=1`) and returns only the
  CLI lines for fields that actually differ.
- **Per-interface**: [`stp_interface_changes`](filter_plugins/stp.md#2-stp_interface_changesinterfaces-enhanced_facts)
  compares the four custom fields per interface against
  `aoscx_enhanced_interface_facts[name].stp_config` and returns only the
  interfaces (and only the specific commands) that changed.

Both are populated by
[`tasks/gather_facts_rest_api.yml`](../tasks/gather_facts_rest_api.yml),
gated on `aoscx_gather_facts_rest_api: true` **and** `aoscx_configure_stp: true`.

There is no cleanup step for STP — a custom field removed from NetBox
(set back to `null`) is never actively un-configured on the device (the
"unset means leave alone" semantics described above make this the correct
behavior, not a gap).

## Task ordering and tags

STP interface configuration runs **after L2 interface configuration**
(`configure_l2_interfaces.yml`) — the interfaces must already exist with
their VLAN mode set before STP settings can be layered on top.

Tags: `stp`, `layer2` (see [README.md](../README.md#configuration-tags)).
Unlike OSPF/BGP/VSX/static-routes, STP is **not** tag-protected under
[TAG_DEPENDENT_INCLUDES.md](TAG_DEPENDENT_INCLUDES.md) — it's treated as
routine L2 configuration, so a broad `-t layer2` run includes it.

## Operational notes

- **Module-based configuration**: uses `aoscx_config` (CLI, `network_cli`
  connection) with `match: line` for idempotent pushes when facts are
  unavailable.
- **ZTP/template generation**: when `aoscx_generate_template_config: true`,
  [`templates/stp.j2`](../templates/stp.j2) renders the global MSTP config,
  and [`templates/int_phys.j2`](../templates/int_phys.j2) /
  [`templates/int_lag.j2`](../templates/int_lag.j2) render the
  per-interface settings, into generated starting-point configs. This path
  emits plain CLI text and has no idempotency or comparison logic of its
  own — see [TEMPLATE_CONFIGURATION.md](TEMPLATE_CONFIGURATION.md).
- **Filter reference**: see [filter_plugins/stp.md](filter_plugins/stp.md)
  for the full `stp_global_config_diff` / `stp_interface_changes` parameter
  and return-value reference.
- **NetBox custom fields**: see
  [NETBOX_INTEGRATION.md](NETBOX_INTEGRATION.md) for how to create the four
  `if_stp_*` interface custom fields in NetBox.
