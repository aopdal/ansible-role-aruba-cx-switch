"""
Test fixtures for filter plugin unit tests
"""


def get_sample_interfaces():
    """Sample NetBox interface data for testing"""
    return [
        {
            "id": 1,
            "name": "1/1/1",
            "type": {"value": "1000base-t"},
            "enabled": True,
            "description": "Access port",
            "mode": {"value": "access"},
            "untagged_vlan": {"vid": 10, "name": "VLAN10"},
            "tagged_vlans": [],
            "lag": None,
        },
        {
            "id": 2,
            "name": "1/1/2",
            "type": {"value": "1000base-t"},
            "enabled": True,
            "description": "Trunk port",
            "mode": {"value": "tagged"},
            "untagged_vlan": None,
            "tagged_vlans": [
                {"vid": 20, "name": "VLAN20"},
                {"vid": 30, "name": "VLAN30"},
            ],
            "lag": None,
        },
        {
            "id": 3,
            "name": "1/1/3",
            "type": {"value": "1000base-t"},
            "enabled": True,
            "description": "Trunk with native",
            "mode": {"value": "tagged"},
            "untagged_vlan": {"vid": 100, "name": "VLAN100"},
            "tagged_vlans": [
                {"vid": 200, "name": "VLAN200"},
                {"vid": 300, "name": "VLAN300"},
            ],
            "lag": None,
        },
        {
            "id": 4,
            "name": "vlan10",
            "type": {"value": "virtual"},
            "enabled": True,
            "description": "VLAN interface",
            "ip_addresses": [
                {
                    "address": "10.1.10.1/24",
                    "vrf": {"name": "default"},
                }
            ],
        },
        {
            "id": 5,
            "name": "loopback0",
            "type": {"value": "virtual"},
            "enabled": True,
            "description": "Loopback",
            "ip_addresses": [
                {
                    "address": "10.255.255.1/32",
                    "vrf": {"name": "default"},
                }
            ],
        },
        {
            "id": 6,
            "name": "lag1",
            "type": {"value": "lag"},
            "enabled": True,
            "description": "LAG interface",
            "mode": {"value": "access"},
            "untagged_vlan": {"vid": 50, "name": "VLAN50"},
            "tagged_vlans": [],
        },
        {
            "id": 7,
            "name": "1/1/10",
            "type": {"value": "1000base-t"},
            "enabled": True,
            "description": "LAG member",
            "lag": {"name": "lag1", "id": 6},
        },
    ]


def get_sample_vlans():
    """Sample NetBox VLAN data for testing"""
    return [
        {
            "id": 1,
            "vid": 10,
            "name": "VLAN10",
            "description": "Data VLAN",
            "status": {"value": "active"},
            "custom_fields": {},
        },
        {
            "id": 2,
            "vid": 20,
            "name": "VLAN20",
            "description": "Voice VLAN",
            "status": {"value": "active"},
            "custom_fields": {},
        },
        {
            "id": 3,
            "vid": 30,
            "name": "VLAN30",
            "description": "Guest VLAN",
            "status": {"value": "active"},
            "custom_fields": {},
        },
        {
            "id": 4,
            "vid": 100,
            "name": "VLAN100",
            "description": "Server VLAN",
            "status": {"value": "active"},
            "custom_fields": {},
            "l2vpn_termination": {
                "l2vpn": {
                    "name": "EVPN",
                    "identifier": 10100,
                }
            },
        },
    ]


def get_sample_vrfs():
    """Sample NetBox VRF data for testing"""
    return [
        {
            "id": 1,
            "name": "default",
            "rd": None,
            "import_targets": [],
            "export_targets": [],
        },
        {
            "id": 2,
            "name": "customer_a",
            "rd": "65000:100",
            "import_targets": ["65000:100"],
            "export_targets": ["65000:100"],
        },
        {
            "id": 3,
            "name": "customer_b",
            "rd": "65000:200",
            "import_targets": ["65000:200"],
            "export_targets": ["65000:200"],
        },
        {
            "id": 4,
            "name": "mgmt",
            "rd": None,
            "import_targets": [],
            "export_targets": [],
        },
    ]


def get_sample_ip_addresses():
    """Sample NetBox IP address data for testing"""
    return [
        {
            "id": 1,
            "address": "10.1.10.1/24",
            "vrf": {"name": "default"},
            "assigned_object": {
                "id": 4,
                "name": "vlan10",
                "device": {"name": "switch1"},
            },
        },
        {
            "id": 2,
            "address": "10.255.255.1/32",
            "vrf": {"name": "default"},
            "assigned_object": {
                "id": 5,
                "name": "loopback0",
                "device": {"name": "switch1"},
            },
        },
        {
            "id": 3,
            "address": "192.168.100.1/30",
            "vrf": {"name": "customer_a"},
            "assigned_object": {
                "id": 6,
                "name": "1/1/5",
                "device": {"name": "switch1"},
            },
        },
    ]


def get_sample_ansible_facts():
    """Sample aoscx_facts device facts for testing.

    Uses the actual aoscx_facts format:
    - interfaces keyed by name under ansible_network_resources
    - vlan_tag: dict of {vid_str: {}} for the untagged VLAN
    - vlan_trunks: dict of {vid_str: {}} for tagged VLANs
    """
    return {
        "ansible_network_resources": {
            "interfaces": {
                "1/1/1": {
                    "vlan_mode": "access",
                    "vlan_tag": {"10": {}},
                    "vlan_trunks": {},
                },
                "1/1/2": {
                    "vlan_mode": "trunk",
                    "vlan_tag": {},
                    "vlan_trunks": {"20": {}, "30": {}, "40": {}},  # 40 is extra
                },
                "vlan99": {
                    "type": "vlan",
                    "ip4_address": "10.99.99.1/24",
                },
            },
            "vlans": {
                "10": {"name": "VLAN10"},
                "20": {"name": "VLAN20"},
                "30": {"name": "VLAN30"},
                "99": {"name": "VLAN99"},  # Extra VLAN not in NetBox
            },
        },
    }


def get_sample_ospf_config():
    """Sample OSPF configuration data for testing

    Note: config_context is flattened (simulating NetBox inventory with plurals: true)
    """
    return {
        "device": {
            "custom_fields": {
                "device_ospf_1_routerid": "10.255.255.1",
            },
        },
        # Flattened config_context variables
        "ospf_process_id": 1,
        "ospf_vrfs": [
            {
                "vrf": "default",
                "areas": [
                    {"area": "0.0.0.0"},
                    {"area": "0.0.0.1"},
                ],
            },
            {
                "vrf": "customer_a",
                "areas": [
                    {"area": "0.0.0.0"},
                ],
            },
        ],
        "interfaces": [
            {
                "name": "1/1/1",
                "ip_addresses": [{"address": "10.1.1.1/30", "vrf": {"name": "default"}}],
                "custom_fields": {
                    "if_ip_ospf_1_area": "0.0.0.0",
                    "if_ip_ospf_network": "point-to-point",
                },
            },
            {
                "name": "1/1/2",
                "ip_addresses": [
                    {"address": "10.2.2.1/24", "vrf": {"name": "customer_a"}}
                ],
                "custom_fields": {
                    "if_ip_ospf_1_area": "0.0.0.0",
                    "if_ip_ospf_network": "broadcast",
                },
            },
        ],
    }
