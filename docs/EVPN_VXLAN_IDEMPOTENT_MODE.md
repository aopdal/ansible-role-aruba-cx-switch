# EVPN/VXLAN Cleanup with Idempotent Mode - Final Implementation

## Summary

Successfully implemented EVPN and VXLAN cleanup tasks that are **connected to the idempotent mode**, ensuring proper lifecycle management.

## Key Changes

### 1. Added `aoscx_idempotent_mode` Requirement

All three cleanup tasks now require `aoscx_idempotent_mode: true`:

```yaml
# tasks/main.yml

- name: Include EVPN cleanup tasks
  when:
    - aoscx_configure_evpn | default(false) | bool
    - custom_fields.device_evpn | default(false) | bool
    - aoscx_idempotent_mode | bool  # ✅ ADDED

- name: Include VXLAN cleanup tasks
  when:
    - aoscx_configure_vxlan | default(false) | bool
    - custom_fields.device_vxlan | default(false) | bool
    - aoscx_idempotent_mode | bool  # ✅ ADDED

- name: Include VLAN cleanup tasks
  when:
    - aoscx_configure_vlans | bool
    - aoscx_idempotent_mode | bool  # ✅ ALREADY EXISTED
```

## Why This Matters

### Configuration and Cleanup Connected Together

| Mode | Variable | Use Case | Behavior |
|------|----------|----------|----------|
| **Initial Deployment** | `aoscx_idempotent_mode: false` | First-time setup | ✅ Configure EVPN/VXLAN<br>❌ No cleanup |
| **Ongoing Management** | `aoscx_idempotent_mode: true` | Day-to-day ops | ✅ Configure EVPN/VXLAN<br>✅ Cleanup old configs |

### Benefits

✅ **Safe Initial Deployment**
- First-time fabric deployment won't trigger cleanup
- Only creates configurations, never removes

✅ **Connected Lifecycle**
- Configuration and cleanup work together
- VLANs, EVPN, and VXLAN all follow same pattern

✅ **Explicit Control**
- Clear mode selection via single variable
- Predictable behavior

✅ **Proper Ordering Enforced**
```
EVPN Cleanup → VXLAN Cleanup → VLAN Deletion
```

✅ **Consistent with Role Pattern**
- Matches existing L2 interface cleanup behavior
- Follows established role conventions

## Files Modified

### `tasks/main.yml`
- Added `aoscx_idempotent_mode | bool` to EVPN cleanup when condition
- Added `aoscx_idempotent_mode | bool` to VXLAN cleanup when condition
- Updated comments to reflect "only in idempotent mode"

### `docs/EVPN_VXLAN_CONFIGURATION.md`
- Updated cleanup overview to explain idempotent mode requirement
- Updated cleanup execution order showing idempotent mode checks
- Added mode behavior explanation (initial vs ongoing)

### `docs/EVPN_VXLAN_CLEANUP_SUMMARY.md`
- Updated critical ordering section with idempotent mode explanation
- Updated main.yml structure showing CRITICAL comments
- Updated usage section with mode behavior table

## Files Created

### `docs/EVPN_VXLAN_MODES.md`
Complete guide showing:
- Mode comparison (initial deployment vs ongoing management)
- Behavior details for each mode
- Configuration and cleanup flows
- Example scenarios (initial deployment, removing VLAN, adding VLAN)
- Control variables
- Decision matrix
- Best practices

## Complete Cleanup Flow

```
┌──────────────────────────────────────┐
│ Check: aoscx_idempotent_mode?        │
└────────────┬─────────────────────────┘
             │
       ┌─────┴─────┐
       ↓           ↓
    false        true
       ↓           ↓
   ❌ SKIP    ✅ CONTINUE
    cleanup      to cleanup
       │           │
       │           ↓
       │      ┌─────────────────────────┐
       │      │ cleanup_evpn.yml         │
       │      │ Remove EVPN config       │
       │      └────────┬─────────────────┘
       │               ↓
       │      ┌─────────────────────────┐
       │      │ cleanup_vxlan.yml        │
       │      │ Remove VNI and mappings  │
       │      └────────┬─────────────────┘
       │               ↓
       │      ┌─────────────────────────┐
       │      │ cleanup_vlans.yml        │
       │      │ Delete VLANs             │
       │      └─────────────────────────┘
       │
       └─────────────────────────────────→
                  END
```

## Example Playbook Usage

### Initial Deployment (No Cleanup)

