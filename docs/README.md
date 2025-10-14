# Documentation Index

This directory contains all documentation for the `ansible-role-aruba-cx-switch` Ansible role.

## 📚 Viewing Documentation

### Local Documentation Site (Recommended)

This role uses **MkDocs with Material theme** for beautiful, searchable documentation.

```bash
# Install dependencies (first time only)
pip install -r requirements-docs.txt

# Start live preview at http://127.0.0.1:8000
make docs-serve
```

⚠️ **Note:** GitHub Pages is disabled while the repo is private (requires public repo or paid plan).
See **[DOCUMENTATION_SITE.md](DOCUMENTATION_SITE.md)** for details.

---

## Getting Started

- **[QUICKSTART.md](QUICKSTART.md)** - Quick start guide for using the role
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Quick reference for common tasks

## 🔌 Filter Plugins (Essential Reading)

- **[FILTER_PLUGINS.md](FILTER_PLUGINS.md)** - Complete filter plugin reference
  - **22 custom filters** for NetBox data transformation
  - Detailed documentation for VLAN, VRF, interface, OSPF operations
  - Real-world usage examples and complete workflows
  - Development guide and architecture
  - **Critical for understanding how the role processes NetBox data**

## Configuration Guides

### Base System Configuration
- **[BASE_CONFIGURATION.md](BASE_CONFIGURATION.md)** - Base system settings
  - Banner, timezone, NTP, and DNS configuration
  - Configuration flags and NetBox variables
  - Task execution order

- **[DNS_CONFIGURATION.md](DNS_CONFIGURATION.md)** - DNS configuration examples
  - Complete config_context examples
  - Domain name, nameservers, and host mappings
  - Management vs. non-management VRF setup

### Routing Protocols

- **[BGP_CONFIGURATION.md](BGP_CONFIGURATION.md)** - BGP/EVPN configuration guide
  - Complete EVPN/VXLAN fabric setup
  - Route reflector configuration
  - IPv4 unicast and EVPN address families
  - VRF route distinguishers

- **[BGP_SUMMARY.md](BGP_SUMMARY.md)** - BGP configuration summary
- **[BGP_MIGRATION_GUIDE.md](BGP_MIGRATION_GUIDE.md)** - Migration from config_context to NetBox BGP plugin
- **[BGP_EVPN_FABRIC_EXAMPLE.md](BGP_EVPN_FABRIC_EXAMPLE.md)** - Complete fabric example
- **[BGP_HYBRID_CONFIGURATION.md](BGP_HYBRID_CONFIGURATION.md)** - Hybrid config_context + plugin approach
- **[BGP_HYBRID_SUMMARY.md](BGP_HYBRID_SUMMARY.md)** - Hybrid approach summary
- **[NETBOX_BGP_PLUGIN.md](NETBOX_BGP_PLUGIN.md)** - NetBox BGP plugin integration guide
  - Plugin installation and setup
  - Data models and API usage
  - Advantages over config_context

### Tag-Dependent Configuration

- **[TAG_DEPENDENT_SUMMARY.md](TAG_DEPENDENT_SUMMARY.md)** - Tag-dependent task overview
  - BGP, OSPF, and VSX now require explicit tags
  - Behavior matrix for different tag combinations
  - Safety improvements for daily operations

- **[TAG_DEPENDENT_INCLUDES.md](TAG_DEPENDENT_INCLUDES.md)** - Technical implementation details
- **[TAG_DEPENDENT_TESTING.md](TAG_DEPENDENT_TESTING.md)** - Testing tag-dependent tasks
- **[TAG_INHERITANCE_FIX.md](TAG_INHERITANCE_FIX.md)** - Tag inheritance fixes

## Development

- **[DEVELOPMENT.md](DEVELOPMENT.md)** - Complete development guide
  - Dev container setup
  - Local development setup
  - Coding standards and pre-commit hooks
  - Testing procedures
  - Contribution workflow

- **[DEVCONTAINER_SETUP.md](DEVCONTAINER_SETUP.md)** - Detailed dev container configuration
- **[DEVCONTAINER_MOUNTS.md](DEVCONTAINER_MOUNTS.md)** - Mounting additional folders in devcontainer
  - Access test environments and other projects
  - Mount syntax and examples
  - Multi-folder workspace setup

- **[WORKSPACE.md](WORKSPACE.md)** - Multi-folder workspace guide
  - Using `ansible-workspace.code-workspace`
  - Working with multiple projects simultaneously
  - Customization and folder management

- **[SETUP_COMPLETE.md](SETUP_COMPLETE.md)** - Dev environment setup verification

## Testing

- **[TESTING.md](TESTING.md)** - General testing documentation
- **[TESTING_ENVIRONMENT.md](TESTING_ENVIRONMENT.md)** - Comprehensive integration testing guide
  - Complete architecture and topology options
  - NetBox, EVE-NG, and test controller setup
  - 20+ test scenarios
  - Implementation timeline and resource requirements

- **[TESTING_QUICK_START.md](TESTING_QUICK_START.md)** - 30-minute quick start for testing
  - Condensed setup instructions
  - First test walkthrough
  - Troubleshooting guide

- **[TESTING_PROPOSAL.md](TESTING_PROPOSAL.md)** - Testing environment proposal
  - Executive summary
  - Cost analysis and ROI
  - Decision-making guide

## Internal Documentation

- **[REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md)** - History of code refactoring and improvements
  - Filter plugin reorganization
  - Task splitting and optimization
  - Architecture improvements

## Root Documentation

The following files are in the repository root for standard compliance:

- **[../README.md](../README.md)** - Main project documentation
- **[../CHANGELOG.md](../CHANGELOG.md)** - Version history and changes
- **[../CONTRIBUTING.md](../CONTRIBUTING.md)** - Contribution guidelines

## Additional Resources

### Testing Scripts
- **[../testing-scripts/](../testing-scripts/)** - Helper scripts for testing environment
  - `populate_netbox.py` - Populate NetBox with test data
  - `validate_deployment.py` - Validate switch configurations
  - `README.md` - Script usage documentation

## Document Categories

### 📚 Quick Reference (2 docs)
- QUICKSTART.md
- QUICK_REFERENCE.md

### 🔌 Filter Plugins (1 doc)
- FILTER_PLUGINS.md - **Essential for understanding data transformation**

### ⚙️ Configuration Guides (13 docs)
- BASE_CONFIGURATION.md
- DNS_CONFIGURATION.md
- BGP_CONFIGURATION.md
- BGP_SUMMARY.md
- BGP_MIGRATION_GUIDE.md
- BGP_EVPN_FABRIC_EXAMPLE.md
- BGP_HYBRID_CONFIGURATION.md
- BGP_HYBRID_SUMMARY.md
- NETBOX_BGP_PLUGIN.md
- TAG_DEPENDENT_SUMMARY.md
- TAG_DEPENDENT_INCLUDES.md
- TAG_DEPENDENT_TESTING.md
- TAG_INHERITANCE_FIX.md

### 🔧 Development (5 docs)
- DEVELOPMENT.md
- DEVCONTAINER_SETUP.md
- DEVCONTAINER_MOUNTS.md
- WORKSPACE.md
- SETUP_COMPLETE.md

### 🧪 Testing (4 docs)
- TESTING.md
- TESTING_ENVIRONMENT.md
- TESTING_QUICK_START.md
- TESTING_PROPOSAL.md

### 📋 Internal (1 doc)
- REFACTORING_SUMMARY.md

**Total: 27 documentation files**
