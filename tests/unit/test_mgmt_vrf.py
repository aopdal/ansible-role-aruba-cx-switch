"""
Unit tests for management VRF filter functions
"""
from netbox_filters_lib.mgmt_vrf import get_server_vrfs, resolve_mgmt_vrf

OOBM = {"name": "mgmt", "mgmt_only": True, "ip_addresses": [{"address": "10.4.23.1/24"}]}
# CX 6000 without an OOBM port: in-band SVI flagged mgmt_only in NetBox
INBAND_SVI = {
    "name": "vlan1",
    "mgmt_only": True,
    "vrf": None,
    "ip_addresses": [{"address": "172.16.3.48/24"}],
}
USER_VRF_SVI = {
    "name": "vlan99",
    "mgmt_only": False,
    "vrf": {"name": "OOB"},
    "ip_addresses": [{"address": "10.99.0.5/24"}],
}
GLOBAL_VRF_SVI = dict(USER_VRF_SVI, vrf={"name": "Global"})


class TestResolveMgmtVrf:
    """Tests for resolve_mgmt_vrf"""

    def test_oobm_port(self):
        assert resolve_mgmt_vrf([INBAND_SVI, OOBM], "10.4.23.1") == "mgmt"

    def test_inband_svi_flagged_mgmt_only(self):
        assert resolve_mgmt_vrf([INBAND_SVI], "172.16.3.48") == "default"

    def test_inband_user_vrf(self):
        assert resolve_mgmt_vrf([USER_VRF_SVI], "10.99.0.5") == "OOB"

    def test_inband_vrf_given_as_string(self):
        assert resolve_mgmt_vrf([dict(USER_VRF_SVI, vrf="OOB")], "10.99.0.5") == "OOB"

    def test_builtin_vrf_name_maps_to_default(self):
        assert resolve_mgmt_vrf([GLOBAL_VRF_SVI], "10.99.0.5") == "default"

    def test_primary_ip_with_prefix_length(self):
        assert resolve_mgmt_vrf([OOBM], "10.4.23.1/24") == "mgmt"

    def test_primary_ip_not_found(self):
        assert resolve_mgmt_vrf([OOBM], "192.0.2.1") is None

    def test_no_primary_ip(self):
        assert resolve_mgmt_vrf([OOBM], None) is None
        assert resolve_mgmt_vrf([OOBM], "") is None


class TestGetServerVrfs:
    """Tests for get_server_vrfs"""

    def test_oobm_device_needs_no_extra_vrf(self):
        assert get_server_vrfs([OOBM], "10.4.23.1", ["leaf"]) == []

    def test_inband_device_gets_default(self):
        assert get_server_vrfs([INBAND_SVI], "172.16.3.48", ["leaf"]) == ["default"]

    def test_inband_user_vrf(self):
        assert get_server_vrfs([USER_VRF_SVI], "10.99.0.5", ["leaf"]) == ["OOB"]

    def test_access_switch_always_gets_default(self):
        assert get_server_vrfs([OOBM], "10.4.23.1", ["access-switch"]) == ["default"]

    def test_access_switch_role_case_insensitive(self):
        assert get_server_vrfs([], None, ["Access-Switch"]) == ["default"]

    def test_access_switch_inband_not_duplicated(self):
        assert get_server_vrfs([INBAND_SVI], "172.16.3.48", ["access-switch"]) == ["default"]

    def test_access_switch_plus_user_vrf(self):
        assert get_server_vrfs([USER_VRF_SVI], "10.99.0.5", ["access-switch"]) == [
            "OOB",
            "default",
        ]

    def test_unknown_primary_ip_adds_nothing(self):
        """Never open ssh/https in a VRF that could not be determined"""
        assert get_server_vrfs([INBAND_SVI], None, ["leaf"]) == []

    def test_no_roles(self):
        assert get_server_vrfs([INBAND_SVI], "172.16.3.48", None) == ["default"]

    def test_role_as_string(self):
        assert get_server_vrfs([], None, "access-switch") == ["default"]
