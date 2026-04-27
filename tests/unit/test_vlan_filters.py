"""
Unit tests for VLAN filter functions
"""
import pytest
from netbox_filters_lib.vlan_filters import (
    extract_vlan_ids,
    filter_vlans_in_use,
    extract_evpn_vlans,
    extract_vxlan_mappings,
    get_vlans_in_use,
    get_vlans_needing_changes,
    get_vlan_interfaces,
    parse_evpn_evi_output,
)
from .fixtures import get_sample_interfaces, get_sample_vlans


class TestExtractVlanIds:
    """Tests for extract_vlan_ids function"""

    def test_extract_from_access_port(self):
        """Test extracting VLAN from access port"""
        interfaces = [
            {
                "name": "1/1/1",
                "untagged_vlan": {"vid": 10},
                "tagged_vlans": [],
            }
        ]
        result = extract_vlan_ids(interfaces)
        assert result == [10]

    def test_extract_from_trunk_port(self):
        """Test extracting VLANs from trunk port"""
        interfaces = [
            {
                "name": "1/1/2",
                "untagged_vlan": None,
                "tagged_vlans": [{"vid": 20}, {"vid": 30}],
            }
        ]
        result = extract_vlan_ids(interfaces)
        assert result == [20, 30]

    def test_skip_tagged_vlans_on_subinterface(self):
        """Tagged VLANs on subinterfaces should not drive VLAN creation."""
        interfaces = [
            {
                "name": "1/1/3.100",
                "type": {"value": "virtual"},
                "parent": {"name": "1/1/3"},
                "untagged_vlan": None,
                "tagged_vlans": [{"vid": 100}],
            }
        ]
        result = extract_vlan_ids(interfaces)
        assert result == []

    def test_extract_from_vlan_interface(self):
        """Test extracting VLAN from VLAN interface"""
        interfaces = [{"name": "vlan100"}]
        result = extract_vlan_ids(interfaces)
        assert result == [100]

    def test_extract_all_vlan_sources(self):
        """Test extracting VLANs from multiple sources"""
        interfaces = get_sample_interfaces()
        result = extract_vlan_ids(interfaces)
        assert sorted(result) == [10, 20, 30, 50, 100, 200, 300]

    def test_empty_interfaces(self):
        """Test with empty interface list"""
        result = extract_vlan_ids([])
        assert result == []

    def test_no_vlans_configured(self):
        """Test with interfaces that have no VLANs"""
        interfaces = [{"name": "1/1/1", "untagged_vlan": None, "tagged_vlans": []}]
        result = extract_vlan_ids(interfaces)
        assert result == []

    def test_invalid_vlan_name(self):
        """Test with invalid VLAN interface name"""
        interfaces = [{"name": "vlan_invalid"}]
        result = extract_vlan_ids(interfaces)
        assert result == []


class TestFilterVlansInUse:
    """Tests for filter_vlans_in_use function"""

    def test_filter_vlans_in_use(self):
        """Test filtering VLANs that are in use"""
        vlans = get_sample_vlans()
        interfaces = get_sample_interfaces()
        result = filter_vlans_in_use(vlans, interfaces)
        result_vids = [v["vid"] for v in result]
        assert sorted(result_vids) == [10, 20, 30, 100]

    def test_no_vlans_in_use(self):
        """Test when no VLANs are in use"""
        vlans = get_sample_vlans()
        interfaces = []
        result = filter_vlans_in_use(vlans, interfaces)
        assert result == []

    def test_all_vlans_in_use(self):
        """Test when all VLANs are in use"""
        vlans = [{"vid": 10, "name": "VLAN10"}]
        interfaces = [{"name": "1/1/1", "untagged_vlan": {"vid": 10}, "tagged_vlans": []}]
        result = filter_vlans_in_use(vlans, interfaces)
        assert len(result) == 1
        assert result[0]["vid"] == 10


