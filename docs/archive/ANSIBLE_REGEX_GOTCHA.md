# Ansible regex_findall Gotcha: No dotall Parameter

## The Problem

When testing the EVPN/VXLAN detection fix, we encountered this error:

```
fatal: [z13-cx3]: FAILED! => {"msg": "Unexpected templating type error occurred on ({{...}}):
regex_findall() got an unexpected keyword argument 'dotall'.
regex_findall() got an unexpected keyword argument 'dotall'"}
```

## Root Cause

**Ansible's `regex_findall` filter does NOT support the `dotall` parameter**, even though Python's `re.findall()` does.

### Python vs Ansible Regex

| Feature | Python re.findall() | Ansible regex_findall |
|---------|---------------------|----------------------|
| `multiline=True` | ✅ Supported (`re.MULTILINE`) | ✅ Supported |
| `dotall=True` | ✅ Supported (`re.DOTALL`) | ❌ **NOT Supported** |
| Flag parameter | Flags are bitmask | Flags are boolean kwargs |

## The Fix

### ❌ Wrong (doesn't work in Ansible)
```yaml
regex_findall('L2VNI\\s+:\\s+(\\d+).*?VLAN\\s+:\\s+(\\d+)', multiline=True, dotall=True)
```

### ✅ Correct (works in Ansible)
```yaml
regex_findall('L2VNI\\s+:\\s+(\\d+)[\\s\\S]*?VLAN\\s+:\\s+(\\d+)', multiline=True)
```

**Key change:** Use `[\\s\\S]` instead of `.*?`

## Understanding the Pattern

### What is `dotall`?

In Python regex, the `DOTALL` flag makes `.` (dot) match **any character including newlines**.

- Without `DOTALL`: `.` matches any character **except** `\n`
- With `DOTALL`: `.` matches **any character including** `\n`

### The `[\s\S]` Workaround

`[\s\S]` is a character class that means:
- `\s` = any whitespace (spaces, tabs, newlines)
- `\S` = any non-whitespace
- Together: **matches ANY character** (equivalent to `.` with DOTALL)

This pattern works in **both Python and Ansible** without needing the `dotall` flag!

## Practical Example

### Device Output (show evpn evi)
```
L2VNI : 10100010
    Route Distinguisher        : 172.20.1.33:10
    VLAN                       : 10
    Status                     : up
```

### Goal
Match `L2VNI : 10100010` on line 1 and `VLAN : 10` on line 3 (with content between).

### Pattern Breakdown
```
L2VNI\\s+:\\s+(\\d+)     # Match "L2VNI : 10100010", capture VNI
[\\s\\S]*?               # Match EVERYTHING in between (lazy)
VLAN\\s+:\\s+(\\d+)      # Match "VLAN : 10", capture VLAN ID
```

The `[\\s\\S]*?` will match across the newlines and intermediate content.

## Testing

### Python Test (with re.DOTALL)
```python
import re

output = """
L2VNI : 10100010
    Route Distinguisher        : 172.20.1.33:10
    VLAN                       : 10
"""

# Python way with DOTALL flag
matches = re.findall(r'L2VNI\s+:\s+(\d+).*?VLAN\s+:\s+(\d+)', output, re.DOTALL)
print(matches)  # [('10100010', '10')]
```

### Ansible-Compatible Test (with [\s\S])
```python
import re

output = """
L2VNI : 10100010
    Route Distinguisher        : 172.20.1.33:10
    VLAN                       : 10
"""

# Ansible-compatible way without flags
matches = re.findall(r'L2VNI\s+:\s+(\d+)[\s\S]*?VLAN\s+:\s+(\d+)', output)
print(matches)  # [('10100010', '10')]
```

Both produce the same result!

## Files Updated

1. **tasks/configure_vxlan.yml** - Changed regex pattern to use `[\s\S]` instead of `.*?` with dotall
2. **docs/EVPN_VXLAN_DETECTION_FIX.md** - Documented the fix and gotcha
3. **docs/VLAN_DEVELOPER_GUIDE.md** - Updated testing examples with proper patterns

## Key Takeaways

✅ **Use `[\s\S]` instead of `.` when you need to match across newlines in Ansible**

✅ **Test regex patterns in both Python and Ansible context**

✅ **Ansible's regex filters have limitations compared to Python's re module**

✅ **Always check Ansible filter documentation before using advanced regex features**

## References

- [Ansible regex_findall filter documentation](https://docs.ansible.com/ansible/latest/user_guide/playbooks_filters.html#manipulating-strings)
- [Python re.DOTALL documentation](https://docs.python.org/3/library/re.html#re.DOTALL)
- Issue discovered: October 19, 2025
- Fixed in: `tasks/configure_vxlan.yml` commit following this date

## Related Documentation

- `EVPN_VXLAN_DETECTION_FIX.md` - Full context of the EVPN/VXLAN detection fix
- `VLAN_DEVELOPER_GUIDE.md` - Testing procedures and examples
- `VLAN_CHANGE_IDENTIFICATION_WORKFLOW.md` - Overall workflow documentation
