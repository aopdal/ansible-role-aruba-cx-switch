# Fact Gathering

The role supports two ways of gathering device facts. The key difference
between them is **data completeness**: the default `aoscx_facts` module
(pyaoscx-based) is missing information the role needs for several
features, and REST API fact gathering exists to fill those gaps. It also
happens to be faster, but that's a secondary benefit - the actual
mechanism that keeps idempotent reruns fast is a separate layer, covered
in [Change detection](#change-detection-identify__changesyml) below, that
compares whichever facts were gathered against NetBox's intended state.

> **History**: an earlier `aoscx_fast_mode` variable tried to speed things
> up by skipping fact gathering entirely. That made runs *slower* in
> practice — without device state to compare against, the role treated
> every VLAN and interface as needing configuration, pushing more config
> (and making more API calls) than a normal run. It was deprecated and
> fully removed in v0.7.0; see [CHANGELOG.md](CHANGELOG.md) if you're
> looking for it. Use `aoscx_gather_facts_rest_api: true` below instead —
> it fills in data the default module can't provide, which is what makes
> accurate comparison (and therefore a genuine speedup) possible.

## Two fact-gathering modes

| | `aoscx_facts` module (default) | REST API direct (`aoscx_gather_facts_rest_api: true`) |
|---|---|---|
| IPv6 addresses | URI references only, not usable for comparison | Actual addresses |
| VSX virtual IPs | Not included | Included |
| EVPN/VXLAN facts | Separate queries | Same session |
| Compatibility | All supported firmware versions | Requires REST API v10.15+ |
| Typical time (50 interfaces) | 15-30 seconds | 3-5 seconds |
| API calls | Multiple (per resource) | 2-4 total (single session) |

Both modes populate the same `network_resources` facts structure the rest
of the role reads from, so nothing downstream needs to know which mode
gathered them. Where a mode can't provide real data for a field (IPv6
addresses being the main case - see
[FILTER_PLUGINS.md](FILTER_PLUGINS.md#ipv6-address-handling)), the role
falls back to pushing that config unconditionally rather than silently
getting it wrong.

## REST API-based fact gathering (recommended)

The `aoscx_facts` module doesn't expose everything the role needs -
notably real IPv6 addresses (only URL references) and VSX virtual IPs.
Enable direct REST API calls instead to get complete data in a single
session, which is also faster:

```yaml
# group_vars or playbook
aoscx_gather_facts_rest_api: true
aoscx_rest_api_version: "10.15"  # Minimum version required

# REST API credentials (optional - defaults to ansible_host/ansible_user/ansible_password)
aoscx_rest_host: "{{ ansible_host }}"  # Switch management IP/hostname
aoscx_rest_user: "admin"                # REST API username
aoscx_rest_password: "{{ vault_switch_password }}"  # REST API password
aoscx_rest_validate_certs: false        # SSL certificate validation
```

### What it provides

A single authenticated REST API session gathers:

- **Interfaces** - Full config with IPv6, VSX virtual IPs, VLAN assignments
- **VLANs** - Complete VLAN definitions
- **EVPN** - Global EVPN config and per-VLAN settings (when enabled)
- **VXLAN/VNI** - VNI mappings (when enabled)

Several features — OSPF, VSX, static routes, VRFs/route-targets, STP,
port-access, DHCP relay — also get their facts through this same
REST API path; see "Selective fact gathering" below for when their
queries run.

### How it works

```
1. Login to REST API (single authentication)
2. Query /system/interfaces?depth=2 (interfaces + IPv6 + VSX)
3. Query /system/vlans?depth=2 (VLANs)
4. Query /system/evpn?depth=2 (if EVPN enabled)
5. Query /system/virtual_network_ids?depth=1 (if VXLAN enabled)
6. Logout (cleanup session)
```

### Requirements

- REST API version 10.15 or later
- Direct network access from the Ansible controller to the switch
  management interface

### Migration from `aoscx_facts`

Enable the variable — the role handles the data transformation:

```yaml
# Before (using aoscx_facts module)
aoscx_gather_facts: true

# After (using REST API direct)
aoscx_gather_facts_rest_api: true
aoscx_rest_api_version: "10.15"
```

## Selective fact gathering with `aoscx_test_mode`

Feature-specific REST queries (OSPF, VSX, static routes, VRFs, STP,
EVPN/VXLAN, port-access, DHCP relay) only run when their data has a
consumer: the matching `aoscx_configure_*` flag must also be true. In a
regular run, if a feature is disabled (e.g. `aoscx_configure_vsx: false`),
the role skips that feature's REST calls entirely, since nothing
downstream would use the facts.

Test/report-only playbooks (e.g. the `aruba-role-testing` workspace) often
set `aoscx_configure_*: false` to verify device state without pushing
config, but still need the REST facts gathered so they can compare NetBox
intent against what the device actually has. Set `aoscx_test_mode: true`
for these playbooks to force the REST queries regardless of the
`aoscx_configure_*` flags:

```yaml
aoscx_gather_facts_rest_api: true
aoscx_test_mode: true      # gather all feature facts for verification
aoscx_configure_ospf: false
aoscx_configure_vsx: false
```

## Change detection (`identify_*_changes.yml`)

Fast fact gathering only matters if the role then avoids doing unnecessary
work with the facts it gathered. That's the job of the
`identify_vlan_changes.yml`, `identify_interface_changes.yml`,
`identify_vrf_changes.yml`, and `identify_ospf_changes.yml` task files
(see `tasks/main.yml`): each one compares gathered device facts against
NetBox-desired state up front and sets a single source-of-truth changes
structure (`vlan_changes`, `interface_changes`, etc.) that every
downstream configuration and cleanup task reads from, instead of every
task re-deriving its own idea of "did this change."

This is what actually keeps a no-op rerun fast and idempotent — VLANs,
interfaces, VRFs, and OSPF settings that already match NetBox are simply
not pushed, so a rerun is dominated by fact-gathering time, not
configuration time. See
[VLAN_CHANGE_IDENTIFICATION_WORKFLOW.md](VLAN_CHANGE_IDENTIFICATION_WORKFLOW.md)
for the fullest write-up of the pattern; the other `identify_*` files
follow the same shape for their feature.

## Parallelizing across devices

The change-detection work above is per-device; across devices, Ansible's
own fork-based parallelism applies as normal:

```ini
# ansible.cfg
[defaults]
forks = 10  # Run up to 10 devices in parallel
```

There's nothing role-specific here — it's standard Ansible behavior, worth
remembering because it's easy to leave at the low default (`5`) and
bottleneck a large inventory.
