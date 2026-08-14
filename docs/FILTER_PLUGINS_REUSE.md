# Filter Plugins: Reuse with Other Network Devices

Most filters in this library operate on **NetBox data** — not on device-specific facts. Since NetBox uses a vendor-neutral data model (interfaces, VLANs, VRFs, IP addresses, BGP sessions), many filters work unchanged or with minor adaptation for any network device type. A growing share of the library, however, exists specifically to pre-compare desired NetBox state against **AOS-CX REST API facts** (for modules that aren't idempotent on their own) or to build **AOS-CX CLI command text** — that portion is Aruba-specific by design.

This document describes which filters are portable, which need adaptation, and which are Aruba AOS-CX specific.

---

## TL;DR: Portability Summary

| Module | Portability | Notes |
|--------|-------------|-------|
| `utils.py` | **Fully portable** | No device-specific logic |
| `bgp_filters.py` | **Mostly portable** | 4 of 8 functions are pure NetBox transforms; the `get_stale_*` functions parse AOS-CX `show running-config` text |
| `vrf_filters.py` | **Mostly portable** | Minor: custom field `address_family`; 2 of 8 functions read AOS-CX REST facts |
| `interface_categorization.py` | **Mostly portable** | Minor: custom field `if_mclag` |
| `interface_ip_processing.py` | **Mostly portable** | Minor: custom field `if_anycast_gateway_mac` |
| `ospf_filters.py` | **Mostly portable** | Minor: custom fields `if_ip_ospf_1_*`; 2 of 8 functions read AOS-CX REST facts |
| `vlan_filters.py` | **Partially portable** | 7 of 14 filters are generic |
| `l3_config_helpers.py` | **Partially portable** | 3 of 8 filters generic; CLI builders are AOS-CX |
| `comparison.py` | **AOS-CX specific** | Reads AOS-CX REST API facts structure |
| `interface_change_detection.py` | **AOS-CX specific** | Deep coupling to AOS-CX facts + VSX |
| `interface_ip_comparisons.py` | **AOS-CX specific** | IPv4/IPv6/VRF/anycast/DHCP-relay comparison, split out of `interface_change_detection.py` |
| `interface_orphans.py` | **AOS-CX specific** | Diffs desired vs. device interface names from AOS-CX facts; naming-convention regexes are portable if renamed |
| `static_route_filters.py` | **AOS-CX specific** | Works around `aoscx_static_route` non-idempotency; reads `aoscx_static_route_facts` |
| `stp.py` | **AOS-CX specific** | Reads `aoscx_stp_global_facts` / `aoscx_enhanced_interface_facts.stp_config`; STP concept is portable, fields are not |
| `port_access.py` | **Aruba-only feature** | Port-access (device-profiles/LLDP-groups/roles) is an AOS-CX-specific feature with no generic NetBox equivalent |
| `port_access_orphans.py` | **Aruba-only feature** | Same feature family as `port_access.py` |
| `vsx.py` | **Aruba-only feature** | VSX is Aruba's MLAG technology; facts fields (`isl_port`, `keepalive_vrf`, `system_mac`) are Aruba-specific |

---

## Fully Portable Filters

These work without modification for any network device whose data comes from NetBox.

### `utils.py` — All functions

| Filter | Description | Reuse |
|--------|-------------|-------|
| `_debug` | Debug output via `DEBUG_ANSIBLE=true` | Drop-in |
| `is_ipv4_address` | Checks whether a string is an IPv4 address | Drop-in |
| `is_ipv6_address` | Checks whether a string is an IPv6 address | Drop-in |
| `get_interface_type_value` | Safely extracts NetBox interface `type.value` | Drop-in |
| `normalize_ipv6` | Normalizes IPv6 address text for comparison | Drop-in |
| `collapse_vlan_list` | Collapses `[10,11,12,20]` → `"10-12,20"` | Drop-in |
| `select_interfaces_to_configure` | Smart interface selection for idempotent mode | Drop-in |
| `extract_ip_addresses` | Extracts IPv4/IPv6 from NetBox interface objects | Drop-in |
| `populate_ip_changes` | Builds `_ip_changes` structure for IP config | Drop-in |

`is_ipv4_address` and `is_ipv6_address` are re-exported by `l3_config_helpers.py` for convenience (same implementation, single source of truth in `utils.py`).

---

## Mostly Portable Filters (minor custom field / facts adaptation)

These filters are generic in logic but either reference NetBox custom field names chosen for this Aruba deployment, or include one or two functions that compare against AOS-CX-shaped device facts. To reuse the generic parts, rename the custom fields to match your NetBox schema, or drop the facts-dependent functions and keep the NetBox-only ones.

### `bgp_filters.py` — 4 of 8 functions are pure NetBox transforms

| Filter | Generic? | Notes |
|--------|----------|-------|
| `get_bgp_session_vrf_info` | Yes | Enriches BGP sessions with `_vrf`/`_af` by cross-referencing interface IPs — NetBox data only |
| `get_bgp_redistribute_config` | Yes | Flattens the `bgp_redistribute` config_context into `(vrf, af, protocol)` entries — generic routing concepts (`connected`, `static`, `ospf`, `ospfv3`, `rip`) |
| `get_bgp_neighbor_options_config` | Mostly | Flattens `bgp_neighbor_options` into per-neighbor CLI option strings; the reserved-keyword skip list (`remote-as`, `route-map`, `activate`, ...) reflects AOS-CX CLI grammar used elsewhere in this role's BGP tasks |
| `get_bgp_bfd_enabled` | Yes | Pure NetBox-derived boolean (no device facts) |
| `collect_ebgp_vrf_policy_config` | No | Builds AOS-CX CLI route-map/prefix-list command text |
| `get_stale_bgp_redistribute` | No | Parses AOS-CX `show running-config` text (`running_config` param) to find stale redistribution lines |
| `get_stale_bgp_neighbor_options` | No | Same — parses AOS-CX running-config text |
| `get_stale_bgp_bfd` | No | Same — parses AOS-CX running-config text |

**Requires** (for the portable functions): NetBox BGP plugin, BGP sessions with `local_address` field.

**Minor assumption**: The built-in VRF set (`mgmt`, `MGMT`, `Global`, `global`, `Default`, `default`) normalizes to `'default'`. This list covers Aruba, Cisco IOS-XE, Cisco NX-OS, Juniper, and most other vendors. Extend `_BUILTIN_VRFS` in `bgp_filters.py` if your vendor uses a different name.

**To port the `get_stale_*` / `collect_ebgp_vrf_policy_config` functions**: the *what changed* logic (diff desired vs. actual) is reusable; the CLI text they read or emit is AOS-CX syntax and needs rewriting per vendor.

### `vrf_filters.py` — 6 of 8 functions are pure NetBox transforms

All core VRF operations work on standard NetBox VRF, interface, and IP address objects.

| Filter | Generic? | Notes |
|--------|----------|-------|
| `extract_interface_vrfs` | Yes | Standard NetBox `vrf` field |
| `filter_vrfs_in_use` | Yes | Standard filtering |
| `get_vrfs_in_use` | Yes | Excludes built-in VRFs |
| `filter_configurable_vrfs` | Yes | Excludes built-in VRFs |
| `get_all_rt_names` | Yes | Standard NetBox RT objects |
| `build_vrf_rt_config` | Minor | Reads `custom_fields.address_family` — rename this field to match your NetBox schema if different |
| `get_vrf_rt_removals` | Partial | Diff algorithm is generic; reads AOS-CX REST facts (`aoscx_vrf_rt_facts`) for device-side state |
| `get_vrf_changes` | Partial | Diff algorithm is generic; reads AOS-CX REST facts (`aoscx_vrf_facts`, `aoscx_vrf_rt_facts`) |

**Built-in VRF exclusion list**: `mgmt`, `MGMT`, `Global`, `global`, `default`, `Default` — covers most vendors. Add your vendor's management VRF if it differs.

**To port `get_vrf_rt_removals` / `get_vrf_changes`**: replace the facts-parsing section with your vendor's facts module output format; both functions already fall back to "push everything" when facts are `None`, which is a reasonable default for a first port.

### `interface_categorization.py` — Both functions

Both `categorize_l2_interfaces` and `categorize_l3_interfaces` operate on standard NetBox L2/L3 interface fields (`mode`, `untagged_vlan`, `tagged_vlans`, `type`, `vrf`).

**One Aruba-specific detail**: MCLAG interfaces are detected via `custom_fields.if_mclag`. This is an Aruba custom field. For other vendors:
- If your vendor uses a different custom field for MCLAG/LAG-pairing: rename `if_mclag` to your field name in the source
- If your vendor doesn't use MCLAG: MCLAG categories simply return empty lists — no harm done

**L2 mode naming** (`access`, `tagged`, `tagged-all`) maps directly to NetBox's own mode field, which is vendor-neutral.

### `interface_ip_processing.py` — `get_interface_ip_addresses`

Matches NetBox IP address objects to their parent interfaces and extracts IP role metadata.

**One Aruba-specific detail**: Reads `custom_fields.if_anycast_gateway_mac` to extract the anycast/active-gateway MAC address. For other vendors:
- If you don't use anycast gateways: the field simply returns `None` — no harm done
- If your vendor uses a different custom field name for anycast MACs: rename the field reference

### `ospf_filters.py` — 6 of 8 functions are NetBox-only

| Filter | Generic? | Notes |
|--------|----------|-------|
| `select_ospf_interfaces` | Minor | Reads `custom_fields.if_ip_ospf_1_area` — rename to your custom field |
| `extract_ospf_areas` | Minor | Depends on `select_ospf_interfaces` |
| `get_ospf_interfaces_by_area` | Minor | Depends on `select_ospf_interfaces` |
| `normalize_ospf_vrfs` | Yes | Pure config_context shape normalization, no device facts or custom fields |
| `filter_ospf_vrfs_in_use` | Yes | Pure NetBox/interface data comparison |
| `validate_ospf_config` | No | Reads `device_ospf_1_routerid` and Aruba-specific OSPF device config structure |
| `get_ospf_router_changes` | Partial | Diff algorithm generic; reads AOS-CX REST facts (`aoscx_ospf_router_facts`) |
| `get_ospf_interface_changes` | Partial | Diff algorithm generic; reads AOS-CX REST facts (`aoscx_ospf_interface_facts`, `aoscx_ospf_router_facts`) |

The custom field suffix `_1` in `if_ip_ospf_1_area` represents OSPF instance 1. If you model OSPF differently in NetBox (e.g., via interface service assignments or a different custom field name), update the one field name lookup in `select_ospf_interfaces`.

---

## Partially Portable Filters

### `vlan_filters.py`

| Filter | Portable? | Notes |
|--------|-----------|-------|
| `extract_vlan_ids` | **Yes** | Pure NetBox interface fields |
| `filter_vlans_in_use` | **Yes** | Generic VLAN ID matching |
| `get_vlans_in_use` | **Yes** | Generic NetBox VLAN/interface data (optional `port_access` merge is additive, not required) |
| `get_vlan_interfaces` | **Yes** | Detects VLAN/SVI interfaces by name prefix and type |
| `parse_vlan_id_spec` | **Yes** | Pure string/int VLAN-ID range parsing, no NetBox or device dependency |
| `filter_out_vlan_groups` | **Yes** | Pure NetBox VLAN group filtering |
| `extract_port_access_vlan_ids` | **Yes** | Pure config_context parsing; the *source* dict (`port_access`) models an AOS-CX-specific feature, but the ID-extraction logic itself is generic |
| `get_vlans_needing_changes` | **Partial** | Compares against device facts; facts structure is Aruba-specific |
| `get_vlans_needing_igmp_update` | **Partial** | Custom field `vlan_ip_igmp_snooping` is a generic concept; compares against AOS-CX enhanced facts |
| `get_vlans_needing_voice_update` | **Partial** | Custom field `vlan_voice_vlan` is a generic concept; compares against AOS-CX enhanced facts |
| `get_vlans_needing_name_update` | **Partial** | Compares desired name/description against AOS-CX device facts |
| `extract_evpn_vlans` | **No** | Reads `custom_fields.vlan_noevpn` (Aruba custom field) and `l2vpn_termination` structure |
| `extract_vxlan_mappings` | **No** | Reads `l2vpn_termination.l2vpn.identifier` for VNI; closely tied to Aruba's L2VPN model in NetBox |
| `parse_evpn_evi_output` | **No** | Parses AOS-CX CLI `show evpn ...` output text |

**For the `get_vlans_needing_*` family**: the comparison logic is sound, but the device facts side expects a specific structure returned by `arubanetworks.aoscx.aoscx_facts` / `aoscx_enhanced_vlan_facts`. Replace the facts parsing section with your vendor's facts module output format.

**For `extract_evpn_vlans` / `extract_vxlan_mappings`**: The EVPN/VXLAN VNI mapping logic is tied to how this deployment models L2VPNs in NetBox. If your NetBox models VNIs differently (e.g., via custom fields or a different L2VPN plugin structure), these need rewriting. The *concept* is portable; the field access paths are not.

### `l3_config_helpers.py`

| Filter | Portable? | Notes |
|--------|-----------|-------|
| `is_ipv4_address` | **Yes** | Re-exported from `utils.py`; generic IP version check |
| `is_ipv6_address` | **Yes** | Re-exported from `utils.py`; generic IP version check |
| `get_interface_vrf` | **Yes** | Generic NetBox interface VRF extraction |
| `group_interface_ips` | **No** | Groups per-IP list into per-interface; concept is generic but tightly paired with AOS-CX config flow (OSPF facts, DHCP-relay/description change flags) |
| `format_interface_name` | **No** | AOS-CX CLI specific: adds space for LAG ("lag1" → "lag 1") and loopback ("loopback0" → "loopback 0") |
| `build_l3_config_lines` | **No** | Generates AOS-CX CLI commands (`vrf attach`, `active-gateway`, `l3-counters`, `ip ospf`, `ip helper-address`) |
| `should_add_interface_ip` | **No** | Decision logic is tightly coupled to the `_ip_changes` structure produced by AOS-CX-facts-based change detection |
| `build_l3_config_preview` | **No** | Debug wrapper around the AOS-CX CLI builders above |

The generic helpers (`is_ipv4_address`, `is_ipv6_address`, `get_interface_vrf`) are straightforward utilities. The AOS-CX specific filters would need full replacement for other vendors — though the grouping concept in `group_interface_ips` is reusable as-is if the CLI builder is rewritten for the target vendor.

---

## AOS-CX Specific Filters (not portable without major rewriting)

### `comparison.py`

Both filters read AOS-CX-specific device facts:
- Field names like `vlan_mode`, `applied_vlan_mode`, `vlan_tag`, `applied_vlan_tag`, `vlan_trunks`, `applied_vlan_trunks` come from the AOS-CX REST API
- VLAN mode values (`access`, `native-tagged`, `native-untagged`) are AOS-CX terminology
- The comment "vlan_tag is a dict like `{'10': '/rest/v10.09/system/vlans/10'}`" shows the tight coupling to AOS-CX REST API URL patterns

**To port**: Rewrite the device facts parsing sections for your vendor's facts format. The comparison *algorithm* (what to add, what to remove) is generic and reusable.

### `interface_change_detection.py` and `interface_ip_comparisons.py`

The IPv4/IPv6/VRF/encapsulation/anycast/DHCP-relay comparison logic lives in
`interface_ip_comparisons.py` (`compute_l3_ip_changes()`,
`compute_dhcp_relay_changes()` — internal helpers called by
`get_interfaces_needing_config_changes()`, not separately registered
filters); both modules are deeply coupled to AOS-CX:
- Admin state detection reads `user_config.admin`, `forwarding_state.enablement`, `admin_state` — AOS-CX REST API fields
- LAG detection reads AOS-CX's `interfaces` sub-dict with `line_card` keys
- VLAN comparison reads AOS-CX-specific mode/tag/trunk field names
- Sub-interface encapsulation comparison reads `subintf_vlan` — AOS-CX REST API field
- VSX virtual IP comparison reads `vsx_virtual_ip4`, `vsx_virtual_ip6` — Aruba VSX feature
- DHCP relay comparison reads `aoscx_dhcp_relay_facts` — AOS-CX REST API shape
- Enhanced facts handling is coupled to AOS-CX REST API `depth=2` response format

**To port**: The *change detection concept* is fully reusable — compare NetBox intent with device state and output only what needs changing. The implementation would need new device-facts parsers written for your vendor's facts module output.

### `interface_orphans.py`

`get_virtual_interfaces_to_delete` finds device-side VLAN SVI / loopback / sub-interface objects that are no longer referenced in NetBox, so they can be cleaned up before a duplicate-IP conflict occurs.

- The interface-type regexes (`^vlan[0-9]+$`, `^loopback[0-9]+$`, `\S+\.[0-9]+$`) match AOS-CX naming conventions
- The `device_interfaces` argument is expected in AOS-CX facts' keyed-by-name shape

**To port**: The regexes and comparison logic are simple enough to adapt directly — update them to match your vendor's interface naming convention and facts shape.

### `static_route_filters.py`

`get_static_route_changes` exists specifically because `arubanetworks.aoscx.aoscx_static_route` is not idempotent (pyaoscx always deletes and recreates the route's next-hop on every `state: create` call). It reads `aoscx_static_route_facts` (AOS-CX REST API shape) to pre-compute the create/update/delete diff.

**To port**: If your vendor's route module *is* idempotent, you likely don't need this filter at all — push desired routes directly. If it isn't, the diff algorithm (compare desired vs. actual per VRF/prefix) is reusable; only the facts-parsing section is AOS-CX specific.

### `stp.py`

`stp_global_config_diff` and `stp_interface_changes` compare NetBox custom fields (`if_stp_bpdu_filter`, `if_stp_bpdu_guard`, `if_stp_edge_port`, `if_stp_root_guard`, plus the global `mstp_config_name`/`mstp_config_revision`/`mstp_priority` config_context keys) against AOS-CX REST facts (`aoscx_stp_global_facts`, `aoscx_enhanced_interface_facts[...].stp_config`) and emit AOS-CX CLI lines (`spanning-tree bpdu-filter`, etc.).

**To port**: Spanning Tree itself is a standard, vendor-neutral protocol — the *concept* (four boolean per-interface toggles plus global MSTP identity) ports cleanly. The device-facts field names and CLI command text are AOS-CX specific and need rewriting per vendor.

### `port_access.py` and `port_access_orphans.py`

Port-access (device-profiles, roles, LLDP groups) is an AOS-CX-specific feature for dynamic port configuration — there is no equivalent concept in most other vendors' NetBox data model, so these modules don't have a "generic core" to extract. `port_access_diff` compares the desired `port_access` config_context against `aoscx_port_access_facts`; `port_access_orphans` finds device-side device-profiles/roles/LLDP-groups no longer referenced in NetBox.

**To port**: Only worth doing if your target vendor has an equivalent dynamic-port-profile feature. Otherwise, drop both modules — nothing else in the library depends on them.

### `vsx.py`

`vsx_config_diff` compares NetBox config_context desired state against `aoscx_vsx_facts` (`device_role`, `system_mac`, `isl_port`, `keepalive_vrf`, `keepalive_src_ip`, `keepalive_peer_ip`). VSX is Aruba's dual-chassis MLAG technology.

**To port**: Other vendors have analogous technologies (Cisco vPC, Juniper MC-LAG/ESI-LAG, Arista MLAG) with a similar shape (ISL/peer-link, keepalive/peer IPs, role) — the *concept* transfers, but every field name and the facts REST shape would need a full rewrite for the target vendor's module.

---

## How to Reuse in a New Role

### Option 1: Copy the library as-is

Copy the entire `filter_plugins/` directory to your new role. The generic filters will work immediately. The Aruba-specific ones will have no effect (empty results) or need adaptation.

```
your-role/
└── filter_plugins/
    ├── netbox_filters.py         # Register only the filters you use
    └── netbox_filters_lib/
        ├── utils.py              # Works as-is
        ├── bgp_filters.py        # Mostly works as-is (drop the get_stale_* / collect_ebgp_vrf_policy_config CLI builders)
        ├── vrf_filters.py        # Works as-is (minor: custom field names; drop get_vrf_rt_removals/get_vrf_changes if no equivalent facts)
        ├── interface_categorization.py  # Works as-is (remove if_mclag if not used)
        ├── vlan_filters.py       # Use extract_vlan_ids, filter_vlans_in_use, get_vlans_in_use, get_vlan_interfaces, parse_vlan_id_spec, filter_out_vlan_groups, extract_port_access_vlan_ids
        └── ospf_filters.py       # Update custom field name in select_ospf_interfaces; normalize_ospf_vrfs/filter_ospf_vrfs_in_use work as-is
```

### Option 2: Extract as a shared collection

If you manage multiple vendor roles, the portable filters are good candidates for a shared Ansible collection:

```
my_org.netbox_filters/
└── plugins/filter/
    ├── utils.py
    ├── bgp_filters.py             # NetBox-only functions only (see table above)
    ├── vrf_filters.py             # NetBox-only functions only
    └── vlan_utils.py              # extract_vlan_ids, filter_vlans_in_use, get_vlans_in_use, parse_vlan_id_spec only
```

Each vendor role then adds its own device-specific comparison and change-detection filters on top.

### Adapting Custom Field Names

All custom field references are single-line lookups. For example:

```python
# In interface_categorization.py — detect MCLAG
is_mclag = intf.get("custom_fields", {}).get("if_mclag", False)

# Change "if_mclag" to your vendor's custom field name, or remove the check entirely
is_mclag = intf.get("custom_fields", {}).get("your_field_name", False)
```

Search for `custom_fields` in the source to find all custom field accesses:

```bash
grep -n "custom_fields" netbox_filters_lib/*.py
```

---

## Custom Fields Used by This Role

For reference, here are all the NetBox custom fields this role relies on and what they represent (see [NetBox Integration](NETBOX_INTEGRATION.md) for the setup-oriented reference):

| Custom Field | Object Type | Purpose | Vendor Specific? |
|--------------|-------------|---------|-----------------|
| `if_mclag` | Interface | Marks interface as MCLAG member | Aruba VSX/MCLAG |
| `if_anycast_gateway_mac` | Interface | MAC for anycast/active-gateway | Aruba active-gateway |
| `if_ip_ospf_1_area` | Interface | OSPF area ID for instance 1 | Concept generic, naming Aruba |
| `if_ip_ospf_network` | Interface | OSPF network type override | Concept generic, naming Aruba |
| `if_ip_helper` | Interface | Enable DHCP relay (`ip helper-address`) | Concept generic, naming Aruba |
| `if_stp_bpdu_filter` | Interface | Enable/disable BPDU filter | Concept generic (standard STP), naming Aruba |
| `if_stp_bpdu_guard` | Interface | Enable/disable BPDU guard | Concept generic (standard STP), naming Aruba |
| `if_stp_edge_port` | Interface | PortFast/admin-edge equivalent | Concept generic (standard STP), naming Aruba |
| `if_stp_root_guard` | Interface | Enable/disable Root Guard | Concept generic (standard STP), naming Aruba |
| `device_ospf_1_routerid` | Device | OSPF router ID | Concept generic, naming Aruba |
| `vlan_noevpn` | VLAN | Exclude VLAN from EVPN | Aruba EVPN config |
| `vlan_ip_igmp_snooping` | VLAN | Enable/disable IGMP snooping | Concept generic, naming Aruba |
| `vlan_voice_vlan` | VLAN | Enable/disable voice VLAN | Concept generic, naming Aruba |
| `address_family` | VRF Route Target | Route target address family | Concept generic |

Custom fields with generic concepts can be renamed to match your organization's NetBox schema without changing filter logic.

---

## See Also

- [Filter Plugins Overview](FILTER_PLUGINS.md) - Complete filter reference
- [BGP Filters](filter_plugins/bgp_filters.md) - BGP session enrichment details
- [NetBox Integration](NETBOX_INTEGRATION.md) - NetBox setup and data modelling
