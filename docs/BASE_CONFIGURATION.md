# Base Configuration Tasks

This document describes the base system configuration tasks added to the Aruba CX switch role.

## Overview

The role now includes four base system configuration tasks that are executed early in the configuration process:

1. **Banner Configuration** (`configure_banner.yml`)
2. **Timezone Configuration** (`configure_timezone.yml`)
3. **NTP Configuration** (`configure_ntp.yml`)
4. **DNS Configuration** (`configure_dns.yml`)

These tasks are controlled by flags in `defaults/main.yml` and execute before interface configurations.

## Configuration Variables

### Defaults (can be overridden)
```yaml
# Base configuration flags
aoscx_configure_banner: true
aoscx_configure_ntp: true
aoscx_configure_timezone: true
aoscx_configure_dns: true
```

### Required NetBox config_context Variables

#### Banner Configuration
```yaml
config_context:
  motd: |
    ========================================
    Welcome to {{ inventory_hostname }}
    Managed by Ansible - Unauthorized access prohibited
    ========================================
  # Optional: Executive banner (displayed after login)
  banner_exec: "Post-login banner message"
```

#### Timezone Configuration
```yaml
config_context:
  timezone: "europe/oslo"  # Timezone string
```

#### NTP Configuration
```yaml
config_context:
  ntp_vrf: "mgmt"          # VRF for NTP traffic
  ntp_servers:
    - server: "pool.ntp.org"
      prefer: true           # Optional: mark as preferred
    - server: "time.google.com"
    - server: "backup.ntp.server"
```

## Task Execution Order

The base configuration tasks execute in this order within `tasks/main.yml`:

1. Fact gathering (if enabled)
2. **Banner configuration** ← Base config
3. **Timezone configuration** ← Base config
4. **NTP configuration** ← Base config
5. **DNS configuration** ← Base config
6. VRF configuration
6. VLAN configuration
7. Physical interfaces
8. ... (rest of configuration)

## Features

### Banner Configuration (`tasks/configure_banner.yml`)

- **Login Banner**: Sets MOTD displayed at login
- **Exec Banner**: Optional post-login banner
- **Template Support**: Supports Ansible variables in banner text (e.g., `{{ inventory_hostname }}`)
- **Cleanup**: Removes banner if not configured in NetBox
- **Conditional**: Only runs if `config_context.motd` is defined and non-empty

### Timezone Configuration (`tasks/configure_timezone.yml`)

- **Simple Setup**: Sets timezone using `clock timezone` command
- **Validation**: Only runs if timezone is defined and non-empty
- **Standard Format**: Supports standard timezone strings (e.g., "europe/oslo")

### NTP Configuration (`tasks/configure_ntp.yml`)

- **Multiple Servers**: Supports multiple NTP servers
- **Preferred Server**: Supports marking servers as preferred with `iburst prefer`
- **Regular Servers**: Non-preferred servers use `iburst` only
- **VRF Support**: Routes NTP traffic through specified VRF (typically `mgmt`)
- **Service Enable**: Automatically enables NTP service

## Usage Example

### NetBox config_context
```yaml
{
  "timezone": "europe/oslo",
  "motd": "Welcome to {{ inventory_hostname }}\nManaged by Ansible",
  "ntp_vrf": "mgmt",
  "ntp_servers": [
    {
      "server": "klokke.opdal.net",
      "prefer": true
    },
    {
      "server": "h1-rpi1.opdal.net"
    }
  ]
}
```

### Generated Configuration
```
# Banner
banner "Welcome to z13-cx3.ao-test.net
Managed by Ansible"

# Timezone
clock timezone europe/oslo

# NTP
ntp server klokke.opdal.net iburst prefer
ntp server h1-rpi1.opdal.net iburst
ntp enable
ntp vrf mgmt
```

## Testing

Test files are provided to validate base configuration functionality:

- `tests/test_base_config.yml` - Focused test for base configuration tasks
- `tests/test_real_data.yml` - Includes base config in comprehensive NetBox data test

### Running Tests
```bash
# Test just base configuration
ansible-playbook tests/test_base_config.yml

# Test with full NetBox data (includes base config)
ansible-playbook tests/test_real_data.yml
```

## Tags

Base configuration tasks support these tags for selective execution:

```bash
# Run only base configuration
ansible-playbook site.yml --tags "base_config"

# Run only banner configuration
ansible-playbook site.yml --tags "banner"

# Run only NTP configuration
ansible-playbook site.yml --tags "ntp"

# Run only timezone configuration
ansible-playbook site.yml --tags "timezone"

# Skip base configuration
ansible-playbook site.yml --skip-tags "base_config"
```

## Implementation Notes

1. **aoscx_config Module**: NTP and timezone use `aoscx_config` with `network_cli` connection as these are not idempotent but provide broader compatibility

2. **aoscx_banner Module**: Banner uses the dedicated `aoscx_banner` module for proper banner handling

3. **Early Execution**: Base configurations execute early to establish system fundamentals before network configurations

4. **Conditional Logic**: All tasks include proper conditional logic to skip execution if required variables are not defined

5. **Debug Support**: All tasks include debug output when `aoscx_debug` is enabled

This base configuration functionality ensures consistent system settings across all managed Aruba CX switches using NetBox as the source of truth.
