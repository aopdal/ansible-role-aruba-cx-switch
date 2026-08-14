# VSX Configuration

This page is the single reference for VSX (Virtual Switching Extension)
configuration with this role. It covers:

1. [How VSX is modelled in NetBox](#how-vsx-is-modelled-in-netbox)
2. [Config context fields](#config-context-fields)
3. [Complete example (primary + secondary)](#complete-example-primary--secondary)
4. [Change detection and idempotency](#change-detection-and-idempotency)
5. [Task ordering and tags](#task-ordering-and-tags)
6. [Operational notes](#operational-notes)

## How VSX is modelled in NetBox

VSX provides active-active redundancy between a pair of AOS-CX switches,
which downstream devices see as a single logical switch (paired with
MCLAG on the member-facing interfaces). Configuration is driven by one
device custom field plus a set of config_context keys:

| NetBox object | Field | Purpose |
|---|---|---|
| Device custom field | `device_vsx` (Boolean) | Enable/disable VSX configuration on this device |
| Device config_context | `vsx_role`, `vsx_system_mac`, `vsx_isl_lag`, `vsx_keepalive_vrf`, `vsx_keepalive_src`, `vsx_keepalive_peer` | VSX pairing parameters |

Both the custom field and config_context must be set — VSX tasks are
skipped entirely unless `custom_fields.device_vsx` is `true` **and**
`aoscx_configure_vsx: true` (default `false` — this is an opt-in feature,
unlike most others in this role). Task file:
[`tasks/configure_vsx.yml`](../tasks/configure_vsx.yml).

## Config context fields

| Key | Required | Description |
|---|---|---|
| `vsx_role` | Yes | `primary` or `secondary` — exactly one of each per pair |
| `vsx_system_mac` | Yes | Shared MAC address, identical on both peers |
| `vsx_isl_lag` | Recommended | Inter-Switch Link LAG interface (e.g. `lag256`). Used for both the live `aoscx_vsx` push and idempotency comparison. Defaults to `lag256` if unset. |
| `vsx_keepalive_peer` | Yes | IP address of the VSX peer's keepalive interface |
| `vsx_keepalive_src` | Yes | This switch's source IP for the keepalive link |
| `vsx_keepalive_vrf` | No (default `mgmt`) | VRF the keepalive link runs in |

## Complete example (primary + secondary)

**Primary switch:**

```yaml
# Device custom field
device_vsx: true
```

```yaml
# Device config context
vsx_role: "primary"
vsx_system_mac: "02:00:00:00:01:00"
vsx_isl_lag: "lag256"
vsx_keepalive_peer: "192.168.100.2"
vsx_keepalive_src: "192.168.100.1"
vsx_keepalive_vrf: "mgmt"
```

**Secondary switch** — same `vsx_system_mac` and `vsx_isl_lag`, role and
keepalive addresses swapped:

```yaml
device_vsx: true
```

```yaml
vsx_role: "secondary"
vsx_system_mac: "02:00:00:00:01:00"   # identical to primary
vsx_isl_lag: "lag256"
vsx_keepalive_peer: "192.168.100.1"   # peer is the primary
vsx_keepalive_src: "192.168.100.2"    # this switch's IP
vsx_keepalive_vrf: "mgmt"
```

Deployment rules:

1. **System MAC** must be identical on both peers.
2. Exactly one switch must be `primary`, the other `secondary`.
3. Keepalive peer IPs must be reachable (typically over the management
   network / `mgmt` VRF).
4. The ISL LAG interface itself (e.g. `lag256`) must already exist —
   create it via a normal LAG interface definition in NetBox before
   enabling VSX; this role does not create the LAG interface as part of
   VSX configuration.

## Change detection and idempotency

Requires [REST API fact gathering](PERFORMANCE_OPTIMIZATION.md)
(`aoscx_gather_facts_rest_api: true`) for accurate comparison; without it,
`vsx_diff` is never computed and the `aoscx_vsx` module call runs
unconditionally every time (still idempotent at the module level, but
every run reports `changed: true`).

[`vsx_config_diff`](filter_plugins/vsx.md) compares `device_role`,
`system_mac`, `isl_port`, `keepalive_vrf`, `keepalive_src_ip`, and
`keepalive_peer_ip` against `aoscx_vsx_facts` (REST API) and returns only
the fields that differ. `tasks/configure_vsx.yml` skips the `aoscx_vsx`
module call entirely when nothing differs.

There is no cleanup step for VSX — disabling `device_vsx` in NetBox does
not un-configure VSX on the device; VSX is a structural, high-impact
setting this role deliberately never removes automatically.

## Task ordering and tags

Tags: `vsx`, `ha` (see [README.md](../README.md#configuration-tags)). VSX
is tag-protected under
[TAG_DEPENDENT_INCLUDES.md](TAG_DEPENDENT_INCLUDES.md#1-vsx-virtual-switching-extension) —
not tagged `layer3`/`interfaces`, so a broad `-t layer3` or `-t interfaces`
run never touches VSX. Use `-t vsx` or `-t ha` (or a full untagged run) to
apply VSX changes.

## Operational notes

- **Module-based configuration**: uses `arubanetworks.aoscx.aoscx_vsx`
  (REST-backed, pyaoscx). `split_recovery_disable: true` and
  `config_sync_features: [vsx-global, mclag-interfaces]` are hardcoded by
  the task, not configurable via config_context.
- **ZTP/template generation**: when `aoscx_generate_template_config: true`,
  [`templates/vsx.j2`](../templates/vsx.j2) renders VSX as plain CLI for
  generated starting-point configs — see the ISL caveat above, and see
  [TEMPLATE_CONFIGURATION.md](TEMPLATE_CONFIGURATION.md) generally. This
  path has no idempotency logic of its own.
- **Filter reference**: see [filter_plugins/vsx.md](filter_plugins/vsx.md)
  for the full `vsx_config_diff` parameter and return-value reference.
- **NetBox custom field**: see
  [NETBOX_INTEGRATION.md](NETBOX_INTEGRATION.md) for how to create the
  `device_vsx` device custom field in NetBox.
