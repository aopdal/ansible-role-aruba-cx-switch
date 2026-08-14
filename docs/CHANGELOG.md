# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- `meta/main.yml`: `min_ansible_version` corrected from `2.18` to `2.19` to
  match the `ansible-core>=2.19.10,<2.20.0` pin already in `requirements.txt`
  (required by arubanetworks.aoscx 4.5.1). Also added `ansible.utils` and
  `ansible.netcommon` to the `collections` dependency list.
- `requirements.yml`: `ansible.utils` raised to `>=6.0.0`; added
  `ansible.netcommon >=8.0.0` (provides the `network_cli` connection plugin
  used by `aoscx_config`/`aoscx_command` tasks).
- `requirements.txt`: added `ansible-lint` (unpinned) alongside the existing
  `ansible-core` pin.

### Documentation

- General documentation review: added `docs/STP_CONFIGURATION.md`,
  `docs/PORT_ACCESS_CONFIGURATION.md`, and `docs/VSX_CONFIGURATION.md` —
  STP and port-access previously had no dedicated topic page at all; VSX had
  only a `README.md` section, inconsistent with every other feature of
  comparable size (BGP/OSPF/static-routes/EVPN-VXLAN).
- Linked 10 previously-orphaned doc pages (unreachable from both
  `README.md` and `docs/README_DOCS.md`) into `docs/README_DOCS.md`:
  `FILTER_PLUGINS_REUSE.md`, `AUTOMATION_ECOSYSTEM_DIAGRAMS.md`,
  `GITHUB_ACTIONS_DEPLOYMENT.md`, `REQUIREMENTS.md`, `ANYCAST_GATEWAY.md`,
  `CONTRIBUTING.md`, `L2_INTERFACE_MODES.md`, `EXAMPLES.md`,
  `TEMPLATE_CONFIGURATION.md`, `ANSIBLE_CACHE_DIRECTORY.md`. Added
  `TEMPLATE_CONFIGURATION.md` and the three new pages to `mkdocs.yml` nav
  (`TEMPLATE_CONFIGURATION.md` was previously in neither the index nor the
  nav — invisible on the built docs site).
- Added STP/Port-Access/VSX rows to `CLAUDE.md` §4.5's doc-update table.
- Trimmed `docs/CODE_AUDIT.md` from a 39KB, 20-finding audit report (19 of
  20 findings already resolved) down to the one still-open finding plus a
  one-line-per-finding resolved log; full history remains in git.
- Fixed a wrong custom-field name in `docs/NETBOX_INTEGRATION.md`'s VSX
  walkthrough (`device_vsx_enabled` → `device_vsx`, matching what
  `tasks/main.yml` actually gates on — following the old walkthrough
  verbatim would have created a custom field the role never reads).
- Removed the placeholder Ansible Galaxy badge (`.../role/XXXXX`) from
  `README.md` — the role isn't published to Galaxy yet.
- `docs/AUTOMATION_ECOSYSTEM.md`: added STP/port-access/static-routes and
  the `device_ospf`/`device_anycast_gateway` custom fields to the
  feature/flag lists (present in code, missing from the doc).

### Known issues (found during the documentation review, not yet fixed)

- **`configure_port_access_mac_group.yml` is dead code.** AOS-CX
  port-access `mac_groups` has a task file to push it, and
  `netbox_filters_lib/port_access.py`'s docstrings reference it, but
  `configure_port_access.yml` never includes the task, and
  `port_access_diff`/`port_access_facts_from_device_profiles` don't
  compare/flatten `mac_groups` either. Setting `mac_groups` or
  `associate_mac_group` in the `port_access` config_context currently has
  no effect. Documented in `docs/PORT_ACCESS_CONFIGURATION.md`.
- **VSX `vsx_isl_lag` vs. `vsx_isl_port` inconsistency.**
  `tasks/configure_vsx.yml`'s live `aoscx_vsx` push reads only
  `vsx_isl_port` (default `lag256`); `vsx_config_diff`'s idempotency
  comparison and `templates/vsx.j2`'s ZTP output both use `vsx_isl_lag`
  instead. Setting only `vsx_isl_lag` (as this role's docs previously
  showed) can silently push the wrong ISL port and never converge to "no
  changes". `templates/vsx.j2` line 5 also checks
  `'lag' in vsx_keepalive_src` (a source IP) where it almost certainly
  meant to check `vsx_isl_lag`. Documented in `docs/VSX_CONFIGURATION.md`.

## [0.14.0] - 2026-08-12

### Removed

- `aoscx_fast_mode` variable (deprecated in v0.7.0, 2026-03-28). The runtime deprecation warning at the top of `tasks/main.yml` and the variable declaration in `defaults/main.yml` are both gone. `docs/PERFORMANCE_OPTIMIZATION.md` already described the variable as removed. Users who still set `aoscx_fast_mode` in inventory will get an Ansible "variable defined but not used" state (silent no-op) - the same behaviour they got while it was deprecated. Use `aoscx_gather_facts_rest_api: true` for genuine fact-gathering speedup (audit finding M1).

### Security

- Five tasks that touch secrets gated `no_log` on the `aoscx_no_log` role variable (default `true`), which meant a user setting `aoscx_no_log: false` for debugging would then leak those secrets on the next production run. All five now hardcode `no_log: true`: `tasks/configure_bgp.yml` lines 26 / 84 / 97 (NetBox API calls carrying the `NETBOX_TOKEN` in the `Authorization` header) and line 708 (AOS-CX REST login POSTing username/password), and `tasks/gather_facts_rest_api.yml` line 194 (same AOS-CX REST login pattern). Every other `no_log` in the role was already correctly hardcoded (OSPF MD5 key push in `tasks/configure_ospf.yml`, REST login/logout and credential `set_fact` blocks in `tasks/gather_facts_rest_api.yml` and the BGP cleanup block in `tasks/configure_bgp.yml`). No task carrying a secret was missing `no_log` altogether. New rule captured in `CLAUDE.md` §4.2 (audit finding T9).

### Deprecated

- `aoscx_no_log` (default `true`) is deprecated and has no runtime effect - every task in the role that touches a secret now hardcodes `no_log: true` (see the Security entry above). The variable is retained in `defaults/main.yml` for backward compatibility with existing inventories that set it; setting it in inventory is now a no-op.

### Changed

