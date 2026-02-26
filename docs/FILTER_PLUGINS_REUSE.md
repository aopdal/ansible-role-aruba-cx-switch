# Filter Plugins: Reuse with Other Network Devices

Most filters in this library operate on **NetBox data** — not on device-specific facts. Since NetBox uses a vendor-neutral data model (interfaces, VLANs, VRFs, IP addresses, BGP sessions), many filters work unchanged or with minor adaptation for any network device type.

This document describes which filters are portable, which need adaptation, and which are Aruba AOS-CX specific.

---

## TL;DR: Portability Summary

| Module | Portability | Notes |
|--------|-------------|-------|
| `utils.py` | **Fully portable** | No device-specific logic |
| `bgp_filters.py` | **Fully portable** | Pure NetBox → enrichment |
| `vrf_filters.py` | **Fully portable** | Minor: custom field `address_family` |
| `interface_categorization.py` | **Mostly portable** | Minor: custom field `if_mclag` |
| `interface_ip_processing.py` | **Mostly portable** | Minor: custom field `if_anycast_gateway_mac` |
| `ospf_filters.py` | **Mostly portable** | Minor: custom fields `if_ip_ospf_1_*` |
| `vlan_filters.py` | **Partially portable** | 3 of 7 filters are generic |
| `l3_config_helpers.py` | **Partially portable** | 3 of 5 filters generic; CLI builders are AOS-CX |
| `comparison.py` | **AOS-CX specific** | Reads AOS-CX REST API facts structure |
| `interface_change_detection.py` | **AOS-CX specific** | Deep coupling to AOS-CX facts + VSX |

---

## Fully Portable Filters

These work without modification for any network device whose data comes from NetBox.

### `utils.py` — All 5 functions

| Filter | Description | Reuse |
|--------|-------------|-------|
| `_debug` | Debug output via `DEBUG_ANSIBLE=true` | Drop-in |
| `collapse_vlan_list` | Collapses `[10,11,12,20]` → `"10-12,20"` | Drop-in |
| `select_interfaces_to_configure` | Smart interface selection for idempotent mode | Drop-in |
| `extract_ip_addresses` | Extracts IPv4/IPv6 from NetBox interface objects | Drop-in |
| `populate_ip_changes` | Builds `_ip_changes` structure for IP config | Drop-in |

### `bgp_filters.py` — `get_bgp_session_vrf_info`

Enriches BGP sessions (from the NetBox BGP plugin) with `_vrf` and `_af` fields by cross-referencing interface IP assignments. The entire function operates on NetBox data only — it never touches device facts or device-specific structures.

**Requires**: NetBox BGP plugin, BGP sessions with `local_address` field.

**Works for**: Any device type where BGP sessions are modelled in NetBox.

**Minor assumption**: The built-in VRF set (`mgmt`, `MGMT`, `Global`, `global`, `Default`, `default`) normalizes to `'default'`. This list covers Aruba, Cisco IOS-XE, Cisco NX-OS, Juniper, and most other vendors. Extend `_BUILTIN_VRFS` in `bgp_filters.py` if your vendor uses a different name.

---

## Mostly Portable Filters (minor custom field adaptation)

These filters are generic in logic but reference NetBox custom field names that were chosen for this Aruba deployment. To reuse them, rename the custom fields in NetBox to match what the filter expects — or patch the one-line field lookup.

### `vrf_filters.py` — All 6 functions

All VRF operations work on standard NetBox VRF, interface, and IP address objects.

| Filter | Generic? | Notes |
|--------|----------|-------|
| `extract_interface_vrfs` | Yes | Standard NetBox `vrf` field |
| `filter_vrfs_in_use` | Yes | Standard filtering |
| `get_vrfs_in_use` | Yes | Excludes built-in VRFs |
| `filter_configurable_vrfs` | Yes | Excludes built-in VRFs |
| `get_all_rt_names` | Yes | Standard NetBox RT objects |
| `build_vrf_rt_config` | Minor | Reads `custom_fields.address_family` — rename this field to match your NetBox schema if different |

**Built-in VRF exclusion list**: `mgmt`, `MGMT`, `Global`, `global`, `default`, `Default` — covers most vendors. Add your vendor's management VRF if it differs.

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

### `ospf_filters.py` — 3 of 4 functions

| Filter | Generic? | Notes |
|--------|----------|-------|
| `select_ospf_interfaces` | Minor | Reads `custom_fields.if_ip_ospf_1_area` — rename to your custom field |
| `extract_ospf_areas` | Minor | Depends on `select_ospf_interfaces` |
| `get_ospf_interfaces_by_area` | Minor | Depends on `select_ospf_interfaces` |
| `validate_ospf_config` | No | Reads `device_ospf_1_routerid` and Aruba-specific OSPF device config structure |

The custom field suffix `_1` in `if_ip_ospf_1_area` represents OSPF instance 1. If you model OSPF differently in NetBox (e.g., via interface service assignments or a different custom field name), update the one field name lookup in `select_ospf_interfaces`.

---

## Partially Portable Filters

### `vlan_filters.py`

