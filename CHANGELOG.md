# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.12] - 2026-02-18

## [0.4.11] - 2026-02-16

## [0.4.10] - 2026-02-16

## [0.4.9] - 2026-02-16

## [0.4.8] - 2026-02-07

## [0.4.7] - 2026-01-28

## [0.4.6] - 2026-01-28

## [0.4.5] - 2026-01-28

## [0.4.4] - 2026-01-26

## [0.4.3] - 2026-01-24

## [0.4.2] - 2026-01-24

## [0.4.1] - 2026-01-22

## [0.4.0] - 2026-01-21

## [0.3.26] - 2026-01-19

## [0.3.25] - 2026-01-17

## [0.3.24] - 2026-01-17

## [0.3.23] - 2026-01-17

## [0.3.22] - 2026-01-17

## [0.3.21] - 2026-01-02

## [0.3.20] - 2026-01-02

## [0.3.19] - 2026-01-02

## [0.3.18] - 2026-01-02

## [0.3.17] - 2025-12-15

## [0.3.16] - 2025-12-09

## [0.3.15] - 2025-12-09

## [0.3.14] - 2025-12-09

## [0.3.13] - 2025-12-08

## [0.3.12] - 2025-12-08

## [0.3.11] - 2025-12-08

## [0.3.10] - 2025-12-08

## [0.3.9] - 2025-12-08

## [0.3.8] - 2025-12-07

## [0.3.7] - 2025-12-06

## [0.3.6] - 2025-12-06

## [0.3.5] - 2025-12-05

## [0.3.4] - 2025-11-23

## [0.3.3] - 2025-11-22

## [0.3.2] - 2025-11-17

## [0.3.1] - 2025-11-10

## [0.3.0] - 2025-11-07

## [0.2.0] - 2025-11-05

## [0.1.19] - 2025-11-05

## [0.1.18] - 2025-11-05

## [0.1.17] - 2025-11-05

## [0.1.16] - 2025-11-04

## [0.1.15] - 2025-11-04

## [0.1.14] - 2025-11-04

## [0.1.13] - 2025-11-03

## [0.1.12] - 2025-11-03

## [0.1.11] - 2025-10-29

## [0.1.10] - 2025-10-27

## [0.1.9] - 2025-10-27

## [0.1.8] - 2025-10-27

## [0.1.7] - 2025-10-25

## [0.1.6] - 2025-10-24

## [0.1.5] - 2025-10-24

## [0.1.4] - 2025-10-24

## [0.1.3] - 2025-10-24

## [0.1.2] - 2025-10-21

## [0.1.1] - 2025-10-21

### Added
- **Loopback interface configuration** - Complete implementation of `configure_loopback.yml` task file
  - Automatic detection of loopback interfaces by type and name pattern
  - IPv4 and IPv6 support with VRF attachment
  - Dual-stack configuration support
  - Proper interface creation before IP assignment
  - Comprehensive debug output and logging
- **VSX (Virtual Switching Extension) configuration** - Complete implementation of `configure_vsx.yml` task file
  - System MAC and role configuration (primary/secondary)
  - Inter-Switch Link (ISL) LAG setup
  - Keepalive configuration with custom VRF support
  - VSX-sync global configuration
  - Validation of required parameters
  - Graceful handling when VSX is not enabled
  - Tag-dependent execution (only runs with `--tags vsx`, `--tags ha`, or full run)
- **Comprehensive unit test suite** - Complete test coverage for all filter plugins
  - 87 tests passing with 81% code coverage across filter plugins
  - 22 filter functions tested across 6 modules
  - pytest configuration with coverage reporting (HTML, XML, terminal)
  - Test fixtures for NetBox data (interfaces, VLANs, VRFs, IP addresses, OSPF config)
  - Makefile targets: `make test-unit` and `make test-unit-coverage`
  - Comprehensive test documentation in tests/unit/README.md
- **CI/CD integration** - Unit tests integrated into GitHub Actions workflow
  - Automated unit test execution on every push and pull request
  - Coverage reporting with Codecov integration
  - Fast feedback on filter plugin functionality
  - Runs after lint and syntax checks, before integration tests
  - Status badges in README for CI and code coverage
