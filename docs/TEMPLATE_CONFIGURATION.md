# Template-Based Configuration Generation

## Overview

This role includes Jinja2 templates for generating AOS-CX device configuration. This is a **starting point** for alternative configuration approaches and allows for rapid iteration during development and testing.

Template generation can run in two scenarios:
- **Normal mode**: With device facts gathered (configuration matches device state)
- **Bootstrap mode**: Without device facts (pre-deployment config generation)

## Status

**Current**: Starting point implementation
- Templates render to text files in `/tmp/`
- Works with or without device facts
- Can run in bootstrap/pre-deployment scenarios
- Used for preview and validation

**Future**: Integration with device push capabilities

## Included Templates

The `aoscx.j2` master template includes:

1. **system.j2** - Hostname, banner (MOTD), user credentials
2. **time.j2** - Timezone, NTP configuration
3. **anycast_no_icmp_redirect.j2** - ICMP redirect disable (Anycast Gateway support)
4. **vrf.j2** - VRF definitions with RD and route targets
5. **vlan.j2** - VLAN configuration
6. **evpn.j2** - EVPN instance definitions
7. **stp.j2** - Spanning Tree Protocol settings
8. **int_mgmt.j2** - Management interface configuration
9. **system_interface_group.j2** - System interface groups
10. **int_lag.j2** - LAG (Link Aggregation) interface configuration
11. **int_phys.j2** - Physical interface settings
12. **int_loopback.j2** - Loopback interface configuration
13. **int_vlan.j2** - VLAN SVI interface configuration
14. **int_vxlan.j2** - VXLAN interface configuration
15. **vsx.j2** - Virtual Switching Extension (VSX) configuration
16. **ospf.j2** - OSPF routing protocol configuration
17. **gateway.j2** - EVPN gateway settings
18. **https.j2** - HTTPS/REST API configuration

## Not Included

- **bgp.j2** - BGP template (requires NetBox BGP plugin integration - future enhancement)

## Configuration Generation

### Task Workflow

1. **gather_template_data.yml** - Gathers VRF and VLAN data from NetBox
   - **Works WITH device facts**: Identifies VRFs/VLANs actually in use on device
   - **Works WITHOUT device facts**: Fetches all available VRFs/VLANs from NetBox
   - Sets template-accessible facts (template_vrfs, template_vlans, etc.)

2. **generate_template_config.yml** - Renders Jinja2 templates
   - Uses data gathered by previous task
   - Renders `aoscx.j2` master template with all includes
   - Generates configuration file to `/tmp/`

### Why Two Tasks?

Separating data gathering from template rendering allows:
- Clean separation of concerns (data loading vs. rendering)
- Easier debugging (check gathered facts before rendering)
- Reusable data gathering logic (can be used by other processes)
- Follows same pattern as other role tasks (identify → configure)

### Data Gathering Details - Two Operating Modes

The `gather_template_data.yml` task gracefully handles scenarios with and without device facts:

**Mode 1: WITH Device Facts** (normal operation, devices running)
- Uses `get_vrfs_in_use()` filter to identify VRFs from interfaces
- Uses `get_vlans_in_use()` filter to identify VLANs from interfaces
- Only provides VRFs/VLANs actually in use on device
- Includes VRF details (RD, route-targets)

**Mode 2: WITHOUT Device Facts** (bootstrap/pre-deployment)
- No errors even if `interfaces` data not gathered
- Fetches ALL VLANs available on device from NetBox
- Provides all available VRFs from NetBox
- Sets `template_has_device_facts: false` flag
- Useful for generating config before devices are deployed

**Template Variables Set:**
- `template_vrfs` - List of VRF names (in-use if facts available, all if not)
- `template_vrfs_details` - VRF details (RD, route-targets)
- `template_vlans` - All VLANs available on device
- `template_vlans_in_use` - VLANs currently assigned to interfaces (empty if no facts)
- `template_has_device_facts` - Boolean indicating if device facts were available

### Running Template Generation

```bash
# Generate configuration for all devices (WITH device facts)
ansible-playbook site.yml --tags template_config

# Generate configuration WITHOUT device facts (bootstrap mode)
# Useful before devices are deployed
ansible-playbook site.yml --tags template_config -e "aoscx_gather_facts=false"

# Generate with debug output
ansible-playbook site.yml --tags template_config -e "aoscx_debug=true" -v

# Combine with other base config
ansible-playbook site.yml --tags base_config
```

### Bootstrap Mode Example

When devices are not yet running or configured:

