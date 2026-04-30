# Filter Plugin Unit Tests

Comprehensive unit tests for all custom Ansible filter plugins in this role.

## Test Coverage

The test suite covers **38 filter functions** across **10 modules**:

### 1. Utility Functions (`test_utils.py`)
- `collapse_vlan_list` - VLAN range collapsing
- `extract_ip_addresses` - IPv4/IPv6 extraction (including `exclude_anycast`)
- `populate_ip_changes` - IP change dict population
- `select_interfaces_to_configure` - Interface selection for idempotent mode

### 2. VLAN Filters (`test_vlan_filters.py`)
- `extract_vlan_ids` - Extract VLANs from interfaces (excludes tagged VLANs on subinterfaces)
- `filter_vlans_in_use` - Filter to in-use VLANs
- `extract_evpn_vlans` - Extract EVPN-enabled VLANs
- `extract_vxlan_mappings` - Extract VXLAN VNI mappings
- `get_vlans_in_use` - Get all VLANs in use (excludes tagged VLANs on subinterfaces)
- `get_vlans_needing_changes` - Identify VLAN changes
- `get_vlans_needing_igmp_update` - Identify VLANs needing IGMP snooping updates (compares NetBox `vlan_ip_igmp_snooping` field vs current device state from enhanced REST API facts)
- `get_vlan_interfaces` - Extract VLAN interfaces
- `parse_evpn_evi_output` - Parse CLI show evpn evi output

### 3. VRF Filters (`test_vrf_filters.py`)
- `extract_interface_vrfs` - Extract VRFs from interfaces
- `filter_vrfs_in_use` - Filter to in-use VRFs
- `get_vrfs_in_use` - Get all VRFs in use
- `filter_configurable_vrfs` - Filter out built-in VRFs

### 4. Interface Filters (`test_interface_filters.py`)
- `categorize_l2_interfaces` - Categorize L2 interfaces
- `categorize_l3_interfaces` - Categorize L3 interfaces
- `get_interface_ip_addresses` - Extract IP addresses

### 5. Comparison Functions (`test_comparison.py`)
- `compare_interface_vlans` - Compare VLAN configurations
- `get_interfaces_needing_changes` - Identify interface changes (includes cleanup detection)

### 6. Interface Change Detection (`test_interface_change_detection.py`)
- `get_interfaces_needing_config_changes` - Full NetBox vs device change detection

### 7. L3 Config Helpers (`test_l3_config_helpers.py`)
- `format_interface_name` - Format interface names for AOS-CX CLI
- `group_interface_ips` - Group per-IP items into per-interface items
- `build_l3_config_lines` - Build L3 configuration command list

### 8. OSPF Filters (`test_ospf_filters.py`)
- `select_ospf_interfaces` - Select OSPF-enabled interfaces
- `extract_ospf_areas` - Extract OSPF areas
- `get_ospf_interfaces_by_area` - Group interfaces by area
- `validate_ospf_config` - Validate OSPF configuration (nested and flat)

### 9. BGP Filters (`test_bgp_filters.py`)
- `get_bgp_session_vrf_info` - Enrich BGP sessions with VRF and address-family
- `collect_ebgp_vrf_policy_config` - Collect routing policies and prefix lists for eBGP VRF sessions

### 10. REST API Transforms (`test_rest_api_transforms.py`)
- `rest_api_to_aoscx_interfaces` - Convert REST API interface objects to aoscx_facts format
- `rest_api_to_aoscx_vlans` - Convert REST API VLAN objects to aoscx_facts format
- `rest_api_to_aoscx_evpn_vlans` - Convert REST API EVPN VLAN objects
- `rest_api_to_aoscx_vnis` - Convert REST API VNI objects

## Running Tests

### Run All Tests
```bash
# From role root directory
pytest tests/unit/

# Or using make
make test-unit
```

### Run Specific Test File
```bash
pytest tests/unit/test_vlan_filters.py
pytest tests/unit/test_vrf_filters.py
```

### Run Specific Test Class
```bash
pytest tests/unit/test_utils.py::TestCollapseVlanList
```

### Run Specific Test
```bash
pytest tests/unit/test_utils.py::TestCollapseVlanList::test_consecutive_vlans
```

### Run with Coverage Report
```bash
pytest tests/unit/ --cov=filter_plugins --cov-report=html
# Open htmlcov/index.html to view coverage

# Or using make
make test-unit-coverage
```

### Run with Verbose Output
```bash
pytest tests/unit/ -v
```

### Run Tests by Category
```bash
# Run only VLAN-related tests
pytest tests/unit/ -m vlan

# Run only VRF-related tests
pytest tests/unit/ -m vrf

# Run only fast tests (skip slow ones)
pytest tests/unit/ -m "not slow"
```

## Test Structure

```
tests/unit/
├── __init__.py                       # Package initialization
├── conftest.py                       # Pytest configuration and setup
├── fixtures.py                       # Shared test data and fixtures
├── test_utils.py                     # Utility function tests
├── test_vlan_filters.py              # VLAN filter tests
├── test_vrf_filters.py               # VRF filter tests
├── test_interface_filters.py         # Interface categorization and IP processing tests
├── test_interface_change_detection.py # Change detection and idempotency tests
├── test_comparison.py                # State comparison tests
├── test_l3_config_helpers.py         # L3 configuration helper tests
├── test_ospf_filters.py              # OSPF filter tests
├── test_bgp_filters.py               # BGP filter tests
└── test_rest_api_transforms.py       # REST API transform tests
```

## Test Fixtures

Located in `tests/unit/fixtures.py`:

- `get_sample_interfaces()` - Sample NetBox interface data
- `get_sample_vlans()` - Sample NetBox VLAN data
- `get_sample_vrfs()` - Sample NetBox VRF data
- `get_sample_ip_addresses()` - Sample NetBox IP address data
- `get_sample_ansible_facts()` - Sample Ansible device facts
- `get_sample_ospf_config()` - Sample OSPF configuration data

## Coverage Goals

Target: **>= 90% code coverage** for all filter plugins

```bash
pytest tests/unit/ --cov=filter_plugins --cov-report=term-missing
```

## Writing New Tests

### Test Naming Convention
- Test files: `test_<module_name>.py`
- Test classes: `Test<FunctionName>`
- Test methods: `test_<specific_behavior>`

### Example Test Structure
```python
class TestMyFunction:
    """Tests for my_function"""

    def test_normal_case(self):
        result = my_function(valid_input)
        assert result == expected_output

    def test_edge_case(self):
        result = my_function(edge_case_input)
        assert result is not None

    def test_error_handling(self):
        with pytest.raises(ValueError):
            my_function(invalid_input)
```

### Best Practices
1. One assertion per test when possible
2. Clear test names that describe what's being tested
3. Use fixtures for common test data
4. Test edge cases and error conditions
5. Keep tests independent — no dependencies between tests

## Debugging Failed Tests

```bash
pytest tests/unit/ --pdb          # Drop into pdb on failure
pytest tests/unit/ -l             # Show local variables on failure
pytest tests/unit/ --lf           # Run only failed tests from last run
pytest tests/unit/ -s             # Show print statements
```

## Performance

Target: < 5 seconds for the full unit test suite.

```bash
pytest tests/unit/ --durations=10  # Show 10 slowest tests
```

## Continuous Integration

Unit tests run automatically on:
- Pre-commit hooks
- Pull request creation
- Main branch commits
- Release tags

See [TESTING.md](TESTING.md) for the full testing guide covering Molecule, integration tests, and CI/CD.
