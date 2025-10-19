# EVPN/VXLAN Detection Fix

## Issue

The logic for detecting existing EVPN and VXLAN/VNI configurations was failing because:

1. **EVPN detection** used `show evpn vlan | include "VLAN ID"` which didn't provide the right output format
2. **VXLAN detection** used `show interface vxlan 1` which also didn't match the expected format

## Root Cause

The commands were returning output that didn't match the regex patterns, causing:
- Existing EVPN VLANs not being detected
- Existing VXLAN/VNI mappings not being detected
- Attempted re-configuration of already configured VLANs
- Potential configuration errors

## Solution

### Changed Command: `show evpn evi`

Both `configure_evpn.yml` and `configure_vxlan.yml` now use the same command:

```yaml
- name: Gather current EVPN/VXLAN configuration
  arubanetworks.aoscx.aoscx_command:
    commands:
      - show evpn evi
```

This command provides **both** EVPN and VXLAN information in a single output:

```
L2VNI : 10100010
    Route Distinguisher        : 172.20.1.33:10
    VLAN                       : 10
    Status                     : up
    RT Import                  : 65005:10
    RT Export                  : 65005:10
    ...
```

### Updated Regex Patterns

#### EVPN Detection (`configure_evpn.yml`)

**Before:**
```yaml
regex_findall('(\\d+)')  # Too generic, matches any number
```

**After:**
```yaml
regex_findall('VLAN\\s+:\\s+(\\d+)')  # Specific: matches "VLAN : 10"
```

**Result:** Extracts VLAN IDs: `[10, 20, 30, 40, 41]`

#### VXLAN Detection (`configure_vxlan.yml`)

**Before:**
```yaml
regex_findall('vni (\\d+)\\s+vlan (\\d+)')  # Wrong format
```

**After (Initial - Had Error):**
```yaml
regex_findall('L2VNI\\s+:\\s+(\\d+).*?VLAN\\s+:\\s+(\\d+)', multiline=True, dotall=True)
```

**After (Fixed - Final):**
```yaml
regex_findall('L2VNI\\s+:\\s+(\\d+)[\\s\\S]*?VLAN\\s+:\\s+(\\d+)', multiline=True)
```
> **Note:** Ansible's `regex_findall` doesn't support `dotall` parameter. Use `[\\s\\S]` (matches any whitespace or non-whitespace character) instead of `.*?` to match across newlines.

**Result:** Extracts VNI-to-VLAN mappings: `[[10100010, 10], [10100020, 20], ...]`

## Files Modified

1. `tasks/configure_evpn.yml`
   - Changed command to `show evpn evi`
   - Updated regex pattern to `VLAN\\s+:\\s+(\\d+)`

2. `tasks/configure_vxlan.yml`
   - Changed command to `show evpn evi`
   - Updated regex pattern to match L2VNI and VLAN in EVI output

3. `docs/VLAN_CHANGE_IDENTIFICATION_WORKFLOW.md`
   - Added "Device Command Optimization" section
   - Documented the new command and regex patterns

4. `docs/VLAN_DEVELOPER_GUIDE.md`
   - Added testing section for EVPN/VXLAN detection
   - Included Python test examples for regex patterns

## Benefits

✅ **Accurate Detection**: Correctly identifies existing EVPN and VXLAN configurations
✅ **Efficiency**: Single command provides both EVPN and VXLAN information
✅ **Idempotency**: Prevents re-configuration of already configured VLANs
✅ **Reliability**: Specific regex patterns avoid false matches

## Testing

### Manual Testing

```bash
# On the switch
show evpn evi

# Should show all configured EVIs with VLANs
```

### Playbook Testing

```bash
# Run with debug enabled
ansible-playbook -vv playbook.yml --tags evpn,vxlan

# Check for:
# - "VLANs already configured with EVPN: X"
# - "VLANs already configured with VXLAN: X"
# - No changes on second run (idempotent)
```

### Regex Testing

```python
import re

output = """
L2VNI : 10100010
    Route Distinguisher        : 172.20.1.33:10
    VLAN                       : 10
    Status                     : up

L2VNI : 10100020
    VLAN                       : 20
"""

# Test EVPN regex
vlans = re.findall(r'VLAN\s+:\s+(\d+)', output)
assert vlans == ['10', '20'], f"Expected ['10', '20'], got {vlans}"

# Test VXLAN regex
mappings = re.findall(r'L2VNI\s+:\s+(\d+).*?VLAN\s+:\s+(\d+)', output, re.DOTALL)
assert mappings == [('10100010', '10'), ('10100020', '20')]

print("✅ All regex tests passed")
```

## Verification

### Before Fix
```
TASK [Configure EVPN] *****
changed: [switch] => (item=VLAN 10)  ← Should be "ok" if already configured
changed: [switch] => (item=VLAN 20)  ← Should be "ok" if already configured
```

### After Fix
```
TASK [Gather current EVPN configuration] *****
ok: [switch]

TASK [Parse existing EVPN VLANs] *****
ok: [switch] => existing_evpn_vlans: [10, 20, 30, 40, 41]

TASK [Configure EVPN] *****
skipping: [switch] => (item=VLAN 10)  ← Correctly skipped (already configured)
skipping: [switch] => (item=VLAN 20)  ← Correctly skipped (already configured)
```

## Related Issues

This fix ensures the refactored VLAN workflow works correctly by:
- Detecting existing configurations accurately
- Preventing duplicate configurations
- Maintaining idempotency
- Supporting the cleanup phase correctly

## Version

- **Date**: October 19, 2025
- **Impact**: Critical fix for EVPN/VXLAN configuration detection
- **Severity**: High (affects idempotency and configuration accuracy)