- Extracted two deeply nested Jinja blocks from `tasks/configure_l3_interfaces.yml` into pure filter functions in `netbox_filters_lib/l3_config_helpers.py`: `should_add_interface_ip(interface, address)` replaces the 5-deep `_needs_add` ternary inline in the `Process each interface with IPs` `set_fact` (VRF-change short-circuit, IPv4 diff-list check, IPv6 with/without enhanced facts — semantics preserved exactly), and `build_l3_config_preview(l3_interfaces, aoscx_builtin_vrfs, l3_counters_enable=True)` replaces the ~15-line `_l3_config_preview` Jinja that constructs the per-interface config-lines dict for the debug preview. Both are also registered as Ansible filters. The `Process each interface with IPs` task's `_needs_add` line is now `{{ item.0 | should_add_interface_ip(item.1.address) }}` and the `Build L3 config lines preview` task's body is a single filter call. 25 new unit tests (13 for `should_add_interface_ip`, 12 for `build_l3_config_preview`) cover the extracted logic; total suite 687 → 712 (audit finding T3).
- Collapsed the five L3 wrapper task files (`tasks/configure_l3_physical.yml`, `configure_l3_lag.yml`, `configure_l3_loopback.yml`, `configure_l3_vlan.yml`, `configure_l3_subinterface.yml`) into a single `include_tasks` loop at the bottom of `tasks/configure_l3_interfaces.yml`. The loop iterates over 10 records (`physical|subinterface|vlan|lag|loopback` × `default|custom VRF`) and passes `interface_list`, `interface_type`, `vrf_type` into `configure_l3_interface_common.yml` per iteration. Include order (physical → subinterface → vlan → lag → loopback) and the loopback-by-VRF split (`selectattr`/`rejectattr` on `aoscx_builtin_vrfs`) are preserved. The outer loop variable is renamed to `_l3_cat` (via `loop_control.loop_var`) because Ansible propagates the outer `when:` clause into every task inside the included file; the inner `aoscx_config` task in `configure_l3_interface_common.yml` has its own `loop: _grouped_interfaces` that would otherwise shadow `item` with per-interface dicts and cause the propagated `when` to fail with `'dict' has no attribute 'list'` at runtime. Removes ~70 LOC of copy-paste scaffolding (audit finding T1).
- Collapsed `tasks/configure_l2_lag.yml` and `tasks/configure_l2_mclag.yml` into a single parameterized `tasks/configure_l2_lag_common.yml`. The two files differed only in the CLI parent-interface suffix (`interface lag X` vs. `interface lag X multi-chassis`) and the `l2_interfaces` source-list prefix (`lag_*` vs. `mclag_*`); the common file takes `l2_lag_kind` (`lag`/`mclag`) and `l2_lag_parent_suffix` (`''` / `' multi-chassis'`) as inputs, and `tasks/configure_l2_interfaces.yml` now includes it twice with different `vars:`. `tasks/configure_l2_physical.yml` is intentionally unchanged - it uses the declarative `arubanetworks.aoscx.aoscx_l2_interface` module rather than `aoscx_config` CLI, so unifying it would regress from a proper module to raw CLI. Removes ~85 LOC of copy-paste (audit finding T2). The mermaid diagram in `docs/L2_INTERFACE_MODES.md` was updated accordingly.
- Replaced the ``"'<feature>' in ansible_run_tags or 'routing' in ansible_run_tags or 'all' in ansible_run_tags"`` guards on the OSPF-identify, OSPF-config, static-routes, BGP, and VSX includes in `tasks/main.yml` with Ansible-native tag narrowing. The five `when:` lines are gone; OSPF, BGP, and static-routes includes drop `layer3` from `apply.tags` and their outer `tags:` list, so a broad `-t layer3` run still leaves routing protocols alone — the exact protection the old string matching provided. VSX had no broader tag to worry about and just loses the redundant check. Behavior is unchanged for a bare run, `-t vlans`, `-t <feature>`, `-t routing`, and `-t ha`; the only tag whose semantics change is `-t layer3`, which now runs L3 interface config only, via Ansible's own tag filter instead of a role-level check. `docs/TAG_DEPENDENT_INCLUDES.md` was rewritten to describe the new mechanism (audit finding T6).
- Consolidated duplicated normalization helpers into `netbox_filters_lib/utils.py`: `is_ipv4_address` / `is_ipv6_address` (previously in `l3_config_helpers.py`, also inlined as ``":" in addr`` across ~15 sites), `get_interface_type_value` (extracts NetBox's `type.value` handling dict / bare-string / missing / non-dict input, previously ~12 duplicated blocks), and `normalize_ipv6` (moved out of `interface_change_detection.py`). `l3_config_helpers.py` re-exports the ipv4/ipv6 helpers so the public filter API is unchanged; `interface_change_detection.py` imports `normalize_ipv6 as _normalize_ipv6` so internal call sites keep their original names. Consumers updated: `interface_categorization.py`, `interface_change_detection.py`, `interface_ip_processing.py`, `comparison.py`, `vlan_filters.py`, `bgp_filters.py`. Side effects: `get_interface_type_value` now returns the string when NetBox serialises `type` as a bare string (previously all consumers returned `None` in this case) - real NetBox always returns the dict form, so the change is defensive; one test was updated accordingly. `port_access.py`'s `_norm_str` / `_norm_int` are port-access-specific comparison helpers with no duplicates elsewhere and are intentionally left alone. 22 new unit tests in `tests/unit/test_utils.py` cover the four new helpers; total unit-test count 665 → 687 (audit finding F3).
- Extracted the duplicated OSPF interface block (area / network / passive / MD5 auth, ~20 lines each) and the duplicated `ip helper-address` block from `templates/int_phys.j2` (twice), `templates/int_lag.j2` and `templates/int_vlan.j2` into a new `templates/_macros_interface.j2` (`ospf_interface(intf)` and `ip_helpers(intf)`), imported `with context` so caller-scoped globals (`ospf_process_id`, `ospf_auth_keys`, `ospf_auth_key_id`, `ip_helper_addresses`) remain visible. `templates/int_loopback.j2` is intentionally left alone: loopbacks emit a simpler 3-line OSPF snippet without passive/network-type/auth. Rendered CLI commands are byte-identical before/after across six synthetic interface fixtures (physical L3+OSPF+helpers, physical L2 access, LAG L3, MCLAG L2 tagged, VLAN SVI with anycast, loopback); the macro-call sites do add 1-3 cosmetic blank lines per template in the generated output, which does not affect device behavior since these templates only run under `aoscx_generate_template_config: true` and are treated as starting-point configs (audit findings J1 + J4).
- All `aoscx_config` invocations that previously overrode `ansible_connection` via `"{{ aoscx_connection_type }}"` (34 sites across `tasks/assign_interfaces_to_lag.yml`, `tasks/cleanup_l2_vlans.yml`, `tasks/cleanup_virtual_interfaces.yml`, `tasks/configure_l2_lag.yml`, `tasks/configure_l2_mclag.yml`, `tasks/configure_l3_interface_common.yml`, `tasks/configure_l3_interfaces.yml`, `tasks/configure_lag_interfaces.yml`, `tasks/configure_mclag_interfaces.yml`, `tasks/configure_physical_interfaces.yml`, `tasks/configure_stp.yml`, `tasks/configure_vrfs.yml`) now hardcode `ansible_connection: network_cli`. `aoscx_config` and `aoscx_command` are CLI-only modules, so the value of `aoscx_connection_type` was only ever safe when it resolved to `network_cli` - setting it to anything else broke those tasks, and honoring an inventory-level pyaoscx-REST default (e.g. `ansible_connection: arubanetworks.aoscx.aoscx` set from the NetBox `platform`) would have silently broken the same tasks. Inventory-level `ansible_connection` still controls every other AOS-CX module (`aoscx_facts`, `aoscx_vlan`, `aoscx_interface`, ...). The three `ansible.netcommon.network_cli` FQCN overrides in `tasks/configure_ospf.yml` were also normalized to the short form for consistency (audit finding T8).
- Split `netbox_filters_lib/interface_change_detection.py` (1376 lines, a
  single ~1180-line function): the IPv4/IPv6/VRF/encapsulation/anycast/
  DHCP-relay comparison logic moved to a new
  `netbox_filters_lib/interface_ip_comparisons.py` module as
  `compute_l3_ip_changes()` and `compute_dhcp_relay_changes()`, leaving
  `get_interfaces_needing_config_changes()` focused on orchestration
  (existence checks, physical/L2 property checks, categorization). Both new
  functions are pure - they return `(needs_change, change_reasons,
  ip_changes)` instead of writing `_ip_changes` directly onto the interface
  dict passed in, fixing the "filters must not mutate their inputs"
  violation flagged separately by the audit. `get_interfaces_needing_config_changes()`
  now shallow-copies each interface at the top of its per-interface loop
  (`nb_intf = dict(nb_intf)`) so the function no longer mutates the
  `interfaces` list the caller passed in; the merged `_ip_changes` result
  returned via `interface_changes.*` is unchanged, so no task-level
  behavior changes. 29 new unit tests in
  `tests/unit/test_interface_ip_comparisons.py` cover the extracted
  functions directly (previously only reachable end-to-end), plus 4
  regression tests in `tests/unit/test_interface_change_detection.py`
  asserting the caller's original interface objects are left untouched.
  No public filter signature or output changed (audit findings F4, F5).

### Deprecated

- `aoscx_connection_type` (default `network_cli`) is deprecated and has no runtime effect. The variable is retained in `defaults/main.yml` for backward compatibility with existing inventories that set it. Set `ansible_connection` directly in your inventory / group_vars to control the connection used by pyaoscx-backed modules (see the deprecation comment in `defaults/main.yml`). Existing playbook code will continue to work unchanged; setting `aoscx_connection_type` in inventory is now a no-op.

### Fixed

- `tasks/configure_dns.yml` gated `Configure DNS settings` and `Configure DNS name servers per VRF` on plain `dns_* is defined` checks. `is defined` returns `True` even when the variable is `null`, so a NetBox config_context that (for example) declares `dns_name_servers:` without a value crashed `dict2items` at runtime and setting `dns_domain_name: null` would push an empty `aoscx_dns` call. Both `when:` clauses now use explicit `| default(...) | length > 0` checks per variable shape (string vs. dict), and the `loop:` uses `dns_name_servers | default({}) | dict2items` so an undefined/null value evaluates to an empty loop instead of failing. Also brings the file in line with the `| length > 0` idiom used elsewhere in the role (audit finding T7). Note: audit T7's other two examples (`subinterface_parents_already_routed is not defined`, `aoscx_rest_api_version is not defined`) are scalar existence checks - `is (not) defined` on a scalar already returns a boolean and correctly expresses intent - and are intentionally left as-is.
- Interface templates (`templates/int_phys.j2`, `templates/int_lag.j2`, `templates/int_vlan.j2`, `templates/int_loopback.j2`) hardcoded the OSPF process ID as `1` when rendering `ip ospf 1 area <area>` for `aoscx_generate_template_config: true`, ignoring the `ospf_process_id` config-context value that the rest of the role (`templates/ospf.j2`, `netbox_filters_lib/l3_config_helpers.py:build_l3_config_lines`, `tasks/identify_ospf_changes.yml`, `tasks/gather_facts_rest_api.yml`) already respects. Templates now render `ip ospf {{ ospf_process_id | default(1) }} area <area>`, so a device with `ospf_process_id: 2` in NetBox config_context no longer gets the wrong process ID committed on the interface (audit finding J2). Note: the NetBox custom field name `if_ip_ospf_1_area` still encodes process ID 1 - renaming it to be process-ID-agnostic is tracked separately.

### Added

- New unit tests for `get_interface_ip_addresses()` (`netbox_filters_lib/interface_ip_processing.py`) in `tests/unit/test_interface_ip_processing.py`, covering empty/`None` inputs, interface-ID matching, `mgmt_only` skip, malformed IP objects, VRF resolution (named/dict-without-name/non-dict), IP role as dict vs. string, anycast MAC extraction from `custom_fields.if_anycast_gateway_mac`, and interface-type dict/string/missing variants. This was the only public filter without unit tests (audit finding F2).
- Code audit report (`docs/CODE_AUDIT.md`) covering `tasks/`, `filter_plugins/`, `netbox_filters_lib/`, `templates/`, `defaults/main.yml`, and `meta/main.yml` - inconsistencies, duplicate code, and suboptimal patterns with per-item priorities and a suggested remediation order.

### Changed

- `tasks/main.yml`: the `Include fact gathering tasks` step now uses the same `include_tasks: { file:, apply: { tags: [...] } }` shape as every other include in the file, so the `always`/`facts`/`gather` tags propagate to the tasks inside `gather_facts.yml` (audit finding T5). Previously it used the bare `include_tasks: gather_facts.yml` form, which does not propagate tags to sub-tasks.

### Removed

- Dead `FilterModule` class at the bottom of `netbox_filters_lib/l3_config_helpers.py`. `netbox_filters_lib/` is not on Ansible's filter plugin path (only `filter_plugins/` is), so the class was never loaded; the six functions it exposed are already re-exported from `filter_plugins/netbox_filters.py` (audit finding F1).
- Unreferenced `tasks/configure_loopback.yml`. It was not included from `tasks/main.yml` or any other task file, and its body (create loopbacks via `arubanetworks.aoscx.aoscx_interface`) duplicated what `tasks/configure_l3_interfaces.yml` → `tasks/configure_l3_loopback.yml` → `tasks/configure_l3_interface_common.yml` already does (audit finding T4).

## [0.13.28] - 2026-08-12

### Fixed

- Add extra lin in end of template to make copy and paste easier.

## [0.13.27] - 2026-08-11

### Added

- BGP redistribution (`redistribute connected`/`static`/`ospf`/`ospfv3`/`rip`) is now configurable via a new `bgp_redistribute` NetBox config_context key, per VRF and address family. This is not part of the netbox-bgp plugin's session data model, so without it BGP had no way to originate routes into eBGP sessions (e.g. towards an edge router) - neighbors would come up but nothing would be advertised. New `get_bgp_redistribute_config()` filter (`netbox_filters_lib/bgp_filters.py`) builds the desired state; `tasks/configure_bgp.yml` pushes it idempotently via `aoscx_config` (`match: line`). Removal of entries deleted from config_context is handled under `aoscx_idempotent_mode` by a new `get_stale_bgp_redistribute()` filter, which diffs the desired state against `show running-config` (there is no documented REST field for per-address-family redistribute state). See `docs/BGP_CONFIGURATION.md#bgp-redistribution`.
- Generic per-neighbor BGP options (e.g. `neighbor <ip> soft-reconfiguration inbound`) are now configurable via a new `bgp_neighbor_options` NetBox config_context key, keyed by neighbor IP. Like redistribution, this is not covered by the netbox-bgp plugin's session model. New `get_bgp_neighbor_options_config()` filter (`netbox_filters_lib/bgp_filters.py`) resolves each neighbor IP against live session data to determine its VRF/address-family and skips options for keywords already managed elsewhere in `tasks/configure_bgp.yml` (`remote-as`, `route-map`, `activate`, etc.), so it cannot conflict with those tasks; `tasks/configure_bgp.yml` pushes the result idempotently via `aoscx_config` (`match: line`). Removal of entries deleted from config_context is handled under `aoscx_idempotent_mode` by a new `get_stale_bgp_neighbor_options()` filter, sharing the same `show running-config` fetch used for redistribute cleanup. See `docs/BGP_CONFIGURATION.md#bgp-neighbor-options`.
- `bgp_neighbor_options` now also supports a `"general"` scope for options configured directly under `router bgp`/`vrf`, outside any address-family block (e.g. `neighbor <ip> fall-over bfd`), alongside the existing `"ipv4"`/`"ipv6"` address-family scopes. `get_bgp_neighbor_options_config()`/`get_stale_bgp_neighbor_options()` encode this with `af: null`, and `tasks/configure_bgp.yml` omits the `address-family <af> unicast` parent for those entries when pushing/removing them via `aoscx_config`.
- `neighbor <ip> fall-over bfd` has no effect on AOS-CX unless the global `bfd` command is also enabled (a top-level, switch-wide toggle - not nested under `router bgp`/`vrf` and not per-VRF). Rather than requiring a second config_context entry that could drift out of sync, new `get_bgp_bfd_enabled()` filter (`netbox_filters_lib/bgp_filters.py`) derives whether `bfd` is needed directly from any neighbor declaring `fall-over bfd` in the `"general"` scope of `bgp_neighbor_options`; `tasks/configure_bgp.yml` pushes the global `bfd` line alongside the neighbor options. Removal is handled under `aoscx_idempotent_mode` by a new `get_stale_bgp_bfd()` filter, sharing the same `show running-config` fetch used for redistribute/neighbor-option cleanup. See `docs/BGP_CONFIGURATION.md#bgp-neighbor-options`.

### Fixed

- `tasks/configure_ospf.yml` pushed `interface {{ item.interface_name }}` verbatim (e.g. `interface loopback0`) as the `parents` context for per-interface OSPF area/network-type/authentication and passive config. AOS-CX CLI requires a space before the loopback number (`interface loopback 0`), so the command silently entered an invalid/no-op context - `aoscx_config` reported `changed: true` and re-pushed identical commands on every run, but the OSPF area assignment never actually applied to the device (confirmed via REST OSPF interface facts and `show running-config`, neither of which ever showed the loopback under the area). `tasks/identify_ospf_changes.yml` now records an `interface_type` (`loopback`/`lag`/`physical`) per interface, and `configure_ospf.yml` formats the interface name with the existing `format_interface_name` filter (`netbox_filters_lib/l3_config_helpers.py`) before building `parents`, matching how L3 loopback/LAG interface names are already formatted elsewhere in the role.

## [0.13.26] - 2026-08-07

### Fixed

- REST API fact gathering (`tasks/gather_facts_rest_api.yml`) requested the unused `subintf_parent` interface attribute alongside `subintf_vlan`, causing `Query interfaces via REST API` to fail with `HTTP 400: invalid attribute: 'subintf_parent' for the resource 'Interface'` on switches whose REST API version does not expose that attribute (e.g. observed on `/rest/v10.16`). `subintf_parent` was never consumed by change detection - only `subintf_vlan` is used (see `netbox_filters_lib/interface_change_detection.py`) - so it is now dropped from the query.
- `subintf_vlan` itself was also unconditionally queried and is rejected the same way on platforms that don't support sub-interfaces at all - confirmed on a real CX 6200 VSF stack (`invalid attribute: 'subintf_vlan' for the resource 'Interface'`), which would have broken fact gathering for every device on that platform, not just ones with sub-interfaces. It's now only added to the query when NetBox defines at least one sub-interface (`parent` set) for the device, via a new `_rest_has_subinterfaces` check.

## [0.13.25] - 2026-08-06

### Added

- `get_interfaces_needing_config_changes()` (`netbox_filters_lib/interface_change_detection.py`) now always stores `_ip_changes.dhcp_relay_expected`/`_ip_changes.dhcp_relay_actual` (the desired vs. currently-configured `ip helper-address` servers) for any interface with `if_ip_helper=True`, not just interfaces flagged for a push. Previously this data was only populated on mismatch, so verification/report tooling (e.g. `autotest-aoscx`'s `report_interfaces.yml`) had no way to display ip helper state for interfaces that already matched NetBox.

## [0.13.24] - 2026-08-05

### Added

- New `aoscx_configure_vlans_all_exclude_vlan_groups` variable (default `[]`): excludes VLANs belonging to the given NetBox VLAN group slugs from the `aoscx_configure_vlans_all` "treat every available VLAN as in use" catalog. Fixes region-scoped VLAN groups (e.g. a dedicated linknet group) leaking onto every device in that region - including access switches - since NetBox's `available_on_device` returns VLANs scoped above the device's own site. New `filter_out_vlan_groups()` filter in `netbox_filters_lib/vlan_filters.py`. See `docs/VLAN_CHANGE_IDENTIFICATION_WORKFLOW.md#excluding-vlan-groups-from-configure-all-aoscx_configure_vlans_all_exclude_vlan_groups`.

### Fixed

- `aoscx_configure_vlans_all_exclude_vlan_groups` was only applied in `tasks/identify_vlan_changes.yml`, not in `tasks/gather_template_data.yml`'s independent, duplicated "treat all NetBox-available VLANs as in use" logic used when `aoscx_generate_template_config: true`. Template-based config generation (`templates/vlan.j2`, driven by `template_vlans_in_use`) therefore still rendered excluded VLAN groups (e.g. region-scoped linknet VLANs) on every device. `gather_template_data.yml` now applies the same `filter_out_vlan_groups()` filter as `identify_vlan_changes.yml`.

## [0.13.23] - 2026-08-03

### Fixed

- Sub-interface 802.1Q encapsulation VLAN drift was never detected: `get_interfaces_needing_config_changes()` (`netbox_filters_lib/interface_change_detection.py`) only ever emitted the `encapsulation dot1q <vid>` command as a side effect of an IP/description mismatch already being flagged, so a sub-interface with a correct IP/description but a *wrong* tagged VLAN (e.g. NetBox re-tags `1/1/1.701` from VLAN 701 to 702 without renaming the interface) silently passed as "no changes needed". The REST API attribute query (`tasks/gather_facts_rest_api.yml`) now also requests `subintf_vlan`/`subintf_parent`, and change detection compares the device's `subintf_vlan` (via `aoscx_enhanced_interface_facts`, requires `aoscx_gather_facts_rest_api: true`) against NetBox's `tagged_vlans[0].vid`, flagging a mismatch via the new `_ip_changes.encapsulation_change` flag so `configure_l3_interfaces.yml` re-pushes the correct encapsulation on the next run. See `docs/VIRTUAL_INTERFACE_CLEANUP.md#related-sub-interface-encapsulation-vlan-drift`.
- Every sub-interface was incorrectly flagged as needing changes even when fully in sync with NetBox: NetBox represents a sub-interface's 802.1Q tag using the same `mode`/`tagged_vlans` fields used for L2 trunk ports, but `get_interfaces_needing_config_changes()`'s L2 VLAN mode/membership check only excluded VLAN SVIs by name (`vlan*`), not sub-interfaces. Since AOS-CX never populates `vlan_mode`/`vlan_tag`/`vlan_trunks` for a sub-interface (it uses `subintf_vlan`/`encapsulation dot1q` instead, see above), this check always concluded "VLANs configured in NetBox but not on device" and marked the sub-interface `changed`, independent of whether the encapsulation VLAN actually matched. The L2 VLAN mode/membership check is now skipped for all virtual-type interfaces (VLAN SVIs, loopbacks, sub-interfaces), matching the exclusion already used for the admin/MTU check.

## [0.13.22] - 2026-08-03

### Added

- Idempotent-mode cleanup of orphaned virtual interfaces (VLAN SVIs, loopbacks, sub-interfaces) that exist on the device but are no longer present in NetBox, gated by the new `aoscx_cleanup_virtual_interfaces` variable (default `true`) alongside `aoscx_idempotent_mode`. Unlike the VLAN/EVPN/VXLAN cleanup tasks, this runs **before** `configure_l3_interfaces.yml` rather than after: if NetBox renames or re-parents an interface (e.g. an IP moved from `vlan10` to `vlan20`), the stale device-side object is never touched by L3 configuration and can hold the same IP address as its replacement, causing configuration to fail with a duplicate IP address. See `docs/VIRTUAL_INTERFACE_CLEANUP.md`.

## [0.13.21] - 2026-07-30

### Fixed

- The REST API "Build interface attributes query string" task (`tasks/gather_facts_rest_api.yml`) only requested the `vsx_virtual_ip4`/`vsx_virtual_ip6`/`vsx_virtual_gw_mac_v4`/`vsx_virtual_gw_mac_v6`/`ip4_address_secondary` attributes when `custom_fields.device_vsx` was `true` **and** `aoscx_configure_vsx` (or `aoscx_test_mode`) was `true`. `aoscx_configure_vsx` defaults to `false` and is commonly left off when only L3/anycast-gateway configuration is being pushed (VSX pairing config is a separate feature). Since AOS-CX's REST API omits attributes that were never requested — it does not return them as `null` — the anycast comparison in `netbox_filters_lib/interface_change_detection.py` saw no `vsx_virtual_ip4`/`vsx_virtual_ip6` at all and always concluded the anycast address was missing, even when it was already correctly configured on the device. This produced the same non-idempotent `changed: true` (re-pushing `active-gateway`, `vrf attach`, `description`, `l3-counters` every run) as the CIDR-prefix bug fixed in 0.13.20, but from a different root cause (missing REST attribute vs. mismatched format) that the 0.13.20 fix did not address. The VSX-attributes query is now also triggered when `custom_fields.device_anycast_gateway` is `true` and `aoscx_configure_l3_interfaces` (or `aoscx_test_mode`) is `true`, independent of `aoscx_configure_vsx`/`device_vsx`. The debug output (`-e aoscx_debug=true`) now also prints `Device anycast gateway enabled: <bool>` alongside the existing OSPF/VSX lines.

## [0.13.20] - 2026-07-30

### Fixed

- Anycast gateway IPv4 comparison (`netbox_filters_lib/interface_change_detection.py`) treated a device's `vsx_virtual_ip4` REST API value as an exact string match against the NetBox anycast address (always compared without a `/prefix`, since `active-gateway ip` takes no prefix). When the AOS-CX REST API returns `vsx_virtual_ip4` in CIDR form (e.g. `172.18.19.129/27`, mirroring how `ip4_address` is stored) instead of a bare address, the comparison never matched, so an SVI with an already-correctly-configured anycast gateway was reported as needing the `active-gateway ip mac` / `active-gateway ip` / `vrf attach` / `description` / `l3-counters` lines re-pushed on every run (non-idempotent `changed: true` with no actual drift). The device-side `vsx_virtual_ip4` value(s) are now stripped of any `/prefix` before comparison, matching the normalization the IPv6 side already had via `_normalize_ipv6`. (The IPv6 anycast comparison was not affected — it already normalizes prefixes on both sides.)

## [0.13.19] - 2026-07-22

### Fixed

- The `aoscx_configure_*`-gated `when` added to the "Query VRF route-target facts" and "Query static route facts" REST API tasks (`tasks/gather_facts_rest_api.yml`) is evaluated per loop item, since neither condition depends on the loop's `item`. When the flag was `false` and `aoscx_test_mode` unset, Ansible still looped over a non-empty item list (VRF names / static route VRFs) and marked each iteration skipped, producing a populated `results` list of skip stubs (no `status`/`json` keys) instead of an empty list. The downstream "Build VRF route-target facts"/"Build static route facts" tasks only checked `_rest_vrf_rts is defined`/`_rest_static_routes is defined` - true even for a skipped register - and then iterated those stubs, crashing with `object of type 'dict' has no attribute 'status'`. Fixed by adding the same `aoscx_configure_vrfs`/`aoscx_configure_static_routes` (or `aoscx_test_mode`) gate to the two "Build" tasks so they only run when the query actually executed for real. The equivalent OSPF interface/router "Build" tasks were not affected (their loop source is built by a separate `set_fact` that is itself skipped when the flag is off, yielding a genuinely empty loop rather than per-item stubs) but were given the same explicit gate as defense-in-depth. Also added the missing `aoscx_test_mode` OR-condition to the EVPN/VNI/port-access "Set facts" tasks, which required their `aoscx_configure_*` flag even when `aoscx_test_mode: true` had forced the corresponding query to run.

## [0.13.18] - 2026-07-22

### Added

- New `aoscx_test_mode` variable (default `false`, `defaults/main.yml`). REST API fact gathering (`tasks/gather_facts_rest_api.yml`) now skips a feature's queries (OSPF, VSX, static routes, VRFs/VRF route-targets, STP, EVPN, VXLAN, port-access, DHCP relay) in regular runs when that feature's `aoscx_configure_*` flag is `false`, since nothing downstream would consume the facts. Set `aoscx_test_mode: true` in test/report-only playbooks (e.g. `aruba-role-testing`) to force these queries regardless of the `aoscx_configure_*` flags, so device state can still be verified against NetBox intent without the role pushing configuration. See [docs/PERFORMANCE_OPTIMIZATION.md](docs/PERFORMANCE_OPTIMIZATION.md#selective-fact-gathering-with-aoscx_test_mode).

### Changed

- `aoscx_ospf_interface_facts`/`aoscx_ospf_router_facts`, `aoscx_vsx_facts`, `aoscx_stp_global_facts`, `aoscx_static_route_facts`, `aoscx_vrf_facts`/`aoscx_vrf_rt_facts`, and `aoscx_dhcp_relay_facts` REST API queries (`tasks/gather_facts_rest_api.yml`) are now also gated on their matching `aoscx_configure_*` flag (`aoscx_configure_ospf`, `aoscx_configure_vsx`, `aoscx_configure_stp`, `aoscx_configure_static_routes`, `aoscx_configure_vrfs`, `aoscx_configure_l3_interfaces`) unless `aoscx_test_mode: true` is set. This reverts the unconditional-gathering behaviour added in 0.13.17 for VRF facts (and extends the same pattern to the other feature facts) now that `aoscx_test_mode` gives test/report-only playbooks an explicit way to opt back in, instead of every regular run paying for REST calls whose results nothing consumes.

## [0.13.17] - 2026-07-20

### Changed

- `aoscx_vrf_facts`/`aoscx_vrf_rt_facts` REST API fact gathering (`tasks/gather_facts_rest_api.yml`) no longer requires `aoscx_configure_vrfs: true`. It now only requires `aoscx_gather_facts_rest_api: true` and at least one VRF in use (via `get_vrfs_in_use`), matching the pattern already used for OSPF and static route facts. This unblocks report-only/verification playbooks (`aoscx_configure_vrfs: false`, `aoscx_gather_facts_rest_api: true`) that want to compare NetBox-desired VRF/RD/route-target state against the device without the role also pushing VRF configuration.

## [0.13.16] - 2026-07-19

### Added

- New `aoscx_vrf_rt_facts` REST API fact (`tasks/gather_facts_rest_api.yml`), giving the device's actual VRF route-targets per address family (`{vrf: {ipv4: {export: [...], import: [...]}, ipv6: {...}}}`), gathered from `/system/vrfs/{vrf}/vrf_address_families` for every VRF in use. Requires `aoscx_gather_facts_rest_api: true`.
- New `get_vrf_rt_removals` filter (`netbox_filters_lib/vrf_filters.py`) that compares desired route targets (`build_vrf_rt_config` output) against `aoscx_vrf_rt_facts` to find route targets present on the device but no longer declared in NetBox. `configure_vrfs.yml` now removes these stale route targets (`no route-target export|import <rt>`) when `aoscx_idempotent_mode: true` and REST API facts are available - closing the one idempotency gap in VRF route-target push (additions were already idempotent via `aoscx_config`'s `match: line`; only removals were previously undetectable). See [docs/FILTER_PLUGINS.md](docs/FILTER_PLUGINS.md).
- New `aoscx_vrf_facts` REST API fact (`tasks/gather_facts_rest_api.yml`), giving the device's actual VRF names and Route Distinguishers (`{vrf: {rd: <str or None>}}`) from `/system/vrfs?attributes=name,rd`. Requires `aoscx_gather_facts_rest_api: true`.
- New `tasks/identify_vrf_changes.yml`, the single source of truth for VRF change detection - mirrors `identify_interface_changes.yml`/`identify_vlan_changes.yml` so `configure_vrfs.yml` only pushes VRF creation, Route Distinguisher, and route-target changes that actually differ from device state, instead of relying solely on `aoscx_vrf`'s own idempotency and `aoscx_config`'s `match: line` to no-op unnecessary pushes. Backed by the new `get_vrf_changes` filter (`netbox_filters_lib/vrf_filters.py`), which categorizes VRFs into `to_create`/`rd_changes`/`rt_additions`/`rt_removals`/`no_changes` using `aoscx_vrf_facts` and `aoscx_vrf_rt_facts`; when REST API fact gathering is disabled, every VRF/RD/RT is returned for push, matching the role's previous behaviour. `configure_vrfs.yml` was reworked to consume `vrf_changes` directly. See [docs/FILTER_PLUGINS.md](docs/FILTER_PLUGINS.md).
- New `tasks/identify_ospf_changes.yml`, the single source of truth for OSPF change detection - mirrors `identify_vrf_changes.yml` so `configure_ospf.yml` only pushes OSPF router-id, area, and per-interface (area/network-type/MD5-authentication/passive) changes that actually differ from device state, instead of unconditionally looping over every OSPF VRF/interface on every run. Backed by two new filters (`netbox_filters_lib/ospf_filters.py`): `get_ospf_router_changes` compares desired router-id/areas per VRF against `aoscx_ospf_router_facts`, and `get_ospf_interface_changes` compares desired per-interface area/network-type/authentication/passive state against `aoscx_ospf_interface_facts` and `aoscx_ospf_router_facts` (reusing the same network-type enum mapping and MD5-auth-presence semantics as `l3_config_helpers.group_interface_ips`). No new REST attributes were needed - the existing `ospf_if_type`/`ospf_auth_type` interface facts and `passive_interfaces` router fact already cover everything the role configures. When REST API fact gathering is disabled, every desired router/area/interface setting is returned for push, matching the role's previous behaviour. `configure_ospf.yml` was reworked to consume `ospf_router_changes`/`ospf_interface_changes` directly. See [docs/FILTER_PLUGINS.md](docs/FILTER_PLUGINS.md).

### Fixed

- `identify_vrf_changes.yml` raised `'str' object has no attribute 'get'` on real AOS-CX switches when `aoscx_gather_facts_rest_api: true`, and - once that crash was patched around - kept re-pushing Route Distinguisher and route-target config that already matched the device (masked only by `aoscx_config`'s `match: line` no-op, so no actual harm, just noisy/non-idempotent-looking runs). Root cause: both the VRF facts query (`/system/vrfs`) and the VRF route-target facts query (`/system/vrfs/{vrf}/vrf_address_families`) used `depth=1`, but AOS-CX only expands a **collection** GET's entries into full attribute objects at `depth=2`; at `depth=1` each entry is still a bare URI string (same reason the existing VLAN facts query in `tasks/gather_facts_rest_api.yml` already used `depth=2`, and the same reason code that only reads a collection's *keys*, like the OSPF router areas/passive-interfaces facts, stays correct at `depth=1`). `get_vrf_changes` was silently coercing those URI strings to `{}` via `_to_dict()`, so every RD/route-target compared as "missing" even when already correct. Fixed by bumping both REST queries to `depth=2` (`tasks/gather_facts_rest_api.yml`); the `_to_dict()` hardening in `get_vrf_changes`/`get_vrf_rt_removals` (`netbox_filters_lib/vrf_filters.py`) is kept as defense-in-depth against any future/unexpected REST shape.

## [0.13.15] - 2026-07-19

### Fixed

- OSPF config context (`ospf_vrfs`, or legacy `ospf_1_vrf`/`ospf_areas`) could list areas for VRFs that exist in NetBox but have no interfaces assigned on the device, causing `configure_ospf.yml` to try to push OSPF router/area config for VRFs that don't exist on the switch. New `filter_ospf_vrfs_in_use` filter (`netbox_filters_lib/ospf_filters.py`) drops those entries before configuration, using the same `get_vrfs_in_use` logic already used by `configure_vrfs.yml` to decide which VRFs are actually in use; the built-in `default` VRF is always exempt since it always exists on the device. See [docs/filter_plugins/ospf_filters.md](docs/filter_plugins/ospf_filters.md).
- Interface `description` changes in NetBox were not always reflected on the device. REST API fact gathering (`tasks/gather_facts_rest_api.yml`) already queried `attributes=description` and `filter_plugins/rest_api_transforms.py` already normalized it, but VLAN SVIs, loopbacks, and sub-interfaces (NetBox `type.value == "virtual"`) had no description comparison in change detection at all, so a description-only edit on one of these interface types was silently dropped. `netbox_filters_lib/interface_change_detection.py` now compares `description` for virtual interfaces and sets `_ip_changes.description_change`; `group_interface_ips()` (`netbox_filters_lib/l3_config_helpers.py`) now includes an interface flagged this way even when no IP addresses need adding; and `build_l3_config_lines()` emits a `description` line for `vlan`/`loopback`/`subinterface` types. Physical and LAG interfaces (L2 and L3) already pushed description correctly via `configure_physical_interfaces.yml`/`configure_lag_interfaces.yml`/`configure_mclag_interfaces.yml` and are unchanged; `build_l3_config_lines()` deliberately excludes `physical`/`lag` from the new description logic to avoid duplicating that push.

## [0.13.14] - 2026-07-16

### Added

- New `aoscx_ospf_router_facts` REST API fact (`tasks/gather_facts_rest_api.yml`), giving the OSPF router-id, configured areas, and passive interfaces per VRF/process-id (`{vrf: {process_id: {router_id, areas, passive_interfaces}}}`), alongside the existing `aoscx_ospf_interface_facts`. Both let a report-only playbook (`aoscx_configure_ospf: false`, `aoscx_gather_facts_rest_api: true`) compare what NetBox declares against what the device actually has configured.
- New `normalize_ospf_vrfs` filter (`netbox_filters_lib/ospf_filters.py`) that collapses the multi-VRF (`ospf_vrfs`) and legacy single-VRF (`ospf_1_vrf` + `ospf_areas`) NetBox OSPF config context formats into one shape. Used by both `configure_ospf.yml` and the new OSPF router facts query so the two stay in sync. See [docs/filter_plugins/ospf_filters.md](docs/filter_plugins/ospf_filters.md).

### Changed

- OSPF fact gathering (`aoscx_ospf_interface_facts`, `aoscx_ospf_router_facts`) no longer requires `aoscx_configure_ospf: true`. It now only requires `aoscx_gather_facts_rest_api: true` and the device's `device_ospf` custom field to be `true`, matching the pattern used for static route facts. This unblocks report-only/verification playbooks that gather OSPF facts via the role without pushing OSPF configuration.

### Fixed

- Legacy single-VRF OSPF config context (`ospf_1_vrf` + `ospf_areas`) silently failed to configure any areas: `configure_ospf.yml` copied `ospf_areas` entries (keyed `ospf_1_area`) straight into the normalized `areas` list without renaming the key to `area`, but the area-configuration loop reads `item.1.area`. Fixed by the new `normalize_ospf_vrfs` filter, which correctly maps `ospf_1_area` to `area`.
- `configure_ospf.yml` raised `object of type 'dict' has no attribute 'if_ip_ospf_network'` under ansible-core 2.19 for any OSPF-enabled interface missing the `if_ip_ospf_network` custom field (e.g. loopbacks, which typically only set `if_ip_ospf_1_area`). Ansible 2.19's templating engine raises `AttributeError` instead of returning `Undefined` when an unguarded missing-attribute lookup is stored into a dict/list literal inside a `{% set %}` block. Fixed by defaulting the lookup to an empty string (`| default('', true)`).
- `Build OSPF router facts from REST API responses` (`tasks/gather_facts_rest_api.yml`) raised `object of type 'str' has no attribute 'keys'`. The `areas` field on the `ospf_routers` REST endpoint is a child-table URI reference, not a reference-list attribute like `passive_interfaces`, so it never expands into a dict via `attributes=`/`depth=` on that endpoint - it always comes back as the raw sub-collection URL string. Fixed by querying the `.../ospf_routers/{process_id}/areas?depth=1` sub-collection directly for the area IDs, merged into `aoscx_ospf_router_facts` alongside the router-id/passive-interfaces query.
- `group_interface_ips` (`netbox_filters_lib/l3_config_helpers.py`) broke idempotency for OSPF interfaces with `if_ip_ospf_network` set to `nbma` or `point-to-multipoint`: its `_OSPF_TYPE_MAP` only mapped `point-to-point`, so those two types always compared as a mismatch against gathered facts even when already correctly configured, causing the role to flag them as needing a change on every run. Also fixed the same broadcast-default gap identified in `report_ospf.yml`: `broadcast` is the AOS-CX default network type, so a `null`/missing `ospf_if_type` in facts is now correctly treated as equivalent to `broadcast` rather than a mismatch. Replaced the partial hardcoded map with the same general `type.replace('-', '').replace('tt', 't')` transform used by the AOS-CX Ansible collection.

## [0.13.13] - 2026-07-09

### Fixed

- Changing a VLAN's `name` or `description` in NetBox was not propagated to the device. `configure_vlans.yml` only ever created VLANs (`state: create`, a no-op if the VLAN already exists) and updated IGMP/voice settings, never the name/description of an existing in-use VLAN. New `get_vlans_needing_name_update` filter compares desired NetBox `name`/`description` against `aoscx_enhanced_vlan_facts` (REST API facts, already queried with these attributes) and a new task in `configure_vlans.yml` pushes `aoscx_vlan` with `state: update` only when they differ.

## [0.13.12] - 2026-07-08

### Fixed

- Physical interfaces that are the parent of a dot1q sub-interface (`templates/int_phys.j2` and `tasks/configure_physical_interfaces.yml`) now explicitly enable routed mode (`routing`). Some AOS-CX hardware/firmware defaults physical ports to L2 (switching) mode, which previously left the parent unrouted and blocked sub-interface encapsulation. The runtime task compares against gathered device facts so `routing` is only pushed when the parent is not already routed.
- Physical and LAG interfaces configured with an L3 address (`netbox_filters_lib/l3_config_helpers.py` and `templates/int_lag.j2`) now explicitly enable routed mode (`routing`), to support platforms that default physical/LAG ports to L2 (switching) mode instead of L3. VLAN SVIs and loopbacks are unaffected, since they are always L3 by default on every platform. `templates/int_phys.j2` already emitted `routing` for L3 physical interfaces.

## [0.13.11] - 2026-07-08

### Fixed

- Update docs regarding ospf configuration
- Remove fail settings in ospf template

## [0.13.10] - 2026-07-08

### Fixed

- Change order in template to match copy and paste order into devices.

## [0.13.9] - 2026-07-07

### Fixed

- `tasks/configure_ospf.yml` failed with `object of type 'NoneType' has no len()` when configuring OSPF interfaces without an entry in `ospf_auth_keys` for the interface's VRF (i.e. no authentication configured). Jinja's `default('')` filter only substitutes for undefined values, not `None`, so `key_secret` stayed `None` and the subsequent `| length` check crashed. Fixed by using `default('', true)` to also substitute falsy/`None` values.

## [0.13.8] - 2026-07-07

### Fixed

- REST API static route fact gathering (`aoscx_static_route_facts`) no longer requires `aoscx_configure_static_routes: true`. It now only requires `aoscx_gather_facts_rest_api: true` and a non-empty `static_routes` config_context, matching the pattern used by other facts (e.g. VSX, DHCP relay). This unblocks report-only/verification playbooks that gather facts via the role without pushing static route configuration.

## [0.13.7] - 2026-07-07

### Added

- New static route management, configured from a `static_routes` NetBox config_context key (organised per VRF, JSON data model documented in [docs/STATIC_ROUTES_CONFIGURATION.md](docs/STATIC_ROUTES_CONFIGURATION.md)). Supports `forward`, `blackhole`, and `reject` route types via `arubanetworks.aoscx.aoscx_static_route`. New `aoscx_configure_static_routes` variable (default `true`), new `tasks/configure_static_routes.yml` (tag-dependent like OSPF/BGP — requires `static_routes`, `routing`, or `all` tag), and a new `get_static_route_changes` filter that pre-compares desired routes against REST API facts (`aoscx_static_route_facts`, gathered when `aoscx_gather_facts_rest_api: true`) since the underlying module is not idempotent. Cleanup of stale routes only runs in `aoscx_idempotent_mode`. Only a single next-hop per prefix is supported (no ECMP). `templates/gateway.j2` (ZTP/template-based config generation) also renders `static_routes` as `ip route`/`ipv6 route` CLI lines, auto-detecting the address family per prefix and emitting `nullroute`/`reject`/`distance`/`vrf` clauses as needed.
- New `vlan_voice_vlan` NetBox VLAN custom field. When `true`, `configure_vlans.yml` sets `voice: true` on `aoscx_vlan` (AOS-CX `voice` command) at creation, and updates in-use VLANs whose voice setting differs from the current device state. New `get_vlans_needing_voice_update` filter mirrors `get_vlans_needing_igmp_update`, comparing against the `voice` attribute in `aoscx_enhanced_vlan_facts`. The template-based config generator (`templates/vlan.j2`) also emits `voice` when the custom field is set.

### Fixed

- `templates/int_loopback.j2` (template-based config generation) generated `interface loopback0` instead of `interface loopback 0`. AOS-CX requires a space between `loopback` and the interface number, the same as `vlan` and `lag` interfaces (which already inserted the space correctly).

## [0.13.6] - 2026-07-01

### Added

- REST API fact gathering now queries VSX configuration (`/system/vsx`) when `custom_fields.device_vsx` is true. The response is stored as `aoscx_vsx_facts` with `device_role`, `system_mac`, `isl_port`, `keepalive_vrf`, `keepalive_src_ip`, and `keepalive_peer_ip`. Non-VSX devices skip the query entirely.
- New `vsx_config_diff` filter compares NetBox config_context VSX settings against `aoscx_vsx_facts`. Returns per-field diffs so `configure_vsx.yml` only pushes configuration when the device state differs from the desired state.
- REST API fact gathering now queries global STP configuration (`/system?attributes=stp_config&depth=1`). The response is stored as `aoscx_stp_global_facts` with `mstp_config_name`, `mstp_config_revision`, `priority`, and other STP settings.
- New `stp_global_config_diff` filter compares NetBox config_context MSTP settings (`mstp_config_name`, `mstp_config_revision`, `mstp_priority`) against `aoscx_stp_global_facts`. Returns per-field diffs and CLI lines so `configure_stp.yml` only pushes global MSTP configuration when the device state differs. Default priority is 8 when not set in config_context.

### Fixed

- REST API interface fact gathering now includes the `interfaces` attribute (LAG member list). Previously the attribute was missing from the query, causing the LAG membership reverse map to be empty. This made `get_interfaces_needing_config_changes` report all LAG member interfaces as needing reassignment even when correctly configured.

## [0.13.5] - 2026-06-30

### Changed

- Moved `netbox_filters_lib/` from `filter_plugins/netbox_filters_lib/` to the role root. Ansible's plugin loader was scanning the subdirectory and emitting warnings for every library module (`No module named 'ansible.plugins.filter.utils'`). No user-facing API change — all filters work identically.

## [0.13.4] - 2026-06-30

### Added

- New variable `aoscx_configure_icmp_redirect` (default: `true`) to control anycast gateway ICMP redirect configuration. Previously this task was only gated on `custom_fields.device_anycast_gateway` and could not be disabled via role variables.

### Fixed

- REST API VLAN query now includes `name`, `description`, `admin`, `type`, `voice`, and `oper_state` attributes. Previously only `mgmd_*` attributes were requested, causing `rest_api_to_aoscx_vlans` to fall back to default names like `VLAN15` instead of the actual configured names.

## [0.13.3] - 2026-06-30

### Changed

- NTP and DNS tags changed from `base_config`/`system` to `services`. These tasks depend on VRFs and could fail when run with `-t base_config` if VRFs were not configured. Use `-t services` (or `-t ntp`/`-t dns`) to target them individually.

### Fixed

## [0.13.2] - 2026-06-26

- **OSPF interface auth handling**: Replaced interface-level `aoscx_ospf_interface` usage with CLI-based `aoscx_config` in `tasks/configure_ospf.yml`. Interface area/network/auth are now handled in one path with explicit `md5 plaintext` or `md5 ciphertext` output based on `ospf_auth_keys[vrf].encrypted`. This avoids REST API ciphertext reprocessing and keeps encrypted vault values intact on-device.

## [0.13.1] - 2026-06-22

### Fixed

- Change of VRF on L3 interfaces is handled correctly.

## [0.13.0] - 2026-06-17

### Added

- Support for updated Ansible collection for AOS CX to 4.5.1, ugrade Ansible to 2.19.10

## [0.12.3] - 2026-06-12

### Added

- Configuration of IP helper based on Config Context and custom field on interface.

## [0.12.2] - 2026-06-01

### Fixed

- Configure correct mtu and description on already enabled interfaces

## [0.12.1] - 2026-05-14

### Added

- Port-access roles now support an optional `extra_lines` list in the NetBox config_context schema. Lines are appended verbatim to the `port-access role` CLI block, enabling any AOS-CX role attribute without requiring code changes. Roles that include `extra_lines` always push (REST API diff is bypassed for that role, since arbitrary CLI cannot be compared against structured facts).

## [0.12.0] - 2026-05-12

### Added

- STP interface configuration: new `configure_stp.yml` task applies per-interface spanning-tree settings (`bpdu-filter`, `bpdu-guard`, `port-type admin-edge`, `root-guard`) from NetBox custom fields (`if_stp_bpdu_filter`, `if_stp_bpdu_guard`, `if_stp_edge_port`, `if_stp_root_guard`). Change detection uses REST API `stp_config` facts so only differing settings are pushed.
- Global MSTP configuration in `configure_stp.yml`: applies `spanning-tree config-name`, `config-revision`, and optional `priority` from `config_context` when `mstp_config_name` is defined.
- New `aoscx_configure_stp` variable (default: `true`) to enable/disable all STP tasks. Supports the `stp` tag for targeted runs.
- REST API fact gathering now includes `stp_config` (depth=2) in the interface attribute query when `aoscx_configure_stp: true`, exposing per-interface STP state via `aoscx_enhanced_interface_facts`.
- New `stp_interface_changes` filter in `filter_plugins/netbox_filters_lib/stp.py` — pure function comparing NetBox desired state against device `stp_config` facts; returns only the interfaces and CLI lines that need to change.

## [0.11.4] - 2026-05-08

### Added

- add dns template
- add config task for hostname

### Fixed

- cleanup of debug events

## [0.11.3] - 2026-05-06

### Added

- configuration task for defult gateway for mgmt vlan

## [0.11.2] - 2026-05-06

### Added

- ssh server in default VRF (for management vlan)
- https server in default VRF (for management vlan)
- added defaut gateway in default vrf based on management VLAN ip address

## [0.11.1] - 2026-05-05

### Fixed

- Variable naming in port-access lldp groups

## [0.11.0] - 2026-05-05

### Added

- New filter `port_access_diff(desired, current)` that compares the
  desired `port_access` config_context against `aoscx_port_access_facts`
  (REST API fact gathering) and returns only the items that need to be
  configured. Compares LLDP/MAC group match-sets (sequence-number
  agnostic), role attributes (`description`, `poe_priority`, `trust_mode`
  vs REST `qos_trust_mode`, `vlan_trunk_native`/`vlan_access` vs
  `vlan_tag`, `vlan_trunk_allowed` range expansion vs `vlan_trunks`
  list), and device-profile associations (`enable`, `associate_role`,
  `associate_lldp_group`, `associate_mac_group`). When facts are missing
  the filter falls back to "push everything", so behaviour is unchanged
  for users who haven't enabled REST API fact gathering. 20 unit tests.
- `tasks/configure_port_access.yml` now consumes `port_access_diff` and
  loops only over the items that differ - skipping unneeded SSH
  connections and CLI pushes when the device already matches NetBox.
  A new debug summary prints `<changed>/<total>` per object kind.
- REST API fact gathering for port-access objects. When
  `aoscx_gather_facts_rest_api: true` and the device has a `port_access`
  dict in its NetBox config_context, a single GET to
  `/system/device_profiles?depth=5` returns every device-profile with its
  associated role, lldp-groups (with expanded match entries) and
  mac-groups inline. The new
  `port_access_facts_from_device_profiles` filter flattens that response
  into the `aoscx_port_access_facts` shape (`device_profiles`, `roles`,
  `lldp_groups`, `mac_groups`) used by `port_access_diff`. Replaces the
  earlier four separate REST queries; queries are skipped entirely on
  devices with no `port_access` config_context.
- The `port_access_diff` LLDP/MAC match comparison now also recognises
  the device-side REST field names (`system_name`, `system_description`,
  `sequence_number`) so depth=5 payloads diff correctly against
  desired-side keys (`sys_name`, `sys_desc`, `seq`).
- Port-access (device-profile) configuration. New tasks
  `tasks/configure_port_access.yml` (orchestrator) plus per-object
  includes `configure_port_access_lldp_group.yml`,
  `configure_port_access_mac_group.yml`,
  `configure_port_access_role.yml`,
  `configure_port_access_device_profile.yml`. Renders LLDP groups, MAC
  groups, port-access roles and port-access device-profiles from the
  `port_access` config_context dict and pushes via
  `arubanetworks.aoscx.aoscx_config` (network_cli). New variable
  `aoscx_configure_port_access` (default `true`); auto-skipped on devices
  whose NetBox config_context has no `port_access` dict (no custom field
  required). Wired into `tasks/main.yml` after L2 interfaces, before
  OSPF. Tags: `port_access`, `device_profile`, `layer2`.
- New template `templates/port_access.j2` rendering AOS-CX
  `port-access lldp-group`, `port-access mac-group`, `port-access role` and
  `port-access device-profile` blocks from the `port_access`
  config_context dict. Included from `templates/aoscx.j2` between the
  management interface and LAG interface sections (used when
  `aoscx_generate_template_config: true`).
- New variable `aoscx_configure_vlans_all` (default `false`). When set to
  `true`, the role skips the "VLANs in use on interfaces" detection and
  treats every VLAN that NetBox returns for the device as in use, so all
  NetBox-scoped VLANs are created on the device and protected from
  idempotent cleanup. Useful for access/edge switches.
- VLAN change identification now includes VLAN IDs referenced by
  `port_access` roles in NetBox config_context (`vlan_trunk_native`,
  `vlan_trunk_allowed`, `vlan_access`). These VLANs are auto-created on the
  device and protected from idempotent cleanup. Range and list syntax
  (e.g. `"11-13"`, `"11,13,15-20"`) is supported.
- New filters: `extract_port_access_vlan_ids`, `parse_vlan_id_spec`.
- `get_vlans_in_use` accepts a third optional `port_access` argument
  (backward compatible).

## [0.10.6] - 2026-05-03

### Fixed

- Order of configuration depending on VRFs
- Cleanup documentation

## [0.10.5] - 2026-04-30

### Added

- Manage IGMP snooping pr VLAN

## [0.10.4] - 2026-04-29

### Fixed

- Remove OSPF authentication on Loopback interfaces

### Added

- OSPF passive interfaces
- Posibility to exclude interfaces from OSP authentication.

## [0.10.3] - 2026-04-28

### Added

- OSPF authentication on interfaces

### Fixed

- filter plugins and testing doc - exclude VLAN on subinterfaces
- configuration templates config order

## [0.10.2] - 2026-04-27

### Fixed

- exclude VLAN ID on subinterfaces to be created as VLAN

## [0.10.1] - 2026-04-23

### Fixed

- added tests
- correction to tests
- cleaning up documentation

### Added

- path in config generation using variable

## [0.10.0] - 2026-04-12

### Added

- no icmp redirect when using active gateway.
- config generation (not feature complete)

## [0.9.4] - 2026-04-11

### Fixed

- Disable physical interface check on mgmt did not work

## [0.9.3] - 2026-04-09

### Fixed

- Documentation cleanup

## [0.9.2] - 2026-04-09

### Fixed

- BGP documentation cleanup
- Documentation cleanup

## [0.9.1] - 2026-04-07

### Fixed

- bgp route reflector conf using device_roles

## [0.9.0] - 2026-04-07

### Added

- support DNS nameserver per vrf

### Fixed

- corrections and clarifications in docs
- uppdated example

## [0.8.0] - 2026-04-05

### Added

- ipv6 prefix-list
- route map for ipv6
- bgp ipv6 neighbours iBGP
- bgp ipv6 neighbours eBGP
- route maps import and export for ipv6

## [0.7.1] - 2026-04-03

### Fixed

- Documentation updated regarding VSF / VSX
- Remove IPv6 address from interface if removed / changed in NetBox

## [0.7.0] - 2026-03-28

### Removed

- aoscx_fast_mode variable is deprecated - it slowed things down.

### Fixed

- Don't try to create or update Vlan 1 it exist default

## [0.6.4] - 2026-03-26

### Changed

- Anycast gateway IPv6 change to configure ipv6 link-local if anycast address in NetBox is link-local address.
- Filter logic updated for removal of IPv6 addresses not in NetBox.
- Detect if link-local addres is not configured when anycast gateway is configure using link-local address.
- Documentation updated with new feature.

## [0.6.3] - 2026-03-11

### Changed

- Consolidate gather facts using rest api.
- Refactor IP Filters
- Refactor IP config tasks
- Refactor loopback interfaces
- Refactor gather enhanced facts using API

## [0.6.2] - 2026-03-07

### Fixed

- Docs - update to fetch latest tag from repo
- meta - updates to fields
- Example - created proper example ffor usage of the role

## [0.6.1] - 2026-03-07

### Removed

- ZTP - the fature was incompleat and didn't work good
- BGP - usage of config-contexts is removed

## [0.6.0] - 2026-03-07

### Added

- IP Prefix Lists from BGP plugin
- Route-Maps from BGP Plugin

## [0.5.1] - 2026-03-02

### Fixed

- Filter out mgmt interface when not compare existing and new config.

## [0.5.0] - 2026-02-25

First public release. See the [documentation](https://aopdal.github.io/ansible-role-aruba-cx-switch/) for full details on all features.

### Added

- NetBox as source of truth for switch configuration
- VRF configuration with route distinguisher, import/export targets
- VLAN management with create and idempotent cleanup
- L2 interface configuration (access, trunk, LAG, MC-LAG)
- L3 interface configuration (physical, LAG, loopback, VLAN, sub-interfaces)
- BGP routing protocol with VRF support
- OSPF routing protocol configuration
- EVPN/VXLAN overlay support with VNI mappings
- VSX (Virtual Switching Extension) support
- Anycast gateway / active-gateway IP configuration
- Idempotent mode for detecting and cleaning stale configuration
- Enhanced fact gathering via REST API for full IPv6 and VSX data
- 36 custom filter plugins across 2 plugin files
- ZTP (Zero Touch Provisioning) support
- CI/CD with GitHub Actions (lint, syntax check, unit tests)
- Comprehensive documentation site (MkDocs)
- Branch protection and CODEOWNERS for contribution workflow

[Unreleased]: https://github.com/aopdal/ansible-role-aruba-cx-switch/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/aopdal/ansible-role-aruba-cx-switch/releases/tag/v0.5.0
