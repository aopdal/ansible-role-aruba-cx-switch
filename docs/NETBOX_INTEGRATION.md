# NetBox Integration Reference

## Overview

This role relies heavily on **NetBox** as the source of truth for network configuration. This document provides a comprehensive reference for all NetBox integration points, including custom fields, config_context usage, and NetBox plugins.

## Critical Integration Points

### 1. Custom Fields (Per-Device Control)

### 2. Config Context (Configuration Data)

### 3. NetBox Standard Objects (VLANs, Interfaces, L2VPNs)

### 4. NetBox Plugins (netbox-bgp Plugin — required for BGP)

---

## Custom Fields

Custom fields provide **per-device control** over which features are enabled. These are Boolean or Text fields assigned to Device objects.

### Complete Custom Fields Reference

| Custom Field Name | Type | Object | Required | Purpose | Used By |
|-------------------|------|--------|----------|---------|---------|
| `device_anycast_gateway` | Boolean | Device | No | Enable/disable Anycast Gateway global settings | `configure_anycast_gateway.yml` |
| `device_bgp` | Boolean | Device | Yes (for BGP) | Enable/disable inclusion of BGP configuration tasks | `main.yml` (gates whether `configure_bgp.yml` runs at all) |
| `device_evpn` | Boolean | Device | Yes (for EVPN) | Enable/disable EVPN configuration and cleanup | `configure_evpn.yml`, `cleanup_evpn.yml` |
| `device_vxlan` | Boolean | Device | Yes (for VXLAN) | Enable/disable VXLAN configuration and cleanup | `configure_vxlan.yml`, `cleanup_vxlan.yml` |
| `device_vsx` | Boolean | Device | Yes (for VSX) | Enable/disable VSX configuration | `configure_vsx.yml` |
| `vlan_ip_igmp_snooping` | Boolean | VLAN | No | Enable/disable IGMP snooping per VLAN | `configure_vlans.yml` |
| `vlan_voice_vlan` | Boolean | VLAN | No | Enable/disable voice VLAN per VLAN | `configure_vlans.yml` |
| `if_stp_bpdu_filter` | Boolean | Interface | No | Enable/disable BPDU filter on an L2 interface | `configure_stp.yml` |
| `if_stp_bpdu_guard` | Boolean | Interface | No | Enable/disable BPDU guard on an L2 interface | `configure_stp.yml` |
| `if_stp_edge_port` | Boolean | Interface | No | Set port-type admin-edge (PortFast equivalent) | `configure_stp.yml` |
| `if_stp_root_guard` | Boolean | Interface | No | Enable/disable Root Guard on an L2 interface | `configure_stp.yml` |
| `if_ip_helper` | Boolean | Interface | No | Enable DHCP relay (`ip helper-address`) on an L3 interface | `configure_l3_interfaces.yml` |

### Creating Custom Fields in NetBox

#### 1. device_anycast_gateway (Boolean)

```
Name: device_anycast_gateway
Type: Boolean
Object Type: dcim > device
Label: Enable Anycast Gateway
Description: Enable Anycast Gateway global settings (no ip icmp redirect)
Default: false
Required: No
```

**NetBox UI:**

```
Customization → Custom Fields → Add
├─ Name: device_anycast_gateway
├─ Type: Boolean
├─ Content Types: dcim | device
├─ Label: Enable Anycast Gateway
└─ Default: ☐ (unchecked)
```

**Purpose:** Enables global device configuration required for Anycast Gateway functionality (disables ICMP redirect). This is a base system setting that persists and may be required by other features even if not actively using Anycast Gateway.

#### 2. device_bgp (Boolean)

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

**Purpose:** Gates whether `tasks/main.yml` includes `configure_bgp.yml` at all
(`when: aoscx_configure_bgp | bool` and `custom_fields.device_bgp | default(false) | bool`).
There is no companion "router ID" custom field — all BGP session data (ASN, peers,
local/remote addresses) comes exclusively from the **netbox-bgp plugin**. The router ID is
derived at runtime from the `local_address` of the device's first BGP plugin session
(`device_bgp_sessions[0].local_address`) — see
[BGP_CONFIGURATION.md](BGP_CONFIGURATION.md).

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

#### 5. device_vsx (Boolean)

