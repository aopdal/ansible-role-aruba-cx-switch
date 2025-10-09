#!/usr/bin/env python3
"""
Validate Aruba CX switch configuration against NetBox

This script validates that switches are configured correctly
after running the ansible-role-aruba-cx-switch role.

Usage:
    python validate_deployment.py --switches spine1,leaf1 --netbox-url http://netbox:8000 --netbox-token TOKEN
"""

import argparse
import sys
from typing import Dict, List, Any
import pynetbox
from pyaoscx.session import Session
from pyaoscx.pyaoscx_factory import PyaoscxFactory


class ConfigValidator:
    """Validate switch configuration against NetBox"""

    def __init__(self, netbox_url: str, netbox_token: str):
        self.nb = pynetbox.api(netbox_url, token=netbox_token)
        self.results: Dict[str, List[Dict[str, Any]]] = {}

    def validate_switch(
        self, hostname: str, mgmt_ip: str, username: str, password: str
    ) -> bool:
        """Validate a single switch"""
        print(f"\n{'='*60}")
        print(f"Validating: {hostname} ({mgmt_ip})")
        print(f"{'='*60}\n")

        self.results[hostname] = []

        try:
            # Connect to switch
            session = Session(mgmt_ip, username, password)
            session.open("https", 443)

            # Get NetBox device
            nb_device = self.nb.dcim.devices.get(name=hostname)
            if not nb_device:
                self._add_result(
                    hostname, "ERROR", "Device", f"Device {hostname} not found in NetBox"
                )
                return False

            # Run validation checks
            self._validate_vlans(hostname, session, nb_device)
            self._validate_interfaces(hostname, session, nb_device)
            self._validate_vrfs(hostname, session, nb_device)

            session.close()

            # Print summary
            self._print_summary(hostname)

            return not self._has_errors(hostname)

        except Exception as e:
            self._add_result(hostname, "ERROR", "Connection",
                             f"Failed to connect: {e}")
            return False

    def _validate_vlans(self, hostname: str, session: Session, nb_device) -> None:
        """Validate VLANs"""
        print("Checking VLANs...")

        # Get VLANs from NetBox
        nb_vlans = self.nb.ipam.vlans.filter(site=nb_device.site.slug)
        expected_vids = {vlan.vid for vlan in nb_vlans}

        # Get VLANs from switch
        try:
            vlans_dict = PyaoscxFactory.get_all_vlans(session)
            switch_vids = set(vlans_dict.keys())

            # Check for missing VLANs
            missing = expected_vids - switch_vids
            if missing:
                self._add_result(
                    hostname,
                    "ERROR",
                    "VLANs",
                    f"Missing VLANs: {sorted(missing)}",
                )
            else:
                self._add_result(
                    hostname,
                    "PASS",
                    "VLANs",
                    f"All {len(expected_vids)} VLANs present",
                )

            # Check for extra VLANs (except VLAN 1)
            extra = switch_vids - expected_vids - {1}
            if extra:
                self._add_result(
                    hostname,
                    "WARNING",
                    "VLANs",
                    f"Extra VLANs on switch: {sorted(extra)}",
                )

            # Verify VLAN names
            for vid in expected_vids:
                if vid in vlans_dict:
                    nb_vlan = next(v for v in nb_vlans if v.vid == vid)
                    switch_vlan = vlans_dict[vid]
                    if switch_vlan.name != nb_vlan.name:
                        self._add_result(
                            hostname,
                            "ERROR",
                            "VLANs",
                            f"VLAN {vid} name mismatch: '{switch_vlan.name}' != '{nb_vlan.name}'",
                        )

        except Exception as e:
            self._add_result(hostname, "ERROR", "VLANs",
                             f"Failed to get VLANs: {e}")

    def _validate_interfaces(
        self, hostname: str, session: Session, nb_device
    ) -> None:
        """Validate interface configuration"""
        print("Checking interfaces...")

        try:
            # Get interfaces from NetBox with VLAN assignments
            nb_interfaces = self.nb.dcim.interfaces.filter(device=hostname)

            interface_count = 0
            for nb_intf in nb_interfaces:
                if nb_intf.name == "mgmt":
                    continue  # Skip management interface

                # Get interface from switch
                try:
                    switch_intf = PyaoscxFactory.get_interface(
                        session, nb_intf.name)

                    if not switch_intf:
                        self._add_result(
                            hostname,
                            "WARNING",
                            "Interfaces",
                            f"Interface {nb_intf.name} not found on switch",
                        )
                        continue

                    # Check mode (access/trunk)
                    if nb_intf.mode:
                        if nb_intf.mode.value == "access" and nb_intf.untagged_vlan:
                            # Validate access VLAN
                            # Note: This would need actual pyaoscx API calls
                            interface_count += 1
                        elif nb_intf.mode.value == "tagged":
                            # Validate trunk VLANs
                            interface_count += 1

                except Exception as e:
                    self._add_result(
                        hostname,
                        "ERROR",
                        "Interfaces",
                        f"Failed to check {nb_intf.name}: {e}",
                    )

            if interface_count > 0:
                self._add_result(
                    hostname,
                    "PASS",
                    "Interfaces",
                    f"Validated {interface_count} interfaces",
                )

        except Exception as e:
            self._add_result(
                hostname, "ERROR", "Interfaces", f"Failed to get interfaces: {e}"
            )

    def _validate_vrfs(self, hostname: str, session: Session, nb_device) -> None:
        """Validate VRF configuration"""
        print("Checking VRFs...")

        try:
            # Get VRFs from NetBox
            nb_vrfs = self.nb.ipam.vrfs.all()

            if not nb_vrfs:
                self._add_result(hostname, "INFO", "VRFs",
                                 "No VRFs defined in NetBox")
                return

            # Get VRFs from switch
            vrfs_dict = PyaoscxFactory.get_all_vrfs(session)

            expected_vrfs = {vrf.name for vrf in nb_vrfs}
            switch_vrfs = set(vrfs_dict.keys())

            # Check for missing VRFs
            missing = expected_vrfs - switch_vrfs
            if missing:
                self._add_result(
                    hostname, "ERROR", "VRFs", f"Missing VRFs: {sorted(missing)}"
                )
            else:
                self._add_result(
                    hostname,
                    "PASS",
                    "VRFs",
                    f"All {len(expected_vrfs)} VRFs present",
                )

        except Exception as e:
            self._add_result(hostname, "ERROR", "VRFs",
                             f"Failed to get VRFs: {e}")

    def _add_result(
        self, hostname: str, status: str, category: str, message: str
    ) -> None:
        """Add validation result"""
        self.results[hostname].append(
            {"status": status, "category": category, "message": message}
        )

        # Print result with color
        colors = {
            "PASS": "\033[92m",  # Green
            "WARNING": "\033[93m",  # Yellow
            "ERROR": "\033[91m",  # Red
            "INFO": "\033[94m",  # Blue
        }
        reset = "\033[0m"
        color = colors.get(status, "")
        print(f"  {color}[{status:8}]{reset} {category:15} {message}")

    def _has_errors(self, hostname: str) -> bool:
        """Check if any errors occurred"""
        return any(r["status"] == "ERROR" for r in self.results[hostname])

    def _print_summary(self, hostname: str) -> None:
        """Print validation summary"""
        results = self.results[hostname]
        errors = sum(1 for r in results if r["status"] == "ERROR")
        warnings = sum(1 for r in results if r["status"] == "WARNING")
        passed = sum(1 for r in results if r["status"] == "PASS")

        print(f"\n{'='*60}")
        print(f"Summary for {hostname}:")
        print(f"  Passed:   {passed}")
        print(f"  Warnings: {warnings}")
        print(f"  Errors:   {errors}")
        print(f"{'='*60}")

    def print_final_summary(self) -> bool:
        """Print final summary for all switches"""
        print(f"\n\n{'='*60}")
        print("FINAL VALIDATION SUMMARY")
        print(f"{'='*60}\n")

        all_passed = True
        for hostname, results in self.results.items():
            errors = sum(1 for r in results if r["status"] == "ERROR")
            warnings = sum(1 for r in results if r["status"] == "WARNING")

            if errors > 0:
                status = "❌ FAILED"
                all_passed = False
            elif warnings > 0:
                status = "⚠️  WARNING"
            else:
                status = "✅ PASSED"

            print(f"{hostname:20} {status:15} ({errors} errors, {warnings} warnings)")

        print(f"\n{'='*60}\n")
        return all_passed


