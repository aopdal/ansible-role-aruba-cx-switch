#!/usr/bin/env python3
"""
Populate NetBox with test data for Aruba CX role testing

Usage:
    python populate_netbox.py --url http://netbox:8000 --token YOUR_TOKEN --topology simple

Topologies:
    simple: 2 switches (1 spine, 1 leaf)
    fabric: 4 switches (2 spines, 2 leafs) with EVPN/VXLAN
    vsx: 4 switches (VSX pair + 2 leafs)
"""

import argparse
import sys
import pynetbox
from pynetbox.core.query import RequestError


class NetBoxPopulator:
    """Populate NetBox with test data"""

    def __init__(self, url, token):
        self.nb = pynetbox.api(url, token=token)
        self.site = None
        self.manufacturer = None
        self.device_type = None
        self.roles = {}

    def create_site(self, name="test-lab"):
        """Create test site"""
        print(f"Creating site: {name}")
        try:
            self.site = self.nb.dcim.sites.get(slug=name)
            if self.site:
                print(f"  Site '{name}' already exists")
            else:
                self.site = self.nb.dcim.sites.create(name=name, slug=name)
                print(f"  ✓ Created site: {name}")
        except RequestError as e:
            print(f"  ✗ Error creating site: {e}")
            sys.exit(1)

    def create_manufacturer(self, name="Aruba"):
        """Create manufacturer"""
        print(f"Creating manufacturer: {name}")
        try:
            self.manufacturer = self.nb.dcim.manufacturers.get(slug=name.lower())
            if self.manufacturer:
                print(f"  Manufacturer '{name}' already exists")
            else:
                self.manufacturer = self.nb.dcim.manufacturers.create(
                    name=name, slug=name.lower()
                )
                print(f"  ✓ Created manufacturer: {name}")
        except RequestError as e:
            print(f"  ✗ Error creating manufacturer: {e}")
            sys.exit(1)

    def create_device_type(self, model="CX 8360 Virtual"):
        """Create device type"""
        print(f"Creating device type: {model}")
        slug = model.lower().replace(" ", "-")
        try:
            self.device_type = self.nb.dcim.device_types.get(slug=slug)
            if self.device_type:
                print(f"  Device type '{model}' already exists")
            else:
                self.device_type = self.nb.dcim.device_types.create(
                    manufacturer=self.manufacturer.id, model=model, slug=slug
                )
                print(f"  ✓ Created device type: {model}")
        except RequestError as e:
            print(f"  ✗ Error creating device type: {e}")
            sys.exit(1)

    def create_device_roles(self):
        """Create device roles"""
        print("Creating device roles")
        roles_config = [
            ("spine", "Spine Switch", "2196f3"),  # Blue
            ("leaf", "Leaf Switch", "4caf50"),  # Green
            ("border", "Border Leaf", "ff9800"),  # Orange
        ]

        for slug, name, color in roles_config:
            try:
                role = self.nb.dcim.device_roles.get(slug=slug)
                if role:
                    print(f"  Role '{name}' already exists")
                    self.roles[slug] = role
                else:
                    role = self.nb.dcim.device_roles.create(
                        name=name, slug=slug, color=color
                    )
                    self.roles[slug] = role
                    print(f"  ✓ Created role: {name}")
            except RequestError as e:
                print(f"  ✗ Error creating role {name}: {e}")

    def create_device(self, name, role_slug, mgmt_ip):
        """Create a device"""
        try:
            device = self.nb.dcim.devices.get(name=name)
            if device:
                print(f"  Device '{name}' already exists")
                return device

            device = self.nb.dcim.devices.create(
                name=name,
                device_type=self.device_type.id,
                device_role=self.roles[role_slug].id,
                site=self.site.id,
            )
            print(f"  ✓ Created device: {name}")

            # Create management interface
            mgmt_intf = self.nb.dcim.interfaces.create(
                device=device.id, name="mgmt", type="virtual"
            )

            # Create IP address
            ip = self.nb.ipam.ip_addresses.create(
                address=mgmt_ip,
                assigned_object_type="dcim.interface",
                assigned_object_id=mgmt_intf.id,
            )

            # Set as primary IP
            device.primary_ip4 = ip.id
            device.save()
            print(f"    ✓ Assigned management IP: {mgmt_ip}")

            return device
        except RequestError as e:
            print(f"  ✗ Error creating device {name}: {e}")
            return None

    def create_interfaces(self, device_name, interface_count=48):
        """Create interfaces for a device"""
        device = self.nb.dcim.devices.get(name=device_name)
        if not device:
            print(f"  ✗ Device {device_name} not found")
            return

        print(f"  Creating {interface_count} interfaces for {device_name}")
        for i in range(1, interface_count + 1):
            intf_name = f"1/1/{i}"
            try:
                intf = self.nb.dcim.interfaces.get(device_id=device.id, name=intf_name)
                if not intf:
                    self.nb.dcim.interfaces.create(
                        device=device.id, name=intf_name, type="1000base-t"
                    )
            except RequestError as e:
                print(f"    ✗ Error creating interface {intf_name}: {e}")

        print(f"    ✓ Created {interface_count} interfaces")

    def create_vlans(self, vlan_list):
        """Create VLANs"""
        print("Creating VLANs")
        for vid, name, description in vlan_list:
            try:
                vlan = self.nb.ipam.vlans.get(vid=vid, site_id=self.site.id)
                if vlan:
                    print(f"  VLAN {vid} ({name}) already exists")
                else:
                    vlan = self.nb.ipam.vlans.create(
                        vid=vid, name=name, site=self.site.id, description=description
                    )
                    print(f"  ✓ Created VLAN {vid}: {name}")
            except RequestError as e:
                print(f"  ✗ Error creating VLAN {vid}: {e}")

    def create_vrfs(self, vrf_list):
        """Create VRFs"""
        print("Creating VRFs")
        for name, rd, description in vrf_list:
            try:
                vrf = self.nb.ipam.vrfs.get(name=name)
                if vrf:
                    print(f"  VRF '{name}' already exists")
                else:
                    vrf = self.nb.ipam.vrfs.create(
                        name=name, rd=rd, description=description
                    )
                    print(f"  ✓ Created VRF: {name} (RD: {rd})")
            except RequestError as e:
                print(f"  ✗ Error creating VRF {name}: {e}")

    def topology_simple(self):
        """Create simple topology: 1 spine, 1 leaf"""
        print("\n=== Creating Simple Topology ===\n")

        # Create devices
        devices = [
            ("spine1", "spine", "192.168.1.11/24"),
            ("leaf1", "leaf", "192.168.1.21/24"),
        ]

        print("Creating devices:")
        for name, role, ip in devices:
            self.create_device(name, role, ip)
            self.create_interfaces(name, interface_count=16)

        # Create VLANs
        vlans = [
            (10, "servers", "Server VLAN"),
            (20, "storage", "Storage VLAN"),
            (30, "management", "Management VLAN"),
        ]
        self.create_vlans(vlans)

        # Create VRFs
        vrfs = [("management", "65000:100", "Management VRF")]
        self.create_vrfs(vrfs)

        print("\n✓ Simple topology created successfully!")

    def topology_fabric(self):
        """Create EVPN/VXLAN fabric: 2 spines, 2 leafs"""
        print("\n=== Creating Fabric Topology (EVPN/VXLAN) ===\n")

        # Create devices
        devices = [
            ("spine1", "spine", "192.168.1.11/24"),
            ("spine2", "spine", "192.168.1.12/24"),
            ("leaf1", "leaf", "192.168.1.21/24"),
            ("leaf2", "leaf", "192.168.1.22/24"),
        ]

        print("Creating devices:")
        for name, role, ip in devices:
            self.create_device(name, role, ip)
            self.create_interfaces(name, interface_count=32)

        # Create VLANs
        vlans = [
            (10, "tenant1-web", "Tenant 1 Web Servers"),
            (20, "tenant1-app", "Tenant 1 App Servers"),
            (30, "tenant1-db", "Tenant 1 Database"),
            (100, "tenant2-web", "Tenant 2 Web Servers"),
            (200, "tenant2-app", "Tenant 2 App Servers"),
        ]
        self.create_vlans(vlans)

        # Create VRFs
        vrfs = [
            ("tenant1", "65000:1000", "Tenant 1 VRF"),
            ("tenant2", "65000:2000", "Tenant 2 VRF"),
            ("management", "65000:100", "Management VRF"),
        ]
        self.create_vrfs(vrfs)

        print("\n✓ Fabric topology created successfully!")

    def topology_vsx(self):
        """Create VSX topology: VSX pair + 2 leafs"""
        print("\n=== Creating VSX Topology ===\n")

        # Create devices
        devices = [
            ("spine1-vsx", "spine", "192.168.1.11/24"),
            ("spine2-vsx", "spine", "192.168.1.12/24"),
            ("leaf1", "leaf", "192.168.1.21/24"),
            ("leaf2", "leaf", "192.168.1.22/24"),
        ]

        print("Creating devices:")
        for name, role, ip in devices:
            self.create_device(name, role, ip)
            self.create_interfaces(name, interface_count=32)

        # Create VLANs
        vlans = [
            (10, "servers", "Server VLAN"),
            (20, "storage", "Storage VLAN"),
            (30, "management", "Management VLAN"),
            (4094, "vsx-keepalive", "VSX Keepalive VLAN"),
        ]
        self.create_vlans(vlans)

        # Create VRFs
        vrfs = [("management", "65000:100", "Management VRF")]
        self.create_vrfs(vrfs)

        print("\n✓ VSX topology created successfully!")


