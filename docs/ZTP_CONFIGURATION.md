# ZTP (Zero Touch Provisioning) Configuration Generation

This role can generate Zero Touch Provisioning configurations for initial switch deployment. The ZTP configuration includes basic system settings and management interface configuration to establish initial connectivity.

## Overview

ZTP (Zero Touch Provisioning) allows switches to automatically download and apply an initial configuration during first boot. This feature generates a minimal configuration file that includes:

- Hostname configuration
- Admin user setup
- Management interface IP configuration
- Basic services (SSH, HTTPS API)
- Security settings

## Usage

### Basic Configuration

Enable ZTP configuration generation:

```yaml
aoscx_generate_ztp_config: true
aoscx_ztp_admin_user: "admin"
aoscx_ztp_admin_password: "SecurePassword123!"
```

### Advanced Configuration

```yaml
# ZTP settings
aoscx_generate_ztp_config: true
aoscx_ztp_output_dir: "/path/to/ztp/configs"  # Default: ./ztp_configs
aoscx_ztp_backup_configs: true
aoscx_ztp_admin_user: "netops"
aoscx_ztp_admin_password: "{{ vault_ztp_password }}"  # Use Ansible Vault
```

### Required NetBox Inventory Configuration

**Important**: This role relies on the NetBox dynamic inventory plugin to provide interface data. Configure your inventory properly:

```yaml
# inventory.netbox.yml
plugin: netbox.netbox.nb_inventory
api_endpoint: "{{ netbox_url }}"
token: "{{ netbox_token }}"
validate_certs: false

# CRITICAL: Enable interface fetching for ZTP generation
interfaces: true
fetch_all: true

compose:
  ansible_network_os: custom_fields.ansible_network_os
  device_id: id

group_by:
  - device_roles
  - sites
```

This automatically populates the `interfaces` variable for each device, which includes all interface data needed for ZTP configuration. This approach:

- ✅ Works with virtual chassis (stacked switches)
- ✅ Works with regular switches
- ✅ No additional API queries needed
- ✅ Uses same inventory source as rest of playbook

### Required NetBox Configuration

The ZTP template requires management interfaces to be configured in NetBox with the `mgmt_only` flag. This works with two common scenarios:

#### Scenario 1: Dedicated Management Interface

Switches with a dedicated out-of-band management port:

1. **Management Interface**: Create interface and mark it as management-only

   ```
   Name: mgmt
   Type: 1000BASE-T (1GE)
   Management Only: ✓ (checked)
   ```

2. **IP Address**: Assign IP to management interface

   ```
   IP Address: 192.168.1.10/24
   Assigned Object: mgmt (on switch)
   ```

#### Scenario 2: VLAN Interface for Management

Switches using an in-band VLAN interface (SVI) for management:

1. **VLAN Interface**: Create VLAN interface and mark it as management-only

   ```
   Name: vlan100
   Type: Virtual
   Management Only: ✓ (checked)
   VRF: (optional - e.g., "mgmt-vrf" for management VRF)
   ```

2. **IP Address**: Assign IP to VLAN interface

   ```
   IP Address: 10.0.100.10/24
   Assigned Object: vlan100 (on switch)
   VRF: (optional - must match interface VRF if set)
   ```

3. **VLAN Configuration**: Ensure the VLAN exists in NetBox

   ```
   VLAN ID: 100
   Name: Management
   ```

**Important**:

- The `Management Only` checkbox must be enabled
- For VLAN interfaces, a default route is automatically generated using the first usable IP in the prefix (e.g., `10.0.100.1` for `10.0.100.10/24`)
- If the IP address is assigned to a VRF, the default route includes the VRF specification
- Example generated command: `ip route 0.0.0.0/0 10.0.100.1 vrf mgmt-vrf`

**Important**: The `Management Only` checkbox must be enabled in NetBox for the interface (mgmt or VLAN) to be included in ZTP configuration.

#### Common Configuration (Both Scenarios)

**Config Context**: Add management network settings to device/site config context

   ```yaml
   mgmt_defaultgateway: "192.168.1.1"  # Used for dedicated mgmt interfaces
   mgmt_nameserver: "8.8.8.8"
   # Or use multiple DNS servers:
   dns_servers:
     - "8.8.8.8"
     - "8.8.4.4"
   ```

