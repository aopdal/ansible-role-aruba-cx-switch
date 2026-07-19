"""
Unit tests for OSPF filter functions
"""
import pytest
from netbox_filters_lib.ospf_filters import (
    select_ospf_interfaces,
    extract_ospf_areas,
    get_ospf_interfaces_by_area,
    normalize_ospf_vrfs,
    filter_ospf_vrfs_in_use,
    validate_ospf_config,
    get_ospf_router_changes,
    get_ospf_interface_changes,
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


class TestNormalizeOspfVrfs:
    """Tests for normalize_ospf_vrfs function"""

    def test_multi_vrf_passthrough(self):
        """Test that the multi-VRF format is returned unchanged"""
        ospf_vrfs = [
            {"vrf": "default", "areas": [{"area": "0.0.0.0"}]},
            {"vrf": "CUSTOMER", "areas": [{"area": "0.0.0.1"}]},
        ]
        result = normalize_ospf_vrfs(ospf_vrfs)
        assert result == ospf_vrfs

    def test_multi_vrf_takes_precedence_over_legacy(self):
        """Test that ospf_vrfs wins even if legacy args are also given"""
        ospf_vrfs = [{"vrf": "default", "areas": [{"area": "0.0.0.0"}]}]
        result = normalize_ospf_vrfs(
            ospf_vrfs, ospf_1_vrf="default", ospf_areas=[{"ospf_1_area": "0.0.0.9"}]
        )
        assert result == ospf_vrfs

    def test_legacy_format_normalizes_ospf_1_area_key(self):
        """Test that legacy ospf_1_area key is renamed to area"""
        result = normalize_ospf_vrfs(
            None,
            ospf_1_vrf="default",
            ospf_areas=[{"ospf_1_area": "0.0.0.0"}, {"ospf_1_area": "0.0.0.1"}],
        )
        assert result == [
            {
                "vrf": "default",
                "areas": [{"area": "0.0.0.0"}, {"area": "0.0.0.1"}],
            }
        ]

    def test_legacy_format_accepts_pre_normalized_area_key(self):
        """Test that legacy area entries already using 'area' key still work"""
        result = normalize_ospf_vrfs(
            None, ospf_1_vrf="default", ospf_areas=[{"area": "0.0.0.0"}]
        )
        assert result == [{"vrf": "default", "areas": [{"area": "0.0.0.0"}]}]

    def test_legacy_format_defaults_vrf_to_default(self):
        """Test that ospf_1_vrf defaults to 'default' when not provided"""
        result = normalize_ospf_vrfs(
            None, ospf_1_vrf=None, ospf_areas=[{"ospf_1_area": "0.0.0.0"}]
        )
        assert result == [{"vrf": "default", "areas": [{"area": "0.0.0.0"}]}]

    def test_no_inputs_returns_empty_list(self):
        """Test that no config context input returns an empty list"""
        assert normalize_ospf_vrfs(None) == []
        assert normalize_ospf_vrfs([]) == []
        assert normalize_ospf_vrfs(None, None, None) == []


class TestFilterOspfVrfsInUse:
    """Tests for filter_ospf_vrfs_in_use function"""

    def test_keeps_default_vrf_always(self):
        """Test that the 'default' VRF is kept even if not in vrf_names_in_use"""
        ospf_vrfs = [{"vrf": "default", "areas": [{"area": "0.0.0.0"}]}]
        result = filter_ospf_vrfs_in_use(ospf_vrfs, [])
        assert result == ospf_vrfs

    def test_drops_vrf_not_in_use(self):
        """Test that a non-default VRF absent from vrf_names_in_use is dropped"""
        ospf_vrfs = [
            {"vrf": "default", "areas": [{"area": "0.0.0.0"}]},
            {"vrf": "CUSTOMER", "areas": [{"area": "0.0.0.1"}]},
        ]
        result = filter_ospf_vrfs_in_use(ospf_vrfs, ["OTHER"])
        assert result == [{"vrf": "default", "areas": [{"area": "0.0.0.0"}]}]

    def test_keeps_vrf_in_use(self):
        """Test that a non-default VRF present in vrf_names_in_use is kept"""
        ospf_vrfs = [
            {"vrf": "default", "areas": [{"area": "0.0.0.0"}]},
            {"vrf": "CUSTOMER", "areas": [{"area": "0.0.0.1"}]},
        ]
        result = filter_ospf_vrfs_in_use(ospf_vrfs, ["CUSTOMER"])
        assert result == ospf_vrfs

    def test_empty_ospf_vrfs_returns_empty(self):
        """Test that an empty/None input returns an empty list"""
        assert filter_ospf_vrfs_in_use([], ["CUSTOMER"]) == []
        assert filter_ospf_vrfs_in_use(None, ["CUSTOMER"]) == []

    def test_none_vrf_names_in_use_only_keeps_default(self):
        """Test that None for vrf_names_in_use is treated as no VRFs in use"""
        ospf_vrfs = [
            {"vrf": "default", "areas": [{"area": "0.0.0.0"}]},
            {"vrf": "CUSTOMER", "areas": [{"area": "0.0.0.1"}]},
        ]
        result = filter_ospf_vrfs_in_use(ospf_vrfs, None)
        assert result == [{"vrf": "default", "areas": [{"area": "0.0.0.0"}]}]


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
        result_final = validate_ospf_config(device_config, interfaces)
        assert len(result_final["warnings"]) > 0


class TestGetOspfRouterChanges:
    """Tests for get_ospf_router_changes function"""

    def _config(self, router_id="10.255.255.1", vrfs=None):
        return {
            "process_id": 1,
            "router_id": router_id,
            "vrfs": vrfs
            if vrfs is not None
            else [{"vrf": "default", "areas": [{"area": "0.0.0.0"}]}],
        }

    def test_no_facts_pushes_everything(self):
        """No REST facts available - every VRF/area is returned for push"""
        result = get_ospf_router_changes(self._config(), None)
        assert len(result["router_changes"]) == 1
        assert result["area_additions"] == [{"vrf": "default", "area": "0.0.0.0"}]
        assert result["no_changes"] == []

    def test_matching_state_yields_no_changes(self):
        """Router-id and area already on device - nothing to push"""
        facts = {
            "default": {
                "1": {
                    "router_id": "10.255.255.1",
                    "areas": ["0.0.0.0"],
                    "passive_interfaces": [],
                }
            }
        }
        result = get_ospf_router_changes(self._config(), facts)
        assert result["router_changes"] == []
        assert result["area_additions"] == []
        assert result["no_changes"] == ["default"]

    def test_router_id_mismatch_detected(self):
        """Router-id differs from device state - flagged for push"""
        facts = {
            "default": {
                "1": {
                    "router_id": "10.255.255.9",
                    "areas": ["0.0.0.0"],
                    "passive_interfaces": [],
                }
            }
        }
        result = get_ospf_router_changes(self._config(), facts)
        assert len(result["router_changes"]) == 1
        assert result["router_changes"][0]["vrf"] == "default"
        assert result["area_additions"] == []

    def test_missing_area_detected(self):
        """Area not yet present on device - flagged for push"""
        facts = {
            "default": {
                "1": {
                    "router_id": "10.255.255.1",
                    "areas": [],
                    "passive_interfaces": [],
                }
            }
        }
        result = get_ospf_router_changes(self._config(), facts)
        assert result["router_changes"] == []
        assert result["area_additions"] == [{"vrf": "default", "area": "0.0.0.0"}]

    def test_no_router_id_skips_router_check(self):
        """No router-id desired - only areas are checked"""
        facts = {
            "default": {
                "1": {
                    "router_id": "",
                    "areas": ["0.0.0.0"],
                    "passive_interfaces": [],
                }
            }
        }
        result = get_ospf_router_changes(self._config(router_id=""), facts)
        assert result["router_changes"] == []
        assert result["no_changes"] == ["default"]

    def test_scalar_facts_value_does_not_crash(self):
        """Unexpected non-dict facts value coerces safely instead of crashing"""
        facts = {"default": "https://example/system/vrfs/default/ospf_routers"}
        result = get_ospf_router_changes(self._config(), facts)
        assert len(result["router_changes"]) == 1
        assert result["area_additions"] == [{"vrf": "default", "area": "0.0.0.0"}]


class TestGetOspfInterfaceChanges:
    """Tests for get_ospf_interface_changes function"""

    def _item(self, **overrides):
        item = {
            "interface_name": "vlan10",
            "vrf": "default",
            "area_id": "0.0.0.0",
            "network_type": "",
            "passive": False,
            "auth_enabled": True,
            "md5_auth_desired": False,
        }
        item.update(overrides)
        return item

    def test_no_facts_pushes_everything(self):
        """No REST facts available - every item is returned for push"""
        items = [self._item()]
        result = get_ospf_interface_changes(items, None, None)
        assert result["config_changes"] == items
        assert result["passive_clear"] == items
        assert result["no_changes"] == []

    def test_matching_state_yields_no_changes(self):
        """Interface already in area, broadcast type, no auth, not passive"""
        items = [self._item()]
        interface_facts = {
            "default": {
                "1": {
                    "0.0.0.0": {
                        "vlan10": {
                            "ospf_if_type": None,
                            "ospf_auth_type": "null",
                        }
                    }
                }
            }
        }
        router_facts = {"default": {"1": {"passive_interfaces": []}}}
        result = get_ospf_interface_changes(items, interface_facts, router_facts)
        assert result["config_changes"] == []
        assert result["passive_set"] == []
        assert result["passive_clear"] == []
        assert result["no_changes"] == ["vlan10"]

    def test_network_type_mismatch_detected(self):
        """Desired point-to-point differs from device broadcast (None)"""
        items = [self._item(network_type="point-to-point")]
        interface_facts = {
            "default": {"1": {"0.0.0.0": {"vlan10": {"ospf_if_type": None}}}}
        }
        router_facts = {"default": {"1": {"passive_interfaces": []}}}
        result = get_ospf_interface_changes(items, interface_facts, router_facts)
        assert len(result["config_changes"]) == 1

    def test_auth_state_mismatch_detected(self):
        """MD5 auth desired but device shows no auth configured"""
        items = [self._item(md5_auth_desired=True)]
        interface_facts = {
            "default": {
                "1": {"0.0.0.0": {"vlan10": {"ospf_if_type": None, "ospf_auth_type": "null"}}}
            }
        }
        router_facts = {"default": {"1": {"passive_interfaces": []}}}
        result = get_ospf_interface_changes(items, interface_facts, router_facts)
        assert len(result["config_changes"]) == 1

    def test_interface_not_in_area_detected(self):
        """Interface not yet registered in the desired area"""
        items = [self._item()]
        interface_facts = {"default": {"1": {"0.0.0.0": {}}}}
        router_facts = {"default": {"1": {"passive_interfaces": []}}}
        result = get_ospf_interface_changes(items, interface_facts, router_facts)
        assert result["config_changes"] == items

    def test_passive_set_detected(self):
        """Passive desired but interface not in device passive_interfaces"""
        items = [self._item(passive=True)]
        interface_facts = {
            "default": {"1": {"0.0.0.0": {"vlan10": {"ospf_if_type": None}}}}
        }
        router_facts = {"default": {"1": {"passive_interfaces": []}}}
        result = get_ospf_interface_changes(items, interface_facts, router_facts)
        assert result["passive_set"] == items
        assert result["passive_clear"] == []

    def test_passive_clear_detected(self):
        """Passive not desired but interface is in device passive_interfaces"""
        items = [self._item(passive=False)]
        interface_facts = {
            "default": {"1": {"0.0.0.0": {"vlan10": {"ospf_if_type": None}}}}
        }
        router_facts = {"default": {"1": {"passive_interfaces": ["vlan10"]}}}
        result = get_ospf_interface_changes(items, interface_facts, router_facts)
        assert result["passive_clear"] == items
        assert result["passive_set"] == []

    def test_loopback_skips_passive_check(self):
        """Loopback interfaces are excluded from passive set/clear entirely"""
        items = [self._item(interface_name="loopback1", passive=False)]
        interface_facts = {
            "default": {"1": {"0.0.0.0": {"loopback1": {"ospf_if_type": None}}}}
        }
        router_facts = {"default": {"1": {"passive_interfaces": ["loopback1"]}}}
        result = get_ospf_interface_changes(items, interface_facts, router_facts)
        assert result["passive_set"] == []
        assert result["passive_clear"] == []
        assert result["no_changes"] == ["loopback1"]

    def test_scalar_facts_value_does_not_crash(self):
        """Unexpected non-dict facts values coerce safely instead of crashing"""
        items = [self._item()]
        interface_facts = {"default": "https://example/ospf_interfaces"}
        router_facts = {"default": "https://example/ospf_routers"}
        result = get_ospf_interface_changes(items, interface_facts, router_facts)
        assert result["config_changes"] == items
