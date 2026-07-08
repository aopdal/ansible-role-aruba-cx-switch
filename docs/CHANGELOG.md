# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
