"""
Unit tests for HPE Aruba Networking Central connection filter functions
"""
from netbox_filters_lib.central_filters import (
    central_disabled_in_running_config,
    get_central_changes,
    has_device_tag,
)

TAG = "hpe-anw-central-mon"
TAGGED = ["dhcp", TAG]

# REST /system/hpe_anw_central responses (trimmed), from ao-01 / ao-02
REST_ENABLED = {"disable": False, "central_source": "activate", "status": {"central_connection": "connected"}}
REST_DISABLED = {"disable": True, "central_source": None, "status": {}}

RUNNING_DISABLED = """hostname ao-02
!
hpe-anw-central
    disable
ssh server vrf mgmt
!
"""
RUNNING_ENABLED = """hostname ao-01
!
ssh server vrf mgmt
!
"""


class TestHasDeviceTag:
    """Tests for has_device_tag"""

    def test_slug_string(self):
        assert has_device_tag(TAGGED, TAG) is True

    def test_missing(self):
        assert has_device_tag(["dhcp"], TAG) is False

    def test_case_insensitive(self):
        assert has_device_tag(["HPE-ANW-Central-Mon"], TAG) is True

    def test_tag_objects(self):
        assert has_device_tag([{"slug": TAG, "name": "Central monitor"}], TAG) is True
        assert has_device_tag([{"slug": "x", "name": "Central monitor"}], "central monitor") is True

    def test_empty_inputs(self):
        assert has_device_tag(None, TAG) is False
        assert has_device_tag(TAGGED, "") is False
        assert has_device_tag(TAGGED, None) is False


class TestCentralDisabledInRunningConfig:
    """Tests for central_disabled_in_running_config"""

    def test_disabled_block(self):
        assert central_disabled_in_running_config(RUNNING_DISABLED) is True

    def test_no_block_means_enabled(self):
        assert central_disabled_in_running_config(RUNNING_ENABLED) is False

    def test_disable_in_other_context_ignored(self):
        config = "interface 1/1/1\n    disable\nhpe-anw-central\n    exit\n"
        assert central_disabled_in_running_config(config) is False

    def test_empty(self):
        assert central_disabled_in_running_config(None) is False
        assert central_disabled_in_running_config("") is False


class TestGetCentralChanges:
    """Tests for get_central_changes"""

    def test_tagged_and_disabled_enables(self):
        result = get_central_changes(REST_DISABLED, TAGGED, TAG)
        assert result == {"desired": "enabled", "current": "disabled", "source": "rest", "action": "enable"}

    def test_tagged_and_enabled_no_change(self):
        assert get_central_changes(REST_ENABLED, TAGGED, TAG)["action"] is None

    def test_untagged_left_alone_outside_idempotent_mode(self):
        result = get_central_changes(REST_ENABLED, ["dhcp"], TAG)
        assert result["desired"] == "unmanaged"
        assert result["action"] is None

    def test_untagged_disabled_in_idempotent_mode(self):
        result = get_central_changes(REST_ENABLED, ["dhcp"], TAG, idempotent_mode=True)
        assert result["desired"] == "disabled"
        assert result["action"] == "disable"

    def test_untagged_already_disabled_in_idempotent_mode(self):
        assert get_central_changes(REST_DISABLED, [], TAG, idempotent_mode=True)["action"] is None

    def test_running_config_fallback(self):
        result = get_central_changes(None, TAGGED, TAG, running_config=RUNNING_DISABLED)
        assert result["source"] == "running_config"
        assert result["action"] == "enable"
        assert get_central_changes(None, TAGGED, TAG, running_config=RUNNING_ENABLED)["action"] is None

    def test_rest_facts_win_over_running_config(self):
        result = get_central_changes(REST_ENABLED, TAGGED, TAG, running_config=RUNNING_DISABLED)
        assert result["source"] == "rest"
        assert result["action"] is None

    def test_rest_facts_without_disable_key_fall_back(self):
        result = get_central_changes({}, TAGGED, TAG, running_config=RUNNING_DISABLED)
        assert result["source"] == "running_config"

    def test_unknown_state_pushes_desired(self):
        result = get_central_changes(None, TAGGED, TAG)
        assert result["current"] == "unknown"
        assert result["action"] == "enable"
        assert get_central_changes(None, [], TAG, idempotent_mode=True)["action"] == "disable"
