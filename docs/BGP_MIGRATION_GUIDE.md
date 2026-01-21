# Quick Migration Guide: config_context → netbox-bgp Plugin

## Prerequisites

✅ NetBox BGP plugin installed
✅ pynetbox >= 7.3.0 (already in requirements-test.txt)
✅ NETBOX_API and NETBOX_TOKEN environment variables set

## 5-Step Migration Process

### Step 1: Verify Plugin Installation

```bash
# Check plugin is installed
curl -H "Authorization: Token $NETBOX_TOKEN" \
  "$NETBOX_API/api/plugins/installed-plugins/" | jq '.[] | select(.name == "netbox_bgp")'

# Expected output:
# {
#   "name": "netbox_bgp",
#   "package": "netbox-bgp",
#   "version": "0.17.0"
# }
```

### Step 2: Create AS Objects in NetBox

```bash
# Via UI: Plugins → BGP → ASNs → Add
# Or via API:
curl -X POST "$NETBOX_API/api/plugins/bgp/asn/" \
  -H "Authorization: Token $NETBOX_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "asn": 65000,
    "description": "Private AS for EVPN Fabric"
  }'
```

### Step 3: Create BGP Sessions

**For each device, create sessions for all neighbors.**

#### Example: leaf-1 → spine-1

```bash
curl -X POST "$NETBOX_API/api/plugins/bgp/session/" \
  -H "Authorization: Token $NETBOX_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "leaf-1-to-spine-1-evpn",
    "device": 123,
    "status": "planned",
    "local_as": 1,
    "remote_as": 1,
    "local_address": 456,
    "remote_address": 789,
    "description": "EVPN overlay to spine-1"
  }'
```

**Field IDs:**

- `device`: Device object ID (get from `/api/dcim/devices/`)
- `local_as`: ASN object ID (get from `/api/plugins/bgp/asn/`)
- `local_address`: IP Address ID (get from `/api/ipam/ip-addresses/`)
- `remote_address`: IP Address ID

### Step 4: Test with One Device

```bash
# Test with debug mode
ansible-playbook -i netbox_inv_int.yml configure_aoscx.yml \
  -l leaf-1 \
  -t bgp \
  -e aoscx_debug=true \
  --check

# Expected output:
# "NetBox BGP plugin: Available ✓"
# "BGP Configuration Source: netbox-bgp plugin"
# "Plugin Sessions: 2"

# Apply if test successful
ansible-playbook -i netbox_inv_int.yml configure_aoscx.yml \
  -l leaf-1 \
  -t bgp
```

### Step 5: Change Session Status to Active

```bash
# In NetBox UI: Change status from "Planned" to "Active"
# Or via API:
curl -X PATCH "$NETBOX_API/api/plugins/bgp/session/42/" \
  -H "Authorization: Token $NETBOX_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "active"}'
```

## Quick Create Script (Python)

```python
#!/usr/bin/env python3
"""Create BGP sessions from config_context data"""

import pynetbox
import os

# Connect to NetBox
nb = pynetbox.api(
    url=os.getenv('NETBOX_API'),
    token=os.getenv('NETBOX_TOKEN')
)

def migrate_device_bgp(device_name):
    """Migrate one device from config_context to netbox-bgp plugin"""

    # Get device
    device = nb.dcim.devices.get(name=device_name)
    if not device:
        print(f"Device {device_name} not found")
        return

    # Get AS object (create if needed)
    bgp_as = device.config_context.get('bgp_as')
    asn_obj = nb.plugins.bgp.asn.get(asn=bgp_as)
    if not asn_obj:
        asn_obj = nb.plugins.bgp.asn.create(asn=bgp_as, description=f"AS {bgp_as}")

    # Get local address (loopback)
    local_ip = device.custom_fields.get('device_bgp_routerid')
    local_addr = nb.ipam.ip_addresses.get(address=f"{local_ip}/32")

    # Create session for each peer
    for peer in device.config_context.get('bgp_peers', []):
        peer_ip = peer['peer']
        remote_addr = nb.ipam.ip_addresses.get(address=f"{peer_ip}/32")

        # Create session
        session = nb.plugins.bgp.session.create(
            name=f"{device_name}-to-{peer_ip}",
            device=device.id,
            status='planned',
            local_as=asn_obj.id,
            remote_as=asn_obj.id,  # iBGP
            local_address=local_addr.id if local_addr else None,
            remote_address=remote_addr.id if remote_addr else None,
            description=f"EVPN overlay session"
        )
        print(f"Created session: {session.name}")

# Migrate devices
devices_to_migrate = ['leaf-1', 'leaf-2', 'spine-1', 'spine-2']
for device in devices_to_migrate:
    print(f"\nMigrating {device}...")
    migrate_device_bgp(device)
```

## Bulk Migration Script

```bash
#!/bin/bash
# migrate-bgp-sessions.sh

DEVICES=(
  "leaf-1"
  "leaf-2"
  "leaf-3"
  "leaf-4"
  "spine-1"
  "spine-2"
)

echo "=== BGP Migration to netbox-bgp Plugin ==="
echo

for device in "${DEVICES[@]}"; do
  echo "Testing $device..."

  # Check if device has sessions in plugin
  ansible-playbook -i netbox_inv_int.yml configure_aoscx.yml \
    -l "$device" \
    -t bgp \
    -e aoscx_debug=true \
    --check 2>&1 | grep "Plugin Sessions"

  # If plugin sessions found, deploy
  if [ $? -eq 0 ]; then
    echo "Deploying $device with netbox-bgp plugin..."
    ansible-playbook -i netbox_inv_int.yml configure_aoscx.yml \
      -l "$device" \
      -t bgp
  else
    echo "Skipping $device (no plugin sessions yet)"
  fi

  echo
  sleep 2
done

echo "=== Migration Complete ==="
```

