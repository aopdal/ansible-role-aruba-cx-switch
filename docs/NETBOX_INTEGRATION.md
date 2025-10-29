# NetBox Integration Reference

## Overview

This role relies heavily on **NetBox** as the source of truth for network configuration. This document provides a comprehensive reference for all NetBox integration points, including custom fields, config_context usage, and NetBox plugins.

## Critical Integration Points

### 1. Custom Fields (Per-Device Control)

### 2. Config Context (Configuration Data)

### 3. NetBox Standard Objects (VLANs, Interfaces, L2VPNs)

### 4. NetBox Plugins (Optional: BGP Plugin)

---

## Custom Fields

Custom fields provide **per-device control** over which features are enabled. These are Boolean or Text fields assigned to Device objects.

### Complete Custom Fields Reference

| Custom Field Name | Type | Object | Required | Purpose | Used By |
|-------------------|------|--------|----------|---------|---------|
| `device_bgp` | Boolean | Device | Yes (for BGP) | Enable/disable BGP configuration | `configure_bgp.yml` |
| `device_bgp_routerid` | Text | Device | Yes (for BGP) | BGP Router ID (typically loopback IP) | `configure_bgp.yml` (config_context mode) |
| `device_evpn` | Boolean | Device | Yes (for EVPN) | Enable/disable EVPN configuration and cleanup | `configure_evpn.yml`, `cleanup_evpn.yml` |
| `device_vxlan` | Boolean | Device | Yes (for VXLAN) | Enable/disable VXLAN configuration and cleanup | `configure_vxlan.yml`, `cleanup_vxlan.yml` |
| `device_vsx` | Boolean | Device | Yes (for VSX) | Enable/disable VSX configuration | `configure_vsx.yml` |

### Creating Custom Fields in NetBox

#### 1. device_bgp (Boolean)

```
Name: device_bgp
Type: Boolean
Object Type: dcim > device
Label: Enable BGP
Description: Enable BGP configuration on this device
Default: false
Required: No
```

**NetBox UI:**

```
Customization → Custom Fields → Add
├─ Name: device_bgp
├─ Type: Boolean
├─ Content Types: dcim | device
├─ Label: Enable BGP
└─ Default: ☐ (unchecked)
```

#### 2. device_bgp_routerid (Text)

```
Name: device_bgp_routerid
Type: Text
Object Type: dcim > device
Label: BGP Router ID
Description: BGP Router ID (typically loopback IP address)
Required: No
Validation Regex: ^(\d{1,3}\.){3}\d{1,3}$ (optional)
```

**NetBox UI:**

```
Customization → Custom Fields → Add
├─ Name: device_bgp_routerid
├─ Type: Text
├─ Content Types: dcim | device
├─ Label: BGP Router ID
└─ Validation: ^(\d{1,3}\.){3}\d{1,3}$
```

**Note:** Only required when using `config_context` for BGP. Not needed if using netbox-bgp plugin.

#### 3. device_evpn (Boolean)

```
Name: device_evpn
Type: Boolean
Object Type: dcim > device
Label: Enable EVPN
Description: Enable EVPN configuration and cleanup on this device
Default: false
Required: No
```

#### 4. device_vxlan (Boolean)

```
Name: device_vxlan
Type: Boolean
Object Type: dcim > device
Label: Enable VXLAN
Description: Enable VXLAN configuration and cleanup on this device
Default: false
Required: No
```

#### 5. device_vsx_enabled (Boolean)

```
Name: device_vsx_enabled
Type: Boolean
Object Type: dcim > device
Label: Enable VSX
Description: Enable VSX (Virtual Switching Extension) configuration on this device
Default: false
Required: No
```

**NetBox UI:**

```
Customization → Custom Fields → Add
├─ Name: device_vsx_enabled
├─ Type: Boolean
├─ Content Types: dcim | device
├─ Label: Enable VSX
└─ Default: ☐ (unchecked)
```

### Custom Field Usage Patterns

#### Per-Device Control

```yaml
# Leaf switches (full EVPN/VXLAN fabric participation)
custom_fields:
  device_bgp: true
  device_bgp_routerid: "10.255.255.11"
  device_evpn: true
  device_vxlan: true

# Spine switches (BGP route reflectors, no VXLAN)
custom_fields:
  device_bgp: true
  device_bgp_routerid: "10.255.255.1"
  device_evpn: false
  device_vxlan: false

# Access switches (no BGP/EVPN/VXLAN)
custom_fields:
  device_bgp: false
  device_evpn: false
  device_vxlan: false
```

