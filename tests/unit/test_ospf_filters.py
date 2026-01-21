"""
Unit tests for OSPF filter functions
"""
import pytest
from netbox_filters_lib.ospf_filters import (
    select_ospf_interfaces,
    extract_ospf_areas,
    get_ospf_interfaces_by_area,
    validate_ospf_config,
)
from .fixtures import get_sample_ospf_config


class TestSelectOspfInterfaces:
    """Tests for select_ospf_interfaces function"""

    def test_select_ospf_interfaces(self):
        """Test selecting interfaces configured for OSPF"""
        interfaces = [
            {
                "name": "1/1/1",
                "custom_fields": {
                    "if_ip_ospf_1_area": "0.0.0.0",
                },
            },
            {
                "name": "1/1/2",
                "custom_fields": {},  # No OSPF config
            },
        ]
        result = select_ospf_interfaces(interfaces)
        assert len(result) == 1
        assert result[0]["name"] == "1/1/1"

    def test_select_ospf_interfaces_null_area(self):
        """Test that null/empty area values are excluded"""
        interfaces = [
            {
                "name": "1/1/1",
                "custom_fields": {
                    "if_ip_ospf_1_area": None,
                },
            },
            {
                "name": "1/1/2",
                "custom_fields": {
                    "if_ip_ospf_1_area": "",
                },
            },
            {
                "name": "1/1/3",
                "custom_fields": {
                    "if_ip_ospf_1_area": "null",
                },
            },
        ]
        result = select_ospf_interfaces(interfaces)
        assert len(result) == 0

    def test_select_ospf_interfaces_empty(self):
        """Test with empty interface list"""
        result = select_ospf_interfaces([])
        assert result == []


class TestExtractOspfAreas:
    """Tests for extract_ospf_areas function"""

    def test_extract_ospf_areas_basic(self):
        """Test extracting unique OSPF areas"""
        interfaces = [
            {
                "name": "1/1/1",
                "custom_fields": {
                    "if_ip_ospf_1_area": "0.0.0.0",
                },
            },
            {
                "name": "1/1/2",
                "custom_fields": {
                    "if_ip_ospf_1_area": "0.0.0.1",
                },
            },
            {
                "name": "1/1/3",
                "custom_fields": {
                    "if_ip_ospf_1_area": "0.0.0.0",
                },
            },
        ]
        result = extract_ospf_areas(interfaces)
        assert sorted(result) == ["0.0.0.0", "0.0.0.1"]

    def test_extract_ospf_areas_empty(self):
        """Test with no interfaces"""
        result = extract_ospf_areas([])
        assert result == []

    def test_extract_ospf_areas_no_ospf(self):
        """Test with interfaces but no OSPF config"""
        interfaces = [
            {
                "name": "1/1/1",
                "custom_fields": {},
            },
        ]
        result = extract_ospf_areas(interfaces)
        assert result == []


class TestGetOspfInterfacesByArea:
    """Tests for get_ospf_interfaces_by_area function"""

    def test_get_ospf_interfaces_by_area(self):
        """Test filtering interfaces by specific area"""
        interfaces = [
            {
                "name": "1/1/1",
                "custom_fields": {
                    "if_ip_ospf_1_area": "0.0.0.0",
                },
            },
            {
                "name": "1/1/2",
                "custom_fields": {
                    "if_ip_ospf_1_area": "0.0.0.1",
                },
            },
            {
                "name": "1/1/3",
                "custom_fields": {
                    "if_ip_ospf_1_area": "0.0.0.0",
                },
            },
        ]
        result = get_ospf_interfaces_by_area(interfaces, "0.0.0.0")
        assert len(result) == 2
        assert result[0]["name"] == "1/1/1"
        assert result[1]["name"] == "1/1/3"

    def test_get_ospf_interfaces_by_area_no_match(self):
        """Test when no interfaces match the area"""
        interfaces = [
            {
                "name": "1/1/1",
                "custom_fields": {
                    "if_ip_ospf_1_area": "0.0.0.0",
                },
            },
        ]
        result = get_ospf_interfaces_by_area(interfaces, "0.0.0.99")
        assert len(result) == 0

    def test_get_ospf_interfaces_by_area_empty(self):
        """Test with no interfaces"""
        result = get_ospf_interfaces_by_area([], "0.0.0.0")
        assert result == []


class TestValidateOspfConfig:
    """Tests for validate_ospf_config function"""

    def test_validate_ospf_config_valid(self):
        """Test validation of valid OSPF configuration"""
        device_config = {
            "custom_fields": {"device_ospf_1_routerid": "10.255.255.1"},
            "config_context": {
                "ospf_areas": [
                    {"ospf_1_area": "0.0.0.0"},
                ],
            },
        }
        interfaces = [
            {
                "name": "1/1/1",
                "custom_fields": {
                    "if_ip_ospf_1_area": "0.0.0.0",
                },
            },
        ]
        result = validate_ospf_config(device_config, interfaces)
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_validate_ospf_config_missing_router_id(self):
        """Test validation warns without router ID"""
        device_config = {
            "custom_fields": {},
            "config_context": {
                "ospf_areas": [{"ospf_1_area": "0.0.0.0"}],
            },
        }
        interfaces = [
            {
                "name": "1/1/1",
                "custom_fields": {
                    "if_ip_ospf_1_area": "0.0.0.0",
                },
            },
        ]
        result = validate_ospf_config(device_config, interfaces)
        assert len(result["warnings"]) > 0
        assert any("router ID" in w for w in result["warnings"])

    def test_validate_ospf_config_interface_area_not_in_config(self):
        """Test validation warns when interface area not in config"""
        device_config = {
            "custom_fields": {"device_ospf_1_routerid": "10.255.255.1"},
            "config_context": {
                "ospf_areas": [{"ospf_1_area": "0.0.0.0"}],
            },
        }
        interfaces = [
            {
                "name": "1/1/1",
                "custom_fields": {
                    "if_ip_ospf_1_area": "0.0.0.99",  # Area not in config
                },
            },
        ]
        result = validate_ospf_config(device_config, interfaces)
        assert len(result["warnings"]) > 0

    def test_validate_ospf_config_no_interfaces(self):
        """Test validation with config but no interfaces"""
        device_config = {
            "custom_fields": {"device_ospf_1_routerid": "10.255.255.1"},
            "config_context": {
                "ospf_areas": [{"ospf_1_area": "0.0.0.0"}],
            },
        }
        result = validate_ospf_config(device_config, [])
        assert result["valid"] is True

    def test_validate_ospf_config_flattened_valid(self):
        """Test validation with flattened config_context (plurals: true)"""
        device_config = {
            "custom_fields": {"device_ospf_1_routerid": "10.255.255.1"},
            "ospf_areas": [
                {"ospf_1_area": "0.0.0.0"},
            ],
        }
        interfaces = [
            {
                "name": "1/1/1",
                "custom_fields": {
                    "if_ip_ospf_1_area": "0.0.0.0",
                },
            },
        ]
        result = validate_ospf_config(device_config, interfaces)
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_validate_ospf_config_flattened_missing_area(self):
        """Test validation with flattened config when area is missing"""
        device_config = {
            "custom_fields": {"device_ospf_1_routerid": "10.255.255.1"},
            "ospf_areas": [{"ospf_1_area": "0.0.0.0"}],
        }
        interfaces = [
            {
                "name": "1/1/1",
                "custom_fields": {
                    "if_ip_ospf_1_area": "0.0.0.99",  # Area not in config
                },
            },
        ]
        result = validate_ospf_config(device_config, interfaces)
        assert len(result["warnings"]) > 0
