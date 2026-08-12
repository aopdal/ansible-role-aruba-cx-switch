# Tag-Dependent Task Includes

## Overview

Some configuration tasks should **only run when explicitly requested** — not
by a broad layer tag like `-t layer3`. This is achieved by *narrowing the
tag list* on the include so that Ansible's own tag filter skips it under
broad-tag runs. No custom `ansible_run_tags` string matching is used or
needed.

## Use Cases

Tasks that are:

- **High-impact**: changes that could disrupt service (VSX, BGP, OSPF).
- **Risky**: could cause network connectivity issues (routing protocols,
  static routes).

## Implementation

### Basic pattern

The include is tagged only with feature-specific tags (its own name and the
category it belongs to). The broader layer tag (`layer3`) is intentionally
omitted so that `-t layer3` does not sweep the include in:

```yaml
- name: Include OSPF configuration tasks
  ansible.builtin.include_tasks:
    file: configure_ospf.yml
    apply:
      tags:
        - ospf
        - routing
  when:
    - aoscx_configure_ospf | bool
    - custom_fields.device_ospf | default(false) | bool
  tags:
    - ospf
    - routing
```

Compare with a regular L3 include, which does carry `layer3`:

```yaml
- name: Include L3 interface configuration tasks
  ansible.builtin.include_tasks:
    file: configure_l3_interfaces.yml
    apply:
      tags:
        - interfaces
        - l3_interfaces
        - layer3
  when: aoscx_configure_l3_interfaces | bool
  tags:
    - interfaces
    - l3_interfaces
    - layer3
```

### How it works

Ansible's own tag filter drives include selection based on `--tags` and the
tags declared on each include. The role does not evaluate
`ansible_run_tags` itself.

1. **Normal run (no tags)**

   ```bash
   ansible-playbook configure_aoscx.yml
   ```

   Every include that has tags (and isn't `never`) runs, subject to its
   `when:` clause. OSPF/BGP/static-routes/VSX run.

2. **Specific tags without a routing tag**

   ```bash
   ansible-playbook configure_aoscx.yml -t vlans
   ```

   OSPF/BGP/static-routes/VSX are not tagged `vlans`, so Ansible skips
   their includes.

3. **Broad layer tag**

   ```bash
   ansible-playbook configure_aoscx.yml -t layer3
   ```

   OSPF/BGP/static-routes intentionally *do not* carry the `layer3` tag,
   so Ansible skips them. L3-interface config still runs (it carries
   `layer3`). This is the specific protection the design provides.

4. **Explicit feature request**

   ```bash
   ansible-playbook configure_aoscx.yml -t ospf
   ```

   OSPF include runs.

5. **`routing` sweep**

   ```bash
   ansible-playbook configure_aoscx.yml -t routing
   ```

   OSPF, BGP, and static routes all run (they all carry `routing`).

6. **`-t vsx` / `-t ha`**

   VSX runs (its include carries both `vsx` and `ha`).

## Current tag layout for protected features

The following includes are protected from broad `layer3` (or, for VSX,
broad interface-layer) sweeps by omitting the broad tag rather than by
`when:` filtering.

### 1. VSX (Virtual Switching Extension)

Tags: `[vsx, ha]`. Not tagged `layer3` — a `-t layer3` run leaves VSX
untouched. `-t vsx` or `-t ha` runs it.

### 2. OSPF

Tags: `[ospf, routing]`. Not tagged `layer3`. `-t ospf` or `-t routing`
runs it.

### 3. BGP

Tags: `[bgp, routing]`. Not tagged `layer3`. `-t bgp` or `-t routing` runs
it.

### 4. Static routes

Tags: `[static_routes, routing]`. Not tagged `layer3`. `-t static_routes`
or `-t routing` runs it. Cleanup of stale routes is additionally gated by
`aoscx_idempotent_mode` (see
[STATIC_ROUTES_CONFIGURATION.md](STATIC_ROUTES_CONFIGURATION.md)).

## Not protected

### Cleanup tasks

Protected by the `aoscx_idempotent_mode` role variable, not by tag
narrowing.

### EVPN / VXLAN

Must run alongside VLAN changes; the overlay depends on the underlay
VLANs staying in sync. Not high-risk enough to require narrowing.

### L2 / L3 interfaces, VLANs, LAGs, base config, NTP / DNS

Regular day-to-day operations. Carry their normal feature + layer tags.

## Testing

The [autotest-aoscx](../../autotest-aoscx) playbooks include tag-selection
tests. To verify the design manually against a device:

```bash
# 1. No tags - all protected features should run.
ansible-playbook -i inv.yml configure_aoscx.yml -l zone13-cx3 --check

# 2. -t vlans - protected features must not run.
ansible-playbook -i inv.yml configure_aoscx.yml -l zone13-cx3 -t vlans --check

# 3. -t layer3 - L3 interface config runs, OSPF/BGP/static routes must not.
ansible-playbook -i inv.yml configure_aoscx.yml -l zone13-cx3 -t layer3 --check

# 4. -t routing - OSPF, BGP, static routes all run.
ansible-playbook -i inv.yml configure_aoscx.yml -l zone13-cx3 -t routing --check

# 5. --list-tasks shows the expected filter.
ansible-playbook -i inv.yml configure_aoscx.yml -l zone13-cx3 -t layer3 --list-tasks
# Must NOT list "Include OSPF/BGP/static route configuration tasks".
```

## Example workflows

### Day-to-day operations (safe — no routing changes)

```bash
# Add new VLANs.
ansible-playbook configure_aoscx.yml -t vlans

# Update interfaces.
ansible-playbook configure_aoscx.yml -t interfaces

# Modify base config (hostname, banner, timezone).
ansible-playbook configure_aoscx.yml -t base_config

# Configure NTP / DNS (may depend on VRFs).
ansible-playbook configure_aoscx.yml -t services

# Push L3 interface config only, without touching routing protocols.
ansible-playbook configure_aoscx.yml -t layer3
```

### Intentional high-impact changes

```bash
# Explicitly configure VSX.
ansible-playbook configure_aoscx.yml -t vsx

# Update BGP.
ansible-playbook configure_aoscx.yml -t bgp

# Update OSPF.
ansible-playbook configure_aoscx.yml -t ospf

# Update static routes.
ansible-playbook configure_aoscx.yml -t static_routes

# All routing protocols.
ansible-playbook configure_aoscx.yml -t routing

# Full run (everything, including routing).
ansible-playbook configure_aoscx.yml
```

## Notes

- The role deliberately does not read `ansible_run_tags` itself. Prior
  versions used `"'ospf' in ansible_run_tags or 'routing' in
  ansible_run_tags or 'all' in ansible_run_tags"` inside `when:` clauses;
  this pattern duplicated Ansible's own tag filter and was removed in
  favor of the tag-narrowing described above.
- Protected includes still respect the boolean enable flag (e.g.
  `aoscx_configure_ospf | bool`) and the NetBox custom-field gate (e.g.
  `custom_fields.device_ospf`).