- **Enhanced README documentation**:
  - Complete loopback configuration guide with NetBox setup examples
  - Comprehensive VSX configuration documentation with primary/secondary examples
  - NetBox config context requirements and complete configuration examples
  - VSX deployment notes and best practices
  - Unit testing section with examples and coverage details

### Changed
- **Updated Ansible version requirements** - Updated CI and requirements to match actual usage
  - CI now tests with Ansible 2.16, 2.17, and 2.18 (previously 2.14, 2.15, 2.16)
  - `requirements-test.txt` updated to `ansible-core>=2.16,<2.19`
  - CI now uses Python 3.12 (previously 3.11) to match development environment
- **Unified L2 interface configuration** - Merged `configure_l2_interfaces.yml` and `configure_l2_interfaces_idempotent.yml` into a single unified task file that handles both standard and idempotent modes automatically
- `configure_l2_interfaces.yml` now intelligently detects `aoscx_idempotent_mode` and adjusts behavior accordingly
- Simplified `tasks/main.yml` by removing duplicate L2 interface task includes
- Enhanced README with detailed explanation of both configuration modes

### Deprecated
- `configure_l2_interfaces_idempotent.yml` - Now redirects to unified `configure_l2_interfaces.yml`. Will be removed in v2.0.0

### Fixed
- **Empty task files resolved** - Implemented missing functionality:
  - `configure_loopback.yml` - Was empty, now fully functional
  - `configure_vsx.yml` - Was empty, now fully functional
- **pytest-ansible conflict** - Removed `pytest-ansible` from `requirements-test.txt` as it conflicts with pytest's argument parser and is not needed for filter plugin unit tests
- Banner configuration module parameters (use `banner_exec` instead of `exec`, `delete` instead of `absent`)
- Line length violations in EVPN configuration tasks

## [1.0.0] - 2025-10-15

### Added
- Initial release
- NetBox integration as single source of truth
- VRF configuration with RD and route-targets
- VLAN management with idempotent mode
- Physical interface configuration
- L2 interface configuration (access and trunk)
- L3 interface configuration (IPv4/IPv6 with VRF support)
- VLAN interfaces (SVIs) with automatic creation
- Loopback interfaces with VRF support
- OSPF configuration (router instance, areas, interfaces)
- BGP configuration with NetBox BGP plugin support
- EVPN/VXLAN support for modern datacenter fabrics
- VSX/MCLAG support for virtual chassis
- ZTP configuration generation for Zero Touch Provisioning
- Comprehensive documentation with MkDocs
- Dev Container support for easy development
- GitHub Actions CI/CD pipeline
- Molecule testing framework
- Pre-commit hooks for code quality
- Custom filter plugins for data transformation
- Multiple test scenarios (base config, DNS, LAG, tags)

### Documentation
- Extensive README with quick start guide
- Architecture diagrams using Mermaid
- Development guidelines
- Testing environment documentation
- Quick reference guides
- Automation ecosystem overview

### Requirements
- Ansible >= 2.12
- Python >= 3.8
- arubanetworks.aoscx >= 4.0.0
- netbox.netbox >= 3.0.0
- pyaoscx >= 2.6.0
- pynetbox >= 6.0.0

---

## Version History

- **v1.0.0** (2025-10-15): Initial release with comprehensive NetBox integration
- **Unreleased**: Unified L2 configuration, improved documentation

## Upgrade Notes

### From 1.0.0 to Unreleased

**No breaking changes** - The role maintains full backward compatibility.

**Recommendations:**
1. Update playbooks to use unified `configure_l2_interfaces.yml` (optional - old way still works)
2. Review new `docs/L2_INTERFACE_MODES.md` for understanding mode differences
3. Test idempotent mode in development before production deployment

**Deprecated features will continue to work** with deprecation warnings until v2.0.0.

## Future Plans

### v1.1.0 (Planned)
- Enhanced error handling with rescue blocks
- Performance metrics and timing information
- Variable validation at role start
- API retry logic for NetBox calls

### v1.2.0 (Planned)
- Filter plugin unit tests
- Type hints in Python code
- Expanded examples directory
- Comprehensive troubleshooting guide

### v2.0.0 (Planned - Breaking Changes)
- Remove deprecated `configure_l2_interfaces_idempotent.yml`
- Update minimum Ansible version to 2.14
- Restructure task organization
- Enhanced idempotent mode with more granular control
