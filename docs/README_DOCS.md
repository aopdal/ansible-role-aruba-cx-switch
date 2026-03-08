# Documentation Index

This directory contains all documentation for the `ansible-role-aruba-cx-switch` Ansible role.

## Viewing Documentation

### Local Documentation Site (Recommended)

This role uses **MkDocs with Material theme** for beautiful, searchable documentation.

```bash
# Install dependencies (first time only)
pip install -r requirements-docs.txt

# Start live preview at http://127.0.0.1:8000
make docs-serve
```

**Note:** GitHub Pages is disabled while the repo is private (requires public repo or paid plan).
See **[DOCUMENTATION_SITE.md](DOCUMENTATION_SITE.md)** for details.

---

## Getting Started

- **[QUICKSTART.md](QUICKSTART.md)** - Quick start guide for development of the role
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Quick reference for common tasks

## Examples (Recommended Starting Point)

- **[examples/](../examples/)** - Complete, runnable examples
    - **[minimal-deployment/](../examples/minimal-deployment/)** - Simple single-switch deployment for getting started
    - **[bgp-evpn-fabric/](../examples/bgp-evpn-fabric/)** - Production BGP/EVPN fabric with spine-leaf topology
    - Each example includes inventory, playbooks, group_vars, and sample NetBox data
    - **Best way to understand how all the pieces fit together**

## Filter Plugins (Essential Reading)

- **[FILTER_PLUGINS.md](FILTER_PLUGINS.md)** - Complete filter plugin reference
    - Custom filters for NetBox data transformation
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

### VLAN Management

- **[VLAN_CHANGE_IDENTIFICATION_WORKFLOW.md](VLAN_CHANGE_IDENTIFICATION_WORKFLOW.md)** - VLAN change workflow
    - Single source of truth for VLAN analysis
    - Configuration and cleanup phases
    - Integration with EVPN/VXLAN
    - Benefits and safety features

- **[VLAN_WORKFLOW_DIAGRAMS.md](VLAN_WORKFLOW_DIAGRAMS.md)** - Visual workflow diagrams
    - Mermaid diagrams for configuration and cleanup phases
    - Fact dependencies visualization

- **[VLAN_DEVELOPER_GUIDE.md](VLAN_DEVELOPER_GUIDE.md)** - Developer quick reference
    - Adding new VLAN-related tasks
    - Common patterns and best practices
    - Available facts and debugging

### EVPN & VXLAN

- **[EVPN_VXLAN_CONFIGURATION.md](EVPN_VXLAN_CONFIGURATION.md)** - Complete EVPN/VXLAN configuration guide
- **[EVPN_VXLAN_MODES.md](EVPN_VXLAN_MODES.md)** - Configuration modes (initial vs idempotent)

### BGP Routing

- **[BGP_CONFIGURATION.md](BGP_CONFIGURATION.md)** - BGP/EVPN configuration guide
    - Complete EVPN/VXLAN fabric setup
    - Route reflector configuration
    - IPv4 unicast and EVPN address families
    - VRF route distinguishers

- **[BGP_HYBRID_CONFIGURATION.md](BGP_HYBRID_CONFIGURATION.md)** - Hybrid config_context + NetBox BGP plugin approach
- **[NETBOX_BGP_PLUGIN.md](NETBOX_BGP_PLUGIN.md)** - NetBox BGP plugin integration guide
- **[BGP_MIGRATION_GUIDE.md](BGP_MIGRATION_GUIDE.md)** - Migration from config_context to NetBox BGP plugin
- **[BGP_EVPN_FABRIC_EXAMPLE.md](BGP_EVPN_FABRIC_EXAMPLE.md)** - Complete fabric example

### Tag-Dependent Configuration

- **[TAG_DEPENDENT_INCLUDES.md](TAG_DEPENDENT_INCLUDES.md)** - Tag-dependent task implementation
    - BGP, OSPF, and VSX require explicit tags
    - Behavior matrix for different tag combinations
    - Safety improvements for daily operations

- **[TAG_DEPENDENT_TESTING.md](TAG_DEPENDENT_TESTING.md)** - Testing tag-dependent tasks

## Development

- **[DEVELOPMENT.md](DEVELOPMENT.md)** - Complete development guide
    - Dev container setup
    - Local development setup
    - Coding standards and pre-commit hooks
    - Testing procedures
    - Contribution workflow

- **[DEVCONTAINER_SETUP.md](DEVCONTAINER_SETUP.md)** - Detailed dev container configuration
- **[DEVCONTAINER_MOUNTS.md](DEVCONTAINER_MOUNTS.md)** - Mounting additional folders in devcontainer
- **[WORKSPACE.md](WORKSPACE.md)** - Multi-folder workspace guide

## Testing

- **[TESTING.md](TESTING.md)** - General testing documentation
- **[TESTING_ENVIRONMENT.md](TESTING_ENVIRONMENT.md)** - Comprehensive integration testing guide
- **[TESTING_QUICK_START.md](TESTING_QUICK_START.md)** - 30-minute quick start for testing

## Reference

- **[PERFORMANCE_OPTIMIZATION.md](PERFORMANCE_OPTIMIZATION.md)** - Performance tuning guide
- **[NETBOX_INTEGRATION.md](NETBOX_INTEGRATION.md)** - NetBox integration reference
- **[AUTOMATION_ECOSYSTEM.md](AUTOMATION_ECOSYSTEM.md)** - Architecture overview

### Release Process

- **[RELEASE_PROCESS.md](RELEASE_PROCESS.md)** - Full release guide
- **[RELEASE_QUICK_REFERENCE.md](RELEASE_QUICK_REFERENCE.md)** - Quick release steps
- **[CHANGELOG.md](CHANGELOG.md)** - Version history

### Documentation Management

- **[DOCUMENTATION_SITE.md](DOCUMENTATION_SITE.md)** - How to use MkDocs
- **[DOCS_SYNC_WORKFLOW.md](DOCS_SYNC_WORKFLOW.md)** - How README.md syncs to docs/

## Internal Documentation

- **[DOCUMENTATION_INTEGRATION.md](DOCUMENTATION_INTEGRATION.md)** - Documentation integration details
- **[VERIFICATION_CHECKLIST.md](VERIFICATION_CHECKLIST.md)** - Final verification checklist
- **[archive/README.md](archive/README.md)** - Archived development notes and historical documentation