```bash
# Skip fact gathering, fetch only NetBox data
ansible-playbook site.yml \
  -e "aoscx_gather_facts=false" \
  -e "aoscx_generate_template_config=true" \
  --tags template_config

# Generated config available for review
cat /tmp/device-1-config.txt
```

During bootstrap, templates receive:
- `template_has_device_facts: false`
- All available VLANs from NetBox
- All available VRFs from NetBox
- No "in-use" filtering (since interfaces are unavailable)

### Output Example

```
TASK [Render aoscx configuration template] **********************************
ok: [device-1]

TASK [Display generated configuration] ***************************************
ok: [device-1] => {
    "msg": "/tmp/device-1-config.txt"
}

TASK [Show configuration preview (first 50 lines)] ***************************
ok: [device-1]

TASK [Debug - Display configuration preview] **********************************
ok: [device-1] => {
    "msg": [
        "hostname device-1",
        "!",
        "user admin group administrators password plaintext xxxxxx",
        "...",
    ]
}
```

## Template Variables

Before rendering templates, the role gathers VRF and VLAN data using `gather_template_data.yml`. This ensures all necessary NetBox data is available to templates.

### Available Variables

**NetBox Data**:
- `template_vrfs` - List of VRF names in use on device
- `template_vrfs_details` - Dictionary of VRF details (RD, route-targets, etc.)
- `template_vlans` - List of all VLANs available on device
- `template_vlans_in_use` - List of VLANs currently in use by interfaces
- `interfaces` - Interface objects from NetBox and device facts
- `ip_addresses` - IP addresses from NetBox

**Inventory & Config**:
- `inventory_hostname` - Device name
- `custom_fields` - Device custom fields from NetBox
- `config_context` - Custom configuration data (MOTD, NTP, DNS, etc.)
- `device_id` - NetBox device ID

**Role Variables**:
- `netbox_url` - NetBox API endpoint
- `netbox_token` - NetBox API token
- All role defaults and variables

### Example: Accessing VRF Data in Templates

```jinja2
{% for vrf_name in template_vrfs %}
vrf {{ vrf_name }}
{% if template_vrfs_details[vrf_name] is defined %}
  rd {{ template_vrfs_details[vrf_name].rd }}
{% endif %}
!
{% endfor %}
```

### Example: Accessing VLAN Data in Templates

```jinja2
{% for vlan in template_vlans %}
vlan {{ vlan.vid }}
  name {{ vlan.name }}
{% endfor %}
```

## Template Development Guide

### Adding a Template

1. Create new `templates/*.j2` file
2. Add include line to `templates/aoscx.j2`:
   ```jinja2
   {% include 'my_feature.j2' %}
   ```
3. Use NetBox data and role variables in template

### Example Template Structure

```jinja2
{% if custom_fields.my_feature_enabled | default(false) | bool %}
!
feature my_feature
{% for config in my_feature_configs %}
  config {{ config.name }}
{% endfor %}
!
{% endif %}
```

### Using Gathered VRF and VLAN Data

Before template rendering, `gather_template_data.yml` provides NetBox data as template variables. Use these in your templates:

**VRF Template Example** (`templates/vrf.j2`):

```jinja2
{% if template_vrfs is defined and template_vrfs | length > 0 %}
!
! VRF Configuration
{% for vrf_name in template_vrfs %}
vrf {{ vrf_name }}
{% if template_vrfs_details[vrf_name].rd is defined %}
  rd {{ template_vrfs_details[vrf_name].rd }}
{% endif %}
!
{% endfor %}
{% endif %}
```

**VLAN Template Example** (`templates/vlan.j2`):

```jinja2
{% if template_vlans is defined and template_vlans | length > 0 %}
!
! VLAN Configuration
{% for vlan in template_vlans | selectattr('id', 'defined') %}
vlan {{ vlan.vid }}
  name {{ vlan.name | default('VLAN' + vlan.vid | string) }}
{% if vlan.description is defined %}
  description {{ vlan.description }}
{% endif %}
!
{% endfor %}
{% endif %}
```

**Handling Both Bootstrap and Normal Modes:**

If your template needs to behave differently with/without device facts:

```jinja2
{% if template_has_device_facts %}
! Device facts available - showing in-use VRFs only
{% for vrf in template_vrfs %}
vrf {{ vrf }}
{% endfor %}
{% else %}
! Bootstrap mode - showing all available VRFs from NetBox
! (No interface data, all VRFs included for reference)
{% for vrf in template_vrfs %}
! vrf {{ vrf }}
{% endfor %}
{% endif %}
```

### Best Practices

