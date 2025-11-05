# Ansible Role: Aruba AOS-CX Switch

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/aopdal/ansible-role-aruba-cx-switch/workflows/CI/badge.svg)](https://github.com/aopdal/ansible-role-aruba-cx-switch/actions)
[![codecov](https://codecov.io/gh/aopdal/ansible-role-aruba-cx-switch/branch/main/graph/badge.svg)](https://codecov.io/gh/aopdal/ansible-role-aruba-cx-switch)
[![Ansible Role](https://img.shields.io/ansible/role/XXXXX)](https://galaxy.ansible.com/aopdal/aruba_cx_switch)

Comprehensive Ansible role for configuring Aruba AOS-CX switches with **NetBox as the source of truth**.

## Table of Contents

- [NetBox Integration Requirement](#netbox-integration-requirement)
- [Getting Started](#getting-started)
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Documentation](#-documentation)
- [Role Variables](#role-variables)
- [Example Playbook](#example-playbook)
- [Usage Examples](#usage-examples)
- [Tags](#tags)
- [Idempotent Mode](#idempotent-mode)
- [Testing](#testing)
- [Contributing](#contributing)
- [License](#license)

## NetBox Integration Requirement

**This role requires NetBox** as the authoritative source for all network configuration data. Before using this role, ensure you have:

- **NetBox instance** (v3.0+) installed and accessible
- **NetBox API token** with appropriate permissions
- **Network devices** added to NetBox with required custom fields
- **VLANs, interfaces, and IP addresses** configured in NetBox

See [NetBox Integration](#netbox-configuration) below for detailed setup requirements and [docs/NETBOX_INTEGRATION.md](docs/NETBOX_INTEGRATION.md) for comprehensive integration documentation.

## Getting Started

This section covers using the role for network configuration. For development setup, see [Developer Documentation](#developer-documentation).

### Prerequisites

1. **NetBox** - Install and configure NetBox with your network devices
2. **Ansible** - Version 2.9 or higher
3. **Python libraries** - See [Requirements](#requirements) below
4. **Network access** - Connectivity to your Aruba switches and NetBox API

### Quick Start

```bash
# 1. Install the role and dependencies
ansible-galaxy install -r requirements.yml
pip install -r requirements.txt

# 2. Configure NetBox inventory (see NetBox Configuration section)
# 3. Create your playbook
# 4. Run configuration
ansible-playbook site.yml
```

For a complete walkthrough, see [docs/QUICKSTART.md](docs/QUICKSTART.md).

## Features

- ✅ **VRF Configuration** - Creates VRFs with RD and route-targets
- ✅ **VLAN Management** - Idempotent VLAN creation and cleanup
- ✅ **Physical Interface Configuration** - Enable/disable and description
- ✅ **L2 Interface Configuration** - Access and trunk ports with LACP support
- ✅ **L3 Interface Configuration** - IPv4/IPv6 with VRF support, ip mtu, and l3-counters
- ✅ **VLAN Interfaces (SVIs)** - Automatic creation and IP configuration
- ✅ **Loopback Interfaces** - Automatic detection, IPv4/IPv6, with VRF support
- ✅ **OSPF Configuration** - Router instance, areas, and interface configuration
- ✅ **VSX Configuration** - Active-active redundancy with system MAC, ISL, and keepalive
- ✅ **BGP/EVPN Configuration** - Hybrid support for NetBox BGP plugin and config context
- ✅ **VXLAN Configuration** - Overlay networks with VNI mapping and cleanup
- ✅ **Idempotent Mode** - Removes configurations not in NetBox
- ✅ **NetBox Integration** - Uses NetBox as single source of truth
- ✅ **ZTP Configuration Generation** - Creates base configs for Zero Touch Provisioning

## Advanced L3 Interface Features

This role uses `aoscx_config` instead of `aoscx_l3_interface` for L3 interface configuration to provide full control over advanced AOS-CX features:

### Supported L3 Interface Features

- **IP MTU Configuration**: Automatically configures `ip mtu` when MTU is defined in NetBox
- **L3 Counters**: Enables `l3-counters` on all L3 interfaces (configurable via `aoscx_l3_counters_enable`)
- **VRF Attachment**: Full support for custom VRFs based on interface configuration
- **IPv4 and IPv6**: Dual-stack support with proper address family handling

### Example Generated Configuration

For interface 1/1/5 with MTU 9198 in VRF "customer_a":

```bash
interface 1/1/5
  vrf attach customer_a
  ip address 10.1.1.1/30
  ip mtu 9198
  l3-counters
```

The `aoscx_l3_interface` module limitations (no `ip mtu` or `l3-counters` support) are bypassed by using raw CLI configuration through `aoscx_config`.

### Important Notes

⚠️ **IPv4 Idempotency**: IPv4 address configuration tasks only execute when changes are needed. The role compares NetBox's intended configuration with device facts to determine which specific IP addresses require addition. This optimization significantly reduces configuration time by avoiding unnecessary device connections.

⚠️ **IPv6 Performance Trade-off**: IPv6 addresses in AOS-CX device facts are returned as REST API URL references (e.g., `/rest/v10.09/system/interfaces/vlan11/ip6_addresses`) rather than actual address values. While it's technically possible to retrieve IPv6 addresses via CLI commands, testing confirmed that the overhead of fetching and comparing IPv6 data exceeds the time it takes to simply apply the idempotent configuration. As a result:

- IPv6 configuration tasks always execute (no pre-comparison)
- Tasks use `changed_when: false` to suppress false positive "changed" status
- IPv6 configuration remains idempotent at the CLI level (duplicate commands have no effect)
- This approach is faster than checking before applying

⚠️ **General Note**: Tasks using `aoscx_config` may occasionally show `changed` status due to module state detection limitations, but actual device configuration remains correct and idempotent.

## Requirements

### Ansible Collections

```yaml
collections:
  - arubanetworks.aoscx >= 4.4.0
  - netbox.netbox >= 3.21.0
  - ansible.utils >= 2.0.0
```

Install with:

```bash
ansible-galaxy collection install -r requirements.yml
```

### Python Libraries

This role requires several Python libraries for the Aruba and NetBox collections to function. Install all dependencies with:

```bash
pip install -r requirements.txt
```

Required libraries:

- **pyaoscx** >= 2.6.0 - Aruba AOS-CX Python SDK
- **pynetbox** >= 6.0.0 - NetBox API client
- **paramiko** >= 2.7.0 - SSH library for device connections
- **ansible-pylibssh** >= 1.0.0 - Python SSH library wrapper
- **requests** >= 2.25.0 - HTTP library
- **packaging** >= 20.0 - Version parsing
- **pytz** >= 2021.1 - Timezone support

## Installation

### Quick Start

Install all dependencies (role, collections, and Python libraries):

```bash
# Install Ansible role and collections
ansible-galaxy install -r requirements.yml

# Install Python dependencies
pip install -r requirements.txt
```

### From GitHub (Private Repository)

Since this role is currently private on GitHub, you'll need SSH access. Add the following to your project's `requirements.yml`:

```yaml
---
roles:
  - name: aopdal.aruba_cx_switch
    src: git@github.com:aopdal/ansible-role-aruba-cx-switch.git
    version: main  # or specify a tag like 'v1.0.0'
    scm: git

collections:
  - name: arubanetworks.aoscx
    version: ">=4.4.0"
  - name: netbox.netbox
    version: ">=3.21.0"
```

Install with:

```bash
ansible-galaxy install -r requirements.yml
```

**Note:** Ensure you have SSH access to the repository:

```bash
# Test SSH connection
ssh -T git@github.com

# If needed, add your SSH key
ssh-add ~/.ssh/id_rsa
```

### Direct Installation

```bash
# Install directly from GitHub (SSH)
ansible-galaxy install git+git@github.com:aopdal/ansible-role-aruba-cx-switch.git,main

# Or using HTTPS (requires authentication for private repos)
ansible-galaxy install git+https://github.com/aopdal/ansible-role-aruba-cx-switch.git,main
```

### From Ansible Galaxy (When Published)

Once the role is published to Ansible Galaxy:

```bash
ansible-galaxy install aopdal.aruba_cx_switch
```

Or in `requirements.yml`:

```yaml
---
roles:
  - name: aopdal.aruba_cx_switch
    version: ">=1.0.0"
```

## 📚 Documentation

### Quick Start & Usage

- **[docs/QUICKSTART.md](docs/QUICKSTART.md)** - Quick start guide for using the role
- **[docs/QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md)** - Common tasks reference
- **[docs/README.md](docs/README.md)** - Complete documentation index

### NetBox Integration (Essential)

- **[docs/NETBOX_INTEGRATION.md](docs/NETBOX_INTEGRATION.md)** - **Required reading** - Comprehensive NetBox integration guide
    - Custom fields required for device configuration
    - Config context structure and examples
    - NetBox inventory plugin setup
    - Troubleshooting NetBox integration issues

- **[docs/FILTER_PLUGINS.md](docs/FILTER_PLUGINS.md)** - NetBox data transformation
    - 22 custom filters for VLAN, VRF, interface, and OSPF operations
    - Critical for understanding how the role processes NetBox data

### Configuration Guides

- **[docs/BASE_CONFIGURATION.md](docs/BASE_CONFIGURATION.md)** - Base system (banner, NTP, DNS, timezone)
- **[docs/VLAN_CHANGE_IDENTIFICATION_WORKFLOW.md](docs/VLAN_CHANGE_IDENTIFICATION_WORKFLOW.md)** - VLAN management workflow
- **[docs/BGP_CONFIGURATION.md](docs/BGP_CONFIGURATION.md)** - BGP/EVPN fabric configuration
- **[docs/TAG_DEPENDENT_SUMMARY.md](docs/TAG_DEPENDENT_SUMMARY.md)** - Tag-dependent tasks (BGP, OSPF, VSX)

### Developer Documentation

For contributors and developers:

- **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)** - Complete development guide
    - Dev Container setup (recommended)
    - Local development environment setup
    - Testing and code standards

- **[docs/TESTING_ENVIRONMENT.md](docs/TESTING_ENVIRONMENT.md)** - Integration testing guide

### Documentation Site

View all documentation with beautiful formatting using MkDocs:

```bash
pip install -r requirements-docs.txt
make docs-serve  # Opens at http://127.0.0.1:8000
```

### NetBox Configuration

This role requires the NetBox dynamic inventory plugin with specific settings:

```yaml
# inventory.netbox.yml
plugin: netbox.netbox.nb_inventory
api_endpoint: "{{ netbox_url }}"
token: "{{ netbox_token }}"
validate_certs: false
interfaces: true
fetch_all: true

compose:
  ansible_network_os: custom_fields.ansible_network_os
  device_id: id

group_by:
  - device_roles
  - sites
  - platforms
```

## Role Variables

See [defaults/main.yml](defaults/main.yml) for all available variables.

### Core Variables

```yaml
# Enable/disable features
aoscx_configure_vrfs: true
aoscx_configure_vlans: true
aoscx_configure_physical_interfaces: true
aoscx_configure_l2_interfaces: true
aoscx_configure_l3_interfaces: true
aoscx_configure_loopback: true
aoscx_configure_ospf: true

# Idempotent mode - removes configs not in NetBox
aoscx_idempotent_mode: false

# Save configuration after changes
aoscx_save_config: true

# Debug output
aoscx_debug: false

# L3 interface settings
aoscx_l3_counters_enable: true  # Enable l3-counters on L3 interfaces
```

### NetBox Connection

```yaml
netbox_url: "{{ lookup('env', 'NETBOX_URL') }}"
netbox_token: "{{ lookup('env', 'NETBOX_TOKEN') }}"
```

### OSPF Configuration

Configure OSPF in NetBox using custom fields and config context. Supports both single-VRF and multi-VRF configurations.

#### Device Custom Fields

```yaml
# Required custom field on devices
device_ospf_1_routerid: "10.1.1.1"  # OSPF Router ID
```

#### Device Config Context - Multi-VRF Format (Recommended)

```yaml
# OSPF configuration supporting multiple VRFs
ospf_process_id: 1  # Optional, defaults to 1
ospf_vrfs:
  - vrf: "default"
    areas:
      - area: "0.0.0.0"      # Backbone area
      - area: "0.0.0.1"      # Additional areas
  - vrf: "cust_2"
    areas:
      - area: "0.0.0.0"
      - area: "0.0.0.1"
```

#### Device Config Context - Single-VRF Format (Legacy, still supported)

```yaml
# Simple single-VRF configuration
ospf_1_vrf: "default"  # or specify VRF name
ospf_areas:
  - ospf_1_area: "0.0.0.0"      # Backbone area
  - ospf_1_area: "0.0.0.1"      # Additional areas
```

#### Interface Custom Fields

```yaml
# Required custom fields on interfaces
if_ip_ospf_1_area: "0.0.0.0"           # OSPF area for this interface
if_ip_ospf_network: "point-to-point"    # Network type (broadcast, point-to-point, etc.)
```

#### Complete Examples

**Multi-VRF Example:**

Device custom fields:

```yaml
device_ospf_1_routerid: "192.168.1.1"
```

Device config context:

```yaml
ospf_process_id: 1
ospf_vrfs:
  - vrf: "default"
    areas:
      - area: "0.0.0.0"
      - area: "0.0.0.1"
  - vrf: "CUSTOMER_A"
    areas:
      - area: "0.0.0.0"
```

Interface custom fields (for each OSPF-enabled interface):

```yaml
if_ip_ospf_1_area: "0.0.0.0"
if_ip_ospf_network: "point-to-point"
```

**Single-VRF Example (Legacy):**

Device custom fields:

```yaml
device_ospf_1_routerid: "192.168.1.1"
```

Device config context:

```yaml
ospf_1_vrf: "default"
ospf_areas:
  - ospf_1_area: "0.0.0.0"
  - ospf_1_area: "0.0.0.1"
```

Interface custom fields (for each OSPF-enabled interface):

```yaml
if_ip_ospf_1_area: "0.0.0.0"
if_ip_ospf_network: "point-to-point"
```

### Loopback Configuration

Loopback interfaces are automatically detected from NetBox and configured with IP addresses and VRF assignments.

#### Requirements

- Interface type: `virtual`
- Interface name pattern: `loopback*` (e.g., `loopback0`, `loopback1`)
- IP addresses assigned to the interface in NetBox
- Optional: VRF assignment for custom routing tables

#### NetBox Configuration

**Interface Setup:**

```yaml
# Interface properties in NetBox
name: loopback0
type: virtual
enabled: true
description: "Router ID and BGP peering"
```

**IP Address Assignment:**

```yaml
# Assign IP addresses to loopback interface
address: 10.255.255.1/32
vrf: default  # or custom VRF name
```

#### Example Configuration

**Single Loopback (Default VRF):**

```yaml
# In NetBox, create:
# - Interface: loopback0, type=virtual, enabled=true
# - IP Address: 10.255.255.1/32, assigned to loopback0
```

Generated configuration:

```bash
interface loopback0
  ip address 10.255.255.1/32
```

**Multiple Loopbacks with Custom VRFs:**

```yaml
# Loopback 0 (default VRF) - Router ID
# - Interface: loopback0
# - IP: 10.255.255.1/32, vrf=default

# Loopback 1 (custom VRF) - Customer A
# - Interface: loopback1
# - IP: 192.168.1.1/32, vrf=customer_a
```

Generated configuration:
```bash
interface loopback0
  ip address 10.255.255.1/32

interface loopback1
  vrf attach customer_a
  ip address 192.168.1.1/32
```

#### Features

- ✅ Automatic detection of loopback interfaces by type and name
- ✅ IPv4 and IPv6 support
- ✅ VRF attachment for custom routing tables
- ✅ Dual-stack configuration
- ✅ Proper ordering (interface creation before IP assignment)

### VSX Configuration

VSX (Virtual Switching Extension) provides active-active redundancy for Aruba AOS-CX switches. This role configures VSX pairs with proper system MAC, role assignment, ISL, and keepalive settings.

#### Requirements

VSX configuration requires custom fields and config context in NetBox.

#### Device Custom Field

```yaml
# Required custom field on devices
device_vsx: true  # Enable VSX on this device
```

#### Device Config Context

```yaml
# VSX configuration parameters
vsx_system_mac: "02:00:00:00:01:00"  # Shared system MAC for VSX pair
vsx_role: "primary"                   # Role: primary or secondary
vsx_isl_lag: "isl"                    # ISL LAG interface name
vsx_keepalive_peer: "192.168.1.2"     # IP address of VSX peer
vsx_keepalive_src: "192.168.1.1"      # Source IP for keepalive
vsx_keepalive_vrf: "mgmt"             # VRF for keepalive (default: mgmt)
```

#### Complete Example

**Primary Switch Configuration:**

Device custom field:

```yaml
device_vsx: true
```

Device config context:

```yaml
vsx_system_mac: "02:00:00:00:01:00"
vsx_role: "primary"
vsx_isl_lag: "isl"
vsx_keepalive_peer: "192.168.100.2"
vsx_keepalive_src: "192.168.100.1"
vsx_keepalive_vrf: "mgmt"
```

Generated configuration:

```bash
vsx-sync vsx-global
vsx
  system-mac 02:00:00:00:01:00
  inter-switch-link lag isl
  role primary
  keepalive peer 192.168.100.2 source 192.168.100.1 vrf mgmt
```

**Secondary Switch Configuration:**

Device custom field:

```yaml
device_vsx: true
```

Device config context:

```yaml
vsx_system_mac: "02:00:00:00:01:00"  # Same MAC as primary
vsx_role: "secondary"                 # Different role
vsx_isl_lag: "isl"
vsx_keepalive_peer: "192.168.100.1"  # Peer is primary
vsx_keepalive_src: "192.168.100.2"   # This switch's IP
vsx_keepalive_vrf: "mgmt"
```

#### VSX Deployment Notes

1. **System MAC**: Must be identical on both VSX peers
2. **Roles**: One switch must be `primary`, the other `secondary`
3. **Keepalive**: Peer IPs should be reachable (typically over management network)
4. **ISL**: Configure ISL LAG interfaces separately with `mclag_interfaces` configuration
5. **MCLAG**: Multi-Chassis LAG interfaces require VSX to be configured first

#### Tag-Dependent Execution

VSX configuration only runs when explicitly requested:

- `ansible-playbook site.yml --tags vsx`
- `ansible-playbook site.yml --tags ha`
- `ansible-playbook site.yml` (full run without tags)

#### Features

- ✅ System MAC and role configuration
- ✅ Inter-Switch Link (ISL) LAG setup
- ✅ Keepalive configuration with custom VRF support
- ✅ VSX-sync global configuration
- ✅ Validation of required parameters
- ✅ Comprehensive debug output
- ✅ Graceful handling when VSX is not enabled

## Dependencies

None.

## Example Playbook

```yaml
---
- name: Configure Aruba CX Switches
  hosts: aoscx_switches
  gather_facts: false

  roles:
    - role: aruba_cx_switch
      vars:
        aoscx_idempotent_mode: true
        aoscx_debug: false
```

### Example with Tags

```yaml
---
- name: Configure VLANs and L2 Interfaces Only
  hosts: aoscx_switches
  gather_facts: false

  roles:
    - role: aruba_cx_switch

  tags:
    - vlans
    - l2_interfaces
```

## Usage Examples

### Basic Configuration

```bash
# Configure everything
ansible-playbook site.yml

# Configure specific components
ansible-playbook site.yml --tags vlans,l2_interfaces

# Configure in idempotent mode (removes extra configs)
ansible-playbook site.yml -e aoscx_idempotent_mode=true

# Debug mode
DEBUG_ANSIBLE=true ansible-playbook site.yml -v
```

### Layer 2 Configuration Only

```bash
ansible-playbook site.yml --tags layer2
```

### Layer 3 Configuration Only

```bash
ansible-playbook site.yml --tags layer3
```

### Don't Save Configuration (Testing)

```bash
ansible-playbook site.yml -e aoscx_save_config=false
```

## Tags

### Always-Running Tags

- `always` - Always runs (fact gathering, save config)
- `facts`, `gather` - Fact gathering

### Configuration Tags

- `ztp`, `config_generation` - ZTP configuration generation
- `banner`, `base_config`, `system` - Banner configuration
- `timezone`, `base_config`, `system` - Timezone configuration
- `ntp`, `base_config`, `system` - NTP configuration
- `dns`, `base_config`, `system` - DNS configuration
- `vrfs`, `layer3`, `routing` - VRF configuration
- `vlans`, `layer2` - VLAN configuration
- `interfaces`, `physical_interfaces`, `layer1` - Physical interface configuration
- `interfaces`, `lag_interfaces`, `layer2` - LAG interface configuration
- `interfaces`, `mclag_interfaces`, `vsx` - MCLAG interface configuration (VSX)
- `interfaces`, `lag_interfaces`, `mclag_interfaces`, `lag_assignment` - LAG member assignment
- `interfaces`, `l2_interfaces`, `layer2` - L2 interface configuration (access/trunk)
- `interfaces`, `l3_interfaces`, `layer3` - L3 interface configuration (IP addresses)
- `loopback`, `layer3` - Loopback interface configuration
- `evpn`, `overlay` - EVPN configuration
- `vxlan`, `overlay` - VXLAN configuration
- `evpn`, `overlay`, `cleanup`, `idempotent` - EVPN cleanup (idempotent mode only)
- `vxlan`, `overlay`, `cleanup`, `idempotent` - VXLAN cleanup (idempotent mode only)
- `vlans`, `layer2`, `cleanup`, `idempotent` - VLAN cleanup (idempotent mode only)
- `ospf`, `routing`, `layer3` - OSPF configuration (tag-dependent)
- `bgp`, `routing`, `layer3` - BGP configuration (tag-dependent)
- `vsx`, `ha` - VSX configuration (tag-dependent)
- `save`, `config` - Save configuration

### Aggregate Tags

- `base_config` - All base system configuration (banner, timezone, NTP, DNS)
- `layer1` - Physical interface configuration
- `layer2` - All L2 configuration (VLANs + L2 interfaces + LAG)
- `layer3` - All L3 configuration (VRFs + L3 interfaces + loopbacks + routing)
- `interfaces` - All interface configuration (physical, LAG, MCLAG, L2, L3)
- `routing` - All routing protocol configuration (OSPF, BGP)
- `overlay` - All overlay configuration (EVPN, VXLAN)
- `cleanup` - All cleanup tasks (idempotent mode only)
- `idempotent` - All idempotent cleanup tasks
- `system` - All system configuration (banner, timezone, NTP, DNS)
- `vsx` - VSX/MCLAG configuration
- `ha` - High availability configuration (VSX)

### Tag-Dependent Tasks

Some tasks only run when explicitly requested with specific tags:

- **OSPF** - Requires `--tags ospf`, `--tags routing`, or no tags (full run)
- **BGP** - Requires `--tags bgp`, `--tags routing`, or no tags (full run)
- **VSX** - Requires `--tags vsx`, `--tags ha`, or no tags (full run)

## VRF Handling

### Built-in VRFs

These VRFs are automatically filtered and not configured:

- `default` / `Default` - Default routing instance
- `Global` / `global` - Alias for default VRF
- `mgmt` / `MGMT` - Management VRF (non-configurable)

### Custom VRFs

Custom VRFs are:
1. Created with `aoscx_vrf` module
2. Configured with RD and route-targets from NetBox
3. Attached to interfaces before IP configuration

## Virtual Chassis Support

This role supports AOS-CX virtual chassis (VSX):
- VLANs are queried using `available_on_device` (shared across chassis)
- IP addresses are per-chassis-member (from interface objects)
- Each member is configured independently

## Idempotent Mode

The role supports two configuration modes controlled by the `aoscx_idempotent_mode` variable:

### Standard Mode (Default: `aoscx_idempotent_mode: false`)

- ✅ **Additive configuration** - Only adds/updates configurations from NetBox
- ✅ **Faster execution** - Skips current state analysis
- ✅ **Safer for initial deployment** - Won't remove existing configs
- ✅ **Use case**: Initial device setup, adding new configurations

### Idempotent Mode (`aoscx_idempotent_mode: true`)

- ✅ **Full synchronization** - Device state matches NetBox exactly
- ✅ **Removes configurations not in NetBox**:
    - VLANs not in NetBox (except VLAN 1 - default VLAN)
    - VLAN assignments from interfaces not in NetBox
    - Trunk allowed VLANs not matching NetBox
    - EVPN configuration for VLANs being removed
    - VXLAN VNI and VLAN-to-VNI mappings for VLANs being removed
- ✅ **Intelligent cleanup** - Only removes configs not referenced in NetBox
- ✅ **Proper cleanup order** - EVPN → VXLAN → VLAN (prevents orphaned configurations)
- ✅ **Use case**: Ongoing management, drift detection, compliance enforcement

**⚠️ Important Notes:**

- **Idempotent mode is more thorough** but takes longer as it analyzes current device state
- **Use caution in production** - Always test idempotent mode in a dev environment first
- **Unified task file** - Both modes use the same `configure_l2_interfaces.yml` task file
- The role automatically detects the mode and adjusts behavior accordingly

**Example Configuration:**

```yaml
# group_vars/switches.yml

# For initial deployment or adding configs
aoscx_idempotent_mode: false

# For ongoing management and drift detection
aoscx_idempotent_mode: true
```

**Migration Note:** The `configure_l2_interfaces_idempotent.yml` file has been deprecated in favor of a unified
approach. Both modes now use `configure_l2_interfaces.yml` which intelligently handles both standard and idempotent operation.

## Testing

This role includes comprehensive testing. For detailed testing information, see:

- **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)** - Unit tests and development testing
- **[docs/TESTING_ENVIRONMENT.md](docs/TESTING_ENVIRONMENT.md)** - Integration testing setup
- **[tests/unit/README.md](tests/unit/README.md)** - Unit test documentation
- **[testing-scripts/README.md](testing-scripts/README.md)** - Testing scripts usage

## License

MIT

## Author Information

Created by Arne Opdal

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Changelog

### Version 1.0.0 (2025-10-14)

- Initial release
- VRF configuration support
- VLAN management with idempotent mode
- L2 interface configuration (access/trunk/LAG)
- L3 interface configuration (physical/VLAN/LAG/loopback)
- Virtual chassis support
- NetBox integration

## Support

For issues and questions:

- GitHub Issues: https://github.com/aopdal/ansible-role-aruba-cx-switch/issues
- Documentation: https://github.com/aopdal/ansible-role-aruba-cx-switch/wiki
