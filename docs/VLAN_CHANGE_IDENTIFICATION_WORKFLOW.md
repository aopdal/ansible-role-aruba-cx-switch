# VLAN Change Identification Workflow

## Overview

### Single Source of Truth: `identify_vlan_changes.yml`

The `identify_vlan_changes.yml` task file is now the **single source of truth** for all VLAN change calculations. It:

1. **Fetches VLANs from NetBox** (if not already provided)
2. **Gathers current VLAN state** from the device
3. **Calculates VLANs in use** by interfaces
4. **Determines VLAN changes** needed (create/delete)

### Facts Set by `identify_vlan_changes.yml`

This task sets the following facts used by all downstream tasks:

| Fact | Description | Used By |
|------|-------------|---------|
| `vlans` | VLANs available from NetBox (desired state) | All VLAN-related tasks |
| `vlans_in_use` | VLANs currently in use on interfaces | configure_vlans.yml, configure_evpn.yml, configure_vxlan.yml |
| `vlan_changes` | VLANs to create/delete based on analysis | configure_vlans.yml, cleanup_*.yml |

### Task Execution Order

#### Configuration Phase (Create/Update)

```
1. identify_vlan_changes.yml  ← Analyze VLANs ONCE
   ↓
2. configure_vlans.yml         ← Create VLANs
   ↓
3. configure_evpn.yml          ← Configure EVPN for VLANs
   ↓
4. configure_vxlan.yml         ← Configure VXLAN/VNI for VLANs
```

#### Cleanup Phase (Delete) - Only in Idempotent Mode

```
1. identify_vlan_changes.yml  ← RE-analyze VLANs based on current state
   ↓
2. cleanup_evpn.yml            ← Remove EVPN config for deleted VLANs
   ↓
3. cleanup_vxlan.yml           ← Remove VXLAN/VNI for deleted VLANs
   ↓
4. cleanup_vlans.yml           ← Delete VLANs themselves
```

### Why Run `identify_vlan_changes.yml` Twice?

The task runs **twice** (before configuration and before cleanup) for important reasons:

1. **Before Configuration**: Analyzes initial state to determine what to create
2. **Before Cleanup**: Re-analyzes after interface changes to determine what can be safely deleted

Between these two runs, interface configurations may change (L2 interfaces updated, LAGs modified, etc.), which affects what VLANs are "in use" and therefore what can be deleted.

## Implementation Details

### Assertions for Safety

All dependent tasks now include assertions to verify that `identify_vlan_changes.yml` has run:

```yaml
- name: Verify VLAN analysis has been performed
  ansible.builtin.assert:
    that:
      - vlans is defined
      - vlans_in_use is defined
      - vlan_changes is defined
    fail_msg: "ERROR: identify_vlan_changes.yml must run before this task"
    success_msg: "VLAN analysis completed - proceeding with task"
```

This prevents tasks from running with stale or missing data.

### Removed Duplicate Logic

The following duplicate logic was **removed** from downstream tasks:

- ❌ Fetching VLANs from NetBox API
- ❌ Calculating VLANs in use
- ❌ Determining VLAN changes

These tasks now simply **use** the facts set by `identify_vlan_changes.yml`.

### Device Command Optimization

Both EVPN and VXLAN configuration tasks use the same efficient command to check existing configuration:

```yaml
- name: Gather current EVPN/VXLAN configuration
  arubanetworks.aoscx.aoscx_command:
    commands:
      - show evpn evi
```

The `show evpn evi` command provides both EVPN VLANs and VXLAN/VNI mappings in a single output, eliminating the need for multiple device queries. The output format is:

```
L2VNI : 10100010
    VLAN                       : 10
    Status                     : up
    ...
```

**Regex patterns used:**

- EVPN VLANs: `VLAN\s+:\s+(\d+)` - Extracts VLAN IDs
- VXLAN VNI-to-VLAN mappings: `L2VNI\s+:\s+(\d+).*?VLAN\s+:\s+(\d+)` - Extracts both VNI and VLAN ID

## Benefits

- ✅ **Consistency**: All tasks work from the same VLAN analysis
- ✅ **Maintainability**: VLAN logic centralized in one place
- ✅ **Safety**: Assertions prevent tasks running with stale data
- ✅ **Clarity**: Clear execution order documented
- ✅ **Idempotency**: Proper re-analysis before cleanup ensures safe deletions

## Files Modified

### Primary Task Files

- `tasks/identify_vlan_changes.yml` - Enhanced as single source of truth
- `tasks/main.yml` - Added identify_vlan_changes.yml before configuration tasks

### Configuration Tasks (Simplified)

- `tasks/configure_vlans.yml` - Removed duplicate logic, added assertion
- `tasks/configure_evpn.yml` - Removed duplicate logic, added assertion
- `tasks/configure_vxlan.yml` - Removed duplicate logic, added assertion

### Cleanup Tasks (Verified)

- `tasks/cleanup_vlans.yml` - Added assertion
- `tasks/cleanup_evpn.yml` - Added assertion
- `tasks/cleanup_vxlan.yml` - Added assertion

## Testing Recommendations

When testing this refactored workflow:

1. **Test Configuration**: Verify VLANs, EVPN, and VXLAN are created correctly
2. **Test Idempotency**: Run twice, second run should make no changes
3. **Test Cleanup**: Enable idempotent mode, remove VLANs from NetBox, verify cleanup
4. **Test Assertions**: Try running tasks out of order to verify assertions catch issues
5. **Test Debug Output**: Enable debug mode to see VLAN analysis results

## Debug Mode

Enable debug output to see VLAN analysis results:

```yaml
aoscx_debug: true
# or
ansible-playbook -vv playbook.yml
```

Debug output includes:

- VLANs available from NetBox
- VLANs in use on interfaces
- VLANs to create
- VLANs to delete
- Protected VLANs (in use, cannot delete)

## Related Documentation

- [BGP Configuration](BGP_CONFIGURATION.md)
- [Base Configuration](BASE_CONFIGURATION.md)
- [Contributing Guide](CONTRIBUTING.md)
