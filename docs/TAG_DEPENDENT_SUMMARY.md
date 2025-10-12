# Tag-Dependent Includes Summary

## What Changed?

Three high-impact configuration tasks are now **tag-dependent**, meaning they only run when explicitly requested:

1. **VSX** (Virtual Switching Extension)
2. **OSPF** (Open Shortest Path First)
3. **BGP** (Border Gateway Protocol)

## Why This Matters

### Before
```bash
# Running VLAN changes would also evaluate BGP/OSPF/VSX
ansible-playbook configure_aoscx.yml -t vlans
```
- All routing protocol tasks were included
- Risk of accidental routing changes
- Slower execution due to unnecessary evaluations

### After
```bash
# Running VLAN changes ONLY touches VLANs
ansible-playbook configure_aoscx.yml -t vlans
```
- Routing protocols completely skipped
- Safer day-to-day operations
- Faster execution

## Implementation

Each task now checks if its tag was explicitly requested:

```yaml
when:
  - aoscx_configure_bgp | bool  # Still respects enable flag
  - "'bgp' in ansible_run_tags or 'routing' in ansible_run_tags or 'all' in ansible_run_tags"
```

## Behavior Matrix

| Playbook Command | VLANs | Interfaces | BGP | OSPF | VSX | Notes |
|------------------|-------|------------|-----|------|-----|-------|
| `ansible-playbook configure_aoscx.yml` | ✅ | ✅ | ✅ | ✅ | ✅ | Full run |
| `ansible-playbook configure_aoscx.yml -t vlans` | ✅ | ❌ | ❌ | ❌ | ❌ | **Safe!** |
| `ansible-playbook configure_aoscx.yml -t interfaces` | ❌ | ✅ | ❌ | ❌ | ❌ | **Safe!** |
| `ansible-playbook configure_aoscx.yml -t routing` | ❌ | ❌ | ✅ | ✅ | ❌ | Explicit |
| `ansible-playbook configure_aoscx.yml -t bgp` | ❌ | ❌ | ✅ | ❌ | ❌ | Explicit |
| `ansible-playbook configure_aoscx.yml -t ospf` | ❌ | ❌ | ❌ | ✅ | ❌ | Explicit |
| `ansible-playbook configure_aoscx.yml -t vsx` | ❌ | ❌ | ❌ | ❌ | ✅ | Explicit |

## Design Decisions

### ✅ Tag-Dependent (Requires Explicit Request)
- **BGP**: High-impact routing protocol
- **OSPF**: High-impact routing protocol
- **VSX**: High-availability configuration

### ❌ NOT Tag-Dependent (Runs When Tagged)
- **Cleanup**: Protected by `aoscx_idempotent_mode` flag
- **EVPN/VXLAN**: Needs to run with VLAN changes
- **VLANs**: Common operational changes
- **Interfaces**: Frequent updates
- **Base Config**: Low-risk (banner, NTP, DNS)

## Quick Test

Verify tag-dependent behavior works:

```bash
# Should NOT show BGP, OSPF, or VSX
ansible-playbook -i netbox_inv_int.yml configure_aoscx.yml -l z13-cx3 -t vlans --list-tasks | grep -E "(OSPF|BGP|VSX)"

# Should show BGP and OSPF
ansible-playbook -i netbox_inv_int.yml configure_aoscx.yml -l z13-cx3 -t routing --list-tasks | grep -E "(OSPF|BGP)"

# Should show everything
ansible-playbook -i netbox_inv_int.yml configure_aoscx.yml -l z13-cx3 --list-tasks | grep -E "(OSPF|BGP|VSX)"
```

## Real-World Impact

### Day-to-Day Operations (Safer)
```bash
# Add VLANs without routing risk
ansible-playbook configure_aoscx.yml -t vlans

# Update interfaces without routing risk
ansible-playbook configure_aoscx.yml -t interfaces

# Change banner/NTP without routing risk
ansible-playbook configure_aoscx.yml -t base_config
```

### Intentional Changes (Explicit)
```bash
# Update BGP configuration
ansible-playbook configure_aoscx.yml -t bgp

# Update all routing
ansible-playbook configure_aoscx.yml -t routing

# Full deployment
ansible-playbook configure_aoscx.yml
```

## Files Modified

1. **tasks/main.yml**: Added `ansible_run_tags` checks to BGP, OSPF, VSX includes
2. **docs/TAG_DEPENDENT_INCLUDES.md**: Complete documentation of pattern and rationale
3. **docs/TAG_DEPENDENT_TESTING.md**: Test procedures and verification scripts

## Related Documentation

- [Tag Inheritance Fix](TAG_INHERITANCE_FIX.md) - How tag filtering works
- [Quick Reference](QUICK_REFERENCE.md) - Common tag combinations
- [Testing Guide](TESTING.md) - Full testing procedures
