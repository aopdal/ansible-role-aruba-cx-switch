# Static Routes Configuration

This page is the single reference for static route configuration with
this role. It covers:

1. [How static routes are modelled in NetBox](#how-static-routes-are-modelled-in-netbox)
   (config context data model)
2. [Route types](#route-types) (forward, blackhole, reject)
3. [Complete config_context example](#complete-config_context-example)
4. [Change detection and idempotency](#change-detection-and-idempotency)
5. [Cleanup](#cleanup)
6. [Known limitations](#known-limitations)
7. [Operational notes](#operational-notes)

## How static routes are modelled in NetBox

Static routes are configured **declaratively from NetBox** using a single
config_context key, `static_routes`, keyed by VRF name. Each VRF maps to a
list of route objects:

| NetBox object | Field / source                | Purpose                                    |
|---------------|--------------------------------|---------------------------------------------|
| Device        | Config context `static_routes` | Per-VRF list of static routes (dict of lists) |

Static route tasks only run when **both** are true:

- `aoscx_configure_static_routes` is `true` (default) **and**
- The device's `static_routes` config_context key is defined and non-empty

See [TAG_DEPENDENT_INCLUDES.md](TAG_DEPENDENT_INCLUDES.md) for the
tag-based gating model — static routes are gated the same way as OSPF/BGP
(`static_routes`, `routing`, or `all` must be in `ansible_run_tags`)
because route changes, especially to a default route, can disrupt
connectivity.

### Route fields

Each entry in a VRF's route list supports:

| Key                  | Required | Type   | Default   | Description                                                        |
|-----------------------|----------|--------|-----------|----------------------------------------------------------------------|
| `prefix`              | Yes      | String | —         | Destination prefix in `address/mask` format, e.g. `10.0.0.0/8`.      |
| `type`                | No       | String | `forward` | One of `forward`, `blackhole`, `reject`.                             |
| `next_hop`            | No       | String | —         | Next-hop IPv4/IPv6 address. Used with `type: forward`.               |
| `next_hop_interface`  | No       | String | —         | Next-hop interface name (e.g. `1/1/2`). Used with `type: forward`.   |
| `distance`            | No       | Int    | `1`       | Administrative distance for the route.                               |

No `name`/description field is supported. Only a **single next-hop per
prefix** is supported (no ECMP) — see [Known limitations](#known-limitations).

## Route types

- **`forward`** — packets matching the route are forwarded to `next_hop`
  and/or out `next_hop_interface`.
- **`blackhole`** — packets matching the route are silently discarded, no
  ICMP message is sent. No next-hop is needed.
- **`reject`** — packets matching the route are discarded and an ICMP
  unreachable message is sent to the sender. No next-hop is needed.

## Complete config_context example

NetBox config_context is JSON — paste this shape directly into the
device's (or site's) config context field:

```json
{
  "static_routes": {
    "default": [
      {
        "prefix": "0.0.0.0/0",
        "type": "forward",
        "next_hop": "172.18.17.33"
      },
      {
        "prefix": "203.0.113.0/24",
        "type": "blackhole"
      },
      {
        "prefix": "198.51.100.0/24",
        "type": "reject",
        "distance": 5
      },
      {
        "prefix": "10.10.0.0/16",
        "type": "forward",
        "next_hop_interface": "1/1/2"
      }
    ],
    "tenant_a": [
      {
        "prefix": "192.168.100.0/24",
        "type": "forward",
        "next_hop": "192.168.1.1",
        "distance": 10
      }
    ]
  }
}
```

Ansible access: `static_routes`, `static_routes.<vrf_name>`.

!!! warning "VRF names MUST match NetBox exactly"
    The key under `static_routes` is matched verbatim against VRF names.
    Use `default` for the global VRF (NetBox exposes it as `Global`, but
    the role's own VRF handling normalizes that to `default` — always
    write `default` here). Names are case-sensitive.

## Change detection and idempotency

The `arubanetworks.aoscx.aoscx_static_route` module is **not idempotent**:
the underlying pyaoscx library always deletes and recreates a route's
next-hop (id `0`) on every `state: create` call, so calling it
unconditionally would report `changed: true` on every run regardless of
whether anything actually changed.

To avoid this, the role pre-compares desired routes (from
`static_routes`) against the device's actual state
(`aoscx_static_route_facts`, gathered via REST API — requires
`aoscx_gather_facts_rest_api: true`) and only pushes routes whose type,
distance, next-hop IP, or next-hop interface differ from what's already
configured. This mirrors the pattern used for non-idempotent L3 interface
configuration (see
[netbox_filters_lib/l3_config_helpers.py](../netbox_filters_lib/l3_config_helpers.py)).

The comparison logic lives in
[`get_static_route_changes`](../netbox_filters_lib/static_route_filters.py),
used by [`tasks/configure_static_routes.yml`](../tasks/configure_static_routes.yml).

!!! note "REST API facts are required for accurate change detection"
    When `aoscx_gather_facts_rest_api: false` (or the REST query fails),
    `aoscx_static_route_facts` is undefined and every desired route is
    pushed unconditionally on every run (`changed: true`), and no cleanup
    is attempted (see [Cleanup](#cleanup)).

## Cleanup

Routes that exist on the device but are no longer present in
`static_routes` are only removed when **both** are true:

- `aoscx_idempotent_mode: true`, **and**
- REST API facts are available (`aoscx_static_route_facts` is defined)

This is a deliberate safety choice: without a reliable read of device
state there is no safe way to tell "not in NetBox" apart from "facts
unavailable", so the role never deletes routes speculatively.

## Known limitations

### No ECMP

Only a single next-hop per prefix is supported. This is a limitation of
the underlying pyaoscx `StaticNexthop` implementation, which always
operates on next-hop id `0` — adding a second next-hop for the same
prefix replaces the first rather than adding a second path.

### Overlap with the access-switch default gateway feature

`aoscx_configure_access_switch_default_gateway` (see
[README.md](../README.md)) independently pushes a default route
(`0.0.0.0/0`) derived from `primary_ip4` for devices whose
`device_roles` contains `access-switch`, using `aoscx_config` +
`match: line`. If a device both has that role **and** defines a
`0.0.0.0/0` entry in `static_routes` for the same VRF, the two features
will compete to manage the same route. Use only one mechanism for the
default route on a given device.

## Operational notes

- **Module-based configuration**: uses `aoscx_static_route` (REST API)
  with `state: create` for both new and changed routes, and
  `state: delete` for cleanup.
- **Task ordering**: runs after VRFs and L3 interfaces (so `next_hop_interface`
  targets already exist) and before EVPN/VXLAN.
- **Tag-dependent**: gated the same way as OSPF/BGP — see
  [TAG_DEPENDENT_INCLUDES.md](TAG_DEPENDENT_INCLUDES.md).
- **Filter reference**: see
  [FILTER_PLUGINS.md](FILTER_PLUGINS.md) for `get_static_route_changes`.
- **ZTP/template generation**: when `aoscx_generate_template_config: true`,
  [`templates/gateway.j2`](../templates/gateway.j2) also renders the same
  `static_routes` config_context as plain `ip route` / `ipv6 route` CLI
  lines (IPv4 vs IPv6 selected automatically from `prefix`), for use in
  generated starting-point configs. `nullroute` is used for `blackhole`,
  `reject` for `reject`, `distance <value>` is added when `distance != 1`,
  and `vrf <name>` is appended when the VRF isn't `default`/`Global`. This
  path does not use the `aoscx_static_route` module and has no idempotency
  or cleanup logic — it just emits text. See
  [TEMPLATE_CONFIGURATION.md](TEMPLATE_CONFIGURATION.md).
