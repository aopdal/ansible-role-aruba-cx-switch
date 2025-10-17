"""
Unit tests for utility functions
"""
import pytest
from netbox_filters_lib.utils import collapse_vlan_list


class TestCollapseVlanList:
    """Tests for collapse_vlan_list function"""

    def test_empty_list(self):
        """Test with empty list"""
        assert collapse_vlan_list([]) == ""

    def test_single_vlan(self):
        """Test with single VLAN"""
        assert collapse_vlan_list([10]) == "10"

    def test_consecutive_vlans(self):
        """Test with consecutive VLANs"""
        assert collapse_vlan_list([10, 11, 12, 13]) == "10-13"

    def test_non_consecutive_vlans(self):
        """Test with non-consecutive VLANs"""
        assert collapse_vlan_list([10, 15, 20]) == "10,15,20"

    def test_mixed_ranges_and_singles(self):
        """Test with mix of ranges and single VLANs"""
        assert collapse_vlan_list([10, 11, 12, 15, 20, 21]) == "10-12,15,20-21"

    def test_unsorted_input(self):
        """Test with unsorted input"""
        assert collapse_vlan_list([30, 10, 20, 11, 12]) == "10-12,20,30"

    def test_duplicate_vlans(self):
        """Test with duplicate VLANs"""
        assert collapse_vlan_list([10, 10, 11, 11, 12]) == "10-12"

    def test_complex_scenario(self):
        """Test with complex real-world scenario"""
        vlans = [1, 2, 3, 5, 7, 10, 11, 12, 20, 30, 31, 32, 100]
        result = collapse_vlan_list(vlans)
        assert result == "1-3,5,7,10-12,20,30-32,100"

    def test_all_consecutive(self):
        """Test with all consecutive VLANs"""
        assert collapse_vlan_list(list(range(1, 101))) == "1-100"

    def test_two_vlan_range(self):
        """Test with two consecutive VLANs"""
        assert collapse_vlan_list([10, 11]) == "10-11"
