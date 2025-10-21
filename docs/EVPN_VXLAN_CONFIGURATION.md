# EVPN and VXLAN Configuration

## Overview

The EVPN and VXLAN tasks configure overlay networking for EVPN/VXLAN fabrics on Aruba CX switches. These tasks only configure VLANs that are **actually in use** on the device.

## Key Features

✅ **Intelligent VLAN filtering** - Only configures VLANs in use on interfaces
✅ **NetBox L2VPN integration** - Uses NetBox L2VPN terminations for VNI mapping
✅ **Per-device control** - Custom fields enable/disable EVPN and VXLAN
✅ **Proper ordering** - EVPN before VXLAN, VNI before VLAN-to-VNI mapping
✅ **Idempotent** - Safe to run multiple times

## Configuration Order

**Critical:** These tasks must run in this order:

1. **VLANs** - Create VLANs first
2. **Interfaces** - Configure interfaces using VLANs
3. **Loopback** - VTEP source interface
4. **EVPN** - Configure EVPN for VLANs in use
5. **VXLAN** - Create VNIs and map to VLANs

This matches your production playbook order.

## Requirements

### NetBox Custom Fields

| Field Name | Type | Object | Required | Description |
|------------|------|--------|----------|-------------|
| `device_evpn` | Boolean | Device | Yes | Enable EVPN on this device |
| `device_vxlan` | Boolean | Device | Yes | Enable VXLAN on this device |

### NetBox L2VPN Configuration

Each VLAN that needs EVPN/VXLAN must have:

1. **L2VPN** object created
2. **L2VPN Termination** linking VLAN to L2VPN
3. **VNI identifier** in L2VPN object

#### Example NetBox Setup

**Step 1: Create L2VPN**
```
Name: VLAN-100-L2VPN
Identifier: 10100  # This is the VNI
Type: VXLAN
```

**Step 2: Create L2VPN Termination**
```
L2VPN: VLAN-100-L2VPN
Assigned Object Type: VLAN
Assigned Object: VLAN 100 (production)
```

**Result:** VLAN 100 is now linked to VNI 10100

## How It Works

### VLAN Filtering Logic

Both tasks filter VLANs using three criteria:

```yaml
vlans_for_evpn: "{{ vlans |
  selectattr('vid', 'in', vlans_in_use.vids) |        # 1. VLAN is in use
  selectattr('l2vpn_termination', 'defined') |        # 2. Has L2VPN termination
  selectattr('l2vpn_termination.id', 'defined') |     # 3. Termination is valid
  list }}"
```

**This ensures:**
- ✅ Only VLANs actually used on interfaces are configured
- ✅ Only VLANs with proper NetBox L2VPN setup are included
- ✅ No orphaned EVPN/VXLAN configurations

### VLANs In Use Detection

A VLAN is considered "in use" if it appears on:
- Physical interface in access mode
- Physical interface in tagged mode (trunk)
- LAG interface in access mode
- LAG interface in tagged mode (trunk)
- SVI (VLAN interface with IP)

This is calculated by the `get_vlans_in_use` filter plugin.

## EVPN Configuration

### Task: configure_evpn.yml

Configures EVPN for VLANs in use with automatic route distinguisher and route targets.

### Configuration Applied

```
evpn
  vlan 100
    rd auto
    route-target export auto
    route-target import auto
  vlan 200
    rd auto
    route-target export auto
    route-target import auto
```

### NetBox Data Required

```json
{
  "vid": 100,
  "name": "production",
  "l2vpn_termination": {
    "id": 42,
    "l2vpn": {
      "identifier": 10100
    }
  }
}
```

### Example

**Device:** leaf-1
**VLANs in use:** 100, 200, 300
**VLANs with L2VPN:** 100, 200
**Result:** EVPN configured for VLANs 100 and 200 only

## VXLAN Configuration

### Task: configure_vxlan.yml

Configures VXLAN in two steps:
1. Create VNI under interface vxlan 1
2. Map VLAN to VNI

### Configuration Applied

```
interface vxlan 1
  vni 10100
    vlan 100
  vni 10200
    vlan 200
```

### NetBox Data Required

Same as EVPN - L2VPN termination with VNI identifier.

### Example

**Device:** leaf-1
**VLANs in use:** 100, 200, 300
**VLANs with L2VPN:** 100, 200
**VNI mappings:**
- VLAN 100 → VNI 10100
- VLAN 200 → VNI 10200