```
Name: device_vsx
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
├─ Name: device_vsx
├─ Type: Boolean
├─ Content Types: dcim | device
├─ Label: Enable VSX
└─ Default: ☐ (unchecked)
```

#### 6. vlan_ip_igmp_snooping (Boolean)

```
Name: vlan_ip_igmp_snooping
Type: Boolean
Object Type: ipam > vlan
Label: Enable IGMP Snooping
Description: Enable IGMP snooping on this VLAN
Default: false
Required: No
```

**NetBox UI:**

```
Customization → Custom Fields → Add
├─ Name: vlan_ip_igmp_snooping
├─ Type: Boolean
├─ Content Types: ipam | vlan
├─ Label: Enable IGMP Snooping
└─ Default: ☐ (unchecked)
```

**Purpose:** Controls IGMP snooping configuration per VLAN. When enabled, the VLAN will listen for IGMP membership reports and only forward multicast traffic to ports that have requested it. This reduces unnecessary multicast flooding and improves network efficiency.

**Behavior:**
- Only applies to VLANs that are in use on interfaces
- Intelligent state comparison (when `aoscx_gather_facts_rest_api: true`)
- Only updates VLANs where IGMP setting differs from current device state
- Skips VLANs not assigned to any interface (no unnecessary configuration)

**Example:**

```yaml
# VLAN 100 - Server VLAN with multicast traffic
custom_fields:
  vlan_ip_igmp_snooping: true

# VLAN 200 - Management VLAN without multicast
custom_fields:
  vlan_ip_igmp_snooping: false  # or omit field
```

#### 7. vlan_voice_vlan (Boolean)

```
Name: vlan_voice_vlan
Type: Boolean
Object Type: ipam > vlan
Label: Enable Voice VLAN
Description: Configure this VLAN as a voice VLAN
Default: false
Required: No
```

**NetBox UI:**

```
Customization → Custom Fields → Add
├─ Name: vlan_voice_vlan
├─ Type: Boolean
├─ Content Types: ipam | vlan
├─ Label: Enable Voice VLAN
└─ Default: ☐ (unchecked)
```

**Purpose:** Controls voice VLAN configuration per VLAN (AOS-CX `voice` command). This tags the VLAN for voice use so IP phones are properly identified, e.g. via LLDP-MED.

**Behavior:**
- Only applies to VLANs that are in use on interfaces
- Intelligent state comparison (when `aoscx_gather_facts_rest_api: true`)
- Only updates VLANs where the voice setting differs from current device state
- Skips VLANs not assigned to any interface (no unnecessary configuration)

**Example:**

```yaml
# VLAN 150 - Voice VLAN for IP phones
custom_fields:
  vlan_voice_vlan: true

# VLAN 200 - Management VLAN, not voice
custom_fields:
  vlan_voice_vlan: false  # or omit field
```

#### 8. if_stp_bpdu_filter (Boolean — Interface)

```
Name: if_stp_bpdu_filter
Type: Boolean
Object Type: dcim > interface
Label: STP BPDU Filter
Description: Enable BPDU filter on this L2 interface (spanning-tree bpdu-filter)
Default: null (not set — leave device as-is)
Required: No
```

**NetBox UI:**

```
Customization → Custom Fields → Add
├─ Name: if_stp_bpdu_filter
├─ Type: Boolean
├─ Content Types: dcim | interface
├─ Label: STP BPDU Filter
└─ Default: — (null, unset)
```

**Purpose:** When `true`, configures `spanning-tree bpdu-filter` on the interface — BPDUs are neither sent nor received. When `false`, configures `no spanning-tree bpdu-filter`. When null (unset), the device setting is left unchanged.

#### 9. if_stp_bpdu_guard (Boolean — Interface)

```
Name: if_stp_bpdu_guard
Type: Boolean
Object Type: dcim > interface
Label: STP BPDU Guard
Description: Enable BPDU guard on this L2 interface (spanning-tree bpdu-guard)
Default: null (not set — leave device as-is)
Required: No
```

**NetBox UI:**

```
Customization → Custom Fields → Add
├─ Name: if_stp_bpdu_guard
├─ Type: Boolean
├─ Content Types: dcim | interface
├─ Label: STP BPDU Guard
└─ Default: — (null, unset)
```

