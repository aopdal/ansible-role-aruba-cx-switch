"""
Unit tests for static route filter functions
"""
from netbox_filters_lib.static_route_filters import get_static_route_changes


class TestGetStaticRouteChanges:
    """Tests for get_static_route_changes function"""

    def test_no_static_routes(self):
        """No static_routes defined - nothing to apply or delete"""
        result = get_static_route_changes({}, None)
        assert result == {"routes_to_apply": [], "routes_to_delete": []}

    def test_not_a_dict_input(self):
        """Non-dict static_routes input is treated as empty"""
        result = get_static_route_changes(None, None)
        assert result == {"routes_to_apply": [], "routes_to_delete": []}

    def test_no_facts_pushes_all_desired_routes(self):
        """When facts are unavailable, every desired route is pushed and nothing is deleted"""
        static_routes = {
            "default": [
                {"prefix": "0.0.0.0/0", "type": "forward", "next_hop": "172.18.17.33"},
            ]
        }
        result = get_static_route_changes(static_routes, None)
        assert len(result["routes_to_apply"]) == 1
        assert result["routes_to_apply"][0] == {
            "vrf_name": "default",
            "destination_address_prefix": "0.0.0.0/0",
            "type": "forward",
            "distance": 1,
            "next_hop_ip_address": "172.18.17.33",
            "next_hop_interface": None,
        }
        assert result["routes_to_delete"] == []

    def test_defaults_applied(self):
        """type defaults to forward and distance defaults to 1 when omitted"""
        static_routes = {"default": [{"prefix": "192.0.2.0/24"}]}
        result = get_static_route_changes(static_routes, None)
        entry = result["routes_to_apply"][0]
        assert entry["type"] == "forward"
        assert entry["distance"] == 1

    def test_blackhole_and_reject_types(self):
        """blackhole/reject routes need no next-hop"""
        static_routes = {
            "default": [
                {"prefix": "203.0.113.0/24", "type": "blackhole"},
                {"prefix": "198.51.100.0/24", "type": "reject", "distance": 5},
            ]
        }
        result = get_static_route_changes(static_routes, None)
        types = {r["destination_address_prefix"]: r["type"] for r in result["routes_to_apply"]}
        assert types["203.0.113.0/24"] == "blackhole"
        assert types["198.51.100.0/24"] == "reject"

    def test_route_with_next_hop_interface(self):
        """next_hop_interface is passed through"""
        static_routes = {
            "default": [
                {"prefix": "10.10.0.0/16", "next_hop_interface": "1/1/2"},
            ]
        }
        result = get_static_route_changes(static_routes, None)
        assert result["routes_to_apply"][0]["next_hop_interface"] == "1/1/2"

    def test_matching_facts_no_changes(self):
        """A route already matching device facts needs no change"""
        static_routes = {
            "default": [
                {"prefix": "0.0.0.0/0", "type": "forward", "next_hop": "172.18.17.33", "distance": 1},
            ]
        }
        facts = {
            "default": {
                "0.0.0.0/0": {
                    "type": "forward",
                    "distance": 1,
                    "next_hop_ip_address": "172.18.17.33",
                    "next_hop_interface": None,
                }
            }
        }
        result = get_static_route_changes(static_routes, facts)
        assert result["routes_to_apply"] == []
        assert result["routes_to_delete"] == []

    def test_changed_next_hop_needs_update(self):
        """A route whose next-hop differs from device facts needs an update"""
        static_routes = {
            "default": [
                {"prefix": "0.0.0.0/0", "type": "forward", "next_hop": "172.18.17.99"},
            ]
        }
        facts = {
            "default": {
                "0.0.0.0/0": {
                    "type": "forward",
                    "distance": 1,
                    "next_hop_ip_address": "172.18.17.33",
                    "next_hop_interface": None,
                }
            }
        }
        result = get_static_route_changes(static_routes, facts)
        assert len(result["routes_to_apply"]) == 1
        assert result["routes_to_apply"][0]["next_hop_ip_address"] == "172.18.17.99"

    def test_changed_distance_needs_update(self):
        """A route whose distance differs from device facts needs an update"""
        static_routes = {
            "default": [
                {"prefix": "0.0.0.0/0", "type": "forward", "next_hop": "172.18.17.33", "distance": 5},
            ]
        }
        facts = {
            "default": {
                "0.0.0.0/0": {
                    "type": "forward",
                    "distance": 1,
                    "next_hop_ip_address": "172.18.17.33",
                    "next_hop_interface": None,
                }
            }
        }
        result = get_static_route_changes(static_routes, facts)
        assert len(result["routes_to_apply"]) == 1

    def test_route_missing_from_device_needs_create(self):
        """A desired route absent from facts needs to be created"""
        static_routes = {"default": [{"prefix": "10.0.0.0/8", "type": "forward", "next_hop": "10.0.0.1"}]}
        facts = {"default": {}}
        result = get_static_route_changes(static_routes, facts)
        assert len(result["routes_to_apply"]) == 1

    def test_route_missing_prefix_is_skipped(self):
        """A route dict with no prefix is ignored"""
        static_routes = {"default": [{"type": "forward"}]}
        result = get_static_route_changes(static_routes, None)
        assert result["routes_to_apply"] == []

    def test_stale_route_marked_for_deletion(self):
        """A route present on the device but not in NetBox is marked for deletion"""
        static_routes = {"default": []}
        facts = {
            "default": {
                "192.0.2.0/24": {
                    "type": "forward",
                    "distance": 1,
                    "next_hop_ip_address": "192.0.2.1",
                    "next_hop_interface": None,
                }
            }
        }
        result = get_static_route_changes(static_routes, facts)
        assert result["routes_to_apply"] == []
        assert result["routes_to_delete"] == [
            {"vrf_name": "default", "destination_address_prefix": "192.0.2.0/24"}
        ]

    def test_no_deletion_without_facts(self):
        """Deletion is never computed when facts are unavailable (None)"""
        static_routes = {"default": []}
        result = get_static_route_changes(static_routes, None)
        assert result["routes_to_delete"] == []

    def test_multiple_vrfs(self):
        """Routes across multiple VRFs are handled independently"""
        static_routes = {
            "default": [{"prefix": "0.0.0.0/0", "next_hop": "172.18.17.33"}],
            "tenant_a": [{"prefix": "10.10.0.0/16", "type": "reject"}],
        }
        result = get_static_route_changes(static_routes, None)
        vrfs = {r["vrf_name"] for r in result["routes_to_apply"]}
        assert vrfs == {"default", "tenant_a"}

    def test_ignores_non_list_routes_for_vrf(self):
        """A non-list value for a VRF's routes is ignored defensively"""
        static_routes = {"default": "not-a-list"}
        result = get_static_route_changes(static_routes, None)
        assert result["routes_to_apply"] == []

    def test_ignores_non_dict_route_entry(self):
        """A non-dict entry in a VRF's route list is skipped"""
        static_routes = {"default": ["not-a-dict"]}
        result = get_static_route_changes(static_routes, None)
        assert result["routes_to_apply"] == []