**Result:** VXLAN configured for VLANs 100 and 200 only

## NetBox Configuration Examples

### Example 1: Simple Fabric

**Fabric:** 2 Spines, 4 Leafs
**VLANs:** 100 (production), 200 (development)
**VNI Scheme:** 10000 + VLAN ID

#### Create L2VPNs

```bash
# VLAN 100
Name: VLAN-100-L2VPN
Identifier: 10100
Type: VXLAN

# VLAN 200
Name: VLAN-200-L2VPN
Identifier: 10200
Type: VXLAN
```

#### Create L2VPN Terminations

For each leaf device (leaf-1, leaf-2, leaf-3, leaf-4):

```bash
# VLAN 100 on leaf-1
L2VPN: VLAN-100-L2VPN
Assigned Object Type: dcim.vlan
Assigned Object: VLAN 100 (available on leaf-1)

# VLAN 200 on leaf-1
L2VPN: VLAN-200-L2VPN
Assigned Object Type: dcim.vlan
Assigned Object: VLAN 200 (available on leaf-1)
```

#### Set Custom Fields

For each leaf:
```
device_evpn: true
device_vxlan: true
```

For spines (no EVPN/VXLAN):
```
device_evpn: false
device_vxlan: false
```

### Example 2: Multi-Tenant Fabric

**Tenants:**
- TENANT-A: VLANs 100-199
- TENANT-B: VLANs 200-299

**VNI Scheme:**
- TENANT-A: VNI 11000-11099
- TENANT-B: VNI 12000-12099

#### L2VPN Naming Convention

```
TENANT-A-VLAN-100
TENANT-A-VLAN-101
TENANT-B-VLAN-200
TENANT-B-VLAN-201
```

#### VNI Mapping

```
VLAN 100 → VNI 11100
VLAN 101 → VNI 11101
VLAN 200 → VNI 12200
VLAN 201 → VNI 12201
```

## Role Variables

### defaults/main.yml

```yaml
# Enable EVPN configuration
aoscx_configure_evpn: false

# Enable VXLAN configuration
aoscx_configure_vxlan: false
```

### Required Variables (from NetBox)

```yaml
# From NetBox inventory
custom_fields:
  device_evpn: true   # Per-device enable
  device_vxlan: true  # Per-device enable

# From NetBox VLAN API
vlans:
  - vid: 100
    name: "production"
    l2vpn_termination:
      id: 42
      l2vpn:
        identifier: 10100  # VNI

# From interface configuration
vlans_in_use:
  vids: [100, 200, 300]  # Calculated from interfaces
```

## Running the Tasks

### Full EVPN/VXLAN Configuration

```bash
# Configure everything including EVPN and VXLAN
ansible-playbook configure_aoscx.yml -l leaf-switches
```

### Only EVPN

```bash
ansible-playbook configure_aoscx.yml -l leaf-switches -t evpn
```

### Only VXLAN

```bash
ansible-playbook configure_aoscx.yml -l leaf-switches -t vxlan
```

### Both (Overlay)

```bash
ansible-playbook configure_aoscx.yml -l leaf-switches -t overlay
```

### Enable/Disable per Device

```yaml
# Enable on leafs (in NetBox custom fields)
device_evpn: true
device_vxlan: true

# Disable on spines (no VTEP needed)
device_evpn: false
device_vxlan: false
```

### Enable/Disable in Role

```yaml
# In group_vars or playbook
aoscx_configure_evpn: true
aoscx_configure_vxlan: true
```

**Both conditions must be true for configuration to apply.**

## Configuration Workflow

### Complete EVPN/VXLAN Fabric Setup

```bash
# 1. Base configuration
ansible-playbook configure_aoscx.yml -l fabric -t base_config

# 2. VRFs
ansible-playbook configure_aoscx.yml -l fabric -t vrfs

# 3. VLANs
ansible-playbook configure_aoscx.yml -l fabric -t vlans

# 4. Interfaces
ansible-playbook configure_aoscx.yml -l fabric -t interfaces

# 5. Loopback (VTEP source)
ansible-playbook configure_aoscx.yml -l leaf* -t loopback

# 6. Underlay routing (OSPF)
ansible-playbook configure_aoscx.yml -l fabric -t ospf

# 7. Overlay control plane (BGP EVPN)
ansible-playbook configure_aoscx.yml -l fabric -t bgp

# 8. EVPN configuration
ansible-playbook configure_aoscx.yml -l leaf* -t evpn

# 9. VXLAN configuration
ansible-playbook configure_aoscx.yml -l leaf* -t vxlan
```

