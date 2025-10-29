# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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

- Enhanced .gitignore for testing artifacts
- Updated role structure for better maintainability

### Fixed

- N/A

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