#### Ansible Task Conditions

Custom fields control task execution:

```yaml
# BGP configuration
when:
  - aoscx_configure_bgp | bool
  - custom_fields.device_bgp | default(false) | bool
  - "'bgp' in ansible_run_tags or 'routing' in ansible_run_tags or 'all' in ansible_run_tags"

# EVPN configuration
when:
  - aoscx_configure_evpn | bool
  - custom_fields.device_evpn | default(false) | bool

# VXLAN configuration
when:
  - aoscx_configure_vxlan | bool
  - custom_fields.device_vxlan | default(false) | bool

# EVPN cleanup (idempotent mode)
when:
  - aoscx_configure_evpn | default(false) | bool
  - custom_fields.device_evpn | default(false) | bool
  - aoscx_idempotent_mode | bool
```

---

## Config Context

Config context provides **configuration data** for features. This is JSON data attached to devices/sites/regions.

### Current Config Context Usage

| Feature | Config Context Key | Type | Purpose | Status |
|---------|-------------------|------|---------|--------|
| **Base System** | `config_context.motd` | String | Message of the Day banner | ✅ Active |
| | `config_context.timezone` | String | System timezone | ✅ Active |
| | `config_context.ntp.servers` | List | NTP server IPs | ✅ Active |
| | `config_context.dns.domain` | String | DNS domain name | ✅ Active |
| | `config_context.dns.servers` | List | DNS server IPs | ✅ Active |
| **VSX** | `config_context.vsx_system_mac` | String | VSX system MAC address | ✅ Active |
| | `config_context.vsx_role` | String | VSX role (primary or secondary) | ✅ Active |
| | `config_context.vsx_isl_ports` | List | Inter-Switch Link ports | ✅ Active |
| | `config_context.vsx_keepalive_peer` | String | VSX peer keepalive IP address | ✅ Active |
| | `config_context.vsx_keepalive_src` | String | Source IP for keepalive | ✅ Active |
| | `config_context.vsx_keepalive_vrf` | String | VRF for keepalive (default: mgmt) | ✅ Active |
| **BGP (Fallback)** | `config_context.bgp_as` | Integer | BGP AS Number | ⚠️ Hybrid (fallback) |
| | `config_context.bgp_peers` | List | BGP EVPN neighbors | ⚠️ Hybrid (fallback) |
| | `config_context.bgp_ipv4_peers` | List | BGP IPv4 unicast peers | ⚠️ Hybrid (fallback) |
| | `config_context.bgp_vrfs` | List | BGP VRF configurations | ⚠️ Hybrid (fallback) |
| | `config_context.bgp_rr_clients` | List | Route reflector clients | ⚠️ Hybrid (fallback) |
| | `config_context.bgp_additional_config` | List | Additional BGP commands | ⚠️ Hybrid (fallback) |

### Base System Config Context Examples

#### Banner (MOTD)

```json
{
  "motd": "WARNING: Authorized access only!\n\nThis is a production network device."
}
```

Ansible access: `config_context.motd`

#### Timezone

```json
{
  "timezone": "Europe/Oslo"
}
```

Ansible access: `config_context.timezone`

#### NTP Servers

```json
{
  "ntp": {
    "servers": [
      "10.0.0.1",
      "10.0.0.2"
    ]
  }
}
```

Ansible access: `config_context.ntp.servers`

#### DNS Configuration

```json
{
  "dns": {
    "domain": "example.com",
    "servers": [
      "10.0.0.53",
      "10.0.0.54"
    ],
    "hosts": {
      "router1": "10.0.1.1",
      "router2": "10.0.1.2"
    }
  }
}
```

Ansible access:
- `config_context.dns.domain`
- `config_context.dns.servers`
- `config_context.dns.hosts`

### BGP Config Context (Fallback Mode)

**Important:** BGP configuration supports **two modes**:

1. **netbox-bgp plugin** (preferred) - Structured data via plugin API
2. **config_context** (fallback) - JSON data for migration period

#### BGP AS Number

```json
{
  "bgp_as": 65000
}
```

#### BGP EVPN Neighbors

```json
{
  "bgp_peers": [
    {
      "peer": "10.255.255.1",
      "remote_as": 65000,
      "description": "spine1-evpn"
    },
    {
      "peer": "10.255.255.2",
      "remote_as": 65000,
      "description": "spine2-evpn"
    }
  ]
}
```

