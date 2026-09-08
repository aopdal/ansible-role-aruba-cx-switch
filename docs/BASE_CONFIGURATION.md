# Base Configuration Tasks

This document describes the base system configuration tasks added to the Aruba CX switch role.

## Overview

The role includes base system configuration tasks that are executed early in the configuration process:

1. **Banner Configuration** (`configure_banner.yml`) — tags: `banner`, `base_config`, `system`
2. **Timezone Configuration** (`configure_timezone.yml`) — tags: `timezone`, `base_config`, `system`
3. **NTP Configuration** (`configure_ntp.yml`) — tags: `ntp`, `services`
4. **DNS Configuration** (`configure_dns.yml`) — tags: `dns`, `services`

Banner and timezone have no VRF dependency and are tagged `base_config`/`system`. NTP and DNS may reference a VRF (e.g., `mgmt`) and are tagged `services` instead, so that running `-t base_config` does not attempt VRF-dependent configuration.

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
2. **Banner configuration** ← Base config (`base_config`, `system`)
3. **Timezone configuration** ← Base config (`base_config`, `system`)
4. VRF configuration (`vrfs`, `layer3`, `routing`)
5. **NTP configuration** ← Services (`ntp`, `services`)
6. **DNS configuration** ← Services (`dns`, `services`)
7. VLAN configuration
8. Physical interfaces
9. ... (rest of configuration)

## Features

### Banner Configuration (`tasks/configure_banner.yml`)

- **Login Banner**: Sets MOTD displayed at login
- **Exec Banner**: Optional post-login banner
- **Template Support**: Supports Ansible variables in banner text (e.g., `{{ inventory_hostname }}`)
- **Cleanup**: Removes banner if not configured in NetBox
- **Conditional**: Only runs if `motd` is defined and non-empty

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

## Troubleshooting

### Banner push fails with `internal_vlan_range_base` out-of-bounds error

Symptom, seen on a physical AOS-CX 6200-series switch/VSF stack:

```
GENERIC OPERATION ERROR: value out of bounds: internal_vlan_range_base must be
between 2 and 4094 value is 0
: Code: 400: on Module: UPDATE SYSTEM BANNER
```

This is **not** a bug in `configure_banner.yml` or in this role. The
`arubanetworks.aoscx.aoscx_banner` module's underlying pyaoscx call
(`Device.update_banner()`) does a read-modify-write of the switch's *entire*
`/system` object: it `GET`s the full writable system config, changes only the
banner field, then `PUT`s the whole object back. AOS-CX 6200-series switches
ship with `system internal-vlan-range start 0 end 0` by default — i.e. no
internal VLAN pool configured at all. That `0` round-trips fine on `GET`, but
fails the device's own write-side validation (2-4094) the moment *anything*
triggers a full-object `PUT` of system config — banner just happens to be the
earliest such call in the task order, so it surfaces here first even though
the range isn't what you're trying to change.

Fix on the switch, not in the role:

```
show running-config | include internal-vlan-range
system internal-vlan-range start <start> end <end>
```

e.g. `system internal-vlan-range start 4093 end 4094`. This is a one-time,
platform-specific prerequisite for 6200-series devices, not something this
role currently manages (it isn't NetBox-driven — it's a platform trait, not
a per-device business fact — and changing an in-use range can renumber
internal VLANs, so it's deliberately left as an operator step rather than
pushed automatically on every run).

## Implementation Notes

1. **aoscx_config Module**: NTP and timezone use `aoscx_config` with `network_cli` connection as these are not idempotent but provide broader compatibility

2. **aoscx_banner Module**: Banner uses the dedicated `aoscx_banner` module for proper banner handling

3. **Early Execution**: Base configurations execute early to establish system fundamentals before network configurations

4. **Conditional Logic**: All tasks include proper conditional logic to skip execution if required variables are not defined

5. **Debug Support**: All tasks include debug output when `aoscx_debug` is enabled

This base configuration functionality ensures consistent system settings across all managed Aruba CX switches using NetBox as the source of truth.
