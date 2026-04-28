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
5. [Operational notes](#operational-notes)

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

OSPF tasks only run when **both** are true:

- `aoscx_configure_ospf` is `true` (default) **and**
- The device's `device_ospf` custom field is `true`

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

## Interface configuration

OSPF on an interface is enabled by setting two custom fields in
NetBox:

```yaml
# On each OSPF-enabled interface
if_ip_ospf_1_area: "0.0.0.0"           # area ID
if_ip_ospf_network: "point-to-point"   # optional network type
```

Both the **L3 task path** (`build_l3_config_lines`) and the
**templated path** (`templates/int_*.j2`) emit:

```text
interface 1/1/10
   ip ospf 1 area 0.0.0.0
   ip ospf network point-to-point
```

Loopbacks, physical, LAG, sub-interface, and VLAN interfaces are all
covered. The role compares against `aoscx_ospf_interface_facts`
(gathered via REST) to skip pushes for interfaces already in the
correct area — see [the L3 helpers
documentation](filter_plugins/l3_config_helpers.md) for details.

## Interface MD5 authentication

OSPFv2 supports MD5 message-digest authentication. The role applies
the **same key to all interfaces in the same VRF**, which matches
typical operational practice.

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
    secret: "ChangeMe-DefaultVrfSecret"
    encrypted: false        # cleartext, pushed as: md5 <secret>
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
    secret: "ChangeMe-DefaultVrfSecret"
    encrypted: false
  mgmt:
    secret: "ChangeMe-MgmtVrfSecret"
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

1. Push cleartext (`encrypted: false`) the first time. The L3 task is
   automatically wrapped with `no_log: true` whenever
   `ospf_auth_keys` is non-empty.
2. On the device, run `show running-config` and copy the ciphertext
   form of the `message-digest-key` line.
3. Replace `secret` with the ciphertext, set `encrypted: true`,
   re-run the playbook.
4. Subsequent runs are idempotent (no false "changed" diffs caused by
   the device echoing the encrypted form).

### What gets generated

For an interface in VRF `tenant_a` with `if_ip_ospf_1_area = 0.0.0.0`:

```text
interface 1/1/10
   ip ospf 1 area 0.0.0.0
   ip ospf message-digest-key 1 md5 ciphertext $1$mdp$abcdef...
```

And in `templates/ospf.j2` for the same VRF:

```text
router ospf 1 vrf tenant_a
    router-id 10.0.0.1
    area 0.0.0.0
    area 0.0.0.0 authentication message-digest
```

## Operational notes

- **`no_log`**: the L3 push task sets `no_log: true` whenever
  `ospf_auth_keys` is non-empty. Output of that task will show
  `[censored due to no_log]` — this is intentional. Set
  `ospf_auth_keys: {}` to debug interface line generation without
  secrets.
- **Key rotation**: change `ospf_auth_key_id` and rotate `secret`
  for the affected VRFs. AOS-CX supports multiple keys; only the
  highest ID is used for transmit.
- **Mixed device fleet**: keys are looked up only when an interface
  has `if_ip_ospf_1_area` set, so devices without OSPF are
  unaffected. The OSPF tasks themselves are also gated by the
  `device_ospf` custom field.
- **Filter reference**: see
  [filter_plugins/ospf_filters.md](filter_plugins/ospf_filters.md)
  for `select_ospf_interfaces`, `extract_ospf_areas`, and
  `validate_ospf_config`, and
  [filter_plugins/l3_config_helpers.md](filter_plugins/l3_config_helpers.md)
  for how interface lines are assembled.
