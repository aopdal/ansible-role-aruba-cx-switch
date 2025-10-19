# EVPN/VXLAN Detection Debugging Guide

## Issue: Detection Not Working (Oct 19, 2025)

### Problem
The EVPN/VXLAN detection logic was showing "VLANs already configured: 0" even when VLANs were configured on the device.

### Symptoms
```yaml
"VLANs already configured with VXLAN: 0 - []"
"VNIs already configured: 0 - []"
"VLANs needing VXLAN config: 5"
```

But the device actually had 5 VLANs configured with VXLAN/EVPN.

### Root Causes Discovered

1. **Ansible regex_findall doesn't support `dotall` parameter** - Fixed by using `[\s\S]` instead
2. **Silent failures in data parsing** - The regex was working but data transformation was failing
3. **Lack of debugging output** - Couldn't see what the regex actually matched

### Solutions Implemented

#### 1. Split Parsing into Multiple Steps

**Before (single complex step):**
```yaml
existing_vxlan_mappings: >-
  {{
    vxlan_config_output.stdout[0] |
    regex_findall('L2VNI\\s+:\\s+(\\d+)[\\s\\S]*?VLAN\\s+:\\s+(\\d+)', multiline=True) |
    map('map', 'int') |
    list
    if vxlan_config_output.stdout is defined and vxlan_config_output.stdout | length > 0
    else []
  }}
```

**After (multiple explicit steps with error handling):**
```yaml
# Step 1: Parse raw strings from device output
- name: Parse existing VXLAN VNI-to-VLAN mappings from device (as strings)
  ansible.builtin.set_fact:
    existing_vxlan_mappings_raw: >-
      {{
        vxlan_config_output.stdout[0] |
        regex_findall('L2VNI\\s+:\\s+(\\d+)[\\s\\S]*?VLAN\\s+:\\s+(\\d+)', multiline=True)
        if vxlan_config_output.stdout is defined and vxlan_config_output.stdout | length > 0
        else []
      }}

# Step 2: Convert to integers (only if we have matches)
- name: Convert VXLAN mappings to integers
  ansible.builtin.set_fact:
    existing_vxlan_mappings: "{{ existing_vxlan_mappings_raw | map('map', 'int') | list }}"
  when:
    - existing_vxlan_mappings_raw is defined
    - existing_vxlan_mappings_raw | length > 0

# Step 3: Handle empty case explicitly
- name: Initialize empty VXLAN mappings if none found
  ansible.builtin.set_fact:
    existing_vxlan_mappings: []
  when:
    - existing_vxlan_mappings_raw is not defined or existing_vxlan_mappings_raw | length == 0
```

#### 2. Added Debug Output at Each Stage

**Raw device output:**
```yaml
- name: Debug - Raw VXLAN output from device
  ansible.builtin.debug:
    msg:
      - "=== Raw output from 'show evpn evi' ==="
      - "Output type: {{ vxlan_config_output.stdout | type_debug }}"
      - "Output length: {{ vxlan_config_output.stdout | length }}"
      - "First 500 chars: {{ vxlan_config_output.stdout[0][:500] if ... }}"
  when: aoscx_debug_mode | default(false) | bool
```

**Regex match results:**
```yaml
- name: Debug - Raw regex matches
  ansible.builtin.debug:
    msg:
      - "Raw mappings: {{ existing_vxlan_mappings_raw }}"
      - "Type: {{ existing_vxlan_mappings_raw | type_debug }}"
      - "Count: {{ existing_vxlan_mappings_raw | length }}"
  when: aoscx_debug_mode | default(false) | bool
```

#### 3. Explicit Error Handling

Added separate tasks for:
- Empty output handling
- Failed regex matches
- Integer conversion
- List extraction

Each step now has explicit `when` conditions and default values.

## How to Debug

### Enable Debug Mode
```yaml
# In your playbook or inventory
aoscx_debug_mode: true
```

### What to Look For

1. **Check raw device output** - Is it actually being captured?
   ```
   "Output type: list"
   "Output length: 1"
   "First 500 chars: L2VNI : 10100010..."
   ```