class TestExtractEvpnVlans:
    """Tests for extract_evpn_vlans function"""

    def test_extract_evpn_vlans(self):
        """Test extracting VLANs configured for EVPN"""
        vlans = get_sample_vlans()
        interfaces = get_sample_interfaces()
        result = extract_evpn_vlans(vlans, interfaces)
        assert len(result) == 1
        assert result[0]["vid"] == 100

    def test_evpn_with_noevpn_flag(self):
        """Test EVPN extraction respects vlan_noevpn flag"""
        vlans = [
            {
                "vid": 100,
                "name": "VLAN100",
                "custom_fields": {"vlan_noevpn": True},
                "l2vpn_termination": {"l2vpn": {"name": "EVPN"}},
            }
        ]
        interfaces = [{"name": "vlan100"}]
        result = extract_evpn_vlans(vlans, interfaces, check_noevpn=True)
        assert len(result) == 0

    def test_evpn_without_l2vpn_termination(self):
        """Test VLANs without L2VPN termination are excluded"""
        vlans = [{"vid": 10, "name": "VLAN10", "custom_fields": {}}]
        interfaces = [{"name": "vlan10"}]
        result = extract_evpn_vlans(vlans, interfaces)
        assert len(result) == 0


class TestExtractVxlanMappings:
    """Tests for extract_vxlan_mappings function"""

    def test_extract_vxlan_mappings_with_l2vpn_id(self):
        """Test extracting VXLAN VNI mappings from L2VPN ID"""
        vlans = [
            {
                "vid": 100,
                "name": "VLAN100",
                "l2vpn_termination": {"l2vpn": {"identifier": 10100}},
            }
        ]
        interfaces = [{"name": "vlan100"}]
        result = extract_vxlan_mappings(vlans, interfaces, use_l2vpn_id=True)
        assert len(result) == 1
        assert result[0]["vlan"] == 100
        assert result[0]["vni"] == 10100

    def test_extract_vxlan_mappings_with_custom_field(self):
        """Test extracting VXLAN VNI mappings using VLAN ID as VNI"""
        vlans = [
            {
                "vid": 100,
                "name": "VLAN100",
            }
        ]
        interfaces = [{"name": "vlan100"}]
        result = extract_vxlan_mappings(vlans, interfaces, use_l2vpn_id=False)
        assert len(result) == 1
        assert result[0]["vlan"] == 100
        assert result[0]["vni"] == 100


class TestGetVlansInUse:
    """Tests for get_vlans_in_use function"""

    def test_get_vlans_in_use(self):
        """Test getting all VLANs in use on device"""
        interfaces = get_sample_interfaces()
        vlan_interfaces = [{"name": "vlan10"}, {"name": "vlan50"}]
        result = get_vlans_in_use(interfaces, vlan_interfaces)
        assert sorted(result["vids"]) == [10, 20, 30, 50, 100, 200, 300]
        assert len(result["vids"]) == 7

    def test_get_vlans_in_use_empty(self):
        """Test with no VLANs in use"""
        result = get_vlans_in_use([], [])
        assert result["vids"] == []
        assert len(result["vids"]) == 0

    def test_get_vlans_in_use_skips_subinterface_tagged_vlan(self):
        """Subinterface tagged VLANs should not be marked as VLANs in use."""
        interfaces = [
            {
                "name": "1/1/3.200",
                "type": {"value": "virtual"},
                "parent": {"name": "1/1/3"},
                "untagged_vlan": None,
                "tagged_vlans": [{"vid": 200}],
            },
            {
                "name": "1/1/10",
                "type": {"value": "1000base-t"},
                "untagged_vlan": {"vid": 10},
                "tagged_vlans": [],
            },
        ]

        result = get_vlans_in_use(interfaces, [])
        assert sorted(result["vids"]) == [10]


class TestGetVlansNeedingChanges:
    """Tests for get_vlans_needing_changes function"""

    def test_vlans_needing_changes_create_only(self):
        """Test when VLANs need to be created"""
        vlans = get_sample_vlans()
        vlans_in_use = {"vids": [10, 20, 30, 100]}
        ansible_facts = {}  # No device facts means create all
        result = get_vlans_needing_changes(vlans, vlans_in_use, ansible_facts)
        assert len(result["vlans_to_create"]) == 4
        assert len(result["vlans_to_delete"]) == 0

    def test_vlans_needing_changes_delete(self):
        """Test when VLANs need to be deleted"""
        vlans = get_sample_vlans()
        vlans_in_use = {"vids": [10, 20]}
        ansible_facts = {
            "ansible_network_resources": {
                "vlans": {
                    "10": {},
                    "20": {},
                    "99": {},  # Extra VLAN to delete
                }
            }
        }
        result = get_vlans_needing_changes(vlans, vlans_in_use, ansible_facts)
        assert 99 in result["vlans_to_delete"]
        assert 1 not in result["vlans_to_delete"]

    def test_vlans_needing_changes_skip_vlan_1(self):
        """Test that VLAN 1 is never marked for deletion"""
        vlans = []
        vlans_in_use = {"vids": []}
        ansible_facts = {
            "ansible_network_resources": {
                "vlans": {
                    "1": {},  # VLAN 1 should never be deleted
                }
            }
        }
        result = get_vlans_needing_changes(vlans, vlans_in_use, ansible_facts)
        assert 1 not in result["vlans_to_delete"]