```yaml
---
- name: Deploy EVPN/VXLAN Fabric
  hosts: leaf_switches
  gather_facts: false

  vars:
    # Initial deployment mode - only create configs
    aoscx_idempotent_mode: false

    # Enable configuration tasks
    aoscx_configure_vlans: true
    aoscx_configure_evpn: true
    aoscx_configure_vxlan: true

  roles:
    - aopdal.aruba_cx_switch
```

**Result:**
- ✅ Creates VLANs
- ✅ Configures EVPN for VLANs in use
- ✅ Configures VXLAN VNIs and mappings
- ❌ No cleanup runs

### Ongoing Management (With Cleanup)

```yaml
---
- name: Manage EVPN/VXLAN Fabric
  hosts: leaf_switches
  gather_facts: false

  vars:
    # Ongoing management mode - create AND cleanup
    aoscx_idempotent_mode: true

    # Enable configuration tasks
    aoscx_configure_vlans: true
    aoscx_configure_evpn: true
    aoscx_configure_vxlan: true

  roles:
    - aopdal.aruba_cx_switch
```

**Result:**
- ✅ Creates new VLANs
- ✅ Configures EVPN for VLANs in use
- ✅ Configures VXLAN VNIs and mappings
- ✅ Removes EVPN for deleted VLANs
- ✅ Removes VXLAN VNIs for deleted VLANs
- ✅ Deletes VLANs not in use

## Verification

### Check Cleanup Conditions

```bash
# All three conditions must be true for cleanup to run:

1. Configuration enabled:
   - aoscx_configure_evpn: true (for EVPN cleanup)
   - aoscx_configure_vxlan: true (for VXLAN cleanup)
   - aoscx_configure_vlans: true (for VLAN cleanup)

2. Custom field enabled:
   - device_evpn: true (for EVPN cleanup)
   - device_vxlan: true (for VXLAN cleanup)

3. Idempotent mode enabled:
   - aoscx_idempotent_mode: true (for ALL cleanups)
```

### Check During Playbook Run

Look for these task names:
```
TASK [aopdal.aruba_cx_switch : Include EVPN cleanup tasks]
TASK [aopdal.aruba_cx_switch : Include VXLAN cleanup tasks]
TASK [aopdal.aruba_cx_switch : Include VLAN cleanup tasks]
```

If `aoscx_idempotent_mode: false`, these tasks will show as "skipped".

## Documentation Updates

All documentation now reflects the idempotent mode requirement:

1. **EVPN_VXLAN_CONFIGURATION.md**
   - Cleanup Process section explains idempotent mode
   - Shows mode behavior in examples

2. **EVPN_VXLAN_CLEANUP_SUMMARY.md**
   - Critical ordering includes idempotent mode
   - Usage section shows mode table

3. **EVPN_VXLAN_MODES.md** (NEW)
   - Complete guide to both modes
   - Example scenarios
   - Best practices

## Testing Recommendations

### Test 1: Initial Deployment (No Cleanup)

```bash
# Set idempotent_mode to false
ansible-playbook playbook.yml -e "aoscx_idempotent_mode=false"

# Verify:
# - EVPN configured: show evpn vlan
# - VXLAN configured: show interface vxlan 1
# - No cleanup tasks ran (check playbook output)
```

### Test 2: Ongoing Management (With Cleanup)

```bash
# Remove VLAN 100 from all interfaces in NetBox
# Run with idempotent_mode true
ansible-playbook playbook.yml -e "aoscx_idempotent_mode=true"

# Verify:
# - EVPN cleanup ran: VLAN 100 removed from "show evpn vlan"
# - VXLAN cleanup ran: VNI removed from "show interface vxlan 1"
# - VLAN deleted: VLAN 100 not in "show vlan"
```

### Test 3: Mode Toggle

```bash
# Run 1: Initial deployment
ansible-playbook playbook.yml -e "aoscx_idempotent_mode=false"

# Run 2: Switch to ongoing management
ansible-playbook playbook.yml -e "aoscx_idempotent_mode=true"

# Verify:
# - Run 1: No cleanup tasks
# - Run 2: Cleanup tasks run if needed
```

## Summary

✅ **EVPN cleanup** requires `aoscx_idempotent_mode: true`
✅ **VXLAN cleanup** requires `aoscx_idempotent_mode: true`
✅ **VLAN cleanup** requires `aoscx_idempotent_mode: true`
✅ **All three connected** via same variable
✅ **Proper ordering** enforced: EVPN → VXLAN → VLAN
✅ **Safe initial deployment** with `false` mode
✅ **Full lifecycle management** with `true` mode
✅ **Documentation complete** for both modes

The EVPN/VXLAN configuration and cleanup implementation is now complete and properly connected to the role's idempotent mode!
