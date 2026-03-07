# NetBox BGP Plugin Integration

## Overview

The [netbox-bgp plugin](https://github.com/netbox-community/netbox-bgp) provides structured BGP data models in NetBox, which is **much better** than using config_context for BGP configuration.

### Why Use netbox-bgp Plugin?

- ✅ **Structured data models** - Proper objects instead of free-form JSON
- ✅ **Validation** - NetBox validates fields and relationships
- ✅ **Relationships** - Links sessions to devices, peer groups, policies
- ✅ **API access** - RESTful API for querying BGP data
- ✅ **Inventory integration** - Can be used with NetBox inventory plugin
- ✅ **Audit trail** - NetBox tracks all changes
- ✅ **Search and filter** - Query BGP sessions, communities, etc.

### netbox-bgp Plugin Models

1. **BGP Sessions** - Individual BGP neighbor relationships
2. **BGP Peer Groups** - Template for common neighbor settings
3. **BGP Communities** - Community definitions
4. **Routing Policies** - Import/export policies
5. **Prefix Lists** - Prefix filtering
6. **AS Path Lists** - AS path filtering

## Installation

### On NetBox Server

```bash
# Install the plugin
pip install netbox-bgp

# Enable in NetBox configuration
# /opt/netbox/netbox/netbox/configuration.py
PLUGINS = ['netbox_bgp']

# Add to local requirements
echo "netbox-bgp" >> /opt/netbox/local_requirements.txt

# Run migrations
cd /opt/netbox/netbox
python3 manage.py migrate

# Restart NetBox
sudo systemctl restart netbox
```

### Verify Installation

```bash
# Check plugin is loaded
curl -H "Authorization: Token YOUR_TOKEN" \
  http://netbox-url/api/plugins/installed-plugins/
```

## BGP Session Model

### Key Fields

| Field | Type | Description |
| ----- | ---- | ----------- |
| `name` | String | Session identifier |
| `device` | ForeignKey | Device this session belongs to |
| `local_as` | ForeignKey | Local AS number |
| `remote_as` | ForeignKey | Remote AS number |
| `local_address` | IPAddress | Local IP (e.g., loopback) |
| `remote_address` | IPAddress | Remote IP (neighbor) |
| `status` | Choice | Active, Planned, Offline, etc. |
| `peer_group` | ForeignKey | Optional peer group template |
| `import_policies` | ManyToMany | Import routing policies |
| `export_policies` | ManyToMany | Export routing policies |
| `description` | String | Session description |

## API Usage

### Query BGP Sessions for a Device

```bash
# Get all BGP sessions for a device
curl -H "Authorization: Token YOUR_TOKEN" \
  "http://netbox-url/api/plugins/bgp/session/?device=leaf-1"
```

### Python Example

```python
import requests

netbox_url = "https://netbox.example.com"
token = "YOUR_NETBOX_TOKEN"
headers = {
    "Authorization": f"Token {token}",
    "Content-Type": "application/json"
}

# Get BGP sessions for a device
response = requests.get(
    f"{netbox_url}/api/plugins/bgp/session/",
    headers=headers,
    params={"device": "leaf-1"}
)

bgp_sessions = response.json()["results"]

for session in bgp_sessions:
    print(f"Neighbor: {session['remote_address']['address']}")
    print(f"Remote AS: {session['remote_as']['asn']}")
    print(f"Status: {session['status']['value']}")
```

## NetBox Inventory Plugin Integration

The NetBox inventory plugin can access BGP plugin data:

```yaml
# netbox_inv_bgp.yml
plugin: netbox.netbox.nb_inventory
api_endpoint: "{{ lookup('env', 'NETBOX_API') }}"
token: "{{ lookup('env', 'NETBOX_TOKEN') }}"
validate_certs: true

# Include BGP session data
compose:
  bgp_sessions: netbox_bgp_sessions

# The inventory will include bgp_sessions for each device
```

## Ansible Task Integration

### Option 1: Query BGP Plugin API

```yaml
---
- name: Get BGP sessions from NetBox BGP plugin
  ansible.builtin.uri:
    url: "{{ netbox_url }}/api/plugins/bgp/session/"
    method: GET
    headers:
      Authorization: "Token {{ netbox_token }}"
      Content-Type: "application/json"
    return_content: true
  register: bgp_sessions_api
  delegate_to: localhost
  run_once: true

- name: Filter BGP sessions for this device
  ansible.builtin.set_fact:
    device_bgp_sessions: "{{ bgp_sessions_api.json.results |
      selectattr('device.name', 'equalto', inventory_hostname) | list }}"

- name: Debug BGP sessions
  ansible.builtin.debug:
    var: device_bgp_sessions
```

### Option 2: Use Inventory Variables

If NetBox inventory plugin includes BGP data:

```yaml
---
- name: Configure BGP from NetBox BGP plugin data
  arubanetworks.aoscx.aoscx_config:
    lines:
      - router bgp {{ item.local_as.asn }}
      - neighbor {{ item.remote_address.address }} remote-as {{ item.remote_as.asn }}
  loop: "{{ bgp_sessions | default([]) }}"
  when: bgp_sessions is defined
```

## Advantages Over config_context

### config_context Approach (Previous)

```json
{
  "bgp_as": 65000,
  "bgp_peers": [
    {"peer": "10.255.255.1", "remote_as": 65000}
  ]
}
```

**Issues:**

- ❌ No validation of AS numbers or IPs
- ❌ No relationships to other objects
- ❌ Hard to query across devices
- ❌ No status tracking
- ❌ No change history

### netbox-bgp Plugin Approach (Better)

**Benefits:**

- ✅ AS numbers are validated objects
- ✅ IP addresses linked to existing IPs
- ✅ Can query all sessions for an AS
- ✅ Status field (Active, Planned, Offline)
- ✅ Full change history in NetBox
- ✅ Peer groups for templates
- ✅ Routing policies attached
- ✅ Communities attached

## Migration Path

### Current State: config_context

```json
{
  "bgp_as": 65000,
  "bgp_peers": [
    {"peer": "10.255.255.1", "remote_as": 65000},
    {"peer": "10.255.255.2", "remote_as": 65000}
  ]
}
```

### Future State: netbox-bgp Plugin

1. **Install netbox-bgp plugin**
2. **Create AS objects** (65000)
3. **Create BGP Sessions** for each peer
4. **Update Ansible tasks** to query BGP plugin API
5. **Remove config_context BGP data** (keep for other data)

## Example: EVPN/VXLAN Fabric with netbox-bgp

### NetBox Setup

#### 1. Create AS Objects

```
AS 65000 (Private)
```

#### 2. Create Peer Group (Optional)

```
Name: EVPN-OVERLAY
Description: EVPN overlay peers
```

#### 3. Create BGP Sessions**

**Leaf-1 → Spine-1:**

- Device: leaf-1
- Name: leaf-1-to-spine-1
- Local AS: 65000
- Remote AS: 65000
- Local Address: 10.255.255.11/32 (loopback)
- Remote Address: 10.255.255.1/32
- Peer Group: EVPN-OVERLAY
- Status: Active

##### Leaf-1 → Spine-2

- Device: leaf-1
- Name: leaf-1-to-spine-2
- Local AS: 65000
- Remote AS: 65000
- Local Address: 10.255.255.11/32
- Remote Address: 10.255.255.2/32
- Peer Group: EVPN-OVERLAY
- Status: Active

#### *(Repeat for all leaf-spine pairs)*

### Ansible Integration

```yaml
---
- name: Get BGP sessions from NetBox BGP plugin
  ansible.builtin.uri:
    url: "{{ lookup('env', 'NETBOX_API') }}/api/plugins/bgp/session/"
    method: GET
    headers:
      Authorization: "Token {{ lookup('env', 'NETBOX_TOKEN') }}"
    body_format: json
    return_content: true
  register: all_bgp_sessions
  delegate_to: localhost
  run_once: true

- name: Filter sessions for this device
  ansible.builtin.set_fact:
    my_bgp_sessions: "{{ all_bgp_sessions.json.results |
      selectattr('device.name', 'equalto', inventory_hostname) |
      selectattr('status.value', 'equalto', 'active') | list }}"

- name: Configure BGP router process
  arubanetworks.aoscx.aoscx_config:
    lines:
      - router bgp {{ my_bgp_sessions[0].local_as.asn }}
      - bgp router-id {{ my_bgp_sessions[0].local_address.address.split('/')[0] }}
  when: my_bgp_sessions | length > 0

- name: Configure BGP neighbors
  arubanetworks.aoscx.aoscx_command:
    commands:
      - configure terminal
      - router bgp {{ item.local_as.asn }}
      - neighbor {{ item.remote_address.address.split('/')[0] }} remote-as {{ item.remote_as.asn }}
      - neighbor {{ item.remote_address.address.split('/')[0] }} update-source loopback 0
      - address-family l2vpn evpn
      - neighbor {{ item.remote_address.address.split('/')[0] }} send-community extended
      - neighbor {{ item.remote_address.address.split('/')[0] }} activate
      - exit-address-family
  loop: "{{ my_bgp_sessions }}"
  loop_control:
    label: "{{ item.name }}"
  vars:
    ansible_connection: network_cli
```

## Comparison: Both Approaches

### Support Both Methods

The role could support **both** approaches:

```yaml
---
# Try netbox-bgp plugin first
- name: Get BGP sessions from NetBox BGP plugin
  ansible.builtin.uri:
    url: "{{ netbox_url }}/api/plugins/bgp/session/"
    method: GET
    headers:
      Authorization: "Token {{ netbox_token }}"
    status_code: [200, 404]  # 404 if plugin not installed
  register: bgp_plugin_api
  delegate_to: localhost
  run_once: true
  when: aoscx_use_bgp_plugin | default(false) | bool

# Fall back to config_context if plugin not available
- name: Use config_context for BGP if plugin not available
  ansible.builtin.set_fact:
    use_config_context_bgp: true
  when:
    - not (aoscx_use_bgp_plugin | default(false) | bool)
    - bgp_as is defined
```

## Recommendation

### For New Deployments

**Use netbox-bgp plugin** - Better structure, validation, and relationships

### For Existing Deployments

**Migration plan:**

1. Install netbox-bgp plugin
2. Populate BGP sessions in plugin
3. Test with one device using plugin data
4. Update role to support both methods
5. Gradually migrate devices
6. Remove config_context BGP data

### For Simple Deployments

**config_context is fine** if:

- Small number of devices
- Simple BGP configuration
- Don't need complex queries
- Quick deployment needed

### For Complex Deployments

**netbox-bgp plugin is better** for:

- Large fabrics (dozens of devices)
- Complex routing policies
- Need to query BGP data
- Multiple fabrics/sites
- Change management tracking

## Route Reflector Configuration

### Automatic Configuration Based on Device Role

The role automatically configures route reflector settings based on the device's role in NetBox:

**Supported Roles:**

- `spine`
- `route-reflector`
- `rr`

**Behavior:**

- ✅ All BGP neighbors are automatically configured as route-reflector clients
- ✅ No need to manually specify RR clients in config_context
- ✅ Consistent with spine-leaf EVPN architecture best practices

### Example

**NetBox Setup:**

1. **Device**: spine-1
2. **Role**: spine
3. **BGP Sessions**: 4 sessions to leaf switches

**Result:**

```bash
router bgp 65000
  neighbor 10.255.255.11 route-reflector-client
  neighbor 10.255.255.12 route-reflector-client
  neighbor 10.255.255.13 route-reflector-client
  neighbor 10.255.255.14 route-reflector-client
```

### Fallback to config_context

If netbox-bgp plugin is not available or not in use, the role falls back to `bgp_rr_clients`:

```json
{
  "bgp_rr_clients": [
    {"peer": "10.255.255.11"},
    {"peer": "10.255.255.12"}
  ]
}
```

### Customization

To disable automatic RR configuration:

- Set device role to something other than spine/route-reflector/rr
- Or use config_context fallback for granular control

## VRF BGP Sessions and Routing Policies

### How VRF Sessions Work

Sessions whose `local_address` is assigned to an interface in a **non-default VRF** are
automatically placed in VRF context on the device. The role uses the
`get_bgp_session_vrf_info` filter to enrich each session with two extra fields:

| Field | Value | Meaning |
|-------|-------|---------|
| `_vrf` | `"lab-blue"` | Interface VRF name (or `"default"`) |
| `_af`  | `"ipv4"` / `"ipv6"` | Address family derived from local IP syntax |

Sessions in `_vrf == "default"` are configured as EVPN/underlay neighbors.
Sessions in any other VRF are configured under the matching `vrf` context inside `router bgp`.

### iBGP vs eBGP Detection

The role compares `local_as.asn` and `remote_as.asn` for each VRF session:

| Condition | Type | Extra Config |
|-----------|------|--------------|
| `local_as.asn == remote_as.asn` | iBGP | `next-hop-self` added |
| `local_as.asn != remote_as.asn` | eBGP | Import/export route-maps applied |

### Routing Policies (Import/Export)

Sessions can reference routing policies via `import_policies` and `export_policies`
(ManyToMany lists). The role:

1. Fetches all routing policy rules from `/api/plugins/bgp/routing-policy-rule/`
2. Fetches all prefix list rules from `/api/plugins/bgp/prefix-list-rule/`
3. Filters to rules referenced by this device's eBGP VRF sessions
4. Configures **prefix lists first**, then **route-maps**, then **BGP neighbors**

#### Routing Policy Rule Fields (real API)

| Field | Type | Description |
|-------|------|-------------|
| `routing_policy` | FK dict `{id, name}` | The parent policy |
| `index` | int | Sequence number |
| `action` | string | `"permit"` or `"deny"` |
| `match_ip_address` | list of `{id, name}` | Prefix list objects (ManyToMany) |
| `set_actions` | dict | e.g. `{"as-path prepend": [65015], "local-preference": 300}` |

#### Prefix List Rule Fields (real API)

| Field | Type | Description |
|-------|------|-------------|
| `prefix_list` | FK dict `{id, name}` | The parent prefix list |
| `index` | int | Sequence number |
| `action` | string | `"permit"` or `"deny"` |
| `prefix` | IPAM FK dict or `null` | `{"prefix": "172.27.4.0/24", ...}` |
| `prefix_custom` | string or `null` | Plain CIDR fallback when `prefix` is null |

#### AOS-CX Route-Map Syntax

AOS-CX requires `seq` before the sequence number:

```
route-map LAB-BLUE-IPV4-OUT-01 permit seq 10
  match ip address prefix-list LAB-BLUE-IPV4
  set as-path prepend 65015
```

The `collect_ebgp_vrf_policy_config` filter generates commands using this syntax.

### Custom Filters

Two filters in `filter_plugins/netbox_filters_lib/bgp_filters.py` handle BGP data:

#### `get_bgp_session_vrf_info(sessions, interfaces)`

Enriches each BGP session with `_vrf` and `_af` by looking up the session's
`local_address` against device interface IPs in NetBox.

```yaml
- set_fact:
    enriched_sessions: >-
      {{ device_bgp_sessions | get_bgp_session_vrf_info(interfaces | default([])) }}
```

Returns each session with added fields:
- `_vrf`: VRF name (or `"default"` for loopbacks/default VRF interfaces)
- `_af`: `"ipv4"` or `"ipv6"`

#### `collect_ebgp_vrf_policy_config(sessions, policy_rules, prefix_list_rules)`

Collects routing policies and prefix lists referenced by the sessions' `import_policies`
and `export_policies` fields. Returns pre-built AOS-CX CLI command lists.

```yaml
- set_fact:
    bgp_policy_data: >-
      {{ bgp_vrf_sessions |
         collect_ebgp_vrf_policy_config(
           netbox_policy_rules_all | default([]),
           netbox_prefix_list_rules_all | default([])
         ) }}
```

Returns:

```python
{
  "prefix_lists": [
    {
      "name": "LAB-BLUE-IPV4",
      "rules": [{"index": 10, "action": "permit", "prefix": "172.27.4.0/24"}]
    }
  ],
  "route_map_rules": [
    {
      "name": "LAB-BLUE-IPV4-OUT-01",
      "index": 10,
      "action": "permit",
      "commands": [
        "route-map LAB-BLUE-IPV4-OUT-01 permit seq 10",
        "match ip address prefix-list LAB-BLUE-IPV4",
        "set as-path prepend 65015"
      ]
    }
  ]
}
```

### NetBox Setup for VRF Routing Policies

1. **Create Prefix Lists** under `/api/plugins/bgp/prefix-list/`
2. **Create Prefix List Rules** under `/api/plugins/bgp/prefix-list-rule/`
   - Link to a prefix list and an IPAM prefix object (or use `prefix_custom` for a plain string)
3. **Create Routing Policies** under `/api/plugins/bgp/routing-policy/`
4. **Create Routing Policy Rules** under `/api/plugins/bgp/routing-policy-rule/`
   - Set `match_ip_address` to the prefix list(s) to match
   - Set `set_actions` dict for set operations
5. **Assign policies to BGP sessions** via `import_policies` / `export_policies`

## Related Documentation

- [netbox-bgp Plugin GitHub](https://github.com/netbox-community/netbox-bgp)
- [NetBox Plugins Documentation](https://docs.netbox.dev/en/stable/plugins/)
- [BGP_CONFIGURATION.md](BGP_CONFIGURATION.md) - config_context approach
- [BGP_HYBRID_CONFIGURATION.md](BGP_HYBRID_CONFIGURATION.md) - Hybrid mode details
- [BGP_EVPN_FABRIC_EXAMPLE.md](BGP_EVPN_FABRIC_EXAMPLE.md) - Fabric examples

## API Endpoints

```
# BGP Sessions
GET /api/plugins/bgp/session/
GET /api/plugins/bgp/session/{id}/

# BGP Peer Groups
GET /api/plugins/bgp/peer-group/
GET /api/plugins/bgp/peer-group/{id}/

# BGP Communities
GET /api/plugins/bgp/community/
GET /api/plugins/bgp/community/{id}/

# Routing Policies and Rules
GET /api/plugins/bgp/routing-policy/
GET /api/plugins/bgp/routing-policy/{id}/
GET /api/plugins/bgp/routing-policy-rule/
GET /api/plugins/bgp/routing-policy-rule/{id}/

# Prefix Lists and Rules
GET /api/plugins/bgp/prefix-list/
GET /api/plugins/bgp/prefix-list/{id}/
GET /api/plugins/bgp/prefix-list-rule/
GET /api/plugins/bgp/prefix-list-rule/{id}/

# AS Numbers
GET /api/plugins/bgp/asn/
GET /api/plugins/bgp/asn/{id}/
```
