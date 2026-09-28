"""
Unit tests for SNMP filter functions
"""
from netbox_filters_lib.snmp_filters import (
    build_snmp_system_location,
    build_snmpv3_user_line,
    get_snmp_changes,
    resolve_snmp_vrf,
    validate_snmpv3_users,
)

MGMT_INTF = {
    "name": "mgmt",
    "mgmt_only": True,
    "ip_addresses": [{"address": "10.4.23.1/24"}],
}
SVI_INTF = {
    "name": "vlan10",
    "mgmt_only": False,
    "ip_addresses": [{"address": "10.10.0.5/24"}],
}
MGMT_NO_IP = {"name": "mgmt", "mgmt_only": True, "ip_addresses": []}

KEYS = {
    "snmplab": {
        "auth_pass": {"secret": "AQBauth", "encrypted": True},
        "priv_pass": {"secret": "AQBpriv", "encrypted": True},
    }
}
USER = {
    "name": "snmplab",
    "auth_protocol": "sha",
    "priv_protocol": "aes",
    "access_level": "ro",
}


class TestResolveSnmpVrf:
    """Tests for resolve_snmp_vrf"""

    def test_explicit_vrf_returned_unchanged(self):
        assert resolve_snmp_vrf("oob", [MGMT_INTF], "10.4.23.1") == "oob"

    def test_primary_ip_on_mgmt_interface(self):
        assert resolve_snmp_vrf("auto", [SVI_INTF, MGMT_INTF], "10.4.23.1") == "mgmt"

    def test_primary_ip_on_svi(self):
        intfs = [MGMT_NO_IP, SVI_INTF]
        assert resolve_snmp_vrf("auto", intfs, "10.10.0.5") == "default"

    def test_primary_ip_with_prefix_length(self):
        assert resolve_snmp_vrf("auto", [MGMT_INTF], "10.4.23.1/24") == "mgmt"

    def test_primary_ip_on_svi_even_if_mgmt_has_ip(self):
        assert resolve_snmp_vrf("auto", [MGMT_INTF, SVI_INTF], "10.10.0.5") == "default"

    def test_no_primary_ip_mgmt_interface_with_ip(self):
        assert resolve_snmp_vrf("auto", [SVI_INTF, MGMT_INTF], None) == "mgmt"

    def test_no_primary_ip_no_mgmt_ip(self):
        assert resolve_snmp_vrf("auto", [MGMT_NO_IP, SVI_INTF], "") == "default"

    def test_empty_setting_treated_as_auto(self):
        assert resolve_snmp_vrf("", [MGMT_INTF], "10.4.23.1") == "mgmt"

    def test_no_interfaces(self):
        assert resolve_snmp_vrf("auto", None, None) == "default"


class TestBuildSnmpSystemLocation:
    """Tests for build_snmp_system_location"""

    def test_explicit_value_wins(self):
        assert build_snmp_system_location("rack 4", ["site"], ["loc"]) == "rack 4"

    def test_site_and_location_lists(self):
        result = build_snmp_system_location("", ["bgp-isp-2"], ["bgp-location"])
        assert result == "bgp-isp-2/bgp-location"

    def test_site_only(self):
        assert build_snmp_system_location("", ["bgp-isp-2"], []) == "bgp-isp-2"

    def test_scalar_site_and_location(self):
        assert build_snmp_system_location("", "site-a", "room-1") == "site-a/room-1"

    def test_nothing_known(self):
        assert build_snmp_system_location("", None, None) == ""


class TestValidateSnmpv3Users:
    """Tests for validate_snmpv3_users"""

    def test_valid_user(self):
        result = validate_snmpv3_users([USER], KEYS)
        assert result == {"valid": True, "warnings": [], "errors": []}

    def test_empty_list_is_valid(self):
        assert validate_snmpv3_users([], {})["valid"] is True

    def test_not_a_list(self):
        assert validate_snmpv3_users({"name": "x"}, {})["valid"] is False

    def test_missing_name(self):
        result = validate_snmpv3_users([{"auth_protocol": "sha"}], KEYS)
        assert not result["valid"]
        assert "'name' is required" in result["errors"][0]

    def test_invalid_protocols_and_access_level(self):
        user = dict(USER, auth_protocol="sha1", priv_protocol="3des", access_level="admin")
        errors = validate_snmpv3_users([user], KEYS)["errors"]
        assert len(errors) == 3

    def test_priv_without_auth(self):
        user = {"name": "snmplab", "priv_protocol": "aes"}
        errors = validate_snmpv3_users([user], KEYS)["errors"]
        assert any("requires auth_protocol" in e for e in errors)

    def test_missing_keys(self):
        errors = validate_snmpv3_users([USER], {})["errors"]
        assert any("auth_pass" in e for e in errors)
        assert any("priv_pass" in e for e in errors)

    def test_duplicate_user(self):
        result = validate_snmpv3_users([USER, USER], KEYS)
        assert any("duplicate" in e for e in result["errors"])

    def test_weak_protocols_warn(self):
        user = dict(USER, auth_protocol="md5", priv_protocol="des")
        result = validate_snmpv3_users([user], KEYS)
        assert result["valid"] is True
        assert len(result["warnings"]) == 2

    def test_errors_do_not_leak_secrets(self):
        user = dict(USER, auth_protocol="bad")
        result = validate_snmpv3_users([user], KEYS)
        assert not any("AQB" in e for e in result["errors"] + result["warnings"])


