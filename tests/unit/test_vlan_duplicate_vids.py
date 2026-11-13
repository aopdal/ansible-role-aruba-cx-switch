"""
Unit tests for resolve_duplicate_vlan_vids (several NetBox VLANs, one VID)
"""
from netbox_filters_lib.vlan_filters import resolve_duplicate_vlan_vids


def _vlan(obj_id, vid, name, group=None):
    vlan = {"id": obj_id, "vid": vid, "name": name}
    if group:
        vlan["group"] = {"name": group, "slug": group.lower()}
    return vlan


GOOD = _vlan(852, 20, "zL2 vlan 20", "L2_Fabric")
BAD = _vlan(875, 20, "Bad - VLAN 20", "L2_Fabric-fail")
OTHER = _vlan(853, 15, "zL2 vlan 15", "L2_Fabric")


class TestResolveDuplicateVlanVids:
    def test_empty_input(self):
        assert resolve_duplicate_vlan_vids(None) == {
            "vlans": [], "resolved": [], "conflicts": []}
        assert resolve_duplicate_vlan_vids([], [])["vlans"] == []

    def test_no_duplicates_passthrough(self):
        result = resolve_duplicate_vlan_vids([OTHER, GOOD], [])
        assert result["vlans"] == [OTHER, GOOD]
        assert result["resolved"] == []
        assert result["conflicts"] == []

    def test_keeps_referenced_vlan_even_if_listed_first(self):
        interfaces = [{"name": "1/1/1", "untagged_vlan": {"id": 852, "vid": 20}}]
        result = resolve_duplicate_vlan_vids([OTHER, GOOD, BAD], interfaces)
        assert result["vlans"] == [OTHER, GOOD]
        assert result["conflicts"] == []
        (res,) = result["resolved"]
        assert res["vid"] == 20
        assert res["reason"] == "referenced"
        assert res["kept"]["id"] == 852
        assert [d["id"] for d in res["dropped"]] == [875]
        assert res["dropped"][0]["group"] == "L2_Fabric-fail"

    def test_keeps_referenced_vlan_when_listed_last(self):
        interfaces = [{"name": "1/1/1", "tagged_vlans": [{"id": 875, "vid": 20}]}]
        result = resolve_duplicate_vlan_vids([GOOD, BAD], interfaces)
        assert result["vlans"] == [BAD]
        assert result["resolved"][0]["kept"]["id"] == 875

    def test_unreferenced_duplicates_keep_lowest_id(self):
        result = resolve_duplicate_vlan_vids([BAD, GOOD], [])
        assert result["vlans"] == [GOOD]
        assert result["resolved"][0]["reason"] == "unreferenced"
        assert result["resolved"][0]["kept"]["id"] == 852

    def test_conflict_when_both_referenced(self):
        interfaces = [
            {"name": "1/1/1", "untagged_vlan": {"id": 852, "vid": 20}},
            {"name": "1/1/2", "tagged_vlans": [{"id": 875, "vid": 20}]},
        ]
        result = resolve_duplicate_vlan_vids([GOOD, BAD, OTHER], interfaces)
        assert result["resolved"] == []
        (conflict,) = result["conflicts"]
        assert conflict["vid"] == 20
        assert [v["id"] for v in conflict["vlans"]] == [852, 875]
        # Still one object per VID so output stays deterministic
        assert [v["id"] for v in result["vlans"]] == [852, 853]

    def test_ignores_malformed_entries(self):
        interfaces = [None, {"name": "x", "untagged_vlan": None,
                             "tagged_vlans": [None, {"vid": 20}]}]
        result = resolve_duplicate_vlan_vids([None, GOOD, "junk", BAD], interfaces)
        assert result["vlans"] == [GOOD]
        assert result["resolved"][0]["reason"] == "unreferenced"

    def test_idempotent_on_resolved_output(self):
        interfaces = [{"name": "1/1/1", "untagged_vlan": {"id": 852, "vid": 20}}]
        first = resolve_duplicate_vlan_vids([GOOD, BAD], interfaces)
        second = resolve_duplicate_vlan_vids(first["vlans"], interfaces)
        assert second["vlans"] == first["vlans"]
        assert second["resolved"] == []
