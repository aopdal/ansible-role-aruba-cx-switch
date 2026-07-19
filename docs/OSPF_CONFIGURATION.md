# OSPF Configuration

This page is the single reference for OSPFv2 configuration with this
role. It covers:

1. [How OSPF is modelled in NetBox](#how-ospf-is-modelled-in-netbox)
   (custom fields + config context)
2. [Router and area configuration](#router-and-area-configuration)
   (per VRF)
3. [Interface configuration](#interface-configuration)
   (area, network type)
4. [Interface MD5 authentication](#interface-md5-authentication)
   (per-VRF secrets, vault layout, cleartext-to-ciphertext migration)
5. [OSPF facts gathering](#ospf-facts-gathering)
   (`aoscx_ospf_router_facts`, `aoscx_ospf_interface_facts`)
6. [Operational notes](#operational-notes)

## How OSPF is modelled in NetBox

OSPF is configured **declaratively from NetBox** — no per-host
playbook variables are needed for the routing topology itself.

| NetBox object | Field / source                          | Purpose                                            |
|---------------|-----------------------------------------|----------------------------------------------------|
| Device        | Custom field `device_ospf` (bool)       | Master switch — must be `true` to push OSPF        |
| Device        | Custom field `device_ospf_1_routerid`   | OSPF router-id for instance 1                      |
| Device        | Config context `ospf_process_id` (int)  | OSPF process id (default `1`)                      |
| Device        | Config context `ospf_vrfs` (list)       | Per-VRF area list (recommended multi-VRF format)   |
| Device        | Config context `ospf_1_vrf` + `ospf_areas` | Single-VRF legacy format (still supported)      |
| Interface     | Custom field `if_ip_ospf_1_area`        | Area ID — set ⇒ interface participates in OSPF     |
| Interface     | Custom field `if_ip_ospf_network`       | Network type (e.g. `point-to-point`); optional     |
| Interface     | Custom field `if_ip_ospf_passive` (bool)| Passive interface — no OSPF hellos sent/received   |
| Interface     | Custom field `if_ip_ospf_auth` (bool)   | Enable authentication on this interface (default `true`) |

OSPF *configuration* tasks only run when **both** are true:

- `aoscx_configure_ospf` is `true` (default) **and**
- The device's `device_ospf` custom field is `true`

OSPF *facts gathering* is independent of `aoscx_configure_ospf` — see
[OSPF facts gathering](#ospf-facts-gathering) below.

See [TAG_DEPENDENT_INCLUDES.md](TAG_DEPENDENT_INCLUDES.md) for the
tag-based gating model.

## Router and area configuration

### Multi-VRF format (recommended)

Device config context:

```yaml
ospf_process_id: 1                     # optional, defaults to 1
ospf_vrfs:
  - vrf: "default"                     # see VRF naming rules below
    areas:
      - area: "0.0.0.0"                # backbone
      - area: "0.0.0.1"
  - vrf: "tenant_a"
    areas:
      - area: "0.0.0.0"
```

Combined with `device_ospf_1_routerid: "10.0.0.1"`, this produces:

```text
router ospf 1 vrf default
    router-id 10.0.0.1
    area 0.0.0.0
    area 0.0.0.1
router ospf 1 vrf tenant_a
    router-id 10.0.0.1
    area 0.0.0.0
```

### Single-VRF legacy format

Still supported but discouraged for new deployments:

```yaml
ospf_1_vrf: "default"
ospf_areas:
  - ospf_1_area: "0.0.0.0"
  - ospf_1_area: "0.0.0.1"
```

The role normalizes this internally to the multi-VRF shape.

!!! warning "VRF names MUST match NetBox exactly"
    The `vrf` field in `ospf_vrfs` is matched verbatim against:

    - The VRF name as stored in NetBox
      (`interface.vrf.name`) for interface-to-VRF placement, and
    - The lookup key in [`ospf_auth_keys`](#interface-md5-authentication)
      for authentication secrets.

    Common pitfalls:

    - The default/global VRF is exposed by NetBox as **`Global`**.
      The role normalizes that to **`default`** at runtime, so always
      use `default` in `ospf_vrfs` and in `ospf_auth_keys`.
    - VRF names are **case-sensitive**: `Tenant_A` ≠ `tenant_a`.
    - Whitespace and `-` vs `_` must match (`tenant-a` ≠ `tenant_a`).

!!! note "VRFs not in use on the device are skipped"
    `configure_ospf.yml` only pushes OSPF router/area config for VRFs
    that actually have interfaces assigned on this device (or the
    built-in `default` VRF, which always exists). If `ospf_vrfs` lists a
    VRF that exists in NetBox but has no interfaces on this switch, that
    VRF's OSPF config is silently dropped instead of being pushed —
    pushing it would fail since the VRF itself is never created on the
    device. See
    [`filter_ospf_vrfs_in_use`](filter_plugins/ospf_filters.md).

## Interface configuration

OSPF on an interface is enabled by setting custom fields in NetBox:

```yaml
# On each OSPF-enabled interface
if_ip_ospf_1_area: "0.0.0.0"           # area ID (required)
if_ip_ospf_network: "point-to-point"   # optional network type
if_ip_ospf_passive: false              # optional, passive interface (default: false)
if_ip_ospf_auth: true                  # optional, enable auth (default: true)
```

The role configures interfaces using `aoscx_config` (CLI path) for
area attachment, network type, authentication, and passive mode.

### Network Types

Supported values for `if_ip_ospf_network`:

- `point-to-point` (typical for routed links)
- `broadcast` (typical for multi-access networks)
- `nbma` (non-broadcast multi-access)
- `point-to-multipoint`
- `loopback` (implicit for loopback interfaces)

### Passive Interfaces

Set `if_ip_ospf_passive: true` to suppress OSPF hello packets on an
interface while still advertising the subnet. Useful for:

- User-facing subnets (no OSPF neighbors expected)
- Stub networks
- Management interfaces in OSPF

The role applies `ip ospf passive` via CLI and can remove it when the
NetBox state changes back to `false`.

!!! note "Loopbacks are implicitly passive"
    Loopback interfaces cannot form adjacencies. The role automatically
    excludes them from passive configuration tasks.

### Selective Authentication

By default, all OSPF interfaces in a VRF use the same MD5 key (see
[Interface MD5 authentication](#interface-md5-authentication)). To
disable authentication on specific interfaces:

```yaml
if_ip_ospf_auth: false
```

This is useful for:

- Migrating from authenticated to non-authenticated networks
- Mixed environments where some neighbors don't support MD5
- Troubleshooting adjacency issues

Generated configuration for standard interface:

```text
interface 1/1/10
   ip ospf 1 area 0.0.0.0
   ip ospf network point-to-point
```

For passive interface with authentication disabled:

```text
interface vlan100
   ip ospf 1 area 0.0.0.0
   ip ospf network broadcast
   ip ospf passive
```

!!! info "Change detection and idempotency"
  The role uses CLI commands (`aoscx_config`) for both new and
  existing OSPF interface configurations. Area/network/auth/passive
  are applied in a single path with connection override to
  `ansible.netcommon.network_cli`.

## Interface MD5 authentication

OSPFv2 supports MD5 message-digest authentication. The role applies
authentication **per-VRF** using CLI interface commands with
`aoscx_config`. The OSPF interface task runs with `no_log: true`
to avoid exposing secrets in logs.

### CLI-Based Authentication

The role uses a **unified task approach** that configures area,
network type, and authentication in a single interface command block.
This ensures:

- **Bidirectional control**: Can enable AND remove authentication
- **Idempotency**: Works on both new and existing configurations
- **Encrypted support**: Handles both `md5 plaintext` and `md5 ciphertext`

Authentication is applied when ALL conditions are met:

1. Interface is NOT a loopback (loopbacks have no neighbors)
2. Interface is NOT passive (`if_ip_ospf_passive != true`)
3. Interface authentication is enabled (`if_ip_ospf_auth != false`)
4. Auth key exists for the interface's VRF in `ospf_auth_keys`

When any condition fails, the role applies:

- `no ip ospf authentication message-digest`
- `no ip ospf message-digest-key <id>`

to explicitly remove authentication if it exists.

### Removing Authentication

To remove MD5 authentication from interfaces, use one of these methods:

**Method 1: Per-interface control**

```yaml
# In NetBox, set custom field:
if_ip_ospf_auth: false
```

**Method 2: Remove VRF key** (affects all interfaces in VRF)

```yaml
ospf_auth_keys:
  default:    # This VRF will have authentication
    secret: "ChangeMe"
  # tenant_a removed - all interfaces in tenant_a will have auth removed
```

**Method 3: Empty the entire dict** (removes all authentication)

```yaml
ospf_auth_keys: {}
```

### Variables

| Variable             | Type | Required | Description                                                                                              |
|----------------------|------|----------|----------------------------------------------------------------------------------------------------------|
| `ospf_auth_keys`     | dict | no       | Per-VRF MD5 key dictionary (see below). When unset/empty, no authentication lines are emitted.           |
| `ospf_auth_key_id`   | int  | no       | MD5 key ID used in `ip ospf message-digest-key <id> md5 <secret>`. Default: `1`.                         |

### Shape of `ospf_auth_keys`

Each entry is keyed by **VRF name** (same matching rules as
[`ospf_vrfs`](#router-and-area-configuration)). The value may be either
a plain string (cleartext) or a dict:

```yaml
ospf_auth_keys:
  default:
    secret: "ChangeMe-Default"
    encrypted: false        # pushed as: md5 plaintext <secret>
  tenant_a:
    secret: "$1$mdp$abcdef0123456789abcdef01"
    encrypted: true         # pushed as: md5 ciphertext <secret>
  mgmt: "ShortFormStringIsAlsoOk"
```

!!! warning "Same VRF-naming rules apply here"
    Use `default` (not `Global`) for the global VRF. Names are
    case-sensitive and must match NetBox exactly. **If no entry
    matches an interface's VRF, no auth line is emitted for that
    interface** — neighbours will fail to come up.

    Validate coverage against the OSPF-enabled interfaces:

    ```yaml
    - assert:
        that:
          - ospf_interfaces
            | map(attribute='vrf.name', default='default')
            | map('replace', 'Global', 'default')
            | unique
            | difference(ospf_auth_keys.keys() | list)
            | length == 0
        fail_msg: "Missing OSPF auth key for one or more VRFs"
    ```

### Recommended layout (vault indirection)

Store secret material in `group_vars/<group>/vault.yml` under a
`vault_`-prefixed name and expose it via a plaintext indirection
file. Templates and tasks only reference `ospf_auth_keys`, so the
codebase stays grep-friendly without decrypting the vault.

```text
inventory/
└── group_vars/
    └── routing-switch/
        ├── ospf.yml      # plaintext: ospf_auth_keys = vault_ospf_auth_keys
        └── vault.yml     # ansible-vault encrypted
```

`vault.yml` (encrypt with `ansible-vault encrypt`):

```yaml
vault_ospf_auth_keys:
  default:
    secret: "ChangeMe-Default"
    encrypted: false
  mgmt:
    secret: "ChangeMe-MgmtVrf"
    encrypted: false
```

`ospf.yml` (plaintext):

```yaml
ospf_auth_keys: "{{ vault_ospf_auth_keys }}"
ospf_auth_key_id: 1
```

A ready-to-copy skeleton ships in `examples/ospf-authentication/`.

### Cleartext now → ciphertext later

AOS-CX accepts both `md5 <plaintext>` and `md5 ciphertext <hash>`. The
`encrypted` flag lets you migrate without restructuring vars:

1. Push cleartext (`encrypted: false`) the first time. The OSPF
   interface task is automatically wrapped with `no_log: true` whenever
   authentication is being configured to protect secrets.
2. On the device, run `show running-config interface <name>` and copy
   the ciphertext form of the `message-digest-key` line.
3. Replace `secret` with the ciphertext, set `encrypted: true`,
   re-run the playbook.
4. Subsequent runs are idempotent (no false "changed" diffs).

!!! warning "Cleartext keys show as changed on every run"
    When using cleartext secrets (`encrypted: false`), the module
    compares your cleartext value against the device's encrypted value
    and always reports `changed: true` even though the configuration is
    functionally correct.

    **Solutions:**

    - **Development/Testing**: Accept the `changed` status (harmless)
    - **Production**: Use encrypted keys from the device for true
      idempotency (recommended workflow below)

    **Recommended production workflow:**

    1. Deploy cleartext key to first device of each hardware family
    2. Extract encrypted hash: `show run interface X | include message-digest-key`
    3. Update vault with encrypted value, set `encrypted: true`
    4. Deploy to remaining fleet → fully idempotent ✅

### What gets generated

The role configures OSPF authentication via interface CLI commands.
For an interface in VRF `tenant_a` with area `0.0.0.0`:

**With authentication enabled:**

```text
interface 1/1/10
   ip ospf 1 area 0.0.0.0
   ip ospf network point-to-point
   ip ospf authentication message-digest
   ip ospf message-digest-key 1 md5 ciphertext $1$mdp$abcdef...
```

**With authentication disabled** (`if_ip_ospf_auth: false` or no key for VRF):

```text
interface 1/1/10
   ip ospf 1 area 0.0.0.0
   ip ospf network point-to-point
   # No authentication commands
```

For ZTP/template-based deployments, per-interface authentication is
rendered by `templates/int_phys.j2`, `templates/int_lag.j2`, and
`templates/int_vlan.j2` (loopbacks are excluded, matching the runtime
task's `'loopback' not in item.interface_name` check). Each mirrors
the same `ospf_auth_keys[vrf]` lookup and plaintext/ciphertext handling
as `tasks/configure_ospf.yml`:

```text
interface 1/1/10
   ip ospf 1 area 0.0.0.0
   ip ospf network point-to-point
   ip ospf authentication message-digest
   ip ospf message-digest-key 1 md5 ciphertext $1$mdp$abcdef...
```

AOS-CX does not support area-level `authentication message-digest` —
only interface-level. `templates/ospf.j2` (the OSPF router/area
template) therefore only renders `router ospf`/`area` statements and
does not attempt authentication.

!!! note "Templates vs. Module Configuration"
    The role uses TWO paths for OSPF configuration:

    - **CLI task-based** (runtime via `tasks/configure_ospf.yml`): Used when
      managing live devices through Ansible. Secure, idempotent, and
      supports bidirectional changes including ciphertext keys.
    - **Template-based** (`templates/int_phys.j2`, `templates/int_lag.j2`,
      `templates/int_vlan.j2`, `templates/ospf.j2`): Used for ZTP config
      generation and migration scenarios where devices aren't yet
      accessible via Ansible API.

    Both paths generate the same final configuration.

## Known Limitations

### Cleartext Key Idempotency

**Issue:** Playbooks using cleartext MD5 keys (`encrypted: false`)
always show `changed: true` on the authentication task, even when
functionally correct.

**Cause:** The device stores MD5 keys in encrypted form in running
configuration. Re-applying `md5 plaintext <secret>` can still produce
cosmetic `changed` on some platforms.

**Workaround:** Use device-encrypted keys in production (see
[Cleartext now → ciphertext later](#cleartext-now-ciphertext-later)).

**Impact:** Cosmetic only — authentication IS configured correctly.

### Passive Interface Removal

**Issue:** The "Remove OSPF passive from non-passive interfaces" task
shows `changed: true` on ALL non-passive interfaces, even those that
never had `ip ospf passive` configured.

**Cause:** OSPF passive state is reconciled by applying `no ip ospf passive`
on non-passive interfaces. This can still report `changed` on platforms
that do not expose a clean pre-check for this state.

**Workaround:** None available.

**Impact:** Cosmetic only — `no ip ospf passive` is idempotent on the
device (no-op if passive wasn't configured).

### Passive Interface CLI Connection

**Requirement:** Passive interface configuration requires SSH/CLI
access (`ansible.netcommon.network_cli`) in addition to REST API access.

**Cause:** The `aoscx_ospf_interface` module doesn't support passive
configuration. The role uses `aoscx_config` CLI commands with
connection override (`ansible_connection: ansible.netcommon.network_cli`).

**Workaround:** Ensure SSH credentials are configured alongside REST
credentials.

**Impact:** Requires both connection types to be functional.

## OSPF facts gathering

When `aoscx_gather_facts_rest_api: true`, the role queries OSPF facts
from the device's REST API whenever the device's `device_ospf` custom
field is `true` — **independent of `aoscx_configure_ospf`**. This lets
report-only/verification playbooks (which typically set
`aoscx_configure_ospf: false` to avoid pushing config) still compare
what NetBox declares against what the device actually has configured.
It also means the facts-gathering logic itself is exercised on every
run where OSPF is enabled on the device, not only on runs that also
configure it.

Two facts variables are produced:

### `aoscx_ospf_router_facts`

Router-id, configured areas, and passive interfaces, per VRF and
process id. Queried from `/system/vrfs/{vrf}/ospf_routers/{process_id}`
for every VRF found in the NetBox OSPF config context (normalized via
the [`normalize_ospf_vrfs`](filter_plugins/ospf_filters.md) filter, so
both the multi-VRF and legacy single-VRF formats are covered).
`passive_interfaces` lives here (not on the interface facts below)
because AOS-CX models passive state as a per-router list, not a
per-interface REST attribute.

```yaml
aoscx_ospf_router_facts:
  default:
    "1":
      router_id: "10.0.0.1"
      areas: ["0.0.0.0", "0.0.0.1"]
      passive_interfaces: ["1/1/3", "loopback1"]
  tenant_a:
    "1":
      router_id: "10.0.0.1"
      areas: ["0.0.0.0"]
      passive_interfaces: []
```

### `aoscx_ospf_interface_facts`

Per-interface OSPF interface-type and authentication-type, keyed by
VRF, process id, and area. Queried from
`/system/vrfs/{vrf}/ospf_routers/{process_id}/areas/{area}/ospf_interfaces`
for every unique (VRF, area) combination found on NetBox OSPF
interfaces.

```yaml
aoscx_ospf_interface_facts:
  default:
    "1":
      "0.0.0.0":
        1/1/1:
          ospf_if_type: "ospf_iftype_ptop"
          ospf_auth_type: "md5"
```

This is also used internally by `configure_ospf.yml` / interface
change detection to skip interfaces where OSPF configuration has not
changed.

## Operational notes

- **Module-based configuration**: OSPF interface configuration uses
  `aoscx_ospf_interface` (REST API) with `state: update` for
  idempotent area, network type, and authentication management.

- **Unified task approach**: A single task handles area + network type
  + authentication configuration. The module requires auth parameters
  when auth exists on the device, so the role ALWAYS provides
  `ospfv2_auth_type` — either `md5` (with keys) or `none` (explicitly
  remove auth).

- **`no_log` protection**: The authentication task sets `no_log: true`
  to hide MD5 secrets. Output shows `[censored due to no_log]` — this
  is intentional for security.

- **Passive interface implementation**: Uses CLI commands
  (`aoscx_config`) with `ansible_connection: ansible.netcommon.network_cli`
  override since the REST module doesn't support passive configuration.
  Both `ip ospf passive` and `no ip ospf passive` are supported.

- **Loopback exclusion**: Loopback interfaces are automatically
  excluded from authentication (no neighbors) and passive configuration
  (implicit passive, not configurable).

- **Key rotation**: Change `ospf_auth_key_id` and rotate `secret` for
  affected VRFs. AOS-CX supports multiple keys; only the highest ID is
  used for transmit. Deploy new key first, wait for propagation, then
  remove old key.

- **Selective authentication**: Use `if_ip_ospf_auth: false` on
  specific interfaces to disable authentication while keeping it
  enabled for the rest of the VRF.

- **Mixed device fleet**: OSPF tasks are gated by `device_ospf` custom
  field and only run on interfaces with `if_ip_ospf_1_area` set.
  Devices without OSPF are unaffected.

- **Change detection**: Interfaces with cleartext keys or passive
  removal operations may show `changed: true` on every run (see [Known
  Limitations](#known-limitations)). This is expected and doesn't
  indicate configuration drift.

- **Filter reference**: See
  [filter_plugins/ospf_filters.md](filter_plugins/ospf_filters.md)
  for `select_ospf_interfaces`, `extract_ospf_areas`,
  `normalize_ospf_vrfs`, and `validate_ospf_config`.
