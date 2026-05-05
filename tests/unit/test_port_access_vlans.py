"""
Unit tests for port-access VLAN extraction and integration with
``get_vlans_in_use``.
"""
import pytest

from netbox_filters_lib.vlan_filters import (
    extract_port_access_vlan_ids,
    get_vlans_in_use,
    parse_vlan_id_spec,
)


class TestParseVlanIdSpec:
    def test_none_returns_empty(self):
        assert parse_vlan_id_spec(None) == []

    def test_single_int(self):
        assert parse_vlan_id_spec(11) == [11]

    def test_single_string(self):
        assert parse_vlan_id_spec("11") == [11]

    def test_comma_list(self):
        assert parse_vlan_id_spec("11,13,15") == [11, 13, 15]

    def test_range(self):
        assert parse_vlan_id_spec("11-13") == [11, 12, 13]

    def test_mixed_range_and_list(self):
        assert parse_vlan_id_spec("11,13,15-20") == [11, 13, 15, 16, 17, 18, 19, 20]

    def test_whitespace_tolerated(self):
        assert parse_vlan_id_spec(" 11 , 13 - 15 ") == [11, 13, 14, 15]

    def test_reverse_range_normalised(self):
        assert parse_vlan_id_spec("15-13") == [13, 14, 15]

    def test_dedupe(self):
        assert parse_vlan_id_spec("11,11,11-12") == [11, 12]

    def test_invalid_token_skipped(self):
        assert parse_vlan_id_spec("11,foo,13") == [11, 13]

    def test_out_of_range_skipped(self):
        assert parse_vlan_id_spec("0,1,4094,4095") == [1, 4094]

    def test_list_input(self):
        assert parse_vlan_id_spec([11, "13-14", "20"]) == [11, 13, 14, 20]

    def test_bool_rejected(self):
        assert parse_vlan_id_spec(True) == []
        assert parse_vlan_id_spec(False) == []


class TestExtractPortAccessVlanIds:
    def test_none(self):
        assert extract_port_access_vlan_ids(None) == []

    def test_empty(self):
        assert extract_port_access_vlan_ids({}) == []

    def test_no_roles(self):
        assert extract_port_access_vlan_ids({"lldp_groups": []}) == []

    def test_single_role(self):
        port_access = {
            "roles": [
                {
                    "name": "Lab-IAP-role",
                    "vlan_trunk_native": 11,
                    "vlan_trunk_allowed": "11-13",
                }
            ]
        }
        assert extract_port_access_vlan_ids(port_access) == [11, 12, 13]

    def test_multiple_roles_dedupe(self):
        port_access = {
            "roles": [
                {"vlan_trunk_native": 11, "vlan_trunk_allowed": "11-13"},
                {"vlan_trunk_native": 20, "vlan_trunk_allowed": "20,21"},
            ]
        }
        assert extract_port_access_vlan_ids(port_access) == [11, 12, 13, 20, 21]

    def test_vlan_access_shorthand(self):
        port_access = {"roles": [{"vlan_access": 50}]}
        assert extract_port_access_vlan_ids(port_access) == [50]

    def test_role_without_vlans(self):
        port_access = {"roles": [{"name": "no-vlans", "description": "x"}]}
        assert extract_port_access_vlan_ids(port_access) == []

    def test_non_dict_role_skipped(self):
        port_access = {"roles": [None, "bogus", {"vlan_trunk_native": 7}]}
        assert extract_port_access_vlan_ids(port_access) == [7]


class TestGetVlansInUseWithPortAccess:
    def test_port_access_vids_added(self):
        interfaces = [
            {"name": "1/1/1", "untagged_vlan": {"vid": 100}, "tagged_vlans": []}
        ]
        port_access = {
            "roles": [
                {"vlan_trunk_native": 11, "vlan_trunk_allowed": "11-13"},
            ]
        }
        result = get_vlans_in_use(interfaces, port_access=port_access)
        assert result["vids"] == [11, 12, 13, 100]

    def test_port_access_none_is_noop(self):
        interfaces = [
            {"name": "1/1/1", "untagged_vlan": {"vid": 100}, "tagged_vlans": []}
        ]
        result = get_vlans_in_use(interfaces, port_access=None)
        assert result["vids"] == [100]

    def test_port_access_overlap_dedupes(self):
        interfaces = [
            {"name": "1/1/1", "untagged_vlan": {"vid": 11}, "tagged_vlans": []}
        ]
        port_access = {"roles": [{"vlan_trunk_allowed": "11-12"}]}
        result = get_vlans_in_use(interfaces, port_access=port_access)
        assert result["vids"] == [11, 12]

    def test_backward_compatible_signature(self):
        # Existing two-arg call form must still work
        interfaces = [
            {"name": "1/1/1", "untagged_vlan": {"vid": 10}, "tagged_vlans": []}
        ]
        result = get_vlans_in_use(interfaces, [])
        assert result["vids"] == [10]