Or all at once:
```bash
ansible-playbook configure_aoscx.yml -l fabric
```

## Verification Commands

### Check EVPN Configuration

```bash
ssh admin@leaf-1

# Show EVPN VLANs
show evpn

# Show specific EVPN VLAN
show evpn vlan 100

# Should show:
# EVPN Instance: VLAN 100
#   RD: auto
#   Route Target Export: auto
#   Route Target Import: auto
```

### Check VXLAN Configuration

```bash
# Show VXLAN interface
show interface vxlan 1

# Show VNI summary
show vxlan

# Show VLAN to VNI mapping
show vxlan vni

# Expected output:
# VNI    VLAN   Type
# 10100  100    Access
# 10200  200    Access
```

### Check VXLAN Tunnel Status

```bash
# Show VXLAN tunnels
show vxlan tunnel

# Should show tunnels to other VTEPs
# Source: Loopback 0 (e.g., 10.255.255.11)
# Destination: Other leaf loopbacks
```

### Check MAC Learning

```bash
# Show MAC addresses learned via VXLAN
show mac-address-table vxlan

# Should show remote MACs learned from other VTEPs
```

## Troubleshooting

### EVPN Not Configured

**Symptom:** `show evpn` returns empty

**Check:**
```bash
# 1. Role variable enabled
aoscx_configure_evpn: true

# 2. Custom field set
device_evpn: true

# 3. VLANs have L2VPN termination
curl "$NETBOX_API/api/ipam/vlans/100/" | jq '.l2vpn_termination'

# 4. VLANs are in use on device
# Run with debug mode
ansible-playbook configure_aoscx.yml -l leaf-1 -t evpn -e aoscx_debug=true
```

### VXLAN VNI Not Created

**Symptom:** `show vxlan vni` returns empty

**Check:**
```bash
# 1. Role variable enabled
aoscx_configure_vxlan: true

# 2. Custom field set
device_vxlan: true

# 3. L2VPN has identifier (VNI)
curl "$NETBOX_API/api/ipam/l2vpns/1/" | jq '.identifier'

# 4. Interface vxlan 1 exists
show interface vxlan 1
```

### VLAN-to-VNI Mapping Missing

**Symptom:** VNI exists but no VLAN mapped

**Check:**
```yaml
# Task order - VXLAN task runs in 2 steps:
# 1. Create VNI
# 2. Map VLAN to VNI

# Both steps should show in output
```

### VLAN Not Getting EVPN/VXLAN

**Symptom:** VLAN 100 in use but no EVPN/VXLAN configured

**Possible Causes:**

1. **VLAN not in use on interfaces**
   ```bash
   # Check if VLAN appears on any interface
   show vlan 100
   # Should show interfaces using VLAN 100
   ```

2. **No L2VPN termination in NetBox**
   ```bash
   curl "$NETBOX_API/api/ipam/l2vpn-terminations/?assigned_object_type=ipam.vlan&assigned_object_id=VLAN_ID"
   # Should return termination
   ```

3. **VNI identifier missing**
   ```bash
   # Check L2VPN has identifier
   curl "$NETBOX_API/api/ipam/l2vpns/ID/" | jq '.identifier'
   # Should return numeric VNI
   ```

## Best Practices

### 1. VNI Numbering

✅ **Recommended schemes:**
- Simple: VNI = 10000 + VLAN ID (VLAN 100 → VNI 10100)
- Multi-tenant: VNI = tenant_base + VLAN (TENANT-A base 11000, VLAN 100 → VNI 11100)
- Datacenter: VNI = DC_ID + VLAN (DC1 10000, DC2 20000)

❌ **Avoid:**
- Random VNI numbers
- Overlapping VNI ranges
- Using VLAN ID as VNI directly

### 2. L2VPN Organization

✅ **DO:**
- Consistent naming: `VLAN-{VID}-L2VPN` or `{TENANT}-VLAN-{VID}`
- Document VNI scheme in NetBox
- Use L2VPN descriptions

