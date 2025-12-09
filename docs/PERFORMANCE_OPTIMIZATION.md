# Performance Optimization Strategies

## Current Performance Profile

**Observed Performance:**
- 6 virtual AOS-CX switches: ~32 minutes
- Average per device: ~5.3 minutes

**Primary Bottleneck:** API/SSH connection overhead

---

## Current Architecture

### Connection Pattern

The role currently uses a **safety-first, idempotent** approach:

```yaml
1. Gather Facts (REST API)          # ~30-60s per device
2. Analyze Changes (local)          # <1s
3. Configure VLANs (REST API)       # ~10-30s depending on changes
4. Configure VRFs (REST API)        # ~10-30s depending on changes
5. Configure Interfaces (REST API)  # ~30-90s depending on changes
6. Configure L3 IPs (CLI/SSH)       # ~60-120s depending on changes
7. Configure OSPF (CLI/SSH)         # ~20-40s if enabled
8. (Optional) Re-gather & Cleanup   # ~30-60s in idempotent mode
```

**Connection Types:**
- `arubanetworks.aoscx.aoscx` (REST API/httpapi) - Facts, most config
- `network_cli` (SSH) - L3 IP configuration, OSPF, active-gateway

### Why It's Slow

1. **Multiple Fact Gathering Operations**
   - Initial gather at start
   - Re-gather before cleanup (idempotent mode)
   - Each gather = full REST API traversal

2. **Connection Switching Overhead**
   - Switch from `httpapi` to `network_cli` for L3 tasks
   - Each connection type requires authentication
   - Connection pooling helps but doesn't eliminate overhead

3. **Task Granularity**
   - Each task = separate API call
   - Idempotency checks require reading current state
   - Safe but slow

4. **Sequential Execution per Device**
   - Ansible processes devices in batches (forks)
   - Within each device: strictly sequential
   - Cannot parallelize tasks within a device

---

## Optimization Strategies

### Strategy 1: Batch API Calls (High Impact, Moderate Complexity)

**Current:** Each interface/VLAN = separate API call
**Optimized:** Batch multiple operations into single API calls

**Implementation:**
```yaml
# Instead of:
- name: Configure interface 1/1/1
  arubanetworks.aoscx.aoscx_interface: ...
- name: Configure interface 1/1/2
  arubanetworks.aoscx.aoscx_interface: ...

# Do:
- name: Configure all interfaces
  arubanetworks.aoscx.aoscx_config:
    lines: "{{ all_interface_configs | join('\n') }}"
```

**Pros:**
- Reduces API calls from N to 1 (where N = number of items)
- Minimal code changes
- Still uses official modules

**Cons:**
- Less granular error reporting
- May lose some idempotency benefits
- Requires aggregating configs

**Expected Impact:** 30-40% time reduction

---

### Strategy 2: Reduce Fact Gathering (Medium Impact, Low Complexity)

**Current:** Gather facts 1-2 times per run
**Optimized:** Skip unnecessary re-gathering

**Implementation:**
```yaml
# Make cleanup optional with a variable
- name: Gather facts for cleanup
  when:
    - aoscx_idempotent_mode | default(true)
    - aoscx_cleanup_enabled | default(true)  # NEW
```

**Add fast mode:**
```yaml
# New variable: aoscx_fast_mode
# When true:
# - Skip fact re-gathering
# - Skip cleanup detection
# - Trust NetBox as source of truth
```

**Pros:**
- Easy to implement
- No breaking changes
- User choice

**Cons:**
- May leave orphaned config
- Less safety

**Expected Impact:** 20-30% time reduction in idempotent mode

---

### Strategy 3: Connection Pooling & Persistence (Medium Impact, Low Complexity)

**Current:** Connections may not persist across tasks
**Optimized:** Ensure connection persistence

**Implementation:**
```yaml
# In ansible.cfg or role defaults
[defaults]
host_key_checking = False

[persistent_connection]
connect_timeout = 30
command_timeout = 30
connect_retry_timeout = 30

[connection]
pipelining = True
```

**Pros:**
- No code changes
- Benefits all connection types
- Ansible built-in feature

