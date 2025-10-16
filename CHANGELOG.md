# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **Unified L2 interface configuration** - Merged `configure_l2_interfaces.yml` and `configure_l2_interfaces_idempotent.yml` into a single unified task file that handles both standard and idempotent modes automatically
- `configure_l2_interfaces.yml` now intelligently detects `aoscx_idempotent_mode` and adjusts behavior accordingly
- Simplified `tasks/main.yml` by removing duplicate L2 interface task includes
- Enhanced README with detailed explanation of both configuration modes

### Deprecated
- `configure_l2_interfaces_idempotent.yml` - Now redirects to unified `configure_l2_interfaces.yml`. Will be removed in v2.0.0

### Added
- New documentation: `docs/L2_INTERFACE_MODES.md` - Comprehensive guide to L2 configuration modes
- Mode detection and logging in L2 interface configuration
- Debug output showing which mode is active (standard vs idempotent)
- Configuration summary at end of L2 interface tasks

### Fixed
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
