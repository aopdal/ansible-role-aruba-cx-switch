# Unit Test Status

## Current Status

All tests are passing. Run the full suite with:

```bash
pytest tests/unit/ -v
```

## Test Files

| File | Module Under Test | Notes |
|------|-------------------|-------|
| `test_utils.py` | `utils.py` | Includes `exclude_anycast` path |
| `test_vlan_filters.py` | `vlan_filters.py` | |
| `test_vrf_filters.py` | `vrf_filters.py` | |
| `test_interface_filters.py` | `interface_categorization.py`, `interface_ip_processing.py` | |
| `test_interface_ip_processing.py` | `interface_ip_processing.py` | |
| `test_interface_ip_comparisons.py` | `interface_ip_comparisons.py` | |
| `test_interface_orphans.py` | `interface_orphans.py` | |
| `test_interface_change_detection.py` | `interface_change_detection.py` | |
| `test_comparison.py` | `comparison.py` | |
| `test_l3_config_helpers.py` | `l3_config_helpers.py` | |
| `test_ospf_filters.py` | `ospf_filters.py` | Tests both nested and flat config_context |
| `test_bgp_filters.py` | `bgp_filters.py` | |
| `test_static_route_filters.py` | `static_route_filters.py` | |
| `test_stp_filters.py` | `stp.py` | |
| `test_vsx.py` | `vsx.py` | |
| `test_port_access_diff.py` | `port_access.py` (`port_access_diff`) | |
| `test_port_access_facts.py` | `port_access.py` (`port_access_facts_from_device_profiles`) | |
| `test_port_access_vlans.py` | `vlan_filters.py` (port-access VLAN extraction) | |
| `test_port_access_orphans.py` | `port_access_orphans.py` | |
| `test_rest_api_transforms.py` | `rest_api_transforms.py` | |
| `test_netbox_filters.py` | `filter_plugins/netbox_filters.py` (`FilterModule`) | Smoke test only - verifies every filter is registered and resolves; behavioral tests live in the module-specific files above |

## Coverage

```bash
pytest tests/unit/ --cov=filter_plugins --cov=netbox_filters_lib --cov-report=term-missing
```

Coverage is measured across both `filter_plugins/` (the public filter
entry points, `netbox_filters.py` + `rest_api_transforms.py`) and
`netbox_filters_lib/` (the actual filter implementations). Measuring
`filter_plugins/` alone is misleading: `netbox_filters.py` is a thin
re-export shim that every other test bypasses by importing
`netbox_filters_lib` directly, so it reports near-zero coverage on its
own even though the logic it re-exports is thoroughly tested.

Target: **>= 90%** code coverage. Current: ~92%.
