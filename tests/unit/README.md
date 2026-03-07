# Filter Plugin Unit Tests

Comprehensive unit tests for all custom Ansible filter plugins in this role.

## Test Coverage

The test suite covers **23 filter functions** across **7 modules**:

### 1. Utility Functions (`test_utils.py`)
- ✅ `collapse_vlan_list` - VLAN range collapsing (10 tests)

### 2. VLAN Filters (`test_vlan_filters.py`)
- ✅ `extract_vlan_ids` - Extract VLANs from interfaces
- ✅ `filter_vlans_in_use` - Filter to in-use VLANs
- ✅ `extract_evpn_vlans` - Extract EVPN-enabled VLANs
- ✅ `extract_vxlan_mappings` - Extract VXLAN VNI mappings
- ✅ `get_vlans_in_use` - Get all VLANs in use
- ✅ `get_vlans_needing_changes` - Identify VLAN changes
- ✅ `get_vlan_interfaces` - Extract VLAN interfaces

### 3. VRF Filters (`test_vrf_filters.py`)
- ✅ `extract_interface_vrfs` - Extract VRFs from interfaces
- ✅ `filter_vrfs_in_use` - Filter to in-use VRFs
- ✅ `get_vrfs_in_use` - Get all VRFs in use
- ✅ `filter_configurable_vrfs` - Filter out built-in VRFs

### 4. Interface Filters (`test_interface_filters.py`)
- ✅ `categorize_l2_interfaces` - Categorize L2 interfaces
- ✅ `categorize_l3_interfaces` - Categorize L3 interfaces
- ✅ `get_interface_ip_addresses` - Extract IP addresses

### 5. Comparison Functions (`test_comparison.py`)
- ✅ `compare_interface_vlans` - Compare VLAN configurations
- ✅ `get_interfaces_needing_changes` - Identify interface changes (includes cleanup detection)

### 6. OSPF Filters (`test_ospf_filters.py`)
- ✅ `select_ospf_interfaces` - Select OSPF-enabled interfaces
- ✅ `extract_ospf_areas` - Extract OSPF areas
- ✅ `get_ospf_interfaces_by_area` - Group interfaces by area
- ✅ `validate_ospf_config` - Validate OSPF configuration

### 7. BGP Filters (`test_bgp_filters.py`)
- ✅ `get_bgp_session_vrf_info` - Enrich BGP sessions with VRF and address-family
- ✅ `collect_ebgp_vrf_policy_config` - Collect routing policies and prefix lists for eBGP VRF sessions

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
├── __init__.py              # Package initialization
├── conftest.py              # Pytest configuration and setup
├── fixtures.py              # Shared test data and fixtures
├── README.md                # This file
├── test_utils.py            # Utility function tests
├── test_vlan_filters.py     # VLAN filter tests
├── test_vrf_filters.py      # VRF filter tests
├── test_interface_filters.py # Interface filter tests
├── test_comparison.py       # Comparison function tests
├── test_ospf_filters.py     # OSPF filter tests
└── test_bgp_filters.py      # BGP filter tests
```

## Test Fixtures

Located in `fixtures.py`:

- `get_sample_interfaces()` - Sample NetBox interface data
- `get_sample_vlans()` - Sample NetBox VLAN data
- `get_sample_vrfs()` - Sample NetBox VRF data
- `get_sample_ip_addresses()` - Sample NetBox IP address data
- `get_sample_ansible_facts()` - Sample Ansible device facts
- `get_sample_ospf_config()` - Sample OSPF configuration data

## Coverage Goals

Target: **>= 90% code coverage** for all filter plugins

Current coverage can be checked with:
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
        """Test normal operation"""
        result = my_function(valid_input)
        assert result == expected_output

    def test_edge_case(self):
        """Test edge case handling"""
        result = my_function(edge_case_input)
        assert result is not None

    def test_error_handling(self):
        """Test error handling"""
        with pytest.raises(ValueError):
            my_function(invalid_input)
```

### Best Practices
1. **One assertion per test** when possible
2. **Clear test names** that describe what's being tested
3. **Use fixtures** for common test data
4. **Test edge cases** and error conditions
5. **Keep tests independent** - no dependencies between tests

## Continuous Integration

Tests are automatically run on:
- Pre-commit hooks
- Pull request creation
- Main branch commits
- Release tags

## Debugging Failed Tests

### Run with pdb on failure
```bash
pytest tests/unit/ --pdb
```

### Show local variables on failure
```bash
pytest tests/unit/ -l
```

### Run only failed tests from last run
```bash
pytest tests/unit/ --lf
```

### Show print statements
```bash
pytest tests/unit/ -s
```

## Performance

Test suite execution time:
- **Target**: < 5 seconds for all unit tests
- **Current**: ~2 seconds (varies by system)

Run with timing information:
```bash
pytest tests/unit/ --durations=10
```

## Contributing

When adding new filter plugins:
1. Create corresponding test file
2. Aim for >= 90% coverage
3. Include edge cases and error handling tests
4. Update this README with new test information
5. Ensure all tests pass before committing

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest Coverage Plugin](https://pytest-cov.readthedocs.io/)
- [Python Testing Best Practices](https://docs.python-guide.org/writing/tests/)
