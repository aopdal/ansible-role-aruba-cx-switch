# OSPF authentication — example var layout

This example shows the recommended way to provide per-VRF OSPF MD5 keys to
the role.

## Files

- `group_vars/routing-switch/vault.yml` — **encrypted** with `ansible-vault`.
  Contains `vault_ospf_auth_keys`, a dict keyed by VRF name.
- `group_vars/routing-switch/ospf.yml` — plaintext indirection layer.
  Exposes `ospf_auth_keys` (referenced by templates/tasks) and
  `ospf_auth_key_id`.

Copy both files into your inventory's `group_vars/routing-switch/`
directory, then encrypt the vault file:

```bash
ansible-vault encrypt group_vars/routing-switch/vault.yml
```

## How it is consumed

- **L3 task path** (`configure_l3_interface_common.yml`) calls
  `build_l3_config_lines` with `ospf_auth_keys` and `ospf_auth_key_id`.
  When an interface has an OSPF area set and a key exists for the
  interface's VRF, an
  `ip ospf message-digest-key <id> md5 [ciphertext ]<secret>` line is
  emitted on that interface. The task is run with `no_log: true` whenever
  `ospf_auth_keys` is non-empty.
- **Templated path** (`templates/int_*.j2`, `templates/ospf.j2`) emits the
  same per-interface line and adds `area <id> authentication message-digest`
  per VRF in the OSPF router config.

## Cleartext now, ciphertext later

Each entry has an `encrypted` flag:

```yaml
vault_ospf_auth_keys:
  default:
    secret: "MySecret"
    encrypted: false   # pushed as: md5 MySecret
  tenant_a:
    secret: "$1$mdp$abcdef..."
    encrypted: true    # pushed as: md5 ciphertext $1$mdp$abcdef...
```

Workflow:

1. Push cleartext (`encrypted: false`) the first time.
2. Run `show running-config` on the device, copy the ciphertext form of
   the `message-digest-key`.
3. Replace `secret` with the ciphertext and set `encrypted: true`.
4. Re-run the playbook — output stays idempotent.