#### BGP IPv4 Unicast Peers

```json
{
  "bgp_ipv4_peers": [
    {
      "peer": "192.168.1.1",
      "remote_as": 65001,
      "description": "external-peer"
    }
  ]
}
```

#### BGP VRFs

```json
{
  "bgp_vrfs": [
    {
      "name": "customer1",
      "rd": "65000:100",
      "route_targets": {
        "import": ["65000:100"],
        "export": ["65000:100"]
      }
    }
  ]
}
```

#### Complete BGP Config Context Example

```json
{
  "bgp_as": 65000,
  "bgp_peers": [
    {
      "peer": "10.255.255.1",
      "remote_as": 65000,
      "description": "spine1-evpn",
      "update_source": "loopback0"
    },
    {
      "peer": "10.255.255.2",
      "remote_as": 65000,
      "description": "spine2-evpn",
      "update_source": "loopback0"
    }
  ],
  "bgp_rr_clients": [
    "10.255.255.11",
    "10.255.255.12"
  ],
  "bgp_additional_config": [
    "maximum-paths 4",
    "distance bgp 20 200 200"
  ]
}
```

### Config Context Hierarchy

NetBox config_context uses **hierarchical inheritance**:

```
Global Config Context (lowest priority)
  ↓
Region Config Context
  ↓
Site Config Context
  ↓
Device Role Config Context
  ↓
Platform Config Context
  ↓
Tenant Config Context
  ↓
Device Config Context (highest priority)
```

**Best Practice:** Define common settings at site/region level, override per-device as needed.

#### Example Hierarchy

**Site Level (site: datacenter1):**

```json
{
  "ntp": {
    "servers": ["10.0.0.1", "10.0.0.2"]
  },
  "dns": {
    "domain": "dc1.example.com",
    "servers": ["10.0.0.53"]
  }
}
```

**Device Level (leaf1):**

```json
{
  "bgp_as": 65000,
  "bgp_peers": [
    {"peer": "10.255.255.1", "remote_as": 65000}
  ]
}
```

**Merged Result (what Ansible sees):**

```json
{
  "ntp": {"servers": ["10.0.0.1", "10.0.0.2"]},
  "dns": {
    "domain": "dc1.example.com",
    "servers": ["10.0.0.53"]
  },
  "bgp_as": 65000,
  "bgp_peers": [
    {"peer": "10.255.255.1", "remote_as": 65000}
  ]
}
```

---

## NetBox Standard Objects

The role uses standard NetBox objects for configuration.

### VLANs

**Source:** NetBox → VLANs (filtered by site)

**Used by:** `configure_vlans.yml`, `cleanup_vlans.yml`

**Required fields:**

- `vid` - VLAN ID (1-4094)
- `name` - VLAN name
- `site` - Site assignment

**Optional fields:**

- `description` - VLAN description
- `l2vpn_termination` - Link to L2VPN (for EVPN/VXLAN)

### Interfaces

**Source:** NetBox → Interfaces (per device)

**Used by:** All interface configuration tasks

**Required fields:**

- `name` - Interface name
- `type` - Interface type
- `enabled` - Admin state

**Key fields for L2:**

- `mode` - Access or Tagged
- `untagged_vlan` - Access VLAN
- `tagged_vlans` - Trunk VLANs

**Key fields for L3:**

- `ip_addresses` - Assigned IP addresses

**Key fields for LAG:**

- `lag` - Parent LAG interface

### L2VPNs and L2VPN Terminations

**Source:** NetBox → IPAM → L2VPNs

**Used by:** `configure_evpn.yml`, `configure_vxlan.yml`

**Purpose:** Map VLANs to VNIs for EVPN/VXLAN fabric

#### L2VPN Object

```
Name: VLAN-100-L2VPN
Identifier: 10100  ← This is the VNI
Type: VXLAN
```

#### L2VPN Termination

```
L2VPN: VLAN-100-L2VPN
Assigned Object Type: IPAM | VLAN
Assigned Object: VLAN 100 (site: datacenter1)
```

**Ansible access:**

```yaml
vlan.l2vpn_termination.l2vpn.identifier  # VNI (10100)
vlan.l2vpn_termination.id  # Termination exists check
```

---

## NetBox Plugins