## Verification Commands

```bash
# 1. Check plugin sessions in NetBox
curl -H "Authorization: Token $NETBOX_TOKEN" \
  "$NETBOX_API/api/plugins/bgp/session/" | jq '.results[] | {name, device: .device.name, status: .status.value}'

# 2. Test Ansible query
ansible-playbook -i netbox_inv_int.yml configure_aoscx.yml \
  -t bgp \
  -e aoscx_debug=true \
  --check | grep "Configuration Source"

# 3. Verify on device
ssh admin@leaf-1 "show bgp summary"
```

## Rollback Plan

If issues occur, disable plugin and use config_context:

```bash
# Option 1: Disable plugin query
ansible-playbook configure_aoscx.yml -l leaf-1 -t bgp \
  -e aoscx_use_netbox_bgp_plugin=false

# Option 2: Change session status to offline
# In NetBox: Set session status to "Offline"

# Option 3: Delete plugin sessions (temporary)
# Keep config_context as fallback
```

## Post-Migration Cleanup

After all devices are migrated and stable:

```bash
# 1. Document migration in NetBox
# Add note to each device: "Migrated to netbox-bgp plugin on YYYY-MM-DD"

# 2. Remove BGP data from config_context (optional)
# Keep other config_context data (NTP, DNS, etc.)

# 3. Update documentation
# Mark devices as "netbox-bgp plugin" in your documentation

# 4. Keep custom fields (still used)
# device_bgp: true/false (enable/disable)
# device_bgp_routerid: can be removed if using plugin
```

## Comparison: Before/After

### Before (config_context)

**NetBox Config Context:**
```json
{
  "bgp_as": 65000,
  "bgp_peers": [
    {"peer": "10.255.255.1", "remote_as": 65000},
    {"peer": "10.255.255.2", "remote_as": 65000}
  ]
}
```

**Ansible Output:**
```
TASK [Configure BGP neighbors for EVPN from config_context (fallback)]
ok: [leaf-1] => (item=10.255.255.1)
ok: [leaf-1] => (item=10.255.255.2)
```

### After (netbox-bgp plugin)

**NetBox BGP Plugin:**

- 2 BGP Session objects
- Status: Active
- Full relationship tracking

**Ansible Output:**

```
TASK [Configure BGP EVPN neighbors from netbox-bgp plugin]
ok: [leaf-1] => (item=leaf-1-to-spine-1-evpn)
ok: [leaf-1] => (item=leaf-1-to-spine-2-evpn)
```

## Migration Timeline Example

| Week | Action | Devices |
| ---- | ------ | ------- |
| 1 | Install plugin, create AS | - |
| 2 | Create sessions for spines (status: planned) | spine-1, spine-2 |
| 3 | Test & activate spine sessions | spine-1, spine-2 |
| 4 | Create sessions for leaf-1, leaf-2 | leaf-1, leaf-2 |
| 5 | Test & activate leaf-1, leaf-2 | leaf-1, leaf-2 |
| 6 | Create sessions for leaf-3, leaf-4 | leaf-3, leaf-4 |
| 7 | Test & activate leaf-3, leaf-4 | leaf-3, leaf-4 |
| 8 | Cleanup config_context, document | All |

## Common Issues

### Issue 1: IP Address Not Found

**Error:**

```
"local_address": null
```

**Solution:** Create loopback IP in NetBox IPAM first

```bash
curl -X POST "$NETBOX_API/api/ipam/ip-addresses/" \
  -H "Authorization: Token $NETBOX_TOKEN" \
  -d '{
    "address": "10.255.255.11/32",
    "status": "active",
    "assigned_object_type": "dcim.interface",
    "assigned_object_id": 123,
    "description": "Loopback 0"
  }'
```

### Issue 2: Device ID Unknown

**Solution:** Query device ID

```bash
curl -H "Authorization: Token $NETBOX_TOKEN" \
  "$NETBOX_API/api/dcim/devices/?name=leaf-1" | jq '.results[0].id'
```

### Issue 3: Session Not Appearing

**Solution:** Check status filter

```yaml
# Task filters for 'active' and 'planned'
selectattr('status.value', 'in', ['active', 'planned'])

# If status is different, update in NetBox
```

## Quick Reference

```bash
# Check plugin status
curl -s "$NETBOX_API/api/plugins/bgp/session/" | jq '.count'

# Create AS
curl -X POST "$NETBOX_API/api/plugins/bgp/asn/" -d '{"asn": 65000}'

# List all sessions
curl "$NETBOX_API/api/plugins/bgp/session/" | jq '.results[] | .name'

# Test device
ansible-playbook configure_aoscx.yml -l DEVICE -t bgp --check -e aoscx_debug=true

# Deploy device
ansible-playbook configure_aoscx.yml -l DEVICE -t bgp

# Rollback
ansible-playbook configure_aoscx.yml -l DEVICE -t bgp -e aoscx_use_netbox_bgp_plugin=false
```

## Success Criteria

✅ All devices have BGP sessions in plugin
✅ All sessions status = "Active"
✅ Ansible uses plugin as data source
✅ BGP configuration matches expected state
✅ No reliance on config_context for BGP

---

**Next:** [BGP_HYBRID_CONFIGURATION.md](BGP_HYBRID_CONFIGURATION.md) for detailed information
