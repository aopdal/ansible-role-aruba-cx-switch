# Archived Documentation

This directory contains internal development notes and historical documentation that has been archived for reference but is not part of the main user documentation.

## Why Archived?

These files contain:

- Implementation summaries from feature development
- Bug fix notes and debugging guides
- Technical solutions for specific issues
- Internal development decisions
- Proposals and planning documents

They are preserved for historical reference but may be outdated or superseded by the main documentation.

## Contents

### EVPN/VXLAN Development Notes

| File | Description |
|------|-------------|
| `EVPN_VXLAN_SUMMARY.md` | Original EVPN/VXLAN implementation summary |
| `EVPN_VXLAN_CLEANUP_SUMMARY.md` | Cleanup tasks implementation notes |
| `EVPN_VXLAN_IDEMPOTENT_MODE.md` | Idempotent mode implementation details |
| `EVPN_VXLAN_FINAL_SOLUTION.md` | Regex pattern solution for detection |
| `EVPN_VXLAN_DETECTION_FIX.md` | Detection bug fix documentation |
| `EVPN_VXLAN_DEBUGGING.md` | Debug techniques for EVPN/VXLAN |

### BGP Development Notes

| File | Description |
|------|-------------|
| `BGP_SUMMARY.md` | Original BGP implementation summary |
| `BGP_HYBRID_SUMMARY.md` | Hybrid plugin/config_context implementation |

### Refactoring Notes

| File | Description |
|------|-------------|
| `REFACTORING_SUMMARY.md` | Code refactoring notes |
| `REFACTOR_SUMMARY.md` | VLAN refactoring summary |
| `COMPLETE_SUMMARY.md` | Complete implementation summary |

### Bug Fixes and Technical Solutions

| File | Description |
|------|-------------|
| `ANSIBLE_REGEX_GOTCHA.md` | Ansible regex limitations and workarounds |
| `PYLINT_IMPORT_FIX.md` | Pylint import configuration fix |
| `TAG_INHERITANCE_FIX.md` | Ansible tag inheritance fix |
| `TAG_DEPENDENT_SUMMARY.md` | Tag-dependent includes implementation |
| `INTERFACE_IDEMPOTENT_IMPLEMENTATION.md` | Interface idempotent mode implementation |
| `INTERFACE_IDEMPOTENT_QUICK_REFERENCE.md` | Interface idempotent quick reference |
| `CUSTOM_FILTER_SOLUTION.md` | Custom filter plugin solution |
| `GITHUB_PAGES_DISABLED.md` | GitHub Pages configuration notes |

### Documentation and Planning

| File | Description |
|------|-------------|
| `CODE_OPTIMIZATION_2025.md` | Code optimization notes |
| `DOCUMENTATION_REORGANIZATION.md` | Documentation reorganization plan |
| `DOCUMENTATION_SITE_SETUP.md` | MkDocs site setup notes |
| `DOCUMENTATION_STRUCTURE.md` | Documentation structure planning |
| `FILE_ORGANIZATION.md` | File organization notes |
| `README_SYNC.md` | README sync implementation |
| `REST_API_OPTIMIZATION_PROPOSAL.md` | REST API optimization proposal |
| `TESTING_PROPOSAL.md` | Testing environment proposal |
| `VLAN_DOCUMENTATION_ACCESS.md` | VLAN documentation access guide |
| `NETBOX_INTEGRATION_SUMMARY.md` | NetBox integration summary |

## Current Documentation

For up-to-date documentation, see the parent [docs/](../) directory:

- **EVPN/VXLAN**: [EVPN_VXLAN_CONFIGURATION.md](../EVPN_VXLAN_CONFIGURATION.md), [EVPN_VXLAN_MODES.md](../EVPN_VXLAN_MODES.md)
- **BGP**: [BGP_CONFIGURATION.md](../BGP_CONFIGURATION.md), [BGP_HYBRID_CONFIGURATION.md](../BGP_HYBRID_CONFIGURATION.md)
- **NetBox Integration**: [NETBOX_INTEGRATION.md](../NETBOX_INTEGRATION.md)
- **Filter Plugins**: [FILTER_PLUGINS.md](../FILTER_PLUGINS.md)

## Deletion Candidates

These files may be safely deleted if no longer needed for reference. They were archived on 2026-01-02 during documentation cleanup.