❌ **DON'T:**
- Create L2VPNs without terminations
- Reuse VNIs across L2VPNs
- Mix VNI schemes within same fabric

### 3. Custom Fields

✅ **DO:**
- Set `device_evpn` and `device_vxlan` per device
- Enable on leaf switches (VTEPs)
- Disable on spines (no VTEP needed)
- Disable on access switches

❌ **DON'T:**
- Enable EVPN without VXLAN (both needed for overlay)
- Enable on devices without loopback interfaces
- Enable before underlay routing is configured

### 4. Operations

✅ **DO:**
- Configure in order: VLANs → Interfaces → Loopback → Routing → EVPN → VXLAN
- Test with one VLAN first
- Use debug mode to verify filtering
- Check `show evpn` and `show vxlan` after configuration

❌ **DON'T:**
- Configure EVPN/VXLAN before underlay routing
- Configure on spines (unless spine is also acting as VTEP)
- Create L2VPN terminations for VLANs not in use

## Cleanup Process

### Overview

When VLANs are removed from a device, EVPN and VXLAN configurations must be cleaned up in the **correct order** before VLAN deletion:

```
EVPN Cleanup → VXLAN Cleanup → VLAN Deletion
```

**Important:** Cleanup only runs when `aoscx_idempotent_mode` is `true`. This ensures:
- Configuration and cleanup are connected together
- Initial deployments don't trigger cleanup
- Only ongoing management performs cleanup operations

**Why order matters:**
- Removing a VLAN that still has EVPN/VXLAN config can leave orphaned configurations
- VXLAN VNI must be removed before the VLAN itself
- EVPN config must be removed before VXLAN to avoid control plane issues

### Cleanup Tasks

The role automatically runs these cleanup tasks when VLANs are being deleted:

#### 1. EVPN Cleanup (`cleanup_evpn.yml`)

**What it does:**
- Identifies VLANs being deleted that have EVPN config (have L2VPN terminations)
- Removes EVPN configuration: `no vlan X` under `evpn` context
- Only runs when `device_evpn` custom field is enabled

**Example cleanup:**
```
evpn
  no vlan 100
  no vlan 200
```

#### 2. VXLAN Cleanup (`cleanup_vxlan.yml`)

**What it does:**
- Identifies VLANs being deleted that have VXLAN mappings (have L2VPN terminations)
- **Two-step removal** (reverse of configuration):
  1. Remove VLAN from VNI: `no vlan X` under `vni Y`
  2. Remove VNI from VXLAN interface: `no vni Y`
- Only runs when `device_vxlan` custom field is enabled

**Example cleanup:**
```
interface vxlan 1
  vni 10100
    no vlan 100        # Step 1: Remove VLAN from VNI
  no vni 10100         # Step 2: Remove VNI
```

#### 3. VLAN Deletion (`cleanup_vlans.yml`)

**What it does:**
- Deletes VLANs that are no longer in use on any interface
- Runs **after** EVPN and VXLAN cleanup complete

### Cleanup Execution Order in main.yml

```yaml
# EVPN/VXLAN/VLAN cleanup order is critical (only in idempotent mode):
# 1. Remove EVPN configuration
# 2. Remove VXLAN VNI and VLAN-to-VNI mappings
# 3. Delete VLANs themselves

- name: Include EVPN cleanup tasks
  ansible.builtin.include_tasks:
    file: cleanup_evpn.yml
  when:
    - aoscx_configure_evpn | default(false) | bool
    - custom_fields.device_evpn | default(false) | bool
    - aoscx_idempotent_mode | bool  # Cleanup only in idempotent mode

- name: Include VXLAN cleanup tasks
  ansible.builtin.include_tasks:
    file: cleanup_vxlan.yml
  when:
    - aoscx_configure_vxlan | default(false) | bool
    - custom_fields.device_vxlan | default(false) | bool
    - aoscx_idempotent_mode | bool  # Cleanup only in idempotent mode

- name: Include VLAN cleanup tasks
  ansible.builtin.include_tasks:
    file: cleanup_vlans.yml
  when:
    - aoscx_configure_vlans | bool
    - aoscx_idempotent_mode | bool  # Cleanup only in idempotent mode
```

**Key point:** All three cleanup tasks require `aoscx_idempotent_mode: true`. This connects configuration and cleanup together:
- **Initial deployment** (`aoscx_idempotent_mode: false`): Only creates configurations, no cleanup
- **Ongoing management** (`aoscx_idempotent_mode: true`): Creates new configs AND removes old ones