class TestBuildSnmpv3UserLine:
    """Tests for build_snmpv3_user_line"""

    def test_auth_priv_ciphertext(self):
        """Matches the lab switch running-config rendering"""
        assert build_snmpv3_user_line(USER, KEYS) == (
            "snmpv3 user snmplab auth sha auth-pass ciphertext AQBauth "
            "priv aes priv-pass ciphertext AQBpriv"
        )

    def test_plaintext_keys(self):
        keys = {"snmplab": {"auth_pass": "lab-auth", "priv_pass": {"secret": "lab-priv"}}}
        assert build_snmpv3_user_line(USER, keys) == (
            "snmpv3 user snmplab auth sha auth-pass plaintext lab-auth "
            "priv aes priv-pass plaintext lab-priv"
        )

    def test_auth_only_rw(self):
        user = {"name": "snmplab", "auth_protocol": "sha256", "access_level": "rw"}
        assert build_snmpv3_user_line(user, KEYS) == (
            "snmpv3 user snmplab auth sha256 auth-pass ciphertext AQBauth access-level rw"
        )

    def test_no_auth_ro_omits_access_level(self):
        """access-level ro is the AOS-CX default and not shown in running-config"""
        assert build_snmpv3_user_line({"name": "nms"}, {}) == "snmpv3 user nms"


ACTUAL_USER = {
    "auth_protocol": "sha",
    "priv_protocol": "aes",
    "access_level": "ro",
    "auth_pass_phrase": "AQBauth",
    "priv_pass_phrase": "AQBpriv",
}
IN_SYNC_FACTS = {
    "system_location": "bgp-isp-2/bgp-location",
    "system_contact": "",
    "vrfs": ["mgmt"],
    "users": {"snmplab": ACTUAL_USER},
}
LOCATION = "bgp-isp-2/bgp-location"


def _changes(facts, users=None, keys=None, vrf="mgmt", location=LOCATION, contact=""):
    return get_snmp_changes(
        facts, vrf, location, contact,
        [USER] if users is None else users,
        KEYS if keys is None else keys,
    )


class TestGetSnmpChanges:
    """Tests for get_snmp_changes"""

    def test_no_facts_pushes_everything_removes_nothing(self):
        result = _changes(None, contact="noc@example.net")
        assert result["lines_to_push"] == [
            "snmp-server vrf mgmt",
            "snmp-server system-location bgp-isp-2/bgp-location",
            "snmp-server system-contact noc@example.net",
        ]
        assert result["users_to_push"] == [USER]
        assert result["lines_to_remove"] == []

    def test_in_sync(self):
        result = _changes(IN_SYNC_FACTS)
        assert result == {"lines_to_push": [], "users_to_push": [], "lines_to_remove": []}

    def test_location_differs(self):
        facts = dict(IN_SYNC_FACTS, system_location="bgp-isp-2 virtuell")
        result = _changes(facts)
        assert result["lines_to_push"] == [
            "snmp-server system-location bgp-isp-2/bgp-location"
        ]

    def test_vrf_moved(self):
        result = _changes(IN_SYNC_FACTS, vrf="default")
        assert result["lines_to_push"] == ["snmp-server vrf default"]
        assert result["lines_to_remove"] == ["no snmp-server vrf mgmt"]

    def test_extra_user_removed(self):
        facts = dict(IN_SYNC_FACTS, users={"snmplab": ACTUAL_USER, "old": ACTUAL_USER})
        assert _changes(facts)["lines_to_remove"] == ["no snmpv3 user old"]

    def test_missing_user_pushed(self):
        facts = dict(IN_SYNC_FACTS, users={})
        assert _changes(facts)["users_to_push"] == [USER]

    def test_protocol_change_pushed(self):
        facts = dict(IN_SYNC_FACTS, users={"snmplab": dict(ACTUAL_USER, auth_protocol="md5")})
        assert _changes(facts)["users_to_push"] == [USER]

    def test_access_level_change_pushed(self):
        facts = dict(IN_SYNC_FACTS, users={"snmplab": dict(ACTUAL_USER, access_level="rw")})
        assert _changes(facts)["users_to_push"] == [USER]

    def test_ciphertext_change_pushed(self):
        facts = dict(IN_SYNC_FACTS, users={"snmplab": dict(ACTUAL_USER, priv_pass_phrase="AQBold")})
        assert _changes(facts)["users_to_push"] == [USER]

    def test_plaintext_secret_never_compared(self):
        """Plaintext passphrases cannot be compared with device ciphertext"""
        keys = {"snmplab": {"auth_pass": "lab-auth", "priv_pass": "lab-priv"}}
        assert _changes(IN_SYNC_FACTS, keys=keys)["users_to_push"] == []

    def test_contact_removed_when_unset(self):
        facts = dict(IN_SYNC_FACTS, system_contact="old@example.net")
        assert _changes(facts)["lines_to_remove"] == ["no snmp-server system-contact"]

    def test_location_removed_when_unknown(self):
        assert _changes(IN_SYNC_FACTS, location="")["lines_to_remove"] == [
            "no snmp-server system-location"
        ]

    def test_no_users_desired_removes_all(self):
        assert _changes(IN_SYNC_FACTS, users=[])["lines_to_remove"] == [
            "no snmpv3 user snmplab"
        ]

    def test_nothing_desired_removes_everything(self):
        """SNMP variables removed + idempotent mode: strip SNMP from the device"""
        facts = dict(IN_SYNC_FACTS, system_contact="noc@example.net")
        result = _changes(facts, users=[], vrf="", location="", contact="")
        assert result["lines_to_push"] == []
        assert result["users_to_push"] == []
        assert result["lines_to_remove"] == [
            "no snmpv3 user snmplab",
            "no snmp-server vrf mgmt",
            "no snmp-server system-location",
            "no snmp-server system-contact",
        ]

    def test_nothing_desired_without_facts_is_a_noop(self):
        result = _changes(None, users=[], vrf="", location="", contact="")
        assert result == {"lines_to_push": [], "users_to_push": [], "lines_to_remove": []}
