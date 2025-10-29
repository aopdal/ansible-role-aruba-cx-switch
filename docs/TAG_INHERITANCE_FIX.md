# Tag Inheritance Fix for Base Configuration Tasks

## Problem

When running with `-t base_config`, the base configuration tasks were being included but not executed. The tasks inside the included files were being skipped silently.

## Root Cause

Ansible's `include_tasks` does not automatically apply tags to tasks within the included file. The tags on the `include_tasks` statement only control whether the include itself happens, not the tasks within.

## Solution

Use the `apply:` parameter with `include_tasks` to apply tags to all tasks within the included file.

### Before (Not Working)

```yaml
- name: Include banner configuration tasks
  ansible.builtin.include_tasks: configure_banner.yml
  when: aoscx_configure_banner | bool
  tags:
    - banner
    - base_config
    - system
```

### After (Working - Corrected)

```yaml
- name: Include banner configuration tasks
  ansible.builtin.include_tasks:
    file: configure_banner.yml
    apply:
      tags:
        - banner
        - base_config
        - system
  when: aoscx_configure_banner | bool
  tags:
    - banner
    - base_config
    - system
```

## Key Changes

1. **`apply:` parameter**: Tags are now applied to all tasks within the included file
2. **Matching tags**: The `tags:` on the include **must match** the `apply: tags:` to ensure proper filtering
3. **Tag inheritance**: Tasks inside `configure_banner.yml` now inherit the tags and the include itself is filtered

## Why Tags Must Match

**Problem with `tags: always`:**

```yaml
tags:
  - always  # ❌ This causes the include to ALWAYS run, regardless of tag filters
```

When using `tags: always`, the include is evaluated even when you run with specific tags like `-t vlans`. This causes:

- Banner/NTP/DNS includes run even when you only want VLANs
- Unnecessary task evaluations
- Confusing output showing unrelated includes

**Solution with matching tags:**

```yaml
tags:
  - banner
  - base_config
  - system  # ✅ Include only runs when these tags are selected
```

Now when you run:

- `-t vlans` → Only VLAN includes run
- `-t base_config` → Only base config includes run
- `-t banner` → Only banner include runs
- No tags → All includes run (default behavior)

## Updated Inventory

Fresh inventory generated with all base configuration:

```json
"config_context": {
    "motd": "All tilgang til dette systemet er begrenset og monitorert...",
    "timezone": "europe/oslo",
    "ntp_vrf": "mgmt",
    "ntp_servers": [
        {"server": "klokke.opdal.net"}
    ],
    "dns_domain_name": "ao-test.net",
    "dns_mgmt_nameservers": {
        "Primary": "91.90.45.8",
        "Secondary": "172.16.3.10"
    },
    "dns_name_servers": {
        "0": "91.90.45.8",
        "1": "172.16.3.10"
    },
    "dns_domain_list": {
        "0": "ao-test.net",
        "1": "opdal.net"
    },
    "dns_host_v4_address_mapping": {
        "klokke": "91.90.45.8",
        "jumphost": "172.20.0.100"
    },
    "dns_vrf": "mgmt"
}
```

## Testing

### Test with specific tag

```bash
ansible-playbook -i netbox_inv_int.yml configure_aoscx.yml -l z13-cx3 -t banner
```

### Test with base_config tag

```bash
ansible-playbook -i netbox_inv_int.yml configure_aoscx.yml -l z13-cx3 -t base_config
```

### Test without tags (all tasks)

```bash
ansible-playbook -i netbox_inv_int.yml configure_aoscx.yml -l z13-cx3
```

## Expected Behavior

With `-t base_config`, you should now see:

- ✅ Banner task executed (if motd defined)
- ✅ Timezone task executed (if timezone defined)
- ✅ NTP tasks executed (if ntp_servers defined)
- ✅ DNS tasks executed (if dns_* fields defined)

## Files Modified

- `/workspaces/ansible-role-aruba-cx-switch/tasks/main.yml`
    - Updated all base config includes (banner, timezone, NTP, DNS)
    - Applied same pattern for consistency

## References

- Ansible docs: [Including and Importing](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_reuse.html)
- Tag inheritance with `apply`: [Tags](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_tags.html#adding-tags-to-includes)