**Note**: The `mgmt_defaultgateway` setting is only used for dedicated `mgmt` interfaces. For VLAN interfaces (SVIs), the default route is automatically calculated from the IP address prefix.

### Default Route Behavior

The template handles default gateway configuration differently based on interface type:

#### Dedicated Management Interface (`mgmt`)

Uses the `default-gateway` command under the interface:

```
interface mgmt
    ip static 192.168.1.10/24
    default-gateway 192.168.1.1
```
Gateway is taken from `mgmt_defaultgateway`.

#### VLAN Interface (SVI)

Uses a global `ip route` command with automatically calculated gateway:

```
interface vlan100
    vrf attach mgmt-vrf
    ip address 10.0.100.10/24

ip route 0.0.0.0/0 10.0.100.1 vrf mgmt-vrf
```

**Important**:
- VRF is attached to the interface using `vrf attach <name>` if the IP address has a VRF assigned in NetBox
- The `ip address` command is used (not `ip static` like on mgmt interfaces)
- The global `ip route` includes the VRF name when applicable

**Gateway Calculation**:

- Uses `ansible.utils.ipaddr` filter for accurate network calculations
- Calculates: `network_address + 1` to get the first usable IP
- Works with any subnet mask (not just /8, /16, /24)
- Examples:
    - `10.0.100.10/24` → gateway `10.0.100.1`
    - `172.16.50.10/16` → gateway `172.16.0.1`
    - `192.168.1.10/24` → gateway `192.168.1.1`
    - `10.1.2.100/22` → gateway `10.1.0.1`

**Implementation**:

```jinja2
{% set gateway = ip.address | ansible.utils.ipaddr('network') | ansible.utils.ipaddr('1') | ansible.utils.ipaddr('address') %}
```

**VRF Support**:

If the IP address is assigned to a VRF in NetBox, the route includes the VRF:

```
ip route 0.0.0.0/0 10.0.100.1 vrf mgmt-vrf
```

This is required for proper routing when management traffic is isolated in a separate VRF.

### How Management Interface Filtering Works

The `interfaces` variable is automatically populated by the NetBox inventory plugin when `interfaces: true` is configured. The role then filters management interfaces:

1. **Primary Method**: Filter by `mgmt_only=True` flag in NetBox
    - Works with any interface type: mgmt, VLAN, physical
    - Most reliable and explicit
    - Recommended approach
    - Task: `generate_ztp_config.yml` filters `interfaces | selectattr('mgmt_only')`
    - Works with virtual chassis and regular switches
    - Examples:
      - Dedicated mgmt interface: `mgmt` with `mgmt_only=True`
      - VLAN management: `vlan100` with `mgmt_only=True`

2. **Fallback Method**: Search interface names for "mgmt"
    - Used if `mgmt_interfaces` not defined
    - Template searches `interfaces` for names containing "mgmt"
    - Only finds dedicated mgmt interfaces, not VLAN interfaces
    - Less reliable but provides compatibility

   ```
   Address: 192.168.1.100/24
   Interface: mgmt
   ```

3. **Config Context**: Add management settings

    ```json
    {
      "mgmt_defaultgateway": "192.168.1.1",
      "mgmt_nameserver": "8.8.8.8",
      "dns_servers": ["8.8.8.8", "1.1.1.1"]
    }
    ```

## Generated Configuration Example

```bash
hostname sw01-lab

# User configuration
user admin group administrators password plaintext SecurePassword123!

# Aruba Central (disabled for on-premises)
aruba-central
    disable

# Management interface
interface mgmt
    ip static 192.168.1.100/24
    default-gateway 192.168.1.1
    nameserver 8.8.8.8

# Management services
ssh server vrf mgmt
https-server vrf mgmt
https-server rest access-mode read-write
```

## Playbook Examples

### Generate ZTP Configs for All Switches

```yaml
---
- name: Generate ZTP configurations
  hosts: aruba_switches
  gather_facts: yes
  vars:
    aoscx_generate_ztp_config: true
    aoscx_ztp_admin_user: "netops"
    aoscx_ztp_admin_password: "{{ vault_ztp_password }}"
  roles:
    - aopdal.aruba_cx_switch
```

### Generate ZTP Config with Custom Output Directory

