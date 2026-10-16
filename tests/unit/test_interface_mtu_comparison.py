"""
MTU comparison must read the field the role actually configures.

Observed on ao-01 (firmware 10.16) via REST, all with MTU 9198 in NetBox:

- 1/1/17 (physical, `mtu 9198`): user_config.mtu = 9198, top-level mtu = 9500
- lag100 (routed LAG, `ip mtu 9198`): ip_mtu = 9198, mtu = null
- vlan5 (SVI, `ip mtu 9198`): ip_mtu = 9198, mtu = null
- lag256 (L2 LAG, no MTU line): ip_mtu = 1500, mtu = null

The role pushes `mtu` (aoscx_interface, stored in user_config.mtu) on
physical ports and `ip mtu` (build_l3_config_lines) on L3 interfaces, and
never pushes an MTU on L2 LAGs. Comparing the top-level `mtu` flagged every
one of these interfaces on every run.
"""
from netbox_filters_lib.interface_change_detection import (
    get_interfaces_needing_config_changes,
)
from rest_api_transforms import rest_api_to_aoscx_interfaces


def _nb(name, type_value, mtu=9198, mode=None, ips=None):
    intf = {
        "name": name,
        "type": {"value": type_value},
        "enabled": True,
        "description": "",
        "mtu": mtu,
        "lag": None,
        "mode": {"value": mode} if mode else None,
        "untagged_vlan": None,
        "tagged_vlans": [],
        "custom_fields": {"if_mclag": False},
        "ip_addresses": ips or [],
    }
    return intf


def _run(nb, rest_intf):
    """Run change detection the way the role does with REST facts."""
    device = rest_api_to_aoscx_interfaces({nb["name"]: rest_intf})
    facts = {"network_resources": {"interfaces": device}}
    return get_interfaces_needing_config_changes([nb], facts, {nb["name"]: rest_intf})


def _names(result, key):
    return [i["name"] for i in result[key]]


_UC = {"admin": "up", "split_count": "4"}


class TestPhysicalMtu:
    def test_configured_mtu_read_from_user_config(self):
        rest = {"name": "1/1/17", "type": "system", "routing": None, "mtu": 9500,
                "ip_mtu": None, "user_config": dict(_UC, mtu=9198)}
        result = _run(_nb("1/1/17", "10gbase-x-sfpp"), rest)
        assert _names(result, "physical") == []
        assert _names(result, "no_changes") == ["1/1/17"]

    def test_user_config_mtu_mismatch_flagged(self):
        rest = {"name": "1/1/17", "type": "system", "routing": None, "mtu": 9198,
                "ip_mtu": None, "user_config": dict(_UC, mtu=1500)}
        result = _run(_nb("1/1/17", "10gbase-x-sfpp"), rest)
        assert _names(result, "physical") == ["1/1/17"]

    def test_no_user_config_mtu_falls_back_to_mtu(self):
        # Previous behaviour: compare top-level mtu (None treated as 0)
        rest = {"name": "1/1/17", "type": "system", "routing": None, "mtu": None,
                "ip_mtu": None, "user_config": dict(_UC)}
        result = _run(_nb("1/1/17", "10gbase-x-sfpp"), rest)
        assert _names(result, "physical") == ["1/1/17"]


class TestL3Mtu:
    def test_svi_ip_mtu_matches(self):
        rest = {"name": "vlan5", "type": "vlan", "routing": True, "mtu": None,
                "ip_mtu": 9198, "user_config": dict(_UC)}
        result = _run(_nb("vlan5", "virtual"), rest)
        assert _names(result, "l3") == []

    def test_svi_ip_mtu_mismatch_flagged(self):
        rest = {"name": "vlan5", "type": "vlan", "routing": True, "mtu": None,
                "ip_mtu": 1500, "user_config": dict(_UC)}
        result = _run(_nb("vlan5", "virtual"), rest)
        assert _names(result, "l3") == ["vlan5"]
        assert result["l3"][0]["_ip_changes"]["mtu_change"] is True

    def test_routed_lag_ip_mtu_matches(self):
        rest = {"name": "lag100", "type": "lag", "routing": True, "mtu": None,
                "ip_mtu": 9198, "user_config": None}
        result = _run(_nb("lag100", "lag"), rest)
        assert _names(result, "lag") == []
        assert _names(result, "no_changes") == ["lag100"]

    def test_routed_lag_ip_mtu_mismatch_reaches_l3_push(self):
        rest = {"name": "lag100", "type": "lag", "routing": True, "mtu": None,
                "ip_mtu": 1500, "user_config": None}
        result = _run(
            _nb("lag100", "lag", ips=[{"address": "172.27.250.3/31"}]), rest
        )
        assert _names(result, "l3") == ["lag100"]
        assert result["l3"][0]["_ip_changes"]["mtu_change"] is True

    def test_svi_without_ip_mtu_key_keeps_previous_behaviour(self):
        # Facts without ip_mtu (e.g. aoscx_facts module): compare mtu as before
        device = {"vlan5": {"name": "vlan5", "mtu": None, "user_config": {}}}
        facts = {"network_resources": {"interfaces": device}}
        result = get_interfaces_needing_config_changes([_nb("vlan5", "virtual")], facts)
        assert _names(result, "l3") == ["vlan5"]


class TestL2LagMtu:
    def test_l2_lag_mtu_not_compared(self):
        # The role never pushes an MTU on an L2 LAG (members carry it)
        rest = {"name": "lag256", "type": "lag", "routing": False, "mtu": None,
                "ip_mtu": 1500, "user_config": None,
                "vlan_mode": "native-tagged", "vlan_tag": {"1": "x"}}
        result = _run(_nb("lag256", "lag", mode="tagged-all"), rest)
        assert _names(result, "lag") == []
        assert _names(result, "no_changes") == ["lag256"]

    def test_lag_without_routing_key_keeps_previous_behaviour(self):
        device = {"lag256": {"name": "lag256", "type": "lag", "mtu": None}}
        facts = {"network_resources": {"interfaces": device}}
        result = get_interfaces_needing_config_changes([_nb("lag256", "lag")], facts)
        assert _names(result, "lag") == ["lag256"]
