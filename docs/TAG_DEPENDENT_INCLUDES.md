# Tag-Dependent Task Includes

## Overview

Some configuration tasks should **only run when explicitly requested** via tags, not as part of normal day-to-day operations. This is achieved by checking `ansible_run_tags`.

## Use Cases

Tasks that are:

- **High-impact**: Changes that could disrupt service (VSX, BGP, OSPF)
- **Infrequent**: Initial setup tasks rarely modified (VRFs, loopback)
- **Risky**: Could cause network connectivity issues (routing, cleanup)

## Implementation

### Basic Pattern

```yaml
- name: Include VSX configuration tasks
  ansible.builtin.include_tasks:
    file: configure_vsx.yml
    apply:
      tags:
        - vsx
        - ha
  when:
    - aoscx_configure_vsx | bool
    - "'vsx' in ansible_run_tags or 'ha' in ansible_run_tags or 'all' in ansible_run_tags"
  tags:
    - vsx
    - ha
```

### How It Works

1. **Normal run (no tags)**:

   ```bash
   ansible-playbook configure_aoscx.yml
   ```

   - `ansible_run_tags` = `['all']`
   - VSX tasks **DO run** (because of `'all' in ansible_run_tags`)

2. **Specific tags (without vsx)**:

   ```bash
   ansible-playbook configure_aoscx.yml -t vlans
   ```

   - `ansible_run_tags` = `['vlans']`
   - VSX tasks **DO NOT run** (tag not in list)

3. **Explicit VSX request**:

   ```bash
   ansible-playbook configure_aoscx.yml -t vsx
   ```

   - `ansible_run_tags` = `['vsx']`
   - VSX tasks **DO run** (tag explicitly requested)

## When to Use

### ✅ Good Candidates for Tag-Dependent Includes

- **VSX**: High-availability configuration, rarely changes
- **BGP/OSPF**: Routing protocol configuration, could disrupt connectivity
- **VRFs**: Virtual routing configuration, foundational setup
- **Cleanup tasks**: Removing VLANs/interfaces, potentially dangerous
- **EVPN/VXLAN**: Overlay networking, complex configuration

### ❌ Should NOT Be Tag-Dependent

- **VLANs**: Common day-to-day changes
- **Interfaces**: Frequent configuration updates
- **LAGs**: Regular operational changes
- **Banner/NTP/DNS**: Low-risk base configuration

## Current Tag-Dependent Tasks

The following tasks **only run when explicitly requested** via tags:

### 1. VSX (Virtual Switching Extension)

```yaml
when:
  - aoscx_configure_vsx | bool
  - "'vsx' in ansible_run_tags or 'ha' in ansible_run_tags or 'all' in ansible_run_tags"
```

**Reason**: High-availability configuration that rarely changes and could disrupt service.

### 2. OSPF (Open Shortest Path First)

```yaml
when:
  - aoscx_configure_ospf | bool
  - "'ospf' in ansible_run_tags or 'routing' in ansible_run_tags or 'all' in ansible_run_tags"
```

**Reason**: Routing protocol changes are high-impact and could affect network connectivity.

### 3. BGP (Border Gateway Protocol)

```yaml
when:
  - aoscx_configure_bgp | bool
  - "'bgp' in ansible_run_tags or 'routing' in ansible_run_tags or 'all' in ansible_run_tags"
```

**Reason**: Routing protocol changes are high-impact and could affect network connectivity.

## Tasks That Are NOT Tag-Dependent

### Cleanup Tasks

**Decision**: Protected by `aoscx_idempotent_mode` flag instead.

- Cleanup only runs when explicitly enabled via variable
- Idempotent mode prevents accidental deletions

### EVPN/VXLAN

**Decision**: Must run as part of VLAN changes.

- Overlay networking needs to be updated when VLANs change
- Will be run frequently as part of normal operations
- Not high-risk enough to require explicit tagging

### Regular Operations (Always Run When Tagged)

- **VLANs**: Common day-to-day changes
- **Interfaces**: Frequent configuration updates
- **LAGs**: Regular operational changes
- **Banner/NTP/DNS**: Low-risk base configuration

## Testing

### Test Tag-Dependent Behavior

```bash
# 1. Run without tags - VSX should run
ansible-playbook -i netbox_inv_int.yml configure_aoscx.yml -l z13-cx3 --check

# 2. Run with specific tags - VSX should NOT run
ansible-playbook -i netbox_inv_int.yml configure_aoscx.yml -l z13-cx3 -t vlans --check

# 3. Run with VSX tag - VSX should run
ansible-playbook -i netbox_inv_int.yml configure_aoscx.yml -l z13-cx3 -t vsx --check

# 4. Verify with list-tasks
ansible-playbook -i netbox_inv_int.yml configure_aoscx.yml -l z13-cx3 -t vlans --list-tasks
# Should NOT show "Include VSX configuration tasks"
```

## Benefits

1. **Safety**: Prevents accidental changes to critical infrastructure
2. **Performance**: Skips unnecessary task evaluations
3. **Clarity**: Explicit intent when running high-impact configurations
4. **Flexibility**: Can still run everything with no tags or `--tags all`

## Example Workflow

### Day-to-Day Operations (Safe - No Routing Changes)

```bash
# Add new VLANs - no risk of changing VSX/BGP/OSPF
ansible-playbook configure_aoscx.yml -t vlans

# Update interfaces - no risk of changing routing
ansible-playbook configure_aoscx.yml -t interfaces

# Modify base config - no risk of overlay or routing changes
ansible-playbook configure_aoscx.yml -t base_config
```

### Intentional High-Impact Changes

```bash
# Explicitly configure VSX
ansible-playbook configure_aoscx.yml -t vsx

# Update BGP routing
ansible-playbook configure_aoscx.yml -t bgp

# Update OSPF routing
ansible-playbook configure_aoscx.yml -t ospf

# Update all routing protocols
ansible-playbook configure_aoscx.yml -t routing

# Run everything (full configuration including routing)
ansible-playbook configure_aoscx.yml
```

## Notes

- `ansible_run_tags` is a built-in Ansible variable containing list of requested tags
- Always include `'all' in ansible_run_tags` check to allow full runs
- Can combine multiple tags in the condition with `or`
- Tag-dependent includes still respect the boolean enable flag (e.g., `aoscx_configure_vsx | bool`)
