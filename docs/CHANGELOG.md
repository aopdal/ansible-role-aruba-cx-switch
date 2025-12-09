# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Enhanced Fact Gathering via REST API** (experimental)
  - New `aoscx_gather_enhanced_facts` option to gather interface data with `depth=2`
  - Provides actual IPv6 addresses instead of URI references
  - Includes VSX virtual IPs (`vsx_virtual_ip4`, `vsx_virtual_ip6`)
  - Includes anycast gateway MACs (`vsx_virtual_gw_mac_v4`, `vsx_virtual_gw_mac_v6`)
  - New task file: `gather_enhanced_facts.yml`
  - Configuration variables: `aoscx_rest_host`, `aoscx_rest_user`, `aoscx_rest_password`
  - See PERFORMANCE_OPTIMIZATION.md for usage details

- **Code Optimizations & Refactoring**
  - New L3 Configuration Helpers module (`l3_config_helpers.py`)
    - `format_interface_name()` - Interface name formatting for AOS-CX
    - `is_ipv4_address()` / `is_ipv6_address()` - IP version detection
    - `get_interface_vrf()` - VRF extraction with safe fallback
    - `build_l3_config_lines()` - Complete L3 config line generation
  - IP address extraction helpers in utils module
    - `extract_ip_addresses()` - Extract and categorize IPv4/IPv6
    - `populate_ip_changes()` - Populate idempotent change tracking
  - Unified L3 interface configuration task (`configure_l3_interface_common.yml`)
    - Single reusable task for all interface types
    - Supports physical, LAG, and VLAN interfaces
    - Handles IPv4, IPv6, default/custom VRFs, and anycast gateways
  - Configurable built-in VRFs list (`aoscx_builtin_vrfs` in defaults)
  - Comprehensive documentation for new filter helpers

- Comprehensive CI/CD testing infrastructure
  - GitHub Actions workflow for automated testing
  - Molecule testing framework for role validation
  - Pre-commit hooks for code quality
  - YAML and Ansible linting configuration
- Testing documentation (TESTING.md)
- Contributing guidelines (CONTRIBUTING.md)
- Issue templates for bugs and feature requests
- Makefile for easy test command execution
- Setup script for quick testing environment setup

### Changed

- **Major Code Consolidation**
  - Refactored L3 interface configuration tasks (53% reduction)
    - `configure_l3_physical.yml`: 85 → 43 lines (-49%)
    - `configure_l3_lag.yml`: 85 → 43 lines (-49%)
    - `configure_l3_vlan.yml`: 105 → 43 lines (-59%)
  - Eliminated 186 lines of duplicated code across the role
  - Moved complex Jinja2 logic to testable Python functions
  - Centralized IP address extraction (removed 3 duplicate code blocks)

- Enhanced .gitignore for testing artifacts
- Updated role structure for better maintainability
- Improved filter plugins documentation with new L3 helpers

### Fixed

- **Critical**: VLAN interface IPv4 addresses not configured on first run
  - Root cause: Missing `_ip_changes.ipv4_to_add` for new interfaces
  - Solution: Populate IP changes before early continue in interface detection
  - Impact: IPv4 now configures correctly on initial deployment
  - Details: [VLAN_INTERFACE_FIX_SUMMARY.md](../VLAN_INTERFACE_FIX_SUMMARY.md)

- **Critical**: IPv4 filtering broken in unified L3 configuration task
  - Root cause: Regex pattern `^\d+\.\d+\.\d+\.\d+/` not working with `selectattr/rejectattr`
  - Solution: Changed to simple colon check (IPv6 has `:`, IPv4 doesn't)
  - Impact: IPv4 addresses now correctly filtered and configured on all interface types

- **Critical**: IPv4 `_needs_add` logic not defaulting correctly for new interfaces
  - Root cause: Complex conditional not handling missing `_ip_changes` dictionary
  - Solution: Fixed logic to default to `true` for IPv4 when change tracking unavailable
  - Impact: New interfaces now configure correctly on first run while maintaining performance optimization

- **Critical**: Anycast/active-gateway IPs being reconfigured unnecessarily
  - Root cause: Device facts only report regular IPs in `ip4_address`, not active-gateway IPs
  - Solution: Added `exclude_anycast` parameter to `extract_ip_addresses()` function
  - Change detection now excludes anycast IPs when comparing with device facts
  - Impact: Anycast IPs no longer trigger unnecessary reconfiguration

- Magic strings for built-in VRFs (moved to configurable defaults)

## [1.0.0] - YYYY-MM-DD

### Added

- Initial release
- VRF configuration support
- VLAN management (create/cleanup)
- L2 interface configuration (access, trunk, LAG, MC-LAG)
- L3 interface configuration (physical, LAG, loopback, VLAN interfaces)
- VSX (Virtual Switching Extension) support
- OSPF routing protocol configuration
- BGP routing protocol configuration
- EVPN/VXLAN support
- NetBox integration as source of truth
- Idempotent mode for configuration cleanup

[Unreleased]: https://github.com/your-org/ansible-role-aruba-cx-switch/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/your-org/ansible-role-aruba-cx-switch/releases/tag/v1.0.0
