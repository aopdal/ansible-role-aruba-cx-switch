# Quick Reference: VLAN Change Identification

## For Developers Adding New VLAN-Related Tasks

If you're adding a new task that needs to work with VLANs, follow this pattern:

### 1. Add Assertion at the Start

```yaml
- name: Verify VLAN analysis has been performed
  ansible.builtin.assert:
    that:
      - vlans is defined
      - vlans_in_use is defined
      # Add vlan_changes if you need to know what to create/delete
      - vlan_changes is defined
    fail_msg: "ERROR: identify_vlan_changes.yml must run before YOUR_TASK.yml"
    success_msg: "VLAN analysis completed - proceeding with YOUR_TASK"
```

### 2. Use the Facts (Don't Recalculate)

**DON'T DO THIS:**

```yaml
# ❌ BAD: Recalculating vlans_in_use
- name: Get VLANs in use
  ansible.builtin.set_fact:
    vlans_in_use: "{{ interfaces | get_vlans_in_use(...) }}"
```

**DO THIS:**

```yaml
# ✅ GOOD: Use existing fact
- name: Filter VLANs for my task
  ansible.builtin.set_fact:
    my_vlans: "{{ vlans | selectattr('vid', 'in', vlans_in_use.vids) | list }}"
```

### 3. Add to main.yml After identify_vlan_changes.yml

```yaml
# In tasks/main.yml, after the "Identify VLAN changes (before configuration)" task
- name: Include my new VLAN task
  ansible.builtin.include_tasks:
    file: my_vlan_task.yml
    apply:
      tags:
        - my_tag
        - vlans
  when: aoscx_configure_my_feature | bool
  tags:
    - my_tag
    - vlans
```

## Available Facts

### `vlans` - VLANs from NetBox

```yaml
vlans:
  - vid: 10
    name: "Data"
    description: "Data VLAN"
    l2vpn_termination:
      id: 123
      l2vpn:
        identifier: 10010  # VNI
```

### `vlans_in_use` - VLANs on Interfaces

```yaml
vlans_in_use:
  vids: [1, 10, 20, 30]  # List of VLAN IDs
```

### `vlan_changes` - What Needs to Change

```yaml
vlan_changes:
  vlans_to_create:
    - vid: 40
      name: "Voice"
  vlans_to_delete: [50, 60]  # VLAN IDs to delete
  vlans_in_use: [10, 20]     # Protected from deletion
```

## Common Patterns

### Pattern 1: Configure Feature for VLANs with L2VPN

```yaml
- name: Filter VLANs with L2VPN termination
  ansible.builtin.set_fact:
    vlans_with_l2vpn: "{{ vlans |
      selectattr('vid', 'in', vlans_in_use.vids) |
      selectattr('l2vpn_termination', 'defined') |
      selectattr('l2vpn_termination.id', 'defined') |
      list }}"
```

### Pattern 2: Cleanup Feature for Deleted VLANs

```yaml
- name: Filter VLANs to clean up
  ansible.builtin.set_fact:
    vlans_to_cleanup: "{{ vlans |
      selectattr('vid', 'in', vlan_changes.vlans_to_delete) |
      selectattr('l2vpn_termination.id', 'defined') |
      list }}"
```

### Pattern 3: Check if VLAN is in Use

```yaml
- name: Only process unused VLANs
  some_module:
    vlan_id: "{{ item.vid }}"
  loop: "{{ vlans }}"
  when: item.vid not in vlans_in_use.vids
```

## Debugging

Enable debug output to see VLAN analysis:

```bash
# -v or higher triggers debug output in identify_vlan_changes.yml
ansible-playbook -v playbook.yml
```

Or set `aoscx_debug: true` in group_vars/host_vars to enable detailed debug
output in configure_evpn.yml, configure_vxlan.yml, and related tasks:

```yaml
aoscx_debug: true
```

Debug output shows:

- VLANs from NetBox count
- VLANs in use (with IDs)
- VLANs to create (with IDs)
- VLANs to delete (with IDs)

## Testing Your Changes

1. **Test Creation**: Remove a VLAN from device, verify it gets created
2. **Test Idempotency**: Run twice, second run should make no changes
3. **Test Cleanup**: Remove VLAN from NetBox, verify cleanup in idempotent mode
4. **Test Assertions**: Comment out identify_vlan_changes.yml, verify assertion fails
5. **Test Device Detection**: Verify EVPN/VXLAN detection works with `show evpn evi`

### Testing EVPN/VXLAN Detection

The role runs `show evpn evi` on the switch and passes the output through the
`parse_evpn_evi_output` filter plugin (`filter_plugins/netbox_filters_lib/vlan_filters.py`):

```yaml
- name: Get existing EVPN/VXLAN configuration
  arubanetworks.aoscx.aoscx_command:
    commands:
      - show evpn evi
  register: evpn_config_output

- name: Parse EVPN EVI output
  ansible.builtin.set_fact:
    evpn_parsed: "{{ evpn_config_output.stdout[0] | parse_evpn_evi_output }}"
```

The filter returns:

```python
{
  "evpn_vlans":    [10, 20, 30],          # VLAN IDs with EVPN configured
  "vxlan_vlans":   [10, 20, 30],          # VLAN IDs with VXLAN configured
  "vxlan_vnis":    [10100010, 10100020],  # VNI values
  "vxlan_mappings": [[10100010, 10], [10100020, 20]]  # [VNI, VLAN] pairs
}
```

**Expected `show evpn evi` output format:**

```
L2VNI : 10100010
    Route Distinguisher        : 172.20.1.33:10
    VLAN                       : 10
    Status                     : up
    RT Import                  : 65005:10
    RT Export                  : 65005:10
```

**To test the filter locally:**

```python
import re

output = """
L2VNI : 10100010
    Route Distinguisher        : 172.20.1.33:10
    VLAN                       : 10
L2VNI : 10100020
    VLAN                       : 20
"""

# VNI pattern (used by the filter)
vnis = re.findall(r'^L2VNI\s+:\s+(\d+)', output, re.MULTILINE)
print(f"VNIs: {vnis}")   # ['10100010', '10100020']

# VLAN pattern (used by the filter)
vlans = re.findall(r'^\s+VLAN\s+:\s+(\d+)', output, re.MULTILINE)
print(f"VLANs: {vlans}") # ['10', '20']
```

## File Locations

- **Single Source**: `tasks/identify_vlan_changes.yml`
- **Configuration**: `tasks/configure_*.yml`
- **Cleanup**: `tasks/cleanup_*.yml`
- **Orchestration**: `tasks/main.yml`
- **Documentation**: `docs/VLAN_CHANGE_IDENTIFICATION_WORKFLOW.md`
