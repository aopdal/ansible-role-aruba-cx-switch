# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
