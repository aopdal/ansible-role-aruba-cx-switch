# Port-Access (Device-Profile) Configuration

This page is the single reference for AOS-CX port-access (device-profile)
configuration with this role. It covers:

1. [How port-access is modelled in NetBox](#how-port-access-is-modelled-in-netbox)
2. [Object reference](#object-reference) (lldp-groups, roles, device-profiles,
   and the optional [policies and classes](#policies-and-classes))
3. [Complete config_context example](#complete-config_context-example)
4. [Change detection and idempotency](#change-detection-and-idempotency)
5. [Cleanup](#cleanup)
6. [Task ordering and tags](#task-ordering-and-tags)
7. [Not yet implemented: mac-groups](#not-yet-implemented-mac-groups)
8. [User roles (RADIUS / ClearPass)](#user-roles-radius--clearpass)
9. [Operational notes](#operational-notes)

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
| `policies` (optional) | Port-access policy applied to traffic of clients in a role, built from class entries |
| `classes` (optional) | Classifier classes (`class ip` / `class ipv6`) referenced by policy entries |

Configuration is gated by `aoscx_configure_port_access` (default `true`)
**and** the device's `port_access` config_context key being defined and
non-empty — so leaving the variable at its default is safe for devices
that don't use port-access at all. Task files:
`tasks/configure_port_access.yml`,
`tasks/configure_port_access_lldp_group.yml`,
`tasks/configure_port_access_role.yml`,
`tasks/configure_port_access_device_profile.yml`,
`tasks/configure_port_access_class.yml`,
`tasks/configure_port_access_policy.yml`.

Configuration order matters — policies reference classes, roles reference
policies, device-profiles reference roles and LLDP groups, so they're
always pushed in the order **class → policy → lldp-group → role →
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
| `vlan_trunk_allowed` | No | `vlan trunk allowed <vids>` | Accepts NetBox range/list syntax (`"11-13"`, `"11,13,15-20"`). Pushed in the switch's own range form (`"1,101,102"` → `1,101-102`), so the CLI push matches running-config |
| `auth_mode` | No | `auth-mode <value>` | `client-mode`, `device-mode` or `multi-domain`. `auth-mode` (CLI spelling) is accepted as an alias. Unset means the role inherits the port's auth-mode |
| `gateway_zone` | No | `gateway-zone zone <zone> gateway-role <role>` | Tunnels the role's clients to a UBT zone — see [UBT_CONFIGURATION.md](UBT_CONFIGURATION.md) |
| `gateway_role` | No | (part of the `gateway-zone` line) | Role on the gateway. Defaults to the role's `name` |
| `associate_policy` | No | `associate policy <name>` | Must reference a `policies[].name` (or a policy that already exists on the switch) |
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

### Policies and classes

Both lists are optional. Leave them out and a role without
`associate_policy` is configured exactly as before, so existing sites are
unaffected.

`classes`:

| Field | Required | CLI command | Notes |
|---|---|---|---|
| `name` | Yes | `class <type> <name>` | |
| `type` | No (default `ip`) | | `ip` or `ipv6` |
| `entries` | No | | List of entries, each with an optional `seq` (auto-numbered `10, 20, 30...`) and one of: |
| `entries[].match` | | `<seq> match <text>` | Raw match criteria, e.g. `"any any any"` or `"tcp any any eq 443"` |
| `entries[].ignore` | | `<seq> ignore <text>` | Raw ignore criteria |

`policies`:

| Field | Required | CLI command | Notes |
|---|---|---|---|
| `name` | Yes | `port-access policy <name>` | |
| `entries` | No | | List of entries, each with an optional `seq` (auto-numbered) and: |
| `entries[].class` | Yes | `<seq> class <class_type> <class>` | Class name |
| `entries[].class_type` | No (default `ip`) | | `ip` or `ipv6` (MAC classes aren't allowed in a port-access policy) |
| `entries[].action` | No | `... action <text>` | Raw action, e.g. `drop` or `dscp 46`. Omit to permit |

Example — the policy that HPE Aruba Networking Central generates for an AP
role:

```json
{
  "port_access": {
    "classes": [
      {
        "name": "sys_pap_AP-Device-Role_ip_allow_1",
        "entries": [{ "seq": 10, "match": "any any any" }]
      }
    ],
    "policies": [
      {
        "name": "sys_policy_pap_AP-Device-Role",
        "entries": [{ "seq": 10, "class": "sys_pap_AP-Device-Role_ip_allow_1" }]
      }
    ],
    "roles": [
      {
        "name": "AP-Device-Role",
        "associate_policy": "sys_policy_pap_AP-Device-Role",
        "poe_priority": "critical",
        "vlan_trunk_native": 1,
        "vlan_trunk_allowed": "1,10,20,30,40,50",
        "extra_lines": ["auth-mode device-mode", "poe-allocate-by usage"]
      }
    ]
  }
}
```

renders:

```text
class ip sys_pap_AP-Device-Role_ip_allow_1
    10 match any any any
port-access policy sys_policy_pap_AP-Device-Role
    10 class ip sys_pap_AP-Device-Role_ip_allow_1
port-access role AP-Device-Role
    associate policy sys_policy_pap_AP-Device-Role
    poe-priority critical
    ...
```

Write `match`, `ignore` and `action` text the way the switch prints it in
`show running-config`. `aoscx_config` compares line by line against
running-config, so text in a different form shows `changed: true` on every
run.

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
[`port_access_facts_from_device_profiles`](filter_plugins/port_access.md#1-port_access_facts_from_device_profilesprofiles_payload-roles_payload)
from `GET /system/device_profiles?depth=5` plus
`GET /system/port_access_roles?depth=2`, so roles that no device-profile
references are included) and returns only the objects that actually
differ:

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
- **Role `associate_policy`**: compared against the role's `in_policy` on
  the device, but only when the role sets it. Removing `associate_policy`
  from NetBox does not emit `no associate policy` (same as `poe_priority`
  and the other attributes below).
- **Role `auth_mode`**: compared against the role's `auth_mode` on the
  device, but only when the role sets it. Removing it from NetBox does not
  emit `no auth-mode`.
- **Role `gateway_zone` / `gateway_role`**: compared against the role's
  `gateway_zone` and `ubt_gateway_role` on the device, but only when the
  role sets `gateway_zone`. Removing it does not emit `no gateway-zone`.
- **Classes and policies** are not part of the REST diff. They are always
  passed to `aoscx_config`, whose `match: line` compare against
  running-config pushes only missing lines, so a rerun reports `ok`.
  Entries removed from NetBox are not removed from the device.

### Removing a role attribute (e.g. `description`)

Deleting an attribute from a role in NetBox (e.g. removing `description`
from a role that previously had one) is detected the same way as any other
change — `port_access_diff` sees the desired and device-reported
`description` no longer match and re-pushes the role. For `description`
specifically, `tasks/configure_port_access_role.yml`
compares against `aoscx_port_access_facts` and emits `no description` when
the role currently has one on the device but NetBox no longer specifies
one; once removed, the role stops needing a push on subsequent runs (fully
idempotent). This requires REST API facts to be available — without them
`port_access_diff` falls back to "push everything", but no removal line is
generated (there's no device state to compare against), so the description
would be re-pushed with no value change each run without actually clearing
it. Set `aoscx_gather_facts_rest_api: true` to get this behaviour.

`poe_priority`, `trust_mode`, and the VLAN attributes (`vlan_access`,
`vlan_trunk_native`, `vlan_trunk_allowed`) do **not** have the same
removal handling yet — removing one of those from NetBox on an
already-configured role currently leaves the stale value on the device.
Unlike `description` (null when unset), these attributes have device-side
operational defaults, so a naive port of the same fix risks pushing a
spurious `no <keyword>` (and `changed: true`) on every run for roles that
simply never set them; this needs verifying against real device facts
before implementing.

## Cleanup

Objects present on the device but removed from NetBox are only deleted
when **both** are true:

- `aoscx_idempotent_mode: true`, **and**
- REST API facts are available (`aoscx_port_access_facts` is defined)

[`port_access_orphans`](filter_plugins/port_access.md#3-port_access_orphansdesired-current)
computes the orphan list; `tasks/cleanup_port_access.yml`
removes them in the reverse of configuration order —
device-profiles first (they reference roles/groups), then roles, then
LLDP groups.

Roles are cleanup candidates whether or not a device-profile references
them, but only roles the switch reports with `origin: local`. Roles
downloaded from ClearPass (`origin: downloaded`) or built from RADIUS
attributes (`origin: radius`) are never compared or removed. A local role
configured outside NetBox (by hand or from Central) **is** removed in
idempotent mode — add it to `port_access.roles` to keep it.

Policies and classes are **not** cleaned up. Classes are shared with ACL
and QoS policies, and port-access policies can also come from ClearPass or
RADIUS, so the role does not delete either.

## Task ordering and tags

Tags: `port_access`, `device_profile`, `layer2` for configuration;
`port_access`, `cleanup`, `idempotent` for cleanup (see
[README.md](index.md#configuration-tags)). Not tag-protected under
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

## User roles (RADIUS / ClearPass)

A port-access role doesn't need a device-profile. With 802.1X or MAC
authentication, ClearPass (or another RADIUS server) returns the role name
in the `Aruba-User-Role` attribute and the switch applies that local role
to the client. These **user roles** use the same `port_access.roles`
entries as device-profile roles; just leave them out of
`device_profiles`:

```json
{
  "port_access": {
    "roles": [
      {
        "name": "Pod5-Ansatt",
        "description": "Pod5-Ansatt",
        "associate_policy": "sys_policy_pap_Pod5-Ansatt",
        "auth_mode": "client-mode",
        "vlan_access": 10
      }
    ]
  }
}
```

renders:

```text
port-access role Pod5-Ansatt
    description Pod5-Ansatt
    associate policy sys_policy_pap_Pod5-Ansatt
    auth-mode client-mode
    vlan access 10
```

User roles get the same change detection and cleanup as device-profile
roles, because role facts are read from `/system/port_access_roles`
rather than only through the device-profiles. The 802.1X / MAC-auth port
and RADIUS server configuration itself is not managed by this role.

## Operational notes

- **Module-based configuration**: uses `aoscx_config` (CLI, `network_cli`
  connection) with `match: line`.
- **ZTP/template generation**: when `aoscx_generate_template_config: true`,
  `templates/port_access.j2` renders the
  same `port_access` config_context as plain CLI, for use in generated
  starting-point configs. This path has no idempotency or cleanup logic —
  it just emits text. See [TEMPLATE_CONFIGURATION.md](TEMPLATE_CONFIGURATION.md).
- **Filter reference**: see
  [filter_plugins/port_access.md](filter_plugins/port_access.md) for the
  full parameter and return-value reference.