**Purpose:** When `true`, configures `spanning-tree bpdu-guard` on the interface — if a BPDU is received the port is error-disabled. Recommended on access ports facing end-hosts. When `false`, configures `no spanning-tree bpdu-guard`.

#### 10. if_stp_edge_port (Boolean — Interface)

```
Name: if_stp_edge_port
Type: Boolean
Object Type: dcim > interface
Label: STP Edge Port (PortFast)
Description: Set port-type admin-edge on this L2 interface (spanning-tree port-type admin-edge)
Default: null (not set — leave device as-is)
Required: No
```

**NetBox UI:**

```
Customization → Custom Fields → Add
├─ Name: if_stp_edge_port
├─ Type: Boolean
├─ Content Types: dcim | interface
├─ Label: STP Edge Port (PortFast)
└─ Default: — (null, unset)
```

**Purpose:** When `true`, configures `spanning-tree port-type admin-edge` — the port transitions directly to forwarding without going through listening/learning states (equivalent to PortFast). Recommended on access ports facing end-hosts. When `false`, configures `no spanning-tree port-type admin-edge`.

#### 11. if_stp_root_guard (Boolean — Interface)

```
Name: if_stp_root_guard
Type: Boolean
Object Type: dcim > interface
Label: STP Root Guard
Description: Enable Root Guard on this L2 interface (spanning-tree root-guard)
Default: null (not set — leave device as-is)
Required: No
```

**NetBox UI:**

```
Customization → Custom Fields → Add
├─ Name: if_stp_root_guard
├─ Type: Boolean
├─ Content Types: dcim | interface
├─ Label: STP Root Guard
└─ Default: — (null, unset)
```

**Purpose:** When `true`, configures `spanning-tree root-guard` on the interface — prevents the port from becoming a root port, protecting the STP topology. Use on ports facing downstream switches that should never become the root bridge path. When `false`, configures `no spanning-tree root-guard`.

**STP interface custom field semantics summary:**

| Value | Behavior |
|-------|----------|
| `true` | Apply the enable command (e.g. `spanning-tree bpdu-guard`) |
| `false` | Apply the disable command (e.g. `no spanning-tree bpdu-guard`) |
| null / not set | Leave device setting unchanged — no command pushed |

Change detection uses `aoscx_enhanced_interface_facts[name].stp_config` (requires `aoscx_gather_facts_rest_api: true`). Only interfaces where at least one value differs are touched.

**Example — access port facing end-hosts:**

```yaml
# NetBox interface custom fields
custom_fields:
  if_stp_bpdu_guard: true
  if_stp_edge_port: true
  if_stp_bpdu_filter: null   # leave as-is
  if_stp_root_guard: null    # leave as-is
```

Produces:

```
interface 1/1/5
    spanning-tree bpdu-guard
    spanning-tree port-type admin-edge
```

**Example — uplink port facing another switch:**

```yaml
custom_fields:
  if_stp_root_guard: true
  if_stp_bpdu_guard: false
```

Produces:

```
interface 1/1/49
    spanning-tree root-guard
    no spanning-tree bpdu-guard
```

#### 12. if_ip_helper (Boolean — Interface)

```
Name: if_ip_helper
Type: Boolean
Object Type: dcim > interface
Label: IP Helper Address
Description: Enable DHCP relay (ip helper-address) on this L3 interface
Default: false
Required: No
```

**NetBox UI:**

```
Customization → Custom Fields → Add
├─ Name: if_ip_helper
├─ Type: Boolean
├─ Content Types: dcim | interface
├─ Label: IP Helper Address
└─ Default: — (null / false)
```

**Purpose:** When `true`, the role configures `ip helper-address` lines on the interface for each relay server defined in the `ip_helper_addresses` config context key. The servers are looked up by the interface's VRF name. When `false` (or unset), any relay servers already configured on the device are removed.