2. **Check regex matches** - Is the pattern matching?
   ```
   "Raw mappings: [['10100010', '10'], ['10100020', '20'], ...]"
   "Count: 5"
   ```

3. **Check integer conversion** - Did the conversion work?
   ```
   "VLANs already configured with VXLAN: 5 - [10, 20, 30, 40, 41]"
   "VNIs already configured: 5 - [10100010, 10100020, ...]"
   ```

### Testing the Regex Pattern

**Python test:**
```python
import re

output = """L2VNI : 10100010
    Route Distinguisher        : 172.20.1.33:10
    VLAN                       : 10
    Status                     : up

L2VNI : 10100020
    Route Distinguisher        : 172.20.1.33:20
    VLAN                       : 20
    Status                     : up"""

# Test the pattern
pattern = r'L2VNI\s+:\s+(\d+)[\s\S]*?VLAN\s+:\s+(\d+)'
matches = re.findall(pattern, output)
print(f"Matches: {matches}")
# Expected: [('10100010', '10'), ('10100020', '20')]

# Convert to integers (simulating Ansible's map('map', 'int'))
int_matches = [[int(vni), int(vlan)] for vni, vlan in matches]
print(f"As integers: {int_matches}")
# Expected: [[10100010, 10], [10100020, 20]]
```

### Common Issues

| Issue | Symptom | Fix |
|-------|---------|-----|
| No output captured | "Output length: 0" | Check device connection, command permissions |
| Regex not matching | "Count: 0" | Verify output format, test pattern in Python |
| Type conversion failed | Empty lists after conversion | Check if `map('map', 'int')` works, split into steps |
| Silent failures | No errors but wrong results | Add debug tasks at each stage |

## Files Modified

1. **tasks/configure_vxlan.yml**
   - Split parsing into 3 explicit steps
   - Added raw output debug task
   - Added regex match debug task
   - Added explicit empty list initialization

2. **tasks/configure_evpn.yml**
   - Split parsing into 3 explicit steps
   - Added raw output debug task
   - Added regex match debug task
   - Added explicit empty list initialization

## Testing Checklist

- [ ] Enable `aoscx_debug_mode: true`
- [ ] Run playbook and check "Raw output" debug messages
- [ ] Verify "Raw mappings" shows correct matches
- [ ] Confirm "VLANs already configured" shows correct count
- [ ] Test idempotency - second run should show "ok" not "changed"
- [ ] Test with no VLANs configured - should show 0
- [ ] Test with partial VLANs - should only configure missing ones

## Expected Behavior After Fix

### First Run (VLANs not configured)
```
"VLANs already configured with VXLAN: 0 - []"
"VLANs needing VXLAN config: 5"
"VLAN IDs to configure: [10, 20, 30, 40, 41]"
```
**Result:** 5 VLANs configured (changed)

### Second Run (VLANs already configured)
```
"VLANs already configured with VXLAN: 5 - [10, 20, 30, 40, 41]"
"VLANs needing VXLAN config: 0"
"VLAN IDs to configure: []"
```
**Result:** No changes (ok/skipped)

### Third Run (Add 1 new VLAN)
```
"VLANs already configured with VXLAN: 5 - [10, 20, 30, 40, 41]"
"VLANs needing VXLAN config: 1"
"VLAN IDs to configure: [50]"
```
**Result:** Only VLAN 50 configured (changed)

## Related Documentation

- `ANSIBLE_REGEX_GOTCHA.md` - Explains the dotall parameter issue
- `EVPN_VXLAN_DETECTION_FIX.md` - Original fix documentation
- `VLAN_DEVELOPER_GUIDE.md` - Testing and development guide
- `VLAN_CHANGE_IDENTIFICATION_WORKFLOW.md` - Overall workflow

## Date
- Issue discovered: October 19, 2025
- Initial fix: October 19, 2025 (regex pattern)
- Enhanced fix: October 19, 2025 (added debugging and explicit error handling)
