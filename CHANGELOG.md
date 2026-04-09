# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