Requires `aoscx_gather_facts_rest_api: true` for idempotent comparison (otherwise the role conservatively pushes on every run). The `ip_helper_addresses` config context key must also be defined — see [Config Context: ip_helper_addresses](#ip_helper_addresses) below.

**Example — SVI that should relay DHCP to a central server:**

```yaml
# NetBox interface custom fields
custom_fields:
  if_ip_helper: true
```

Combined with the `ip_helper_addresses` config context (VRF `lab-blue`), this produces:

```
interface vlan101
    vrf attach lab-blue
    ip address 172.27.4.1/27
    ip helper-address 172.16.3.10
    ip helper-address 172.16.3.11
    l3-counters
```

### Custom Field Usage Patterns

#### Per-Device Control

```yaml
# Leaf switches (full EVPN/VXLAN fabric participation)
custom_fields:
  device_anycast_gateway: true
  device_bgp: true
  device_evpn: true
  device_vxlan: true

# Spine switches (BGP route reflectors, no VXLAN)
custom_fields:
  device_anycast_gateway: false
  device_bgp: true
  device_evpn: false
  device_vxlan: false

# Access switches (no BGP/EVPN/VXLAN, but using Anycast Gateway)
custom_fields:
  device_anycast_gateway: true
  device_bgp: false
  device_evpn: false
  device_vxlan: false
```

#### Ansible Task Conditions

Custom fields control task execution:

```yaml
# Anycast Gateway configuration
when:
  - custom_fields.device_anycast_gateway | default(false) | bool

# BGP configuration (gates whether configure_bgp.yml is included at all;
# tasks inside configure_bgp.yml additionally require the netbox-bgp plugin
# to be reachable and to return sessions for this device)
when:
  - aoscx_configure_bgp | bool
  - custom_fields.device_bgp | default(false) | bool

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
| **Base System** | `motd` | String | Message of the Day banner | ✅ Active |
| | `timezone` | String | System timezone | ✅ Active |
| | `ntp.servers` | List | NTP server IPs | ✅ Active |
| | `dns_domain_name` | String | Primary DNS domain name | ✅ Active |
| | `dns_mgmt_nameservers` | Dict | Management-VRF nameservers (descriptive keys) | ✅ Active |
| | `dns_name_servers` | Dict of dicts | DNS nameservers per VRF (VRF name → numeric-key dict of IPs) | ✅ Active |
| | `dns_domain_list` | Dict | Additional DNS search domains (numeric keys) | ✅ Active |
| | `dns_host_v4_address_mapping` | Dict | Static host-to-IPv4 mappings | ✅ Active |
| | `dns_vrf` | String | VRF for domain/host/mgmt DNS settings | ✅ Active |
| **BGP (supplement only)** | `bgp_redistribute` | Dict (per VRF) | Redistribute connected/static/ospf/etc. into BGP — supplements netbox-bgp plugin sessions, does not define peers/ASN | ✅ Active |
| | `bgp_neighbor_options` | Dict (per neighbor IP) | Arbitrary per-neighbor CLI options (e.g. `fall-over bfd`) — supplements netbox-bgp plugin sessions | ✅ Active |
| **VSX** | `vsx_system_mac` | String | VSX system MAC address | ✅ Active |
| | `vsx_role` | String | VSX role (primary or secondary) | ✅ Active |
| | `vsx_isl_ports` | List | Inter-Switch Link ports | ✅ Active |
| | `vsx_keepalive_peer` | String | VSX peer keepalive IP address | ✅ Active |
| | `vsx_keepalive_src` | String | Source IP for keepalive | ✅ Active |
| | `vsx_keepalive_vrf` | String | VRF for keepalive (default: mgmt) | ✅ Active |
| **STP (MSTP)** | `mstp_config_name` | String | MSTP region name (`spanning-tree config-name`) | ✅ Active |
| | `mstp_config_revision` | Integer | MSTP revision number, default 0 (`spanning-tree config-revision`) | ✅ Active |
| | `mstp_priority` | Integer | Bridge priority, e.g. 4096 (`spanning-tree priority`) — optional | ✅ Active |
| **Port-Access** | `port_access.roles[*].vlan_trunk_native` | Int / String | Native VLAN for a port-access role. VLAN IDs are auto-added to the device's VLAN create list. | ✅ Active |
| | `port_access.roles[*].vlan_trunk_allowed` | Int / String | Trunk-allowed VLANs. Supports range/list syntax: `11`, `"11,13"`, `"11-13"`, `"11,13,15-20"`. Expanded VIDs are auto-added to the device's VLAN create list and protected from idempotent deletion. | ✅ Active |
| | `port_access.roles[*].vlan_access` | Int / String | Access VLAN for a port-access role (alternative shorthand). Same VLAN auto-creation behaviour. | ✅ Active |
| **Static Routes** | `static_routes.<vrf>[*]` | List (per VRF) | Static routes (forward/blackhole/reject) — see [STATIC_ROUTES_CONFIGURATION.md](STATIC_ROUTES_CONFIGURATION.md) | ✅ Active |

### Base System Config Context Examples

#### Banner (MOTD)

```json
{
  "motd": "WARNING: Authorized access only!\n\nThis is a production network device."
}
```

Ansible access: `motd`

#### Timezone

```json
{
  "timezone": "Europe/Oslo"
}
```

Ansible access: `timezone`

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

Ansible access: `ntp.servers`

#### DNS Configuration

DNS config_context keys are **top-level, flat keys** (not nested under a `dns` object). See
[DNS_CONFIGURATION.md](DNS_CONFIGURATION.md) for the full reference.

```json
{
  "dns_domain_name": "example.com",
  "dns_mgmt_nameservers": {
    "Primary": "10.0.0.53",
    "Secondary": "10.0.0.54"
  },
  "dns_name_servers": {
    "default": {
      "0": "10.0.0.53",
      "1": "10.0.0.54"
    },
    "mgmt": {
      "0": "8.8.8.8",
      "1": "1.1.1.1"
    }
  },
  "dns_domain_list": {
    "0": "example.com",
    "1": "corp.example.com"
  },
  "dns_host_v4_address_mapping": {
    "router1": "10.0.1.1",
    "router2": "10.0.1.2"
  },
  "dns_vrf": "mgmt"
}
```

Ansible access (all top-level, consumed directly by `tasks/configure_dns.yml` via the
`arubanetworks.aoscx.aoscx_dns` module):
- `dns_domain_name`
- `dns_mgmt_nameservers`
- `dns_name_servers` — dict keyed by VRF name; each value is a numeric-key dict of server IPs
- `dns_domain_list`
- `dns_host_v4_address_mapping`
- `dns_vrf`


### STP (MSTP) Config Context

Global spanning-tree settings are applied by `configure_stp.yml` when
`mstp_config_name` is defined. All switches that participate in
the same MSTP region must share the same `mstp_config_name` and
`mstp_config_revision`.

```json
{
  "mstp_config_name": "CORP-SWITCHES",
  "mstp_config_revision": 1,
  "mstp_priority": 4096
}
```

Ansible access: `mstp_config_name`, `mstp_config_revision`, `mstp_priority`

| Key | Required | Type | Default | AOS-CX command |
|-----|----------|------|---------|----------------|
| `mstp_config_name` | Yes (to activate global STP) | String | — | `spanning-tree config-name <name>` |
| `mstp_config_revision` | No | Integer | `0` | `spanning-tree config-revision <rev>` |
| `mstp_priority` | No | Integer | device default | `spanning-tree priority <priority>` |

**Valid priority values:** 0, 4096, 8192, 12288, 16384, 20480, 24576, 28672, 32768, 36864, 40960, 45056, 49152, 53248, 57344, 61440.

**Typical hierarchy placement:** Define `mstp_config_name` and `mstp_config_revision` at the **site** level (all switches in a site share the same region). Override `mstp_priority` at the **device** or **device-role** level to control root bridge election.

```json
// Site config_context — all switches in the site
{
  "mstp_config_name": "SITE-A",
  "mstp_config_revision": 2
}
```

```json
// Device config_context — root bridge candidate
{
  "mstp_priority": 4096
}
```

### Port-Access Config Context

Port-access roles, LLDP groups, and device-profiles are defined under a
top-level `port_access` key. VLAN IDs referenced by any role's
`vlan_trunk_native`, `vlan_trunk_allowed`, or `vlan_access` field are
automatically added to the device's VLAN-create list and protected from
idempotent deletion. Range and list syntax is supported.

Roles that include `extra_lines` always push, this is a way to support
more parameters without needing to rewrite the code.

```json
{
  "port_access": {
    "lldp_groups": [
      {
        "name": "Lab-IAP-group",
        "match": [
          { "seq": 10, "vendor-oui": "000b86" },
          { "seq": 20, "sys-desc": "Aruba" },
          { "seq": 30, "sysname": "LAB-AP" }
        ]
      }
    ],
    "roles": [
      {
        "name": "Lab-IAP-role",
        "description": "Aruba IAP",
           "extra_lines": [
              "stp-admin-edge-port"
           ],
        "poe_priority": "high",
        "trust_mode": "dscp",
        "vlan_trunk_native": 11,
        "vlan_trunk_allowed": "11-13"
      }
    ],
    "device_profiles": [
      {
        "name": "Lab-IAP-prof",
        "enable": true,
        "associate_role": "Lab-IAP-role",
        "associate_lldp_group": "Lab-IAP-group"
      }
    ]
  }
}
```

Ansible access: `port_access`, `port_access.roles`,
`port_access.lldp_groups`, `port_access.device_profiles`.

> The referenced VLANs (`11`, `12`, `13` in the example above) must exist
> in NetBox and be scoped to the device. If a referenced VID is missing
> from NetBox the role will log a warning during VLAN change identification:
> `VLAN X is in use but not available in NetBox for this device!`

### Static Routes Config Context

Static routes are defined under a top-level `static_routes` key,
organised per VRF. Each VRF maps to a list of route objects (`forward`,
`blackhole`, or `reject`):

```json
{
  "static_routes": {
    "default": [
      {
        "prefix": "0.0.0.0/0",
        "type": "forward",
        "next_hop": "172.18.17.33"
      },
      {
        "prefix": "203.0.113.0/24",
        "type": "blackhole"
      }
    ]
  }
}
```

Ansible access: `static_routes`, `static_routes.<vrf_name>`.

See [STATIC_ROUTES_CONFIGURATION.md](STATIC_ROUTES_CONFIGURATION.md) for
the full field reference, idempotency notes, and cleanup behaviour.

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
  "dns_domain_name": "dc1.example.com",
  "dns_name_servers": {
    "default": {"0": "10.0.0.53"}
  }
}
```

**Device Level (leaf1):**

```json
{
  "bgp_redistribute": {
    "default": {
      "ipv4": ["connected", "static"]
    }
  }
}
```

Note: `bgp_redistribute` only adds redistribution config on top of the BGP sessions/peers/ASN
that come from the **netbox-bgp plugin** — it does not define peers or an ASN itself. There is
no config_context key that defines BGP peers or ASN; that data only comes from the plugin.

**Merged Result (what Ansible sees):**

```json
{
  "ntp": {"servers": ["10.0.0.1", "10.0.0.2"]},
  "dns_domain_name": "dc1.example.com",
  "dns_name_servers": {
    "default": {"0": "10.0.0.53"}
  },
  "bgp_redistribute": {
    "default": {
      "ipv4": ["connected", "static"]
    }
  }
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

### netbox-bgp Plugin (Optional but required for BGP)

**Purpose:** Structured BGP data models — the **only** source of BGP session/peer/ASN data used
by this role.

**Status:** Required for BGP. If the plugin is not installed/reachable, or returns no sessions
for a device, BGP configuration is simply skipped for that device (`configure_bgp.yml`'s tasks
are all gated on `netbox_bgp_plugin_available` and `device_bgp_sessions | length > 0`). There is
**no config_context fallback** — `config_context` can only *supplement* plugin-derived sessions
(via `bgp_redistribute` and `bgp_neighbor_options`), it can never replace the plugin as the
source of BGP peers or ASN. See [BGP_CONFIGURATION.md](BGP_CONFIGURATION.md).

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

#### How the Role Queries the Plugin

```yaml
# tasks/configure_bgp.yml queries the plugin for this device's sessions...
- name: Query NetBox BGP plugin for sessions for this device
  ansible.builtin.uri:
    url: "{{ lookup('env', 'NETBOX_API') }}/api/plugins/bgp/session/?device={{ inventory_hostname }}&limit=0"
    headers:
      Authorization: "Token {{ lookup('env', 'NETBOX_TOKEN') }}"
  register: netbox_bgp_sessions_raw
  delegate_to: localhost

# ...and records whether the plugin is available and which sessions are usable.
- name: Set BGP session facts for this device
  ansible.builtin.set_fact:
    netbox_bgp_plugin_available: "{{ netbox_bgp_sessions_raw.status == 200 }}"
    device_bgp_sessions: >-
      {{ netbox_bgp_sessions_raw.json.results | default([]) |
         selectattr('status.value', 'in', ['active', 'staged', 'planned']) |
         list }}

# Every subsequent BGP task in configure_bgp.yml requires both of these to be true.
# If the plugin is unreachable or returns zero usable sessions, BGP is simply not
# configured for this device — there is no config_context-based alternative.
- name: Configure BGP router process from netbox-bgp plugin
  arubanetworks.aoscx.aoscx_config:
    lines:
      - router bgp {{ device_bgp_sessions[0].local_as.asn }}
      - bgp router-id {{ device_bgp_sessions[0].local_address.address.split('/')[0] }}
    match: line
  when:
    - netbox_bgp_plugin_available | default(false)
    - device_bgp_sessions is defined
    - device_bgp_sessions | length > 0
```

**See:** [BGP_CONFIGURATION.md](BGP_CONFIGURATION.md) for complete details.

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
  "dns_domain_name": "example.com",
  "bgp_redistribute": {
    "default": {"ipv4": ["connected", "static"]}
  }
}
```

Note: BGP peers and ASN never appear in config_context — they only come from the netbox-bgp
plugin's session data (`/api/plugins/bgp/session/`), queried separately by `configure_bgp.yml`.

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
  "dns_domain_name": "site1.example.com",
  "dns_name_servers": {
    "default": {"0": "10.0.0.53"}
  }
}
```

### Pattern 3: Role-Based BGP Redistribution

Route reflector behaviour is **not** set via config_context — it is derived automatically from
the device's NetBox device role (`spine`, `route-reflector`, or `rr` → all BGP neighbors become
RR clients). BGP peers and ASN always come from the netbox-bgp plugin. The only role-based
config_context pattern for BGP is supplementing sessions with redistribution or neighbor
options, e.g.:

```json
// Device Role: leaf (config_context) — supplements plugin-derived sessions only
{
  "bgp_redistribute": {
    "default": {
      "ipv4": ["connected", "static"]
    }
  }
}
```

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

**Symptom:** BGP is not configured on a device even though `device_bgp` is enabled

**Check:**

```bash
# Test plugin API endpoint
curl -H "Authorization: Token $TOKEN" \
  "$NETBOX_API/api/plugins/bgp/session/?device=DEVICE_NAME"
