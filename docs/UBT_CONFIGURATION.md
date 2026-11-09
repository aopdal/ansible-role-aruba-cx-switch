# User-based tunneling (UBT) configuration

User-based tunneling sends a client's traffic from the switch port to an
Aruba gateway (or controller) cluster instead of switching it locally.
Clients are tunnelled per **port-access role**: when a client lands in a
role that has a `gateway_zone`, the switch tunnels its traffic to that
zone and the gateway applies the matching `gateway_role`.

This role configures the switch side:

- the UBT client VLAN (`ubt-client-vlan`),
- UBT zones (`ubt zone`), and
- the `gateway-zone` link on port-access roles.

The gateway cluster, ClearPass/RADIUS policy and the 802.1X/MAC-auth port
configuration are not managed by this role.

## NetBox config context

UBT lives under a top-level `ubt` key in the device's config context:

```json
{
  "ubt": {
    "client_vlan": 4000,
    "zones": [
      {
        "name": "UBT-Zone",
        "vrf": "default",
        "primary_controller": "192.168.1.1"
      }
    ]
  }
}
```

renders:

```text
ubt-client-vlan 4000
ubt zone UBT-Zone vrf default
    primary-controller ip 192.168.1.1
    enable
```

| Field | Required | CLI command | Notes |
|---|---|---|---|
| `client_vlan` | No | `ubt-client-vlan <vid>` | VLAN reserved for UBT clients. Never created as a regular VLAN and never removed by idempotent VLAN cleanup |
| `zones[].name` | Yes | `ubt zone <name> vrf <vrf>` | |
| `zones[].vrf` | No | (part of the zone line) | Default `default`. The VRF must exist; UBT runs after VRF configuration |
| `zones[].primary_controller` | No | `primary-controller ip <ip>` | |
| `zones[].backup_controller` | No | `backup-controller ip <ip>` | |
| `zones[].enable` | No | `enable` / `no enable` | Default `true` |
| `zones[].extra_lines` | No | Appended verbatim | For zone settings this table doesn't cover, e.g. `sac-heartbeat-interval 2`. Do not put a PAPI security key here: it would show in task output |

Configuration is gated by `aoscx_configure_ubt` (default `true`) **and**
the device's `ubt` config_context key being defined and non-empty, so the
default is safe for devices without UBT.

## Tunnelling a port-access role

Add `gateway_zone` (and optionally `gateway_role`) to the role in
`port_access.roles` — see
[PORT_ACCESS_CONFIGURATION.md](PORT_ACCESS_CONFIGURATION.md#roles):

```json
{
  "port_access": {
    "roles": [
      {
        "name": "Pod5-IoT",
        "associate_policy": "sys_policy_pap_Pod5-IoT",
        "auth_mode": "client-mode",
        "gateway_zone": "UBT-Zone",
        "gateway_role": "Pod5-IoT"
      }
    ]
  }
}
```

renders:

```text
port-access role Pod5-IoT
    associate policy sys_policy_pap_Pod5-IoT
    auth-mode client-mode
    gateway-zone zone UBT-Zone gateway-role Pod5-IoT
```

`gateway_role` defaults to the role's own name. The role's `gateway_zone`
and `gateway_role` are compared against the device's `gateway_zone` and
`ubt_gateway_role` REST fields in the port-access diff.

## UBT client VLAN

The VLAN set with `client_vlan` belongs to UBT, not to the VLAN tasks:

- it is never added to the VLAN create list, even if an interface or
  NetBox VLAN refers to it, and
- it is never removed by idempotent VLAN cleanup.

Do not use the same VID for a regular VLAN on the switch.

## Task ordering and tags

`tasks/configure_ubt.yml` runs after VRFs (zones are bound to a VRF) and
just before port-access (roles reference a zone). Tags: `ubt`,
`port_access`, `layer2`. It carries `port_access` so that
`--tags port_access` also creates the zones its roles reference.

## Idempotency and limits

- The AOS-CX REST API schema does not publish the UBT objects, so there is
  no REST diff. Every line is passed to `aoscx_config`, whose
  `match: line` compare against running-config keeps a rerun at `ok`.
- `enable: false` pushes `no enable`, which never appears in
  running-config, so a disabled zone reports `changed` on every run.
- **No cleanup**: zones, controller IPs or the client VLAN removed from
  NetBox stay on the device. Removing `gateway_zone` from a role does not
  emit `no gateway-zone`.
- Changing a zone's `vrf` creates a new zone line; remove the old zone by
  hand.
