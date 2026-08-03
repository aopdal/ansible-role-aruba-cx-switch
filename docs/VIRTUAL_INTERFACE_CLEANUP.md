# Virtual Interface Cleanup

## Overview

VLAN SVIs, loopbacks, and sub-interfaces are logical objects that this role
creates and destroys based on NetBox. Unlike physical, LAG, and MCLAG
interfaces (which always exist on the device regardless of NetBox), these
virtual interface types can become **orphaned**: present on the device but
no longer referenced by NetBox.

This typically happens when NetBox is misconfigured - an interface is
renamed, or an IP address is moved to a different interface (e.g. `vlan10`
renamed to `vlan20`, or an IP moved from one sub-interface to another). If
the old device-side object is left behind, it keeps holding the same IP
address as its replacement, and `configure_l3_interfaces.yml` fails with a
duplicate IP address error when it tries to configure the new interface.

## Behaviour

When both `aoscx_idempotent_mode: true` and
`aoscx_cleanup_virtual_interfaces: true` (the default) are set, the role
compares the virtual interfaces present on the device against NetBox
**before** L3 interface configuration runs, and deletes any that are no
longer present in NetBox:

- VLAN SVIs (e.g. `vlan20`)
- Loopback interfaces (e.g. `loopback1`)
- Sub-interfaces (e.g. `1/1/3.200`)

Physical, LAG, and MCLAG interfaces are never candidates for deletion -
AOS-CX does not allow deleting them, and the role never tries.

## Ordering

Unlike VLAN/EVPN/VXLAN cleanup (which runs *after* all configuration, using
re-gathered facts), virtual interface cleanup runs **before**
`configure_l3_interfaces.yml`, using the facts gathered at the start of the
play (`gather_facts.yml`):

```
gather_facts.yml
  -> ... VLAN, physical/LAG/MCLAG/L2, OSPF configuration ...
  -> cleanup_virtual_interfaces.yml   # deletes orphans first
  -> configure_l3_interfaces.yml      # creates/updates SVIs, loopbacks, sub-interfaces
```

This ordering is required: if cleanup ran after L3 configuration (like the
VLAN/EVPN/VXLAN cleanup does), the new interface's L3 config would already
have failed with a duplicate IP address before cleanup ever had a chance to
run.

No re-gather of facts is needed before this step, since nothing earlier in
`tasks/main.yml` creates or deletes VLAN SVI, loopback, or sub-interface
objects.

## Variables

| Variable                            | Default | Description                                                                 |
| ------------------------------------ | ------- | ----------------------------------------------------------------------------- |
| `aoscx_idempotent_mode`             | `false` | Master switch for all idempotent cleanup (VLANs, EVPN, VXLAN, virtual interfaces, static routes). |
| `aoscx_cleanup_virtual_interfaces`  | `true`  | When `aoscx_idempotent_mode` is also `true`, removes orphaned VLAN SVIs, loopbacks, and sub-interfaces. Set to `false` to keep the rest of idempotent cleanup while leaving virtual interfaces untouched. |

## Implementation

- Filter: [`get_virtual_interfaces_to_delete()`](../netbox_filters_lib/interface_orphans.py) in `netbox_filters_lib/interface_orphans.py` - diffs NetBox `interfaces` names against `ansible_facts.network_resources.interfaces`, restricted to VLAN/loopback/sub-interface name patterns.
- Task: [`tasks/cleanup_virtual_interfaces.yml`](../tasks/cleanup_virtual_interfaces.yml) - identifies orphans and issues `no interface <name>` via `aoscx_config`.
- Wired into [`tasks/main.yml`](../tasks/main.yml) immediately before the "Include L3 interface configuration tasks" step.
