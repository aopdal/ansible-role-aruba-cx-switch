# Ansible Role: Aruba AOS-CX Switch

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Ansible Role](https://img.shields.io/ansible/role/XXXXX)](https://galaxy.ansible.com/aopdal/aruba_cx_switch)

Comprehensive Ansible role for configuring Aruba AOS-CX switches with NetBox as the source of truth.

## Features

- ✅ **VRF Configuration** - Creates VRFs with RD and route-targets
- ✅ **VLAN Management** - Idempotent VLAN creation and cleanup
- ✅ **Physical Interface Configuration** - Enable/disable and description
- ✅ **L2 Interface Configuration** - Access and trunk ports with LACP support
- ✅ **L3 Interface Configuration** - IPv4/IPv6 with VRF support, ip mtu, and l3-counters
- ✅ **VLAN Interfaces (SVIs)** - Automatic creation and IP configuration
- ✅ **Loopback Interfaces** - With VRF support
- ✅ **OSPF Configuration** - Router instance, areas, and interface configuration
- ✅ **Virtual Chassis Support** - Works with VSX/stacked switches
- ✅ **Idempotent Mode** - Removes configurations not in NetBox
- ✅ **NetBox Integration** - Uses NetBox as single source of truth

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

⚠️ **Idempotency Behavior**: L3 interface tasks using `aoscx_config` may show `changed` status even when the configuration already exists. This is a limitation of the `aoscx_config` module's state detection, but the actual device configuration remains correct and idempotent at the CLI level.

## Getting Started

### 🚀 Quick Start (Recommended: Dev Container)

The easiest way to start developing is using the **VS Code Dev Container** which provides a pre-configured environment with all dependencies:

1. **Prerequisites**: Install [VS Code](https://code.visualstudio.com/) and [Docker](https://www.docker.com/get-started)
2. **Install Extension**: Install the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
3. **Open in Container**:
   - Open this folder in VS Code
   - When prompted, click **"Reopen in Container"** (or press `F1` → `Dev Containers: Reopen in Container`)
4. **Start Coding**: The container automatically installs all dependencies!

All Python packages, Ansible collections, and tools are pre-configured. No manual setup needed! 🎉

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for detailed development guidelines.

### 📦 Alternative: Traditional Setup

If you don't have Docker, you can use a traditional virtual environment setup. See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for detailed instructions.

## Requirements

### Ansible Collections

```yaml
collections:
  - arubanetworks.aoscx >= 4.0.0
  - netbox.netbox >= 3.0.0
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
    version: ">=4.0.0"
  - name: netbox.netbox
    version: ">=3.0.0"
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

## 📚 Documentation

Comprehensive documentation is available in the `docs/` folder:

### Essential Reading

- **[docs/FILTER_PLUGINS.md](docs/FILTER_PLUGINS.md)** - **Essential** - Custom filters for NetBox data transformation
  - 22 filters for VLAN, VRF, interface, and OSPF operations
  - Real-world examples and workflows
  - Critical for understanding how the role processes NetBox data

- **[docs/QUICKSTART.md](docs/QUICKSTART.md)** - Quick start guide
- **[docs/QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md)** - Common tasks reference

### Configuration Guides

- **[docs/BASE_CONFIGURATION.md](docs/BASE_CONFIGURATION.md)** - Base system (banner, NTP, DNS, timezone)
- **[docs/BGP_CONFIGURATION.md](docs/BGP_CONFIGURATION.md)** - BGP/EVPN fabric configuration
- **[docs/TAG_DEPENDENT_SUMMARY.md](docs/TAG_DEPENDENT_SUMMARY.md)** - Tag-dependent tasks (BGP, OSPF, VSX)

### Development & Testing

- **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)** - Complete development guide
- **[docs/TESTING_ENVIRONMENT.md](docs/TESTING_ENVIRONMENT.md)** - Integration testing guide
- **[docs/README.md](docs/README.md)** - Complete documentation index

### MkDocs Site

View documentation with beautiful formatting:

```bash
pip install -r requirements-docs.txt
make docs-serve  # Opens at http://127.0.0.1:8000
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

- `always` - Always runs (fact gathering)
- `facts`, `gather` - Fact gathering
- `vrfs` - VRF configuration
- `vlans` - VLAN configuration
- `physical_interfaces` - Physical interface configuration (enable/disable)
- `l2_interfaces` - L2 interface configuration
- `l3_interfaces` - L3 interface configuration
- `loopback` - Loopback interface configuration
- `layer1` - Physical interface configuration
- `layer2` - All L2 configuration (VLANs + L2 interfaces)
- `layer3` - All L3 configuration (VRFs + L3 interfaces + loopbacks)
- `ospf` - OSPF configuration
- `routing` - Routing protocol configuration
- `idempotent` - Cleanup tasks (requires `aoscx_idempotent_mode: true`)
- `save` - Save configuration

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

When `aoscx_idempotent_mode: true`:
- ✅ Removes VLANs not in NetBox (except VLAN 1)
- ✅ Removes VLAN assignments from interfaces not in NetBox
- ✅ Cleans up trunk allowed VLANs

**Warning**: Use with caution in production - this removes configurations!

## Testing

This role includes comprehensive integration testing documentation and scripts for testing with real/virtual Aruba AOS-CX switches.

### Testing Documentation

- **[Testing Environment](docs/TESTING_ENVIRONMENT.md)** - Complete testing setup guide
- **[Quick Start](docs/TESTING_QUICK_START.md)** - 30-minute quick start to first test
- **[Testing Proposal](docs/TESTING_PROPOSAL.md)** - Executive summary for stakeholders

### Test Playbooks

- **[tests/test.yml](tests/test.yml)** - Basic integration test with mock data
- **[tests/test_real_data.yml](tests/test_real_data.yml)** - Comprehensive test with real NetBox data (z13-cx3)

The real data test includes:
- **19 interfaces** (physical, LAG, virtual) from production NetBox inventory
- **Multi-VRF OSPF** (default + z13-cust_2 VRFs)
- **Complex LAG configurations** (MCLAG, ISL, tagged/access)
- **VSX and VXLAN features** with real IP addressing schemes
- **Point-to-point and broadcast OSPF networks**
- **Production-like device configuration** from actual Aruba deployment

### Testing Architecture

The testing environment uses:
- **EVE-NG** - Virtual network lab for AOS-CX switches
- **NetBox** - Source of truth for network configuration
- **Ansible** - Role execution and validation
- **pytest** - Automated test validation

### Test Scenarios Covered

1. ✅ VLAN creation and deletion
2. ✅ Orphaned VLAN cleanup (not in NetBox)
3. ✅ L2 interface configuration (trunk/access)
4. ✅ L3 interface configuration (SVIs, routed ports)
5. ✅ VRF configuration
6. ✅ Routing protocols (OSPF, BGP)
7. ✅ EVPN/VXLAN (fabric topology)
8. ✅ VSX configuration
9. ✅ Idempotent operations

### Quick Test Setup

```bash
# 1. Deploy NetBox
git clone https://github.com/netbox-community/netbox-docker.git
cd netbox-docker && docker-compose up -d

# 2. Populate test data
python testing-scripts/populate_netbox.py \
  --url http://localhost:8000 \
  --token YOUR_TOKEN \
  --topology simple

# 3. Run tests
ansible-playbook -i inventory/hosts.yml playbooks/test_vlans.yml

# 4. Validate
python testing-scripts/validate_deployment.py \
  --switches spine1,leaf1 \
  --netbox-url http://localhost:8000 \
  --netbox-token YOUR_TOKEN
```

See [testing-scripts/README.md](testing-scripts/README.md) for detailed script usage.

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
