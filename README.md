# Ansible Role: Aruba AOS-CX Switch

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Ansible Role](https://img.shields.io/ansible/role/XXXXX)](https://galaxy.ansible.com/your-namespace/aruba_cx_switch)

Comprehensive Ansible role for configuring Aruba AOS-CX switches with NetBox as the source of truth.

## Features

- ✅ **VRF Configuration** - Creates VRFs with RD and route-targets
- ✅ **VLAN Management** - Idempotent VLAN creation and cleanup
- ✅ **L2 Interface Configuration** - Access and trunk ports with LACP support
- ✅ **L3 Interface Configuration** - IPv4/IPv6 with VRF support
- ✅ **VLAN Interfaces (SVIs)** - Automatic creation and IP configuration
- ✅ **Loopback Interfaces** - With VRF support
- ✅ **Virtual Chassis Support** - Works with VSX/stacked switches
- ✅ **Idempotent Mode** - Removes configurations not in NetBox
- ✅ **NetBox Integration** - Uses NetBox as single source of truth

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
ansible-galaxy collection install arubanetworks.aoscx netbox.netbox
```

### Python Libraries

```bash
pip install pynetbox
```

## Installation

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

## Role Variables

See [defaults/main.yml](defaults/main.yml) for all available variables.

### Core Variables

```yaml
# Enable/disable features
aoscx_configure_vrfs: true
aoscx_configure_vlans: true
aoscx_configure_l2_interfaces: true
aoscx_configure_l3_interfaces: true
aoscx_configure_loopback: true

# Idempotent mode - removes configs not in NetBox
aoscx_idempotent_mode: false

# Save configuration after changes
aoscx_save_config: true

# Debug output
aoscx_debug: false
```

### NetBox Connection

```yaml
netbox_url: "{{ lookup('env', 'NETBOX_URL') }}"
netbox_token: "{{ lookup('env', 'NETBOX_TOKEN') }}"
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
- `l2_interfaces` - L2 interface configuration
- `l3_interfaces` - L3 interface configuration
- `loopback` - Loopback interface configuration
- `layer2` - All L2 configuration (VLANs + L2 interfaces)
- `layer3` - All L3 configuration (VRFs + L3 interfaces + loopbacks)
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

### Version 1.0.0 (2024-10-05)
- Initial release
- VRF configuration support
- VLAN management with idempotent mode
- L2 interface configuration (access/trunk/LAG)
- L3 interface configuration (physical/VLAN/LAG/loopback)
- Virtual chassis support
- NetBox integration

## Support

For issues and questions:
- GitHub Issues: https://github.com/your-org/ansible-role-aruba-cx-switch/issues
- Documentation: https://github.com/your-org/ansible-role-aruba-cx-switch/wiki
