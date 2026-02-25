# Utils Module - Helper Functions

Part of the NetBox Filters Library for Aruba AOS-CX switches.

## What This Module Does (Plain English)

This is the "toolbox" module that all other filter modules rely on. It provides small, reusable helper functions for common tasks:

- **Debugging**: Print diagnostic messages when troubleshooting (controlled by an environment variable, so there's zero overhead in production)
- **VLAN formatting**: Turn a list of VLAN numbers like `[10, 11, 12, 20, 21, 30]` into a compact range string `"10-12,20-21,30"` that switches understand
- **Interface selection**: Choose which interfaces to configure based on whether you're running in standard mode (configure everything) or idempotent mode (only configure what changed)
- **IP address extraction**: Pull IPv4 and IPv6 addresses from NetBox interface data and categorize them
- **IP change tracking**: Tag interfaces with which IP addresses need to be added, so downstream tasks know what to configure

---

## Overview

The `utils.py` module provides core utility functions used across all filter modules. These helpers enable debugging, VLAN list formatting, interface selection logic, and IP address processing.

**File Location**: [filter_plugins/netbox_filters_lib/utils.py](../../filter_plugins/netbox_filters_lib/utils.py)

**Dependencies**: None (base module)

**Function Count**: 5 (2 exposed as Ansible filters, 3 internal helpers used by other modules)

## Functions

### `_debug(message)`

Internal debugging function that prints messages when the `DEBUG_ANSIBLE` environment variable is set.

#### Purpose

Provides conditional debug output throughout the filter plugin library without impacting production performance.

#### Parameters

- **message** (str): Debug message to print

#### Returns

None (prints to stdout if debugging is enabled)

#### Environment Variables

- **DEBUG_ANSIBLE**: Set to `true`, `1`, or `yes` to enable debug output

#### Implementation Details

```python
def _debug(message):
    """Print debug message if DEBUG_ANSIBLE environment variable is set"""
    if os.environ.get("DEBUG_ANSIBLE", "").lower() in ("true", "1", "yes"):
        print(f"DEBUG: {message}")
```

The function checks the environment variable and only prints if explicitly enabled. This allows developers to troubleshoot filter behavior without modifying code.

#### Usage Examples

**In Filter Code:**
```python
from .utils import _debug

def my_filter(data):
    _debug(f"Processing {len(data)} items")
    # Filter logic here
    _debug(f"Completed processing, found {result_count} results")
    return results
```

**Enabling Debug Output:**
```bash
# Enable debugging
export DEBUG_ANSIBLE=true
ansible-playbook site.yml

# Disable debugging
unset DEBUG_ANSIBLE
ansible-playbook site.yml
```

**Sample Debug Output:**
```
DEBUG: Processing 45 items
DEBUG: Extracted VLAN IDs: [10, 20, 100, 200]
DEBUG: Filtered VLANs in use: [10, 20, 100]
DEBUG: Completed processing, found 3 results
```

#### Best Practices

1. Use descriptive messages that include context
2. Include variable values and counts for troubleshooting
3. Log key decision points (filtering, comparisons, etc.)
4. Don't overuse - focus on actionable information
5. Include interface/VLAN names when relevant

---

### `collapse_vlan_list(vlan_list)`

Formats a list of VLAN IDs into a compact range string suitable for switch configurations.

#### Purpose

Network equipment typically accepts VLAN ranges in compact notation (e.g., "10-15,20,30-35"). This function converts Python lists into that format.

#### Parameters

- **vlan_list** (list): List of VLAN IDs (integers)

#### Returns

- **str**: Compact range string (e.g., "10-12,20-21,30")

#### Algorithm

1. Sort and deduplicate the input list
2. Iterate through VLANs, building consecutive ranges
3. Close ranges when gaps are detected
4. Format single VLANs as standalone numbers
5. Join all ranges with commas

#### Implementation Details

```python
def collapse_vlan_list(vlan_list):
    """Collapse a list of VLAN IDs into a range string"""
    if not vlan_list:
        return ""

    # Sort and remove duplicates
    sorted_vlans = sorted(set(vlan_list))

    collapsed_ranges = []
    range_start = None
    range_end = None

    for vlan in sorted_vlans:
        if range_start is None:
            # Start a new range
            range_start = vlan
            range_end = vlan
        elif vlan == range_end + 1:
            # Continue the range
            range_end = vlan
        else:
            # Close the current range and start a new one
            if range_start == range_end:
                collapsed_ranges.append(f"{range_start}")
            else:
                collapsed_ranges.append(f"{range_start}-{range_end}")

            range_start = vlan
            range_end = vlan

    # Close the final range
    if range_start is not None:
        if range_start == range_end:
            collapsed_ranges.append(f"{range_start}")
        else:
            collapsed_ranges.append(f"{range_start}-{range_end}")

    return ",".join(collapsed_ranges)
```

#### Usage Examples

**Basic Range Collapse:**
```yaml
- name: Format VLAN list as ranges
  set_fact:
    vlan_range: "{{ [10, 11, 12, 20, 21, 30] | collapse_vlan_list }}"
  # Result: "10-12,20-21,30"
```

**With Duplicates:**
```yaml
- name: Collapse with duplicates (auto-deduped)
  set_fact:
    vlan_range: "{{ [10, 10, 11, 12, 12, 20] | collapse_vlan_list }}"
  # Result: "10-12,20"
```

**Unsorted Input:**
```yaml
- name: Collapse unsorted list (auto-sorted)
  set_fact:
    vlan_range: "{{ [30, 10, 20, 11, 12] | collapse_vlan_list }}"
  # Result: "10-12,20,30"
```

**Empty List:**
```yaml
- name: Handle empty list
  set_fact:
    vlan_range: "{{ [] | collapse_vlan_list }}"
  # Result: ""
```

**Single VLAN:**
```yaml
- name: Single VLAN (no range)
  set_fact:
    vlan_range: "{{ [100] | collapse_vlan_list }}"
  # Result: "100"
```

**Non-Consecutive VLANs:**
```yaml
- name: No consecutive VLANs
  set_fact:
    vlan_range: "{{ [10, 20, 30, 40] | collapse_vlan_list }}"
  # Result: "10,20,30,40"
```

#### Real-World Example

```yaml
---
- name: Configure VLAN trunk with compact ranges
  hosts: switches
  tasks:
    # Extract VLANs from interfaces
    - name: Get VLANs in use
      set_fact:
        vlans_in_use: "{{ netbox_interfaces | extract_vlan_ids }}"
      # Returns: [10, 11, 12, 13, 20, 21, 100, 101, 102, 200]

    # Format as compact range string
    - name: Format VLAN range
      set_fact:
        vlan_range_str: "{{ vlans_in_use | collapse_vlan_list }}"
      # Returns: "10-13,20-21,100-102,200"

    # Use in switch configuration
    - name: Configure trunk port
      arubanetworks.aoscx.aoscx_l2_interface:
        interface: "1/1/48"
        vlan_mode: trunk
        vlan_trunk_allowed: "{{ vlan_range_str }}"
      # Configures: trunk allowed vlan 10-13,20-21,100-102,200
```

#### Use Cases

1. **Switch Configuration**: Format VLAN lists for trunk port configuration
2. **Documentation**: Generate human-readable VLAN assignments
3. **Logging**: Compact representation in debug messages
4. **Validation**: Compare expected vs. actual VLAN ranges
5. **Reporting**: Create network documentation with VLAN usage

---

### `select_interfaces_to_configure(interfaces, idempotent_mode, interfaces_needing_changes=None)`

Selects which interfaces should be configured based on the operating mode (standard vs. idempotent).

#### Purpose

Enables idempotent playbook execution by filtering interfaces to only those that need changes. In standard mode, all interfaces are configured; in idempotent mode, only interfaces with detected changes are configured.

#### Parameters

- **interfaces** (list): List of all interface objects from NetBox
- **idempotent_mode** (bool): Whether running in idempotent mode
- **interfaces_needing_changes** (dict, optional): Dict from `get_interfaces_needing_changes()` (required in idempotent mode)

#### Returns

- **list**: Interfaces to configure
  - Standard mode: all interfaces
  - Idempotent mode: only interfaces needing changes

#### Implementation Details

```python
def select_interfaces_to_configure(
    interfaces, idempotent_mode, interfaces_needing_changes=None
):
    """
    Select which interfaces to configure based on the operating mode
    """
    if not interfaces:
        _debug("No interfaces provided to select_interfaces_to_configure")
        return []

    # Standard mode: configure all interfaces
    if not idempotent_mode:
        _debug(
            f"Standard mode: selecting all {len(interfaces)} interfaces for configuration"
        )
        return interfaces

    # Idempotent mode: only configure interfaces that need changes
    if not interfaces_needing_changes or not isinstance(
        interfaces_needing_changes, dict
    ):
        _debug(
            "Idempotent mode but no interfaces_needing_changes provided - "
            "returning all interfaces"
        )
        return interfaces

    configure_list = interfaces_needing_changes.get("configure", [])
    _debug(
        f"Idempotent mode: selecting {len(configure_list)} interfaces "
        f"that need configuration changes"
    )

    return configure_list
```

#### Usage Examples

**Standard Mode (Configure All):**
```yaml
- name: Configure all interfaces
  set_fact:
    interfaces_to_config: "{{
      netbox_interfaces |
      select_interfaces_to_configure(false, None)
    }}"
  # Returns all interfaces from NetBox
```

**Idempotent Mode (Configure Only Changed):**
```yaml
- name: Get interfaces needing changes
  set_fact:
    changes: "{{ netbox_interfaces | get_interfaces_needing_changes(ansible_facts) }}"

- name: Select only interfaces needing configuration
  set_fact:
    interfaces_to_config: "{{
      netbox_interfaces |
      select_interfaces_to_configure(true, changes)
    }}"
  # Returns only interfaces from changes['configure'] list
```

**Complete Idempotent Workflow:**
```yaml
---
- name: Idempotent interface configuration
  hosts: switches
  vars:
    enable_idempotent_mode: true
  tasks:
    # Gather device facts first
    - name: Gather network facts
      arubanetworks.aoscx.aoscx_facts:
        gather_subset:
          - interfaces
          - vlans

    # Determine what needs to change
    - name: Identify interfaces needing changes
      set_fact:
        interface_changes: "{{
          netbox_interfaces |
          get_interfaces_needing_changes(ansible_facts)
        }}"

    # Select interfaces based on mode
    - name: Select interfaces to configure
      set_fact:
        selected_interfaces: "{{
          netbox_interfaces |
          select_interfaces_to_configure(
            enable_idempotent_mode,
            interface_changes
          )
        }}"

    # Show summary
    - name: Display configuration summary
      debug:
        msg: |
          Mode: {{ 'Idempotent' if enable_idempotent_mode else 'Standard' }}
          Total interfaces: {{ netbox_interfaces | length }}
          Interfaces to configure: {{ selected_interfaces | length }}
          Interfaces skipped: {{ (netbox_interfaces | length) - (selected_interfaces | length) }}

    # Configure only selected interfaces
    - name: Configure L2 interfaces
      arubanetworks.aoscx.aoscx_l2_interface:
        interface: "{{ item.name }}"
        # ... configuration ...
      loop: "{{ selected_interfaces }}"
      when: item.mode is defined
```

#### Benefits of Idempotent Mode

1. **Performance**: Skip API calls for interfaces already correctly configured
2. **Safety**: Reduce risk of disruption by avoiding unnecessary changes
3. **Logging**: Clearer change logs showing only actual changes
4. **Auditing**: Easier to track what was modified
5. **Speed**: Faster playbook execution for large deployments

#### Debug Output

```
DEBUG: Standard mode: selecting all 48 interfaces for configuration
```

```
DEBUG: Idempotent mode: selecting 3 interfaces that need configuration changes
```

---

### `extract_ip_addresses(nb_intf, exclude_anycast=False)`

Extracts and categorizes IPv4 and IPv6 addresses from a single NetBox interface object.

#### How It Works (Plain English)

NetBox stores all IP addresses on an interface in a single list, but switches need IPv4 and IPv6 configured separately. This function splits the IP addresses into two lists based on a simple rule: if the address contains a colon (`:`), it's IPv6; otherwise it's IPv4.

It can also optionally skip "anycast" IPs. Anycast IPs are special addresses shared across multiple switches (common in EVPN fabrics with active-gateway). These are configured via a different switch command (`active-gateway`), not the normal `ip address` command, so you sometimes want to exclude them.

#### Parameters

- **nb_intf** (dict): A single NetBox interface object containing an `ip_addresses` list. Each IP address is a dict with an `address` field (in CIDR notation like `"192.168.1.1/24"`) and an optional `role` field.
- **exclude_anycast** (bool, optional): If `True`, skip IP addresses that have `role: "anycast"`. Default: `False`.

#### Returns

- **tuple**: A pair of `(ipv4_list, ipv6_list)` where:
  - `ipv4_list`: List of IPv4 address strings (e.g., `["192.168.1.1/24", "10.0.0.1/30"]`)
  - `ipv6_list`: List of IPv6 address strings (e.g., `["2001:db8::1/64"]`)

#### Usage Example (In Python Filter Code)

This function is **not exposed as an Ansible filter** - it's an internal helper used by other filter modules (particularly `interface_change_detection.py`):

```python
from .utils import extract_ip_addresses

# Get all IPs
ipv4, ipv6 = extract_ip_addresses(interface)

# Get IPs excluding anycast (for comparison with device facts)
ipv4, ipv6 = extract_ip_addresses(interface, exclude_anycast=True)
```

---

### `populate_ip_changes(nb_intf, nb_ipv4, nb_ipv6)`

Tags a NetBox interface object with IP addresses that need to be configured on the device.

#### How It Works (Plain English)

After comparing what IPs NetBox says should be on an interface versus what the device currently has, you end up with lists of IPs to add. This function stamps those lists onto the interface object itself (in a field called `_ip_changes`) so that downstream Ansible tasks can loop over the interface and know exactly which IPs to configure.

The underscore prefix in `_ip_changes` indicates it's a field added by the filter system, not something from NetBox itself.

#### Parameters

- **nb_intf** (dict): NetBox interface object to modify (modified in place).
- **nb_ipv4** (list): List of IPv4 addresses that need to be added.
- **nb_ipv6** (list): List of IPv6 addresses that need to be added.

#### Returns

- None (modifies `nb_intf` in place by adding/updating `_ip_changes` dict)

#### Side Effects

Adds `_ip_changes` to the interface dict:
```yaml
_ip_changes:
  ipv4_to_add: ["192.168.1.1/24"]     # Only present if there are IPv4 changes
  ipv6_addresses: ["2001:db8::1/64"]   # Only present if there are IPv6 changes
```

#### Usage Example (In Python Filter Code)

This function is **not exposed as an Ansible filter** - it's an internal helper used by `interface_change_detection.py`:

```python
from .utils import extract_ip_addresses, populate_ip_changes

# Extract IPs from NetBox interface
ipv4, ipv6 = extract_ip_addresses(nb_interface, exclude_anycast=True)

# After comparing with device facts, populate changes
populate_ip_changes(nb_interface, ipv4_to_add, ipv6_to_add)

# Now nb_interface['_ip_changes'] contains the IPs to configure
```

---

## Module Dependencies

**Used By:**
- [vlan_filters.py](vlan_filters.md) - VLAN operations
- [vrf_filters.py](vrf_filters.md) - VRF operations
- [interface_filters.py](interface_filters.md) - Interface categorization
- [comparison.py](comparison.md) - State comparison

**Imports:**
- `os` - Standard library for environment variable access

---

## Testing

### Manual Testing

```python
# Test collapse_vlan_list
from filter_plugins.netbox_filters_lib.utils import collapse_vlan_list

# Test cases
assert collapse_vlan_list([10, 11, 12]) == "10-12"
assert collapse_vlan_list([10, 20, 30]) == "10,20,30"
assert collapse_vlan_list([10, 11, 20, 21, 22]) == "10-11,20-22"
assert collapse_vlan_list([]) == ""
assert collapse_vlan_list([100]) == "100"
assert collapse_vlan_list([30, 10, 20, 11]) == "10-11,20,30"  # Auto-sorted
assert collapse_vlan_list([10, 10, 11, 11]) == "10-11"  # Deduped

print("All tests passed!")
```

### Debug Mode Testing

```bash
# Enable debug mode
export DEBUG_ANSIBLE=true

# Run playbook and observe debug messages
ansible-playbook -i inventory site.yml

# Sample output:
# DEBUG: Processing 45 items
# DEBUG: Standard mode: selecting all 48 interfaces for configuration
# DEBUG: Extracted VLAN IDs: [10, 20, 100, 200]
```

---

## Performance Considerations

- **`_debug()`**: Near-zero overhead when disabled (single environment variable check)
- **`collapse_vlan_list()`**: O(n log n) due to sorting; efficient for typical VLAN counts (< 1000)
- **`select_interfaces_to_configure()`**: O(1) list selection

---

## Best Practices

1. **Debugging**: Always use `_debug()` for troubleshooting output instead of `print()`
2. **VLAN Ranges**: Use `collapse_vlan_list()` when displaying VLAN lists to users
3. **Idempotent Mode**: Use `select_interfaces_to_configure()` for performance optimization
4. **Environment Variables**: Set `DEBUG_ANSIBLE=true` only during development/troubleshooting

---

## See Also

- [Filter Plugins Overview](../FILTER_PLUGINS.md) - Main filter documentation
- [VLAN Filters](vlan_filters.md) - VLAN operations using these utilities
- [VRF Filters](vrf_filters.md) - VRF operations using these utilities
- [Development Guide](../DEVELOPMENT.md) - Contributing to filter plugins