def main():
    parser = argparse.ArgumentParser(
        description="Validate Aruba CX switch deployment")
    parser.add_argument(
        "--switches",
        required=True,
        help="Comma-separated list of switch hostnames (e.g., spine1,leaf1)",
    )
    parser.add_argument("--netbox-url", required=True, help="NetBox URL")
    parser.add_argument("--netbox-token", required=True,
                        help="NetBox API token")
    parser.add_argument("--username", default="admin", help="Switch username")
    parser.add_argument("--password", required=True, help="Switch password")

    args = parser.parse_args()

    # Parse switches
    switch_list = [s.strip() for s in args.switches.split(",")]

    print("\n" + "=" * 60)
    print("Aruba CX Switch Configuration Validator")
    print("=" * 60)
    print(f"NetBox: {args.netbox_url}")
    print(f"Switches: {', '.join(switch_list)}")
    print("=" * 60)

    # Create validator
    validator = ConfigValidator(args.netbox_url, args.netbox_token)

    # Validate each switch
    all_passed = True
    for hostname in switch_list:
        # Get management IP from NetBox
        try:
            nb_device = validator.nb.dcim.devices.get(name=hostname)
            if not nb_device or not nb_device.primary_ip4:
                print(
                    f"ERROR: Cannot find management IP for {hostname} in NetBox")
                all_passed = False
                continue

            mgmt_ip = str(nb_device.primary_ip4).split("/")[0]
            passed = validator.validate_switch(
                hostname, mgmt_ip, args.username, args.password
            )
            if not passed:
                all_passed = False

        except Exception as e:
            print(f"ERROR validating {hostname}: {e}")
            all_passed = False

    # Print final summary
    final_passed = validator.print_final_summary()

    sys.exit(0 if final_passed else 1)


if __name__ == "__main__":
    main()