def main():
    parser = argparse.ArgumentParser(
        description="Populate NetBox with Aruba CX test data"
    )
    parser.add_argument("--url", required=True, help="NetBox URL")
    parser.add_argument("--token", required=True, help="NetBox API token")
    parser.add_argument(
        "--topology",
        choices=["simple", "fabric", "vsx"],
        default="simple",
        help="Topology to create",
    )
    parser.add_argument(
        "--site-name", default="test-lab", help="Site name (default: test-lab)"
    )

    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"NetBox Populator for Aruba CX Testing")
    print(f"{'='*60}\n")
    print(f"NetBox URL: {args.url}")
    print(f"Topology: {args.topology}")
    print(f"Site: {args.site_name}\n")

    # Create populator
    populator = NetBoxPopulator(args.url, args.token)

    # Create base objects
    populator.create_site(args.site_name)
    populator.create_manufacturer()
    populator.create_device_type()
    populator.create_device_roles()

    # Create topology-specific objects
    if args.topology == "simple":
        populator.topology_simple()
    elif args.topology == "fabric":
        populator.topology_fabric()
    elif args.topology == "vsx":
        populator.topology_vsx()

    print(f"\n{'='*60}")
    print("NetBox population complete!")
    print(f"{'='*60}\n")
    print(f"Next steps:")
    print(f"1. Verify in NetBox: {args.url}")
    print(f"2. Bootstrap switches with management IPs")
    print(f"3. Run Ansible playbooks to configure switches")
    print()


if __name__ == "__main__":
    main()