### netbox-bgp Plugin (Optional)

**Purpose:** Structured BGP data models (preferred over config_context)

**Status:** Hybrid mode - plugin preferred, config_context fallback

**Plugin URL:** https://github.com/netbox-community/netbox-bgp

#### BGP Plugin Objects

| Object | Purpose | Example |
|--------|---------|---------|
| **BGP Session** | Defines peering relationship | leaf1 ↔ spine1 |
| **Community** | BGP community values | 65000:100 |
| **Routing Policy** | Route maps, prefix lists | EVPN-IMPORT |
| **Peer Group** | Template for multiple peers | EVPN-PEERS |

#### API Endpoints Used

```bash
# Get BGP sessions for a device
GET /api/plugins/bgp/session/?device=leaf1&status=active

# Get BGP sessions by device ID
GET /api/plugins/bgp/session/?device_id=123&status=active
```

#### Role's Hybrid Approach

```yaml
# 1. Try netbox-bgp plugin first
- name: Query netbox-bgp plugin
  ansible.builtin.uri:
    url: "{{ lookup('env', 'NETBOX_API') }}/api/plugins/bgp/session/"
    headers:
      Authorization: "Token {{ lookup('env', 'NETBOX_TOKEN') }}"
  register: bgp_sessions_api
  delegate_to: localhost
  run_once: true

# 2. Use plugin data if available
- name: Configure BGP from plugin
  when:
    - bgp_sessions_api.status == 200
    - device_bgp_sessions | length > 0
  # ... configure from plugin data

# 3. Fall back to config_context if plugin unavailable
- name: Configure BGP from config_context
  when:
    - bgp_sessions_api.status == 404 or device_bgp_sessions | length == 0
    - config_context.bgp_as is defined
  # ... configure from config_context
```

**See:** `docs/BGP_HYBRID_CONFIGURATION.md` for complete details.

---

## Integration Verification

### Checking Custom Fields in NetBox

**UI:** Device → Custom Fields tab

**API:**

```bash
curl -H "Authorization: Token $NETBOX_TOKEN" \
  "$NETBOX_API/api/dcim/devices/123/" | jq '.custom_fields'
```

**Expected output:**

```json
{
  "device_bgp": true,
  "device_bgp_routerid": "10.255.255.11",
  "device_evpn": true,
  "device_vxlan": true
}
```

### Checking Config Context in NetBox

**UI:** Device → Config Context tab

**API:**

```bash
curl -H "Authorization: Token $NETBOX_TOKEN" \
  "$NETBOX_API/api/dcim/devices/123/?include=config_context" | jq '.config_context'
```

**Expected output:**

```json
{
  "motd": "Production device",
  "ntp": {
    "servers": ["10.0.0.1"]
  },
  "bgp_as": 65000,
  "bgp_peers": [...]
}
```

### Checking in Ansible Inventory

```yaml
# Run ansible-inventory to see what Ansible receives
ansible-inventory -i netbox_inventory.yml --host leaf1 --yaml

# Check custom fields
ansible-inventory -i netbox_inventory.yml --host leaf1 --yaml | grep -A5 custom_fields

# Check config_context
ansible-inventory -i netbox_inventory.yml --host leaf1 --yaml | grep -A20 config_context
```

---

## Common Integration Patterns

### Pattern 1: Per-Device Feature Control

```yaml
# Enable BGP on leaf switches only
custom_fields:
  device_bgp: true

# Disable on access switches
custom_fields:
  device_bgp: false
```

### Pattern 2: Site-Wide Configuration

```json
// Site config_context for all devices in site
{
  "ntp": {
    "servers": ["10.0.0.1", "10.0.0.2"]
  },
  "dns": {
    "domain": "site1.example.com",
    "servers": ["10.0.0.53"]
  }
}
```

### Pattern 3: Role-Based Configuration

```json
// Device Role: spine (config_context)
{
  "bgp_rr_clients": [
    "10.255.255.11",
    "10.255.255.12",
    "10.255.255.13"
  ]
}

// Device Role: leaf (config_context)
{
  "bgp_peers": [
    {"peer": "10.255.255.1", "remote_as": 65000},
    {"peer": "10.255.255.2", "remote_as": 65000}
  ]
}
```

---

## Migration Path: config_context → Plugins

### Current State

- ✅ Base system: config_context (stable)
- ⚠️ BGP: Hybrid (plugin preferred, config_context fallback)
- ✅ EVPN/VXLAN: Native NetBox objects (L2VPN)

