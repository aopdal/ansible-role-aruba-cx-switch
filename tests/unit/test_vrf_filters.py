"""
Unit tests for VRF filter functions
"""
import pytest
from netbox_filters_lib.vrf_filters import (
    extract_interface_vrfs,
    filter_vrfs_in_use,
    get_vrfs_in_use,
    filter_configurable_vrfs,
)
from .fixtures import get_sample_interfaces, get_sample_ip_addresses, get_sample_vrfs


class TestExtractInterfaceVrfs:
    """Tests for extract_interface_vrfs function"""

    def test_extract_vrfs_from_interfaces(self):
        """Test extracting VRFs from interfaces"""
        interfaces = [
            {
                "name": "1/1/1",
                "vrf": {"name": "default"},
            },
            {
                "name": "1/1/2",
                "vrf": {"name": "customer_a"},
            },
        ]
        result = extract_interface_vrfs(interfaces)
        assert isinstance(result, set)
        assert result == {"customer_a", "default"}

    def test_extract_vrfs_multiple_ips_same_interface(self):
        """Test with multiple interfaces with different VRFs"""
        interfaces = [
            {
                "name": "1/1/1",
                "vrf": {"name": "vrf_a"},
            },
            {
                "name": "1/1/2",
                "vrf": {"name": "vrf_b"},
            },
        ]
        result = extract_interface_vrfs(interfaces)
        assert isinstance(result, set)
        assert result == {"vrf_a", "vrf_b"}

    def test_extract_vrfs_with_none(self):
        """Test with None VRF (should be ignored)"""
        interfaces = [
            {
                "name": "1/1/1",
                "vrf": None,
            },
        ]
        result = extract_interface_vrfs(interfaces)
        assert isinstance(result, set)
        assert result == set()

    def test_extract_vrfs_no_vrf_key(self):
        """Test with interfaces that have no VRF key"""
        interfaces = [{"name": "1/1/1"}]
        result = extract_interface_vrfs(interfaces)
        assert isinstance(result, set)
        assert result == set()

    def test_extract_vrfs_removes_duplicates(self):
        """Test that duplicate VRFs are removed"""
        interfaces = [
            {
                "name": "1/1/1",
                "vrf": {"name": "customer_a"},
            },
            {
                "name": "1/1/2",
                "vrf": {"name": "customer_a"},
            },
        ]
        result = extract_interface_vrfs(interfaces)
        assert isinstance(result, set)
        assert result == {"customer_a"}


class TestFilterVrfsInUse:
    """Tests for filter_vrfs_in_use function"""

    def test_filter_vrfs_in_use(self):
        """Test filtering VRFs that are in use"""
        vrfs = get_sample_vrfs()
        interfaces = [
            {
                "name": "1/1/1",
                "vrf": {"name": "customer_a"},
            },
        ]
        result = filter_vrfs_in_use(vrfs, interfaces)
        assert len(result) == 1
        assert result[0]["name"] == "customer_a"

    def test_filter_vrfs_none_in_use(self):
        """Test with no VRFs in use"""
        vrfs = get_sample_vrfs()
        interfaces = []
        result = filter_vrfs_in_use(vrfs, interfaces)
        assert result == []


class TestGetVrfsInUse:
    """Tests for get_vrfs_in_use function"""

    def test_get_vrfs_in_use(self):
        """Test getting VRFs in use from interfaces"""
        interfaces = [
            {
                "name": "1/1/1",
                "vrf": {"name": "customer_a"},
            },
            {
                "name": "1/1/2",
                "vrf": {"name": "customer_b"},
            },
        ]
        result = get_vrfs_in_use(interfaces, [])
        # Should include customer_a and customer_b (built-in VRFs are filtered)
        assert "customer_a" in result["vrf_names"]
        assert "customer_b" in result["vrf_names"]
        assert "default" not in result["vrf_names"]
        assert "mgmt" not in result["vrf_names"]

    def test_get_vrfs_filters_builtin(self):
        """Test that built-in VRFs are filtered out"""
        interfaces = [
            {
                "name": "1/1/1",
                "vrf": {"name": "default"},
            },
            {
                "name": "1/1/2",
                "vrf": {"name": "Default"},
            },
            {
                "name": "1/1/3",
                "vrf": {"name": "mgmt"},
            },
            {
                "name": "1/1/4",
                "vrf": {"name": "global"},
            },
        ]
        result = get_vrfs_in_use(interfaces, [])
        assert result["vrf_names"] == []

    def test_get_vrfs_empty(self):
        """Test with no VRFs"""
        result = get_vrfs_in_use([], [])
        assert result["vrf_names"] == []
        assert isinstance(result["vrfs"], dict)


class TestFilterConfigurableVrfs:
    """Tests for filter_configurable_vrfs function"""

    def test_filter_configurable_vrfs(self):
        """Test filtering out built-in VRFs"""
        vrfs = ["default", "customer_a", "mgmt", "customer_b", "global"]
        result = filter_configurable_vrfs(vrfs)
        assert sorted(result) == ["customer_a", "customer_b"]

    def test_filter_configurable_vrfs_all_builtin(self):
        """Test when all VRFs are built-in"""
        vrfs = ["default", "mgmt", "global"]
        result = filter_configurable_vrfs(vrfs)
        assert result == []

    def test_filter_configurable_vrfs_none_builtin(self):
        """Test when no VRFs are built-in"""
        vrfs = ["customer_a", "customer_b", "customer_c"]
        result = filter_configurable_vrfs(vrfs)
        assert sorted(result) == ["customer_a", "customer_b", "customer_c"]