class TestGetVlanInterfaces:
    """Tests for get_vlan_interfaces function"""

    def test_get_vlan_interfaces(self):
        """Test extracting VLAN interfaces"""
        interfaces = get_sample_interfaces()
        result = get_vlan_interfaces(interfaces)
        assert len(result) == 1
        assert result[0]["name"] == "vlan10"

    def test_get_vlan_interfaces_none(self):
        """Test with no VLAN interfaces"""
        interfaces = [
            {"name": "1/1/1", "type": {"value": "1000base-t"}},
            {"name": "loopback0", "type": {"value": "virtual"}},
        ]
        result = get_vlan_interfaces(interfaces)
        assert len(result) == 0


class TestParseEvpnEviOutput:
    """Tests for parse_evpn_evi_output function"""

    def test_parse_single_l2vni(self):
        """Test parsing output with single L2VNI entry"""
        output = """L2VNI : 10100
    Route Distinguisher        : 172.20.1.33:10
    VLAN                       : 10
    Status                     : up
    RT Import                  : 65005:10
    RT Export                  : 65005:10"""
        result = parse_evpn_evi_output(output)
        assert result["evpn_vlans"] == [10]
        assert result["vxlan_vnis"] == [10100]
        assert result["vxlan_vlans"] == [10]
        assert result["vxlan_mappings"] == [[10100, 10]]

    def test_parse_multiple_l2vnis(self):
        """Test parsing output with multiple L2VNI entries"""
        output = """L2VNI : 10100
    Route Distinguisher        : 172.20.1.33:10
    VLAN                       : 10
    Status                     : up
    RT Import                  : 65005:10
    RT Export                  : 65005:10
L2VNI : 10200
    Route Distinguisher        : 172.20.1.33:20
    VLAN                       : 20
    Status                     : up
    RT Import                  : 65005:20
    RT Export                  : 65005:20
L2VNI : 10300
    Route Distinguisher        : 172.20.1.33:30
    VLAN                       : 30
    Status                     : up
    RT Import                  : 65005:30
    RT Export                  : 65005:30"""
        result = parse_evpn_evi_output(output)
        assert result["evpn_vlans"] == [10, 20, 30]
        assert result["vxlan_vnis"] == [10100, 10200, 10300]
        assert result["vxlan_vlans"] == [10, 20, 30]
        assert len(result["vxlan_mappings"]) == 3
        assert [10100, 10] in result["vxlan_mappings"]
        assert [10200, 20] in result["vxlan_mappings"]
        assert [10300, 30] in result["vxlan_mappings"]

    def test_parse_empty_output(self):
        """Test parsing empty output"""
        result = parse_evpn_evi_output("")
        assert result["evpn_vlans"] == []
        assert result["vxlan_vnis"] == []
        assert result["vxlan_vlans"] == []
        assert result["vxlan_mappings"] == []

    def test_parse_none_output(self):
        """Test parsing None output"""
        result = parse_evpn_evi_output(None)
        assert result["evpn_vlans"] == []
        assert result["vxlan_vnis"] == []
        assert result["vxlan_vlans"] == []
        assert result["vxlan_mappings"] == []

    def test_parse_non_string_output(self):
        """Test parsing non-string output"""
        result = parse_evpn_evi_output(12345)
        assert result["evpn_vlans"] == []
        assert result["vxlan_vnis"] == []

    def test_parse_output_with_no_matching_data(self):
        """Test parsing output with no EVPN data"""
        output = """Some other command output
that doesn't contain L2VNI data"""
        result = parse_evpn_evi_output(output)
        assert result["evpn_vlans"] == []
        assert result["vxlan_vnis"] == []

    def test_parse_large_vni_numbers(self):
        """Test parsing output with large VNI numbers"""
        output = """L2VNI : 16777200
    Route Distinguisher        : 172.20.1.33:10
    VLAN                       : 4094
    Status                     : up"""
        result = parse_evpn_evi_output(output)
        assert result["vxlan_vnis"] == [16777200]
        assert result["vxlan_vlans"] == [4094]