### Future State (Recommended)

- ✅ Base system: config_context (keep as-is)
- ✅ BGP: netbox-bgp plugin only
- ✅ EVPN/VXLAN: Native NetBox objects (current)

### Migration Steps

1. **Install netbox-bgp plugin** in NetBox
2. **Create BGP objects** (sessions, communities, routing policies)
3. **Test hybrid mode** (role automatically uses plugin)
4. **Verify BGP config** matches expectations
5. **Remove config_context BGP data** (keep other data)
6. **Document migration** for team

**See:** `docs/BGP_MIGRATION_GUIDE.md` for step-by-step instructions.

---

## Troubleshooting

### Custom Fields Not Working

**Symptom:** Task skipped even though custom field is set

**Check:**

```bash
# Verify custom field exists
ansible-inventory -i netbox_inventory.yml --host DEVICE --yaml | grep device_bgp

# Check task condition
ansible-playbook playbook.yml --check -vvv | grep "Conditional result"
```

**Common causes:**

- Custom field not created in NetBox
- Custom field value is null/undefined
- Role variable disabled (`aoscx_configure_bgp: false`)

### Config Context Not Applied

**Symptom:** Configuration not applied, config_context empty

**Check:**

```bash
# View merged config_context
curl -H "Authorization: Token $TOKEN" \
  "$NETBOX_API/api/dcim/devices/123/?include=config_context" | jq '.config_context'
```

**Common causes:**

- No config_context defined at any level
- JSON syntax error in config_context
- Config context not assigned to correct object type

### BGP Plugin Not Working

**Symptom:** Falls back to config_context when it shouldn't

**Check:**

```bash
# Test plugin API endpoint
curl -H "Authorization: Token $TOKEN" \
  "$NETBOX_API/api/plugins/bgp/session/"
```

**Common causes:**

- Plugin not installed
- No BGP sessions created
- BGP sessions not in "active" or "planned" status
- BGP sessions not assigned to device

---

## Summary

### Custom Fields (5 total)

| Field | Type | Purpose |
|-------|------|---------|
| `device_bgp` | Boolean | Enable BGP |
| `device_bgp_routerid` | Text | BGP Router ID (config_context mode) |
| `device_evpn` | Boolean | Enable EVPN |
| `device_vxlan` | Boolean | Enable VXLAN |
| `device_vsx_enabled` | Boolean | Enable VSX |

### Config Context Keys

**Base System (Stable):**

- `motd`, `timezone`, `ntp.servers`, `dns.domain`, `dns.servers`

**VSX (Stable):**

- `vsx_system_mac`, `vsx_role`, `vsx_isl_ports`, `vsx_keepalive_peer`, `vsx_keepalive_src`, `vsx_keepalive_vrf`

**BGP (Hybrid/Fallback):**

- `bgp_as`, `bgp_peers`, `bgp_ipv4_peers`, `bgp_vrfs`, `bgp_rr_clients`

### NetBox Objects

- **VLANs** - VLAN configuration and cleanup
- **Interfaces** - All interface configuration
- **L2VPNs** - EVPN/VXLAN VNI mapping
- **BGP Sessions** (plugin) - BGP configuration

### Best Practices

- ✅ **Use custom fields** for per-device enable/disable control
- ✅ **Use config_context** for configuration data
- ✅ **Use site/region level** config_context for common settings
- ✅ **Use device level** config_context for device-specific overrides
- ✅ **Use netbox-bgp plugin** for BGP when possible
- ✅ **Keep config_context** for base system configuration
- ✅ **Use L2VPN objects** for EVPN/VXLAN VNI mapping

---

## Related Documentation

- [BASE_CONFIGURATION.md](BASE_CONFIGURATION.md) - Base system configuration details
- [BGP_HYBRID_CONFIGURATION.md](BGP_HYBRID_CONFIGURATION.md) - BGP hybrid mode
- [BGP_MIGRATION_GUIDE.md](BGP_MIGRATION_GUIDE.md) - Migrating to netbox-bgp plugin
- [EVPN_VXLAN_CONFIGURATION.md](EVPN_VXLAN_CONFIGURATION.md) - EVPN/VXLAN with L2VPNs
- [NETBOX_BGP_PLUGIN.md](NETBOX_BGP_PLUGIN.md) - netbox-bgp plugin details