### Cleanup Logic

**VLAN identification:**
```yaml
vlans_to_remove_from_evpn: >-
  {{
    vlans | default([])
    | selectattr('vid', 'in', vlan_changes_after.vlans_to_delete)
    | selectattr('l2vpn_termination.id', 'defined')
    | list
  }}
```

**Only VLANs with:**
- VID in `vlans_to_delete` list (not in use on interfaces)
- L2VPN termination defined (have VNI mapping)

### Cleanup Example

**Scenario:** Remove VLAN 100 (VNI 10100) from a leaf switch

**Before cleanup:**
```
vlan 100
  name "Production"

interface vxlan 1
  vni 10100
    vlan 100

evpn
  vlan 100
    rd auto
    route-target export auto
    route-target import auto
```

**After cleanup:**
```
# All EVPN, VXLAN, and VLAN config removed cleanly
```

### Verification

**Check EVPN cleanup:**
```bash
show evpn vlan
# VLAN should not appear in output
```

**Check VXLAN cleanup:**
```bash
show interface vxlan 1
# VNI should not appear in output
```

**Check VLAN deletion:**
```bash
show vlan
# VLAN should not exist
```

### Troubleshooting Cleanup

**Issue:** EVPN config not removed

**Solution:**
- Verify `device_evpn` custom field is `true` in NetBox
- Check `aoscx_configure_evpn` is enabled (default: `false`)
- Verify VLAN has L2VPN termination

**Issue:** VXLAN mapping not removed

**Solution:**
- Verify `device_vxlan` custom field is `true` in NetBox
- Check `aoscx_configure_vxlan` is enabled (default: `false`)
- Verify VLAN has L2VPN termination with identifier (VNI)

**Issue:** "VLAN in use" error during cleanup

**Solution:**
- Cleanup runs after interface cleanup, so VLANs should not be in use
- Check that interface cleanup completed successfully
- Verify EVPN cleanup ran before VXLAN cleanup
- Verify VXLAN cleanup ran before VLAN deletion

## Related Documentation

- [BGP_CONFIGURATION.md](BGP_CONFIGURATION.md) - BGP EVPN configuration
- [BGP_EVPN_FABRIC_EXAMPLE.md](BGP_EVPN_FABRIC_EXAMPLE.md) - Complete fabric example
- [BASE_CONFIGURATION.md](BASE_CONFIGURATION.md) - Base system and VLAN configuration

## Integration with Other Tasks

### Prerequisites

**Must run before EVPN/VXLAN configuration:**
1. VLANs created (`configure_vlans.yml`)
2. Interfaces configured (`configure_*_interfaces.yml`)
3. Loopback configured (`configure_loopback.yml`)
4. Underlay routing (`configure_ospf.yml`)
5. BGP EVPN (`configure_bgp.yml`)

**Must run before VLAN deletion (cleanup order):**
1. EVPN cleanup (`cleanup_evpn.yml`)
2. VXLAN cleanup (`cleanup_vxlan.yml`)
3. VLAN cleanup (`cleanup_vlans.yml`)

### Task Dependencies

**Configuration Flow:**
```
VLANs → Interfaces → Loopback
                        ↓
                  Underlay (OSPF)
                        ↓
                  Overlay Control (BGP EVPN)
                        ↓
                ┌───────┴───────┐
             EVPN            VXLAN
                └───────┬───────┘
                        ↓
                  Fabric Ready
```

**Cleanup Flow (Reverse Order):**
```
EVPN Cleanup → VXLAN Cleanup → VLAN Deletion
```

## Summary

✅ **EVPN task** - Configures EVPN for VLANs in use with auto RD/RT
✅ **VXLAN task** - Creates VNIs and maps to VLANs
✅ **EVPN cleanup** - Removes EVPN config before VLAN deletion
✅ **VXLAN cleanup** - Two-step removal (VLAN from VNI, then VNI itself)
✅ **Intelligent filtering** - Only VLANs in use get configured
✅ **NetBox integration** - Uses L2VPN terminations for VNI mapping
✅ **Custom field control** - Per-device enable/disable
✅ **Proper ordering** - Configuration and cleanup follow correct sequence

The implementation matches your production configuration exactly while integrating properly with the role's structure and NetBox inventory!