**Cons:**
- Limited impact if already enabled
- Doesn't eliminate overhead

**Expected Impact:** 10-15% time reduction if not already enabled

---

### Strategy 4: Parallel Task Execution (High Impact, High Complexity)

**Current:** All tasks sequential per device
**Optimized:** Parallel execution where safe

**Implementation:**
```yaml
# Use async tasks for independent operations
- name: Configure VLANs
  arubanetworks.aoscx.aoscx_vlan: ...
  async: 300
  poll: 0
  register: vlan_task

- name: Configure VRFs
  arubanetworks.aoscx.aoscx_vrf: ...
  async: 300
  poll: 0
  register: vrf_task

# Wait for both to complete
- name: Wait for VLAN configuration
  async_status:
    jid: "{{ vlan_task.ansible_job_id }}"
  register: vlan_result
  until: vlan_result.finished
  retries: 60

- name: Wait for VRF configuration
  async_status:
    jid: "{{ vrf_task.ansible_job_id }}"
  register: vrf_result
  until: vrf_result.finished
  retries: 60
```

**Pros:**
- Can run independent operations in parallel
- Significant time savings

**Cons:**
- Complex error handling
- Must carefully identify independent operations
- Harder to debug
- Not all operations can be parallelized

**Expected Impact:** 40-50% time reduction (if many parallel opportunities)

---

### Strategy 5: Template-Based Bulk Configuration (Highest Impact, Highest Complexity)

**Current:** Use Ansible modules for each config element
**Optimized:** Generate complete config file and apply once

**Implementation:**
```yaml
- name: Generate complete configuration
  template:
    src: complete_config.j2
    dest: /tmp/{{ inventory_hostname }}_config.txt

- name: Apply configuration via single CLI session
  arubanetworks.aoscx.aoscx_config:
    src: /tmp/{{ inventory_hostname }}_config.txt
    match: none
```

**Pros:**
- Minimal API/SSH connections (1-2 per device)
- Fastest possible approach
- Similar to ZTP approach

**Cons:**
- Loss of idempotency
- No per-task error handling
- Hard to debug failures
- Config order matters
- Less flexible
- Essentially a different tool

**Expected Impact:** 70-80% time reduction

**Trade-off:** This becomes more of a "push entire config" tool than an idempotent configuration management system

---

## Recommended Approach

### Phase 1: Quick Wins (Implement Now)

1. **Add Fast Mode Variable**
   ```yaml
   # defaults/main.yml
   aoscx_fast_mode: false
   aoscx_cleanup_enabled: "{{ not aoscx_fast_mode }}"
   ```

2. **Optimize Connection Settings**
   - Document optimal `ansible.cfg` settings
   - Ensure connection persistence is enabled

3. **Skip Unnecessary Re-gathering**
   - Make cleanup optional
   - Skip when fast mode enabled

**Expected Result:** 20-30% faster (32 min → 22-25 min)

**Implementation Status:** ✅ **IMPLEMENTED**

The `aoscx_fast_mode` variable has been implemented in the role:

```yaml
# defaults/main.yml
aoscx_fast_mode: false
```

When enabled (`aoscx_fast_mode: true`), the following optimizations are applied:

1. **Skips Initial Fact Gathering** - The role will not gather device facts at the start
2. **Skips Re-Gather Before Cleanup** - No fact re-gathering for cleanup detection
3. **Skips All Cleanup Operations** - No removal of orphaned VLANs, VRFs, EVPN, VXLAN configs
4. **Skips L2 Interface Analysis** - No comparison against current device state

**⚠️ IMPORTANT WARNINGS:**

- **Use only for initial deployments or when you're certain no cleanup is needed**
- NetBox becomes the single source of truth - any config not in NetBox will persist on device
- No validation that configuration was applied successfully
- Debugging is harder without fact gathering
- Not recommended for production use or ongoing configuration management

**When to use fast mode:**

✅ **Good use cases:**
- Initial switch deployment (ZTP-like scenarios)
- Lab/testing environments
- Known-good configurations
- Time-critical deployments

