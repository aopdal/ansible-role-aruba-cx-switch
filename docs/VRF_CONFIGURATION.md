# VRF configuration

The role creates the VRFs a device needs, sets their route distinguisher
(RD), and keeps their route targets (RTs) in sync with NetBox. It runs early
(see [Ordering and tags](#ordering-and-tags)) because L3 interfaces, NTP,
DNS, SNMP, OSPF, BGP and static routes can all reference a VRF.

Attaching interfaces to a VRF is not part of this step. That happens in the
L3 interface step (`vrf attach <name>`), see
[ANYCAST_GATEWAY.md](ANYCAST_GATEWAY.md) and the L3 sections of the
[README](index.md).

## Which VRFs are configured

Only VRFs **in use** on the device are configured. A VRF is in use when
either of these references it in NetBox:

- an interface of the device (`interface.vrf`), skipping interfaces marked
  `mgmt_only`;
- an IP address assigned to the device (`ip_address.vrf`).

A VRF that exists in NetBox but isn't referenced by the device is ignored.

These names are treated as built-in and never created or changed:
`default`, `Default`, `Global`, `global`, `mgmt`, `MGMT`. NetBox's "Global"
table maps to the AOS-CX `default` VRF.

## How VRFs are modelled in NetBox

| NetBox field | AOS-CX config |
| --- | --- |
| VRF name | `vrf <name>` |
| VRF **Route distinguisher** | `rd <rd>` |
| VRF **Export targets** | `route-target export <rt>` |
| VRF **Import targets** | `route-target import <rt>` |
| Route target custom field `address_family` | the `address-family ipv4 unicast` or `ipv6 unicast` block the RT goes under |

### The `address_family` custom field

Each route target object needs to say which address family it belongs to.
Create a select custom field on **IPAM > Route target**:

```text
Name: address_family
Type: Selection (choice set with the values ipv4 and ipv6)
Object type: ipam > route target
Required: No
```

A route target without the field, or with any other value, is treated as
`ipv4`. NetBox 4.7 returns select fields as `{"value": ..., "label": ...}`
and older versions as a plain string; the role accepts both (see
[NETBOX_INTEGRATION.md](NETBOX_INTEGRATION.md#select-custom-fields-and-netbox-versions)).

A route target object has one `address_family`, so a VRF that needs route
targets in both address families uses separate route target objects, for
example `65015:10` for IPv4 and `65015:11` for IPv6.

## Example

NetBox, for VRF `lab-blue` on the lab device ao-01:

| Field | Value |
| --- | --- |
| Name | `lab-blue` |
| Route distinguisher | `65015:10` |
| Export targets | `65015:10` (address_family `ipv4`), `65015:11` (`ipv6`) |
| Import targets | `65015:10` (`ipv4`), `65015:11` (`ipv6`) |

Plus at least one ao-01 interface or IP address in VRF `lab-blue`. The
resulting device configuration:

```text
vrf lab-blue
    rd 65015:10
    address-family ipv4 unicast
        route-target export 65015:10
        route-target import 65015:10
    exit-address-family
    address-family ipv6 unicast
        route-target export 65015:11
        route-target import 65015:11
    exit-address-family
```

A VRF with no RD and no route targets in NetBox (on ao-01, `lab-ka-vsx`, a
VSX keepalive VRF) is just created: `vrf lab-ka-vsx`.

## What gets pushed

`identify_vrf_changes.yml` works out the changes and
`configure_vrfs.yml` applies them, in this order:

1. **Create** missing VRFs (`aoscx_vrf`, `state: create`).
2. **Set the RD** when NetBox has one and the device's differs
   (`rd <rd>` under `vrf <name>`).
3. **Add route targets** missing on the device
   (`route-target export|import <rt>` under the address-family block).
4. **Remove route targets** that are on the device but no longer in NetBox
   (`no route-target ...`). Idempotent mode only, see [Cleanup](#cleanup).

RD and route-target lines are pushed with `aoscx_config` over
`network_cli`.

## Change detection and idempotency

With REST fact gathering (`aoscx_gather_facts_rest_api: true`), the role
reads the device's VRFs and RDs (`/system/vrfs?attributes=name,rd&depth=2`)
and, for each VRF in use, its route targets
(`/system/vrfs/<vrf>/vrf_address_families`). It then pushes only what
differs. A rerun against a device that matches NetBox pushes nothing.

The NetBox side comes from a `netbox.netbox.nb_lookup` per VRF in use, which
returns the full route target objects, including `address_family`.

Without REST fact gathering there is no device state to compare against:
every VRF, RD and route target is pushed on every run, and `aoscx_vrf` and
`aoscx_config`'s `match: line` keep that from changing the device. Route
target removal needs the device state, so it never happens in this mode.

Set `aoscx_debug: true` (or run with `-v`) to see the analysis: VRFs to
create, RD changes, route targets to add and remove, and VRFs with no
changes.

## Cleanup

In idempotent mode (`aoscx_idempotent_mode: true`) with REST facts, route
targets on an in-use VRF that NetBox no longer lists are removed. That's
the only VRF cleanup:

- VRFs are never deleted, including VRFs no longer used by the device.
- An RD removed in NetBox is left on the device.
- VRFs not in use by the device aren't looked at, so their route targets
  are left alone too.

## Ordering and tags

In `tasks/main.yml`, VRFs run right after the base-system block and before
everything that can reference a VRF: NTP, DNS, ssh/https-server VRFs, SNMP,
interfaces, OSPF, static routes and BGP. Unlike OSPF and BGP, VRFs aren't
tag-protected, so they also run in an untagged run (see
[TAG_DEPENDENT_INCLUDES.md](TAG_DEPENDENT_INCLUDES.md)).

Both VRF includes are tagged `vrfs`, `layer3` and `routing`, so for
example:

```bash
ansible-playbook site.yml -l ao-01 -t vrfs
```

## Variables

| Variable | Default | Description |
| --- | --- | --- |
| `aoscx_configure_vrfs` | `true` | Run VRF change identification and configuration |
| `aoscx_gather_facts_rest_api` | `false` | REST facts; needed for diff-only pushes and route target removal |
| `aoscx_idempotent_mode` | `false` | Allow route target removal |
| `aoscx_test_mode` | `false` | Gather VRF facts even when `aoscx_configure_vrfs` is false (report playbooks) |
| `netbox_url`, `netbox_token` | none | NetBox API used for the per-VRF lookup |

## Known limitations

- **VRFs and RDs are only added or changed, never removed** (see
  [Cleanup](#cleanup)).
- **The built-in VRF list is fixed.** VRF selection uses its own list
  (`default`, `Default`, `Global`, `global`, `mgmt`, `MGMT`), not
  `aoscx_builtin_vrfs`. Changing `aoscx_builtin_vrfs` affects the L3
  interface step but not which VRFs are created.
- **The NetBox VRF lookup doesn't validate TLS certificates.** It sets
  `validate_certs: false` and ignores `aoscx_netbox_validate_certs`.
- **Moving an interface to another VRF clears its L3 config on AOS-CX.**
  With REST facts, the L3 interface step detects the VRF change and
  reapplies every address on the interface, not only the ones that changed.
  Without REST facts the device-side VRF of an interface isn't known, so
  the change isn't detected.