- Use **safe defaults** with `| default(false)`
- Always indent CLI commands properly
- Add **separator lines** (`!`) between sections
- Test with `--tags template_config -v`
- Check `/tmp/` files manually for validation

## Debugging

### Preview Generated Configuration

```bash
# Show first 100 lines
head -100 /tmp/device-1-config.txt

# Show specific section (e.g., VRF)
grep -A 20 "^vrf " /tmp/device-1-config.txt

# Validate configuration syntax (manual)
cat /tmp/device-1-config.txt | ssh admin@device-1 "configure terminal && ?"
```

### Debug Template Variables

```bash
# Enable verbose output with debug flag
ansible-playbook site.yml --tags template_config -e "aoscx_debug=true" -vvv

# Use ansible_debug module to inspect variables
- name: Debug template variables
  ansible.builtin.debug:
    var: custom_fields
```

## Integration with Device Configuration

### Current Workflow

1. Template generates config snapshot in `/tmp/`
2. Manual review of generated configuration
3. Use with other playbook methods (modules, filter plugins, etc.)

### Future Integration

- Direct device push via `aoscx_config` module
- Diff comparison with running configuration
- Atomic configuration transactions

## Limitations & Known Issues

1. **BGP Support**: BGP template not included (requires plugin integration)
2. **No Cleanup**: Template generation is one-way (no rollback)
3. **Manual Testing**: Generated config must be manually validated
4. **Variable Dependency**: Requires all necessary NetBox data and custom_fields
5. **Bootstrap Mode**: Without device facts, only NetBox data available (no interface state)

### Bootstrap Mode Limitations

When running template generation **without device facts** (`aoscx_gather_facts=false`):

- **No interface state data**: Can't determine which VLANs/VRFs are currently "in use"
- **All available data**: Templates receive all VLANs and VRFs from NetBox
- **No device-specific filtering**: Templates apply no per-device filtering
- **Manual review required**: Generated config must be carefully reviewed before deployment

## Related Documentation

- [FILTER_PLUGINS.md](FILTER_PLUGINS.md) - Filter plugin documentation
- [NETBOX_INTEGRATION.md](NETBOX_INTEGRATION.md) - Custom fields reference
- [BASE_CONFIGURATION.md](BASE_CONFIGURATION.md) - System configuration details

## Troubleshooting

### Template Undefined Variable Error

**Problem**: "jinja2.exceptions.UndefinedError: 'variable_name' is undefined"

**Solution**: Check that:
1. Custom field is defined in NetBox
2. Device fact gathering completed successfully (or use `aoscx_gather_facts=false` if intentional)
3. Use `| default(value)` filter for optional variables

### Bootstrap Mode Issues

**Problem**: Running template generation with `aoscx_gather_facts=false` but NetBox API fails

**Solution**:
1. Verify NetBox URL is correct: `-e "netbox_url=https://netbox.example.com"`
2. Verify NetBox token is valid: `-e "netbox_token=your_token"`
3. Check device exists in NetBox and has `device_id` configured
4. Enable debug: `-e "aoscx_debug=true" -vvv`

**Problem**: Template shows empty VRF/VLAN lists in bootstrap mode

**Solution**:
1. Verify device has VLANs/VRFs created in NetBox
2. Check VLANs are marked "available on device" in NetBox
3. Verify API permissions allow fetching VLAN and VRF data
4. Run with debug to see NetBox API responses: `-e "aoscx_debug=true" -v`

**Problem**: Task runs without error but config file not generated

**Solution**:
1. Verify `aoscx_generate_template_config=true` is set
2. Check `/tmp/` permissions for your user
3. Verify templates exist in `templates/` directory
4. Check for Jinja2 template syntax errors in included templates

### Configuration File Not Created

**Problem**: `/tmp/{{ inventory_hostname }}-config.txt` not found

**Solution**:
1. Verify task executed (check Ansible output)
2. Check file permissions in `/tmp/`
3. Look for template syntax errors in `templates/`

### Incomplete Configuration

**Problem**: Generated config missing sections

**Solution**:
1. Verify template includes are in `aoscx.j2`
2. Check conditional logic in individual templates
3. Enable debug: `-e "aoscx_debug=true" -v`

## Next Steps for Feature Expansion

1. **BGP Support**: Integrate with netbox-bgp plugin
2. **Device Push**: Add `aoscx_config` module integration
3. **Validation**: Add configuration syntax checking
4. **Diff Mode**: Compare templates vs running config
5. **Rollback**: Implement atomic config restore

## Contributing

To add new templates:

1. Create `templates/feature.j2`
2. Add to `aoscx.j2` includes
3. Update this documentation
4. Test with `--tags template_config -v`
