# Port-Access (Device-Profile) Configuration

This page is the single reference for AOS-CX port-access (device-profile)
configuration with this role. It covers:

1. [How port-access is modelled in NetBox](#how-port-access-is-modelled-in-netbox)
2. [Object reference](#object-reference) (lldp-groups, roles, device-profiles)
3. [Complete config_context example](#complete-config_context-example)
4. [Change detection and idempotency](#change-detection-and-idempotency)
5. [Cleanup](#cleanup)
6. [Task ordering and tags](#task-ordering-and-tags)
7. [Known limitation: mac-groups](#known-limitation-mac-groups)
8. [Operational notes](#operational-notes)

## How port-access is modelled in NetBox

Port-access is Aruba's network-access-control feature: identify a connected
device by LLDP, apply a role (VLANs, PoE priority, QoS trust) to it
automatically. It's one config_context tree with three kinds of objects,
all under a single top-level `port_access` key:

| Object kind | Purpose |
|---|---|
| `lldp_groups` | Match-sets used to fingerprint a connected device via its LLDP advertisement (vendor OUI, system name, or system description) |
| `roles` | What to apply once a device is identified — VLANs, PoE priority, QoS trust mode, and arbitrary extra CLI lines |
| `device_profiles` | Ties an `lldp_group` to a `role` and enables/disables the combination |

Configuration is gated by `aoscx_configure_port_access` (default `true`)
**and** the device's `port_access` config_context key being defined and
non-empty — so leaving the variable at its default is safe for devices
that don't use port-access at all. Task files:
[`tasks/configure_port_access.yml`](../tasks/configure_port_access.yml),
[`tasks/configure_port_access_lldp_group.yml`](../tasks/configure_port_access_lldp_group.yml),
[`tasks/configure_port_access_role.yml`](../tasks/configure_port_access_role.yml),
[`tasks/configure_port_access_device_profile.yml`](../tasks/configure_port_access_device_profile.yml).

Configuration order matters — device-profiles reference roles and LLDP
groups, so they're always pushed in the order **lldp-group → role →
device-profile**; cleanup (see below) runs the reverse order.

## Object reference

### `lldp_groups`

| Field | Required | Description |
|---|---|---|
| `name` | Yes | LLDP group name |
| `match` | No | List of match entries, each with an optional `seq` (auto-numbered `10, 20, 30...` if omitted) and exactly one of: |
| `match[].vendor-oui` | | Match on LLDP vendor OUI (e.g. Aruba AP OUI `"000b86"`) |
| `match[].sysname` | | Match on LLDP system name |
| `match[].sys-desc` | | Match on LLDP system description |

### `roles`

| Field | Required | CLI command | Notes |
|---|---|---|---|
| `name` | Yes | `port-access role <name>` | |
| `description` | No | `description <text>` | |
| `poe_priority` | No | `poe-priority <value>` | e.g. `low`/`high`/`critical` |
| `trust_mode` | No | `trust-mode <value>` | e.g. `dscp` |
| `vlan_access` | No | `vlan access <vid>` | Access-mode VLAN |
| `vlan_trunk_native` | No | `vlan trunk native <vid>` | Native VLAN for a trunk-mode role |
| `vlan_trunk_allowed` | No | `vlan trunk allowed <vids>` | Accepts NetBox range/list syntax (`"11-13"`, `"11,13,15-20"`) |
| `extra_lines` | No | Appended verbatim | Escape hatch for CLI this table doesn't cover — see the idempotency note below |

`vlan_trunk_native` and `vlan_trunk_allowed` VLAN IDs referenced here are
automatically added to the device's VLAN create list and protected from
idempotent VLAN cleanup — see
[`extract_port_access_vlan_ids`](filter_plugins/vlan_filters.md) and the
`port_access` argument to `get_vlans_in_use()`.

### `device_profiles`

| Field | Required | CLI command | Notes |
|---|---|---|---|
| `name` | Yes | `port-access device-profile <name>` | |
| `enable` | No (default `true`) | `enable` / `disable` | |
| `associate_role` | No | `associate role <name>` | Must reference a `roles[].name` |
| `associate_lldp_group` | No | `associate lldp-group <name>` | Must reference an `lldp_groups[].name` |

## Complete config_context example

```json
{
  "port_access": {
    "lldp_groups": [
      {
        "name": "Lab-IAP-group",
        "match": [
          { "seq": 10, "vendor-oui": "000b86" }
        ]
      }
    ],
    "roles": [
      {
        "name": "Lab-IAP-role",
        "description": "Aruba IAP",
        "poe_priority": "high",
        "trust_mode": "dscp",
        "vlan_trunk_native": 11,
        "vlan_trunk_allowed": "11-13",
        "extra_lines": [
          "reauth-period 3600",
          "cached-reauth-period 86400"
        ]
      }
    ],
    "device_profiles": [
      {
        "name": "Lab-IAP-prof",
        "enable": true,
        "associate_role": "Lab-IAP-role",
        "associate_lldp_group": "Lab-IAP-group"
      }
    ]
  }
}
```

## Change detection and idempotency

Requires [REST API fact gathering](FACT_GATHERING.md)
(`aoscx_gather_facts_rest_api: true`) for accurate comparison; without it,
every object in `port_access` is pushed unconditionally on every run.

[`port_access_diff`](filter_plugins/port_access.md#2-port_access_diffdesired-current)
compares each object against `aoscx_port_access_facts` (built by
[`port_access_facts_from_device_profiles`](filter_plugins/port_access.md#1-port_access_facts_from_device_profilesprofiles_payload)
from a single `GET /system/device_profiles?depth=4` call) and returns only
the objects that actually differ:

- **LLDP groups**: match-sets compared sequence-number-agnostic —
  reordering the same criteria isn't a change.
- **Roles**: `description`, `poe_priority`, `trust_mode`,
  `vlan_trunk_native`/`vlan_access`, and `vlan_trunk_allowed` (range/list
  syntax expanded before comparing) are all compared structurally.
  **Roles that use `extra_lines` always push** — arbitrary raw CLI text
  can't be reliably compared against structured REST facts, so this is a
  deliberate exception, not a bug.
- **Device-profiles**: `enable`, `associate_role`, `associate_lldp_group`
  are compared.

## Cleanup

Objects present on the device but removed from NetBox are only deleted
when **both** are true:

- `aoscx_idempotent_mode: true`, **and**
- REST API facts are available (`aoscx_port_access_facts` is defined)

[`port_access_orphans`](filter_plugins/port_access.md#3-port_access_orphansdesired-current)
computes the orphan list; [`tasks/cleanup_port_access.yml`](../tasks/cleanup_port_access.yml)
removes them in the reverse of configuration order —
device-profiles first (they reference roles/groups), then roles, then
LLDP groups.

## Task ordering and tags

Tags: `port_access`, `device_profile`, `layer2` for configuration;
`port_access`, `cleanup`, `idempotent` for cleanup (see
[README.md](../README.md#configuration-tags)). Not tag-protected under
[TAG_DEPENDENT_INCLUDES.md](TAG_DEPENDENT_INCLUDES.md) — treated as
routine L2 configuration.

## Not yet implemented: mac-groups

The AOS-CX CLI and REST API also support **mac-groups** (matching
connected devices by MAC address/OUI instead of LLDP) as a `port_access`
object kind. A `configure_port_access_mac_group.yml` task file and
matching template logic exist in the role as a starting point, but
mac-group support is **not yet implemented**: `configure_port_access.yml`
doesn't call the task, so a `mac_groups` list or a role's
`associate_mac_group` in config_context has **no effect** today — nothing
will be pushed, diffed, or cleaned up for it. `port_access_diff` and
`port_access_facts_from_device_profiles` also don't yet compare/flatten
`mac_groups`. This is unfinished rather than broken — there's no working
lab/example setup yet to validate the implementation against real
hardware. Use `lldp_groups` for device matching until mac-groups support
is completed.

## Operational notes

- **Module-based configuration**: uses `aoscx_config` (CLI, `network_cli`
  connection) with `match: line`.
- **ZTP/template generation**: when `aoscx_generate_template_config: true`,
  [`templates/port_access.j2`](../templates/port_access.j2) renders the
  same `port_access` config_context as plain CLI, for use in generated
  starting-point configs. This path has no idempotency or cleanup logic —
  it just emits text. See [TEMPLATE_CONFIGURATION.md](TEMPLATE_CONFIGURATION.md).
- **Filter reference**: see
  [filter_plugins/port_access.md](filter_plugins/port_access.md) for the
  full parameter and return-value reference.