```

**Common causes:**

- Plugin not installed (all BGP tasks are skipped — there is no config_context fallback)
- No BGP sessions created for the device
- BGP sessions not in "active", "staged", or "planned" status
- BGP sessions not assigned to the device
- `device_bgp` custom field not set to `true` (gates whether `configure_bgp.yml` is
  included at all, in `tasks/main.yml`)

---

## Summary

### Custom Fields (12 total)

**Device-level (Boolean):**

| Field | Purpose |
|-------|---------|
| `device_anycast_gateway` | Enable Anycast Gateway global settings |
| `device_bgp` | Gate inclusion of BGP configuration tasks (`configure_bgp.yml`); actual BGP data always comes from the netbox-bgp plugin |
| `device_evpn` | Enable EVPN |
| `device_vxlan` | Enable VXLAN |
| `device_vsx` | Enable VSX |

**VLAN-level (Boolean):**

| Field | Purpose |
|-------|---------|
| `vlan_ip_igmp_snooping` | Enable IGMP snooping per VLAN |
| `vlan_voice_vlan` | Enable voice VLAN per VLAN |

**Interface-level (Boolean — L2 interfaces only, null = leave unchanged):**

| Field | AOS-CX command |
|-------|----------------|
| `if_stp_bpdu_filter` | `spanning-tree bpdu-filter` |
| `if_stp_bpdu_guard` | `spanning-tree bpdu-guard` |
| `if_stp_edge_port` | `spanning-tree port-type admin-edge` |
| `if_stp_root_guard` | `spanning-tree root-guard` |

**Interface-level (Boolean — L3 interfaces):**

| Field | AOS-CX command | Notes |
|-------|----------------|-------|
| `if_ip_helper` | `ip helper-address <ip>` | Servers come from `ip_helper_addresses` config context, keyed by interface VRF |

### Config Context Keys

**Base System (Stable):**

- `motd`, `timezone`, `ntp.servers`
- `dns_domain_name`, `dns_mgmt_nameservers`, `dns_name_servers`, `dns_domain_list`,
  `dns_host_v4_address_mapping`, `dns_vrf` — see [DNS_CONFIGURATION.md](DNS_CONFIGURATION.md)

**BGP (Stable, supplement-only — never a peer/ASN source):**

- `bgp_redistribute` — dict keyed by VRF name, redistributes connected/static/ospf/etc. into BGP
- `bgp_neighbor_options` — dict keyed by neighbor IP, arbitrary per-neighbor CLI options
- Both keys only add extra configuration on top of sessions/peers/ASN sourced from the
  **netbox-bgp plugin** — see [BGP_CONFIGURATION.md](BGP_CONFIGURATION.md)

**STP / MSTP (Stable):**

- `mstp_config_name` (required to activate), `mstp_config_revision` (default 0), `mstp_priority` (optional)

**VSX (Stable):**

- `vsx_system_mac`, `vsx_role`, `vsx_isl_ports`, `vsx_keepalive_peer`, `vsx_keepalive_src`, `vsx_keepalive_vrf`

**DHCP Relay (Stable):**

- `ip_helper_addresses` — dict keyed by VRF name; each value is a string-indexed dict of relay server IPs

**Static Routes (Stable):**

- `static_routes` — dict keyed by VRF name; each value is a list of route
  objects (`prefix`, `type`, `next_hop`, `next_hop_interface`, `distance`).
  See [STATIC_ROUTES_CONFIGURATION.md](STATIC_ROUTES_CONFIGURATION.md).

<a name="ip_helper_addresses"></a>

#### ip_helper_addresses

Defines the DHCP relay servers per VRF. Used together with the `if_ip_helper` interface custom field to configure `ip helper-address` on L3 interfaces.

The top-level key is the **VRF name** as it appears on the switch (must match the interface VRF in NetBox). The value is a dict where the keys are string indices (`"0"`, `"1"`, …) and the values are relay server IP addresses. The index order controls the order in which `ip helper-address` commands are pushed.

```json
{
    "ip_helper_addresses": {
        "lab-blue": {
            "0": "172.16.3.10",
            "1": "172.16.3.11"
        },
        "lab-green": {
            "0": "172.16.3.12",
            "1": "172.16.3.13",
            "2": "172.16.3.14"
        }
    }
}
```

**Typical placement:** Site or device-role config context, so all leaf switches in a site share the same relay targets. Override at the device level when a specific switch needs different servers.

**How it works:**

1. Set `if_ip_helper: true` on each interface (SVI, LAG, or physical) that should relay DHCP.
2. Define `ip_helper_addresses` in config context for the device, keyed by the interface's VRF name.
3. The role reads the VRF from the NetBox interface object (not the IP address) and looks up the matching entry.
4. With `aoscx_gather_facts_rest_api: true`, the role compares expected vs. device-configured servers and only pushes when there is a difference. Servers present on the device but absent from NetBox are removed with `no ip helper-address <ip>`.
5. Without REST API facts, the role always pushes the full helper-address set (conservative mode).

**Port-Access (Stable):**

- `port_access.lldp_groups`, `port_access.roles`, `port_access.device_profiles`
- VLAN IDs referenced via `vlan_trunk_native` / `vlan_trunk_allowed` /
  `vlan_access` are auto-created and protected from idempotent cleanup
  (range/list syntax supported, e.g. `"11-13"`, `"11,13,15-20"`).

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
- ✅ **Use netbox-bgp plugin** for BGP — it is the only supported source of BGP
  sessions/peers/ASN; use `config_context` (`bgp_redistribute`, `bgp_neighbor_options`)
  only to supplement plugin-derived sessions
- ✅ **Keep config_context** for base system configuration
- ✅ **Use L2VPN objects** for EVPN/VXLAN VNI mapping

---

## Related Documentation

- [BASE_CONFIGURATION.md](BASE_CONFIGURATION.md) - Base system configuration details
- [DNS_CONFIGURATION.md](DNS_CONFIGURATION.md) - Full DNS config_context schema and examples
- [BGP_CONFIGURATION.md](BGP_CONFIGURATION.md) - BGP configuration and netbox-bgp plugin details
- [EVPN_VXLAN_CONFIGURATION.md](EVPN_VXLAN_CONFIGURATION.md) - EVPN/VXLAN with L2VPNs
- [L2_INTERFACE_MODES.md](L2_INTERFACE_MODES.md) - L2 interface configuration modes and STP interface settings
