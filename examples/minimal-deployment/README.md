# Minimal Deployment Example

This example demonstrates the simplest possible deployment of the `ansible-role-aruba-cx-switch` role, perfect for getting started or managing a small number of switches.

## What This Example Demonstrates

- Basic inventory structure with a single switch
- Essential group_vars configuration
- Base system configuration (banner, NTP, DNS, timezone)
- VLAN management
- Interface configuration (access and trunk ports)
- Simple playbook structure

## Prerequisites

1. **Ansible 2.10+** with AOS-CX collection:
   ```bash
   ansible-galaxy collection install arubanetworks.aoscx
   ```

2. **NetBox** (optional but recommended):
   - NetBox instance accessible via API
   - Switch device created in NetBox
   - VLANs configured in NetBox
   - Interfaces documented in NetBox

3. **Network Access**:
   - SSH connectivity to your switch
   - Management IP configured on the switch

## Quick Start

### 1. Copy the Example

```bash
cp -r examples/minimal-deployment ~/my-switch-config
cd ~/my-switch-config
```

### 2. Configure Your Inventory

Edit `inventory/hosts.yml` with your switch details:

```yaml
all:
  children:
    aruba_switches:
      hosts:
        sw01:
          ansible_host: 192.168.1.10
          ansible_network_os: arubanetworks.aoscx.aoscx
```

### 3. Set Up Credentials

Create an encrypted vault file:

```bash
ansible-vault create inventory/group_vars/all/vault.yml
```

Add your credentials:

```yaml
---
vault_ansible_password: "your_switch_password"
vault_netbox_token: "your_netbox_api_token"
```

### 4. Configure NetBox Connection

Edit `inventory/group_vars/all.yml` and update:

```yaml
netbox_url: "https://your-netbox-instance.com"
netbox_token: "{{ vault_netbox_token }}"
```

### 5. Review Configuration Variables

Check `inventory/group_vars/aruba_switches.yml` and customize as needed:

- Banner text
- NTP servers
- DNS settings
- Timezone
- Which features to enable

### 6. Dry Run (Check Mode)

Test without making changes:

```bash
ansible-playbook -i inventory/hosts.yml playbook.yml --check
```

### 7. Apply Configuration

```bash
ansible-playbook -i inventory/hosts.yml playbook.yml
```

## Using Without NetBox

If you don't have NetBox, you can still use this role by providing configuration via variables:

1. Set `aoscx_use_netbox: false` in `inventory/group_vars/aruba_switches.yml`

2. Define VLANs manually:

```yaml
aoscx_vlans:
  - id: 10
    name: "DATA"
  - id: 20
    name: "VOICE"
  - id: 30
    name: "GUEST"
```

3. Define interfaces manually:

```yaml
aoscx_interfaces:
  - name: "1/1/1"
    description: "Server Port"
    enabled: true
    vlan:
      mode: "access"
      access_vlan: 10
```

See `netbox-export-sample.json` for the data structure NetBox would provide.

## File Structure

```
minimal-deployment/
├── README.md                          # This file
├── playbook.yml                       # Main playbook
├── inventory/
│   ├── hosts.yml                      # Inventory file
│   └── group_vars/
│       ├── all.yml                    # NetBox connection settings
│       └── aruba_switches.yml         # Role configuration variables
└── netbox-export-sample.json          # Sample NetBox data structure
```

## Configuration Features Enabled

This minimal example enables:

✅ **Base Configuration**
- System banner
- Timezone (America/New_York)
- NTP servers
- DNS (domain name, nameservers)

✅ **VLAN Management**
- Automatic VLAN creation from NetBox
- VLAN cleanup (removes VLANs not in NetBox)

✅ **Interface Configuration**
- Physical interface descriptions
- Access port VLAN assignment
- Trunk port VLAN allowlist

## Running Specific Sections

Use Ansible tags to run only specific configuration sections:

```bash
# Only configure VLANs
ansible-playbook -i inventory/hosts.yml playbook.yml --tags vlans

# Only configure interfaces
ansible-playbook -i inventory/hosts.yml playbook.yml --tags interfaces

# Base config only (banner, NTP, DNS, timezone)
ansible-playbook -i inventory/hosts.yml playbook.yml --tags base
```

## Expanding This Example

Once you're comfortable with this minimal setup, you can enable additional features:

### Add L3 Interfaces

In `inventory/group_vars/aruba_switches.yml`:

```yaml
aoscx_configure_l3_interfaces: true
```

### Add VRFs

```yaml
aoscx_configure_vrfs: true
```

Configure VRFs in NetBox config_context or as variables.

### Add OSPF or BGP

```yaml
aoscx_configure_ospf: true  # Requires --tags ospf
aoscx_configure_bgp: true   # Requires --tags bgp
```

See [BGP_CONFIGURATION.md](../../docs/BGP_CONFIGURATION.md) for details.

## Troubleshooting

### Connection Issues

```bash
# Test basic connectivity
ansible -i inventory/hosts.yml aruba_switches -m ping

# Test SSH connection
ssh netops@192.168.1.10
```

### NetBox Connection Issues

```bash
# Test NetBox API access
ansible -i inventory/hosts.yml aruba_switches -m debug -a "var=hostvars[inventory_hostname]"
```

### Check What Would Change

```bash
# Run in check mode with verbose output
ansible-playbook -i inventory/hosts.yml playbook.yml --check -vv
```

### View NetBox Data

```bash
# See what NetBox data is being retrieved
ansible-playbook -i inventory/hosts.yml playbook.yml --tags never -e "debug_netbox=true"
```

## Next Steps

- **Explore more features:** See [QUICK_REFERENCE.md](../../docs/QUICK_REFERENCE.md)
- **Advanced VLAN workflows:** See [VLAN_CHANGE_IDENTIFICATION_WORKFLOW.md](../../docs/VLAN_CHANGE_IDENTIFICATION_WORKFLOW.md)
- **Add EVPN/VXLAN:** See [EVPN_VXLAN_CONFIGURATION.md](../../docs/EVPN_VXLAN_CONFIGURATION.md)
- **Deploy a full fabric:** See the [bgp-evpn-fabric](../bgp-evpn-fabric/) example

## Getting Help

- Check the [documentation](../../docs/README_DOCS.md)
- Review [FILTER_PLUGINS.md](../../docs/FILTER_PLUGINS.md) to understand data transformation
- See [NETBOX_INTEGRATION.md](../../docs/NETBOX_INTEGRATION.md) for NetBox setup details
