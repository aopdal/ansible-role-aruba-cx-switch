# Testing Tag-Dependent Includes

## Quick Verification Commands

### Test 1: VLAN Changes (Should NOT include routing)
```bash
ansible-playbook -i netbox_inv_int.yml configure_aoscx.yml -l z13-cx3 -t vlans --list-tasks | grep -E "(OSPF|BGP|VSX)"
```
**Expected**: No output (routing tasks not included)

### Test 2: Explicit Routing (Should include BGP and OSPF)
```bash
ansible-playbook -i netbox_inv_int.yml configure_aoscx.yml -l z13-cx3 -t routing --list-tasks | grep -E "(OSPF|BGP)"
```
**Expected**: Shows "Include OSPF configuration tasks" and "Include BGP configuration tasks"

### Test 3: Explicit BGP Only
```bash
ansible-playbook -i netbox_inv_int.yml configure_aoscx.yml -l z13-cx3 -t bgp --list-tasks
```
**Expected**: Shows only BGP tasks, not OSPF or VSX

### Test 4: Full Run (Should include everything)
```bash
ansible-playbook -i netbox_inv_int.yml configure_aoscx.yml -l z13-cx3 --list-tasks | grep -E "(OSPF|BGP|VSX)"
```
**Expected**: Shows all three task includes

## Detailed Test Matrix

| Command | VLANs | Interfaces | OSPF | BGP | VSX | Base Config |
|---------|-------|------------|------|-----|-----|-------------|
| `-t vlans` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `-t interfaces` | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `-t routing` | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ |
| `-t ospf` | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| `-t bgp` | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| `-t vsx` | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| `-t base_config` | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| No tags | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

## Real-World Scenarios

### Scenario 1: Adding VLANs to Production
```bash
# Safe - won't touch routing protocols
ansible-playbook -i netbox_inv_int.yml configure_aoscx.yml -l production-switches -t vlans
```

### Scenario 2: Updating BGP Neighbors
```bash
# Explicit - only BGP changes
ansible-playbook -i netbox_inv_int.yml configure_aoscx.yml -l border-routers -t bgp
```

### Scenario 3: Initial Switch Deployment
```bash
# Full run - everything including routing
ansible-playbook -i netbox_inv_int.yml configure_aoscx.yml -l new-switch
```

### Scenario 4: Emergency Interface Fix
```bash
# Quick - no routing protocol risk
ansible-playbook -i netbox_inv_int.yml configure_aoscx.yml -l problematic-switch -t interfaces
```

## Verification Script

Create a test script to verify tag behavior:

```bash
#!/bin/bash
# test-tag-dependencies.sh

INVENTORY="netbox_inv_int.yml"
PLAYBOOK="configure_aoscx.yml"
LIMIT="z13-cx3"

echo "=== Testing Tag Dependencies ==="
echo

echo "1. Testing -t vlans (should NOT show routing):"
ansible-playbook -i "$INVENTORY" "$PLAYBOOK" -l "$LIMIT" -t vlans --list-tasks | grep -E "(OSPF|BGP|VSX)" && echo "❌ FAIL: Routing tasks included" || echo "✅ PASS: No routing tasks"
echo

echo "2. Testing -t routing (should show OSPF and BGP):"
ROUTING_COUNT=$(ansible-playbook -i "$INVENTORY" "$PLAYBOOK" -l "$LIMIT" -t routing --list-tasks | grep -E "(OSPF|BGP)" | wc -l)
if [ "$ROUTING_COUNT" -eq 2 ]; then
    echo "✅ PASS: Both routing protocols included"
else
    echo "❌ FAIL: Expected 2 routing tasks, got $ROUTING_COUNT"
fi
echo

echo "3. Testing no tags (should show everything):"
ALL_COUNT=$(ansible-playbook -i "$INVENTORY" "$PLAYBOOK" -l "$LIMIT" --list-tasks | grep -E "(OSPF|BGP|VSX)" | wc -l)
if [ "$ALL_COUNT" -eq 3 ]; then
    echo "✅ PASS: All high-impact tasks included"
else
    echo "❌ FAIL: Expected 3 tasks, got $ALL_COUNT"
fi
echo

echo "=== Test Complete ==="
```

Make it executable:
```bash
chmod +x test-tag-dependencies.sh
./test-tag-dependencies.sh
```
