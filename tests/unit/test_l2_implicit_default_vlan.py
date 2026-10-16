"""
AOS-CX does not report the default L2 state in REST facts.

An L2 interface configured as `vlan access 1` (the platform default) is
returned with vlan_mode/vlan_tag null and vlan_trunks empty, observed on a
6300 VSF stack (lag1, firmware 10.16) while `show running-config interface
lag1` showed `vlan access 1`. `routing: false` is the only signal that the
interface is L2. Change detection must treat that state as access VLAN 1,
otherwise a NetBox access-VLAN-1 interface is flagged on every run.
"""
import pytest

from netbox_filters_lib.interface_change_detection import (
    get_interfaces_needing_config_changes,
)


def _nb(name="lag1", type_value="lag", mode="access", untagged=1, tagged=None):
    return {
        "name": name,
        "type": {"value": type_value},
        "enabled": True,
        "description": "",
        "mtu": None,
        "lag": None,
        "mode": {"value": mode},
        "untagged_vlan": {"vid": untagged} if untagged is not None else None,
        "tagged_vlans": [{"vid": v} for v in (tagged or [])],
        "custom_fields": {"if_mclag": False},
        "ip_addresses": [],
    }


def _device(name="lag1", **overrides):
    # Shape as seen from rest_api_to_aoscx_interfaces() for lag1 on the lab stack
    intf = {
        "name": name,
        "admin": "up",
        "user_config": None,
        "description": None,
        "mtu": None,
        "type": "lag",
        "routing": False,
        "vlan_mode": None,
        "vlan_tag": None,
        "vlan_trunks": {},
        "interfaces": {},
    }
    intf.update(overrides)
    return intf


def _run(nb, dev):
    facts = {"network_resources": {"interfaces": {nb["name"]: dev}}}
    return get_interfaces_needing_config_changes([nb], facts)


class TestImplicitAccessVlan1:
    def test_lag_access_vlan1_matches_default_state(self):
        result = _run(_nb(), _device())
        assert result["l2"] == []
        assert result["lag"] == []
        assert [i["name"] for i in result["no_changes"]] == ["lag1"]

    def test_physical_access_vlan1_matches_default_state(self):
        result = _run(
            _nb("1/1/5", "1000base-t"), _device("1/1/5", type="system")
        )
        assert result["l2"] == []
        assert [i["name"] for i in result["no_changes"]] == ["1/1/5"]

    def test_access_other_vlan_still_flagged(self):
        result = _run(_nb(untagged=10), _device())
        assert [i["name"] for i in result["l2"]] == ["lag1"]

    @pytest.mark.parametrize(
        "mode,untagged,tagged",
        [("tagged", 1, [10]), ("tagged", None, [10, 20]), ("tagged-all", None, [])],
    )
    def test_trunk_wanted_still_flagged(self, mode, untagged, tagged):
        result = _run(_nb(mode=mode, untagged=untagged, tagged=tagged), _device())
        assert [i["name"] for i in result["l2"]] == ["lag1"]


class TestNoImplicitDefaultWithoutL2Signal:
    """Without an explicit routing: false, keep the conservative behaviour."""

    def test_routing_missing_still_flagged(self):
        dev = _device()
        del dev["routing"]
        result = _run(_nb(), dev)
        assert [i["name"] for i in result["l2"]] == ["lag1"]

    def test_routed_interface_still_flagged(self):
        result = _run(_nb(), _device(routing=True))
        assert [i["name"] for i in result["l2"]] == ["lag1"]
