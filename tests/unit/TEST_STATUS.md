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
| `test_interface_change_detection.py` | `interface_change_detection.py` | |
| `test_comparison.py` | `comparison.py` | |
| `test_l3_config_helpers.py` | `l3_config_helpers.py` | |
| `test_ospf_filters.py` | `ospf_filters.py` | Tests both nested and flat config_context |
| `test_bgp_filters.py` | `bgp_filters.py` | |
| `test_rest_api_transforms.py` | `rest_api_transforms.py` | |

## Coverage

```bash
pytest tests/unit/ --cov=filter_plugins --cov-report=term-missing
```

Target: **>= 90%** code coverage for all filter plugins.