```yaml
---
- name: Generate ZTP configurations for deployment
  hosts: new_switches
  vars:
    aoscx_generate_ztp_config: true
    aoscx_ztp_output_dir: "/var/lib/ztp/configs"
    aoscx_ztp_admin_user: "deploy"
    aoscx_ztp_admin_password: "{{ deploy_password }}"
  tasks:
    - name: Include ZTP generation only
      ansible.builtin.include_role:
        name: aopdal.aruba_cx_switch
        tasks_from: generate_ztp_config
```

### ZTP with Tags

```bash
# Generate only ZTP configs
ansible-playbook site.yml --tags ztp

# Generate configs without connecting to switches
ansible-playbook site.yml --tags ztp,config_generation
```

## Variables Reference

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `aoscx_generate_ztp_config` | Enable ZTP config generation | `true` |
| `aoscx_ztp_admin_password` | Admin password for initial login | `"SecurePass123!"` |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `aoscx_ztp_output_dir` | `"./ztp_configs"` | Directory for generated configs |
| `aoscx_ztp_backup_configs` | `true` | Backup existing config files |
| `aoscx_ztp_admin_user` | `"admin"` | Admin username |

### NetBox Data Variables

The template uses these variables from NetBox integration:

- `mgmt_interfaces` - Management interfaces (filtered from NetBox)
- `mgmt_defaultgateway` - Default gateway IP
- `mgmt_nameserver` - Primary DNS server
- `dns_servers` - List of DNS servers

## File Output

Generated files are saved as:

```
<output_directory>/<inventory_hostname>_ztp_base.cfg
```

Example:

```
./ztp_configs/sw01-lab_ztp_base.cfg
./ztp_configs/sw02-prod_ztp_base.cfg
```

## Security Considerations

### Password Security

⚠️ **Never store passwords in plain text!**

Use Ansible Vault for sensitive data:

```bash
# Create vault file
ansible-vault create group_vars/all/vault.yml
```

```yaml
# In vault.yml
vault_ztp_password: "SecurePassword123!"
```

```yaml
# In playbook
aoscx_ztp_admin_password: "{{ vault_ztp_password }}"
```

### User Privileges

The generated admin user has full administrator privileges. Consider:

1. **Change default passwords** immediately after deployment
2. **Use strong passwords** (minimum 12 characters)
3. **Implement certificate-based SSH** after initial setup
4. **Remove/disable ZTP user** after configuration management takes over

## Integration with ZTP Servers

### DHCP Configuration

Configure DHCP server to provide ZTP script:

```
# ISC DHCP
class "aruba-cx" {
    match if substring(option vendor-class-identifier, 0, 8) = "ArubaOS-";
}

subnet 192.168.1.0 netmask 255.255.255.0 {
    pool {
        allow members of "aruba-cx";
        range 192.168.1.50 192.168.1.99;
        option bootfile-name "http://ztp-server.example.com/ztp-script.py";
    }
}
```

### ZTP Script Integration

The generated configuration can be applied via ZTP script:

```python
#!/usr/bin/env python3
# ZTP Script example

import urllib.request

def main():
    # Download generated config
    hostname = get_hostname()
    config_url = f"http://ztp-server.example.com/configs/{hostname}_ztp_base.cfg"

    try:
        response = urllib.request.urlopen(config_url)
        config = response.read().decode('utf-8')

        # Apply configuration
        apply_config(config)

        print(f"ZTP configuration applied successfully for {hostname}")

    except Exception as e:
        print(f"ZTP failed: {e}")
        return False

    return True

if __name__ == "__main__":
    main()
```

## Troubleshooting

### No Management Interfaces Found

**Problem**: ZTP config shows "Warning: No management interfaces found"

**Causes**:

1. Interface doesn't have `Management Only` checkbox enabled in NetBox
2. `interfaces` variable not defined in playbook
3. Interface name doesn't contain "mgmt" (fallback method)

**Solutions**:

```yaml
# 1. Ensure NetBox inventory plugin is configured with interfaces enabled
# In your inventory.netbox.yml:
interfaces: true
fetch_all: true

# 2. Enable debug to see what's filtered
aoscx_debug: true
ansible_verbosity: 1

# 3. Manually set mgmt_interfaces if needed
- name: Set management interfaces manually
  ansible.builtin.set_fact:
    mgmt_interfaces:
      - name: mgmt
        ip_addresses:
          - address: "192.168.1.10/24"
```