❌ **Bad use cases:**
- Production switches with existing config
- When config drift detection is important
- When you need cleanup of old configurations
- Ongoing configuration management

**Usage Example:**

```yaml
# playbook or group_vars
aoscx_fast_mode: true
aoscx_idempotent_mode: false  # Recommended to disable cleanup entirely
```

---

### Phase 2: Moderate Changes (Consider for Future)

1. **Batch Similar Operations**
   - Combine interface configs where possible
   - Use `aoscx_config` with multiple lines
   - Group L3 interface configurations

2. **Implement Async for Independent Tasks**
   - VLANs and VRFs can run in parallel
   - Physical and LAG interface config can overlap

**Expected Result:** Additional 30-40% improvement (22 min → 13-15 min)

---

### Phase 3: Major Refactor (Only if Needed)

1. **Template-Based Approach for Greenfield**
   - New variable: `aoscx_deployment_mode: incremental|bulk`
   - When `bulk`: Generate and apply complete config
   - When `incremental`: Current behavior

**Expected Result:** 70-80% faster but loses idempotency

---

## Alternative Approach: HPE Aruba DCN Workflows Pattern

**Reference:** [aruba/aoscx-ansible-dcn-workflows](https://github.com/aruba/aoscx-ansible-dcn-workflows)

HPE Aruba has published a reference implementation using a **template-based configuration approach** for Data Center Network deployments. This approach differs significantly from our module-based methodology.

### How It Works

1. **Configuration Retrieval** (Optional for idempotency)
   - Fetch current configuration from device
   - Store as baseline for comparison

2. **Template Generation**
   - Use Jinja2 templates to generate complete device configuration
   - Templates are role-specific (spine.j2, leaf.j2, core.j2, access.j2)
   - All configuration in single template per device role

3. **Configuration Application**
   - Push entire generated config using `aoscx_config` module (SSH/CLI)
   - Single connection, single transaction
   - Optional: Compare with baseline for idempotency

### Example Templates

```jinja2
# templates/spine.j2 - Simplified excerpt
hostname {{ inventory_hostname }}

vlan {{ vlans | join(',') }}
!
{% for vrf in vrfs %}
vrf {{ vrf.name }}
!
{% endfor %}

{% for interface in interfaces %}
interface {{ interface.name }}
  {{ interface.config | indent(2) }}
!
{% endfor %}
```

### Pros

- **Fastest possible approach** - Single API/SSH session per device
- **Proven by HPE** - Used in validated reference designs
- **Simple execution model** - Template → Generate → Push
- **Can be idempotent** - If config comparison is implemented

### Cons

- **Template maintenance overhead** - Must cover all configuration scenarios
- **Difficult to modularize** - Our role handles L2 edge to Spine/Leaf complexity
- **Loss of granular error handling** - All-or-nothing approach
- **Order-dependent** - Config commands must be in correct sequence
- **Less flexible** - Hard to handle partial updates
- **Requires complete templates** - Need different templates for:
  - Pure L2 edge switches
  - L3 access switches
  - EVPN/VXLAN leaf switches
  - Spine switches
  - Campus core switches

### Applicability to Our Role

**Challenges:**

1. **Broad Scope** - Our role covers:
   - Simple L2 edge switches (VLANs only)
   - L3 campus switches (OSPF, VRFs)
   - Data center leaf/spine (BGP, EVPN, VXLAN)
   - Hybrid architectures

2. **Template Complexity** - Would need:
   - Conditional logic for optional features (OSPF, BGP, EVPN, VXLAN, VSX)
   - Different templates per switch role
   - Logic to handle partial feature sets

3. **Integration with NetBox** - Current approach:
   - Queries NetBox per feature (VLANs, VRFs, interfaces)
   - Filters and processes data per module
   - Template approach would need all data upfront

**Potential Hybrid Approach:**

Could be implemented as an **optional mode** rather than replacement:

```yaml
# New variable
aoscx_config_method: "modular"  # Default: current module-based approach
                                # OR "template": template-based bulk config

# When template mode:
aoscx_template_file: "templates/{{ device_role }}.j2"  # User-provided template
```

**Implementation Steps (If Pursued):**

1. **Add template support** as opt-in feature
2. **Provide sample templates** for common device roles:
   - `templates/l2_edge.j2` - Basic L2 switches
   - `templates/l3_access.j2` - L3 campus access
   - `templates/dc_leaf.j2` - Data center leaf
   - `templates/dc_spine.j2` - Data center spine

3. **Preserve modular approach** as default
4. **Document trade-offs** clearly
5. **Add configuration backup** before template push

**Recommendation:**

- **NOT a replacement** - Keep current modular approach as default
- **Consider as addition** - For users who want maximum speed
- **Document clearly** - This is "expert mode" with trade-offs
- **Phase 4 or beyond** - Only after Phases 1-3 are complete
- **User-provided templates** - Don't try to cover all scenarios; let users create their own

### Performance Impact (If Implemented)

- **Expected:** 70-80% reduction (32 min → 6-8 min for 6 devices)
- **Trade-off:** Complete loss of granular configuration management
- **Use case:** Initial deployments, ZTP-like scenarios, advanced users

---

## Performance Testing

### Baseline Measurement

```bash
time ansible-playbook site.yml -i inventory.yml --limit test_switches
```

### Metrics to Track

1. **Total Runtime**
2. **Time per Phase:**
   - Fact gathering
   - Change analysis
   - Configuration application
   - Cleanup
3. **API Call Count** (if possible to measure)
4. **Connection Count**

### Test Matrix

| Configuration | Devices | Expected Time | Actual Time | Notes |
|--------------|---------|---------------|-------------|-------|
| Current (baseline) | 6 | 32 min | 32 min | Measured |
| + Fast mode | 6 | 22-25 min | TBD | Skip cleanup |
| + Batching | 6 | 13-15 min | TBD | Batch API calls |
| + Async | 6 | 10-12 min | TBD | Parallel tasks |
| + Bulk mode | 6 | 6-8 min | TBD | Template-based |

---

## Trade-offs Summary

| Strategy | Speed Gain | Safety Loss | Complexity | Recommendation |
|----------|-----------|-------------|------------|----------------|
| Fast Mode | Medium (20-30%) | Low | Low | **✅ Implemented** |
| Connection Pooling | Low (10-15%) | None | Low | Document |
| Batch API Calls | High (30-40%) | Medium | Medium | Consider Phase 2 |
| Async Tasks | High (40-50%) | Medium | High | Consider Phase 2 |
| Aruba DCN Template | Highest (70-80%) | Highest | High | Phase 4+ (Addition, not replacement) |

**Key Differences:**

- **Fast Mode (Implemented):** Skips fact gathering/cleanup, keeps modular approach
- **Aruba DCN Template:** Complete config generation, single push, different architecture
- **Hybrid Approach:** Could support both methods via `aoscx_config_method` variable

---

## Implementation Priority

### ✅ Completed - Phase 1 (Low Risk, Good Return)
- [x] Add `aoscx_fast_mode` variable
- [x] Make cleanup optional when fast mode enabled
- [x] Skip initial fact gathering in fast mode
- [x] Skip all idempotent cleanup operations in fast mode
- [x] Document fast mode usage and trade-offs

**Status:** Implemented and documented. Expected 20-30% performance improvement.

### Short Term - Phase 2 (Moderate Risk, High Return)
- [ ] Batch interface configurations
- [ ] Use async for VLAN/VRF config
- [ ] Optimize L3 interface task loops
- [ ] Document optimal `ansible.cfg` settings

**Expected Impact:** Additional 30-40% improvement on top of Phase 1

### Long Term - Phase 3 (High Risk, Highest Return)
- [ ] Consider HPE Aruba DCN workflows template approach as **optional mode**
- [ ] Create sample templates for common device roles
- [ ] Add `aoscx_config_method: modular|template` variable
- [ ] Implement configuration backup before template push
- [ ] Document template creation guidelines

**Expected Impact:** 70-80% improvement, but significant trade-offs

**Important:** Template approach should be **addition**, not replacement of current modular approach.

---

## Enhanced Fact Gathering (Experimental)

For more precise change detection, especially for IPv6 and anycast/active-gateway configurations, enable enhanced fact gathering via REST API with `depth=2`.

### Configuration

```yaml
# group_vars or playbook
aoscx_gather_enhanced_facts: true

# REST API credentials (optional - defaults to ansible_host/ansible_user/ansible_password)
aoscx_rest_host: "{{ ansible_host }}"  # Switch management IP/hostname
aoscx_rest_user: "admin"                # REST API username
aoscx_rest_password: "{{ vault_switch_password }}"  # REST API password
aoscx_rest_validate_certs: false        # SSL certificate validation
```

### What It Provides

The standard `aoscx_facts` module has limitations:
- IPv6 addresses are returned as URI references (e.g., `/rest/v10.09/system/interfaces/vlan11/ip6_addresses`)
- VSX virtual IPs (anycast/active-gateway) are not included

With enhanced facts (`depth=2`), you get actual values:
- `ip6_addresses` - Actual IPv6 addresses (not URIs)
- `vsx_virtual_ip4` / `vsx_virtual_ip6` - Anycast/active-gateway IPs
- `vsx_virtual_gw_mac_v4` / `vsx_virtual_gw_mac_v6` - Anycast MAC addresses

### How It Works

1. Task logs into the switch REST API using provided credentials
2. Queries `/system/interfaces?depth=2&attributes=...`
3. Stores results in `aoscx_enhanced_interface_facts`
4. Logs out to clean up the session

### Trade-offs

| Aspect | Standard Facts | Enhanced Facts |
|--------|---------------|----------------|
| IPv6 addresses | URI references only | Actual addresses |
| Anycast IPs | Not available | Available |
| Extra API call | No | Yes (login + query + logout) |
| Credentials | Via aoscx modules | Direct REST API |

### REST API Version Requirement

**Important:** The `aoscx_facts` module reports an older REST API version (e.g., `10.09`), but this version returns `ip6_addresses` as URL references instead of actual data. You need a newer API version for proper IPv6 expansion.

The role attempts to auto-detect the best version via `/rest/v1/firmware`, but this may require authentication. If auto-detection fails, set the version manually:

```yaml
# Tested working versions for ip6_addresses expansion:
aoscx_rest_api_version: "10.14"  # or "10.13", "10.17", etc.
```

| REST API Version | ip6_addresses Format |
|------------------|---------------------|
| 10.09 | URL string (❌ doesn't work) |
| 10.13+ | Dict with addresses (✅ works) |

**Testing tip:** Check what version your switch supports via web browser:
`https://<switch-ip>/rest/v10.14/system/interfaces?depth=2`

### Current Status

With enhanced facts and correct REST API version:
- ✅ IPv6 addresses used for change detection (skip already-configured)
- ✅ VSX virtual IPs available for anycast comparison
- ✅ Truly idempotent IPv6 and anycast configuration

---

## Notes for Users

### When to Use Fast Mode
- Initial deployments (greenfield)
- Trusted NetBox data
- Time-critical deployments
- Virtual lab environments

### When NOT to Use Fast Mode
- Production with manual changes
- Brownfield migrations
- Drift detection needed
- Compliance verification

### Parallelization with Ansible Forks

Don't forget the Ansible-level parallelization:

```ini
# ansible.cfg
[defaults]
forks = 10  # Run 10 devices in parallel
```

Current performance (6 devices):
- Serial: 6 × 5.3 min = 32 min
- Parallel (6 forks): max(5.3 min) = 5.3 min
- You're already benefiting from this!

---

## Conclusion

The role prioritizes **safety and idempotency** over speed, which is appropriate for production use. However, for specific use cases (labs, greenfield, CI/CD), performance optimizations are valuable.

**Recommendation:** Start with Phase 1 (fast mode + connection optimization) for immediate 20-30% improvement with minimal risk. Evaluate Phase 2 based on actual needs.

**Do NOT implement Phase 3** unless you specifically need a "bulk push" tool rather than an idempotent configuration management system.
