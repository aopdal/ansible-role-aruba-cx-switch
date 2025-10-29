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

### Required NetBox Configuration

The ZTP template requires management interfaces to be configured in NetBox:

1. **Management Interface**: Create interface with name containing "mgmt"

   ```
   Name: mgmt
   Type: 1000BASE-T (1GE)
   ```

2. **IP Address**: Assign IP to management interface

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
- `config_context.mgmt_defaultgateway` - Default gateway IP
- `config_context.mgmt_nameserver` - Primary DNS server
- `config_context.dns_servers` - List of DNS servers

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