### Management Interface Not Filtered Correctly

**Problem**: Template doesn't find management interface with `mgmt_only=True`

**Common Scenarios**:

1. Using VLAN interface for management but forgot to check `mgmt_only`
2. Using dedicated `mgmt` interface but forgot to check `mgmt_only`
3. Interface exists but `mgmt_only` field not set in NetBox

**Check NetBox Configuration**:

```bash
# Verify interface has mgmt_only flag
curl -H "Authorization: Token $NETBOX_TOKEN" \
  "$NETBOX_URL/api/dcim/interfaces/?device=switch01&mgmt_only=true"

# Should return interfaces like:
# - name: "mgmt" (dedicated management port)
# - name: "vlan100" (VLAN interface for management)
```

**Verify in Playbook**:

```yaml
- name: Debug - Check interfaces
  ansible.builtin.debug:
    msg:
      - "Total interfaces: {{ interfaces | default([]) | length }}"
      - "Mgmt interfaces: {{ interfaces | default([]) | selectattr('mgmt_only', 'defined') | selectattr('mgmt_only') | list | length }}"
      - "Interface names: {{ interfaces | default([]) | map(attribute='name') | list }}"
      - "Mgmt interface names: {{ interfaces | default([]) | selectattr('mgmt_only', 'defined') | selectattr('mgmt_only') | map(attribute='name') | list }}"
```

**Solution for VLAN Management**:

1. In NetBox, edit the VLAN interface (e.g., `vlan100`)
2. Check the `Management Only` checkbox
3. Ensure IP address is assigned to the VLAN interface
4. Ensure the VLAN exists in NetBox and is assigned to required ports

### Missing IP Address Configuration

**Problem**: Management interface found but no IP configured

**Solutions**:

1. Assign IP address to management interface in NetBox
2. Or use DHCP configuration (manual config needed):
   ```
   interface mgmt
       ip dhcp
   ```

### No Management Interface Found

**Error**: "No management interfaces found"

**Solution**: Ensure NetBox has:

1. Interface with name containing "mgmt"
2. IP address assigned to the interface
3. Device properly configured in NetBox

### Missing Config Context

**Error**: Missing gateway or DNS configuration

**Solution**: Add config context to device or device type:

```json
{
  "mgmt_defaultgateway": "192.168.1.1",
  "mgmt_nameserver": "8.8.8.8"
}
```

### Template Variables Not Found

**Error**: `mgmt_interfaces` variable not defined

**Solution**: Ensure fact gathering is enabled:

```yaml
aoscx_gather_facts: true
```

### Generated Config File Not Found

**Issue**: Config file not created

**Check**:

1. `aoscx_generate_ztp_config: true` is set
2. Output directory exists and is writable
3. Task runs with proper tags: `--tags ztp`

## Best Practices

### 1. Use Version Control

Store generated ZTP configurations in version control:

```bash
git add ztp_configs/
git commit -m "Update ZTP configurations for new switches"
```

### 2. Validate Configurations

Test generated configs before deployment:

```bash
# Syntax check (if available)
aoscx-config-validator sw01-lab_ztp_base.cfg
```

### 3. Automate Deployment
Integrate with ZTP server deployment:

```yaml
- name: Deploy ZTP configs to server
  ansible.builtin.copy:
    src: "{{ item }}"
    dest: "/var/lib/ztp/configs/"
  with_fileglob:
    - "ztp_configs/*.cfg"
  delegate_to: ztp-server
```

### 4. Monitor ZTP Process

Log ZTP deployments for troubleshooting:

```yaml
- name: Log ZTP generation
  ansible.builtin.lineinfile:
    path: /var/log/ztp-generation.log
    line: "{{ ansible_date_time.iso8601 }} - Generated ZTP config for {{ inventory_hostname }}"
  delegate_to: localhost
```

## See Also

- [BASE_CONFIGURATION.md](BASE_CONFIGURATION.md) - Base system configuration
- [NETBOX_INTEGRATION.md](NETBOX_INTEGRATION.md) - NetBox data requirements
- [QUICKSTART.md](QUICKSTART.md) - Quick start guide
- [Aruba ZTP Documentation](https://www.arubanetworks.com/techdocs/AOS-CX/10.08/HTML/ztp/)