| Filter | Portable? | Notes |
|--------|-----------|-------|
| `extract_vlan_ids` | **Yes** | Pure NetBox interface fields |
| `filter_vlans_in_use` | **Yes** | Generic VLAN ID matching |
| `get_vlans_in_use` | **Yes** | Generic NetBox VLAN/interface data |
| `get_vlan_interfaces` | **Yes** | Detects VLAN/SVI interfaces by name prefix and type |
| `get_vlans_needing_changes` | **Partial** | Compares against device facts; facts structure is Aruba-specific |
| `extract_evpn_vlans` | **No** | Reads `custom_fields.vlan_noevpn` (Aruba custom field) and `l2vpn_termination` structure |
| `extract_vxlan_mappings` | **No** | Reads `l2vpn_termination.l2vpn.identifier` for VNI; closely tied to Aruba's L2VPN model in NetBox |

**For `get_vlans_needing_changes`**: The comparison logic is sound, but the device facts side (`ansible_network_resources.vlans`) expects a specific structure returned by `arubanetworks.aoscx.aoscx_facts`. Replace the facts parsing section with your vendor's facts module output format.

**For `extract_evpn_vlans` / `extract_vxlan_mappings`**: The EVPN/VXLAN VNI mapping logic is tied to how this deployment models L2VPNs in NetBox. If your NetBox models VNIs differently (e.g., via custom fields or a different L2VPN plugin structure), these need rewriting. The *concept* is portable; the field access paths are not.

### `l3_config_helpers.py`

| Filter | Portable? | Notes |
|--------|-----------|-------|
| `is_ipv4_address` | **Yes** | Generic IP version check |
| `is_ipv6_address` | **Yes** | Generic IP version check |
| `get_interface_vrf` | **Yes** | Generic NetBox interface VRF extraction |
| `format_interface_name` | **No** | AOS-CX CLI specific: adds space for LAG ("lag1" → "lag 1") |
| `build_l3_config_lines` | **No** | Generates AOS-CX CLI commands (`vrf attach`, `active-gateway`, `l3-counters`) |

The three generic helpers (`is_ipv4_address`, `is_ipv6_address`, `get_interface_vrf`) are straightforward utilities. The two CLI builders are purely AOS-CX and would need full replacement for other vendors.

---

## AOS-CX Specific Filters (not portable without major rewriting)

### `comparison.py`

Both filters read AOS-CX-specific device facts:
- Field names like `vlan_mode`, `applied_vlan_mode`, `vlan_tag`, `applied_vlan_tag`, `vlan_trunks`, `applied_vlan_trunks` come from the AOS-CX REST API
- VLAN mode values (`access`, `native-tagged`, `native-untagged`) are AOS-CX terminology
- The comment "vlan_tag is a dict like `{'10': '/rest/v10.09/system/vlans/10'}`" shows the tight coupling to AOS-CX REST API URL patterns

**To port**: Rewrite the device facts parsing sections for your vendor's facts format. The comparison *algorithm* (what to add, what to remove) is generic and reusable.

### `interface_change_detection.py`

The main function `get_interfaces_needing_config_changes` is deeply coupled to AOS-CX:
- Admin state detection reads `user_config.admin`, `forwarding_state.enablement`, `admin_state` — AOS-CX REST API fields
- LAG detection reads AOS-CX's `interfaces` sub-dict with `line_card` keys
- VLAN comparison reads AOS-CX-specific mode/tag/trunk field names
- VSX virtual IP comparison reads `vsx_virtual_ip4`, `vsx_virtual_ip6` — Aruba VSX feature
- Enhanced facts handling is coupled to AOS-CX REST API `depth=2` response format

**To port**: The *change detection concept* is fully reusable — compare NetBox intent with device state and output only what needs changing. The implementation would need new device-facts parsers written for your vendor's facts module output.

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
        ├── bgp_filters.py        # Works as-is
        ├── vrf_filters.py        # Works as-is (minor: custom field names)
        ├── interface_categorization.py  # Works as-is (remove if_mclag if not used)
        ├── vlan_filters.py       # Use extract_vlan_ids, filter_vlans_in_use, get_vlans_in_use
        └── ospf_filters.py       # Update custom field name in select_ospf_interfaces
```

### Option 2: Extract as a shared collection

If you manage multiple vendor roles, the portable filters are good candidates for a shared Ansible collection:

```
my_org.netbox_filters/
└── plugins/filter/
    ├── utils.py
    ├── bgp_filters.py
    ├── vrf_filters.py
    └── vlan_utils.py             # extract_vlan_ids, filter_vlans_in_use, get_vlans_in_use only
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
grep -n "custom_fields" filter_plugins/netbox_filters_lib/*.py
```

---

## Custom Fields Used by This Role

For reference, here are all the NetBox custom fields this role relies on and what they represent:

| Custom Field | Object Type | Purpose | Vendor Specific? |
|--------------|-------------|---------|-----------------|
| `if_mclag` | Interface | Marks interface as MCLAG member | Aruba VSX/MCLAG |
| `if_anycast_gateway_mac` | Interface | MAC for anycast/active-gateway | Aruba active-gateway |
| `if_ip_ospf_1_area` | Interface | OSPF area ID for instance 1 | Concept generic, naming Aruba |
| `device_ospf_1_routerid` | Device | OSPF router ID | Concept generic, naming Aruba |
| `vlan_noevpn` | VLAN | Exclude VLAN from EVPN | Aruba EVPN config |
| `address_family` | VRF/RT | Route target address family | Concept generic |

Custom fields with generic concepts can be renamed to match your organization's NetBox schema without changing filter logic.

---

## See Also

- [Filter Plugins Overview](FILTER_PLUGINS.md) - Complete filter reference
- [BGP Filters](filter_plugins/bgp_filters.md) - BGP session enrichment details
- [NetBox Integration](NETBOX_INTEGRATION.md) - NetBox setup and data modelling
