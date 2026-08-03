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

## Related: sub-interface encapsulation VLAN drift

Renaming/re-parenting handles the case where NetBox moves an IP to a
*differently-named* interface. A narrower variant of the same misconfiguration
is possible when a sub-interface keeps its name but NetBox changes which VLAN
it is tagged for (e.g. `1/1/1.701` moves from `tagged_vlans: [701]` to
`tagged_vlans: [702]` in NetBox without renaming the sub-interface). Cleanup-
by-name does not catch this, since the interface name is unchanged - only the
`encapsulation dot1q <vid>` command on it is now wrong.

This is detected separately, as ordinary configuration drift rather than an
orphan: `get_interfaces_needing_config_changes()` (see
[`interface_change_detection.py`](../netbox_filters_lib/interface_change_detection.py)
in [FILTER_PLUGINS.md](FILTER_PLUGINS.md)) compares the device's actual
`subintf_vlan` against NetBox's `tagged_vlans[0].vid` and flags a mismatch via
`_ip_changes.encapsulation_change`, causing `configure_l3_interfaces.yml` to
re-push the correct `encapsulation dot1q <vid>` line on the next run.

This comparison requires `aoscx_gather_facts_rest_api: true` -
`subintf_vlan` is only available via the REST API
(`aoscx_enhanced_interface_facts`), not standard `aoscx_facts`. Without it,
the comparison is skipped (no false positives, but also no drift detection
for encapsulation).

### Sub-interfaces are not L2 trunk ports

NetBox represents a sub-interface's 802.1Q tag using the same `mode`/
`tagged_vlans` fields used for L2 trunk ports (e.g. `1/1/1.701` has
`mode: {"value": "tagged"}` and `tagged_vlans: [{"vid": 701}]`), even though
AOS-CX configures it via `encapsulation dot1q <vid>`, not L2 `vlan_mode`.
`get_interfaces_needing_config_changes()` skips the L2 VLAN mode/membership
check for all virtual-type interfaces (VLAN SVIs, loopbacks,
sub-interfaces), since none of them ever populate `vlan_mode`/`vlan_tag`/
`vlan_trunks` on the device - only the encapsulation-VLAN comparison above
applies to sub-interfaces.

## Variables

| Variable                            | Default | Description                                                                 |
| ------------------------------------ | ------- | ----------------------------------------------------------------------------- |
| `aoscx_idempotent_mode`             | `false` | Master switch for all idempotent cleanup (VLANs, EVPN, VXLAN, virtual interfaces, static routes). |
| `aoscx_cleanup_virtual_interfaces`  | `true`  | When `aoscx_idempotent_mode` is also `true`, removes orphaned VLAN SVIs, loopbacks, and sub-interfaces. Set to `false` to keep the rest of idempotent cleanup while leaving virtual interfaces untouched. |

## Implementation

- Filter: [`get_virtual_interfaces_to_delete()`](../netbox_filters_lib/interface_orphans.py) in `netbox_filters_lib/interface_orphans.py` - diffs NetBox `interfaces` names against `ansible_facts.network_resources.interfaces`, restricted to VLAN/loopback/sub-interface name patterns.
- Task: [`tasks/cleanup_virtual_interfaces.yml`](../tasks/cleanup_virtual_interfaces.yml) - identifies orphans and issues `no interface <name>` via `aoscx_config`.
- Wired into [`tasks/main.yml`](../tasks/main.yml) immediately before the "Include L3 interface configuration tasks" step.
