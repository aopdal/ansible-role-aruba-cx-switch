# SNMP Configuration

This page is the reference for SNMP configuration with this role. It
covers:

1. [What is configured](#what-is-configured)
2. [Variables](#variables)
3. [Agent VRF resolution](#agent-vrf-resolution)
4. [System location from NetBox](#system-location-from-netbox)
5. [SNMPv3 users and secrets](#snmpv3-users-and-secrets)
6. [Change detection and idempotency](#change-detection-and-idempotency)
7. [Cleanup](#cleanup)
8. [Known limitations](#known-limitations)

## What is configured

```text
snmp-server vrf mgmt
snmp-server system-location bgp-isp-2/bgp-location
snmp-server system-contact noc@example.net
snmpv3 user snmplab auth sha auth-pass ciphertext AQB... priv aes priv-pass ciphertext AQB...
```

SNMP is configured from **group_vars** (not NetBox config context), with
the system location derived from the device's NetBox site and location.

SNMP tasks only run when **both** are true:

- `aoscx_configure_snmp` is `true` (default) **and**
- at least one of `snmpv3_users`, `snmp_system_location`,
  `snmp_system_contact` is set, or `snmp_vrf` is set to something other
  than `auto` — **or** `aoscx_idempotent_mode` is `true`

In idempotent mode with no SNMP variables set, the desired state is "no
SNMP" and SNMP is removed from the device (see [Cleanup](#cleanup)). Set
`aoscx_configure_snmp: false` to leave SNMP on the device untouched, e.g.
when it is managed outside this role.

The include is tagged `snmp` + `services` and runs after VRFs (the agent
is bound to a VRF), alongside NTP and DNS.

## Variables

| Variable               | Default | Description                                                                 |
|------------------------|---------|-----------------------------------------------------------------------------|
| `aoscx_configure_snmp` | `true`  | Feature toggle.                                                              |
| `snmp_vrf`             | `auto`  | VRF for `snmp-server vrf`. `auto` = see [Agent VRF resolution](#agent-vrf-resolution); any other value is used as-is (e.g. a user-defined management VRF). |
| `snmp_system_location` | `""`    | Explicit location. Empty = derived from NetBox.                              |
| `snmp_system_contact`  | `""`    | `snmp-server system-contact`. Not configured when empty.                     |
| `snmpv3_users`         | `[]`    | SNMPv3 user definitions (no secrets).                                        |
| `snmpv3_user_keys`     | `{}`    | SNMPv3 secrets per user name. Keep in a vault.                               |

## Agent VRF resolution

With `snmp_vrf: auto`:

the management VRF, i.e. the VRF of the interface carrying the device's
`primary_ip4` (same rule as the ssh/https-server VRFs, see
[BASE_CONFIGURATION.md](BASE_CONFIGURATION.md#management-vrf-and-sshhttps-server-vrfs-tasksconfigure_access_switch_server_vrfsyml)):

- `mgmt` when `primary_ip4` is on the interface named `mgmt` (the AOS-CX
  out-of-band management port)
- the interface's NetBox VRF when it has one, otherwise `default`
  (in-band management, e.g. a VLAN interface)
- when `primary_ip4` is not known: `mgmt` if the `mgmt` interface has an IP
  address, otherwise `default`

The NetBox `mgmt_only` flag is deliberately not used: it is also set on
in-band management interfaces, e.g. `vlan1` on a CX 6000, which has no
out-of-band port (and no `mgmt` VRF).

## System location from NetBox

When `snmp_system_location` is empty, the location is built from the
NetBox inventory host vars `sites` / `locations` (or `site` / `location`
when the inventory plugin runs without `plurals: true`):

| NetBox data                            | Result                   |
|----------------------------------------|--------------------------|
| site `bgp-isp-2`, location `bgp-location` | `bgp-isp-2/bgp-location` |
| site `bgp-isp-2`, no location          | `bgp-isp-2`              |
| neither                                | not configured           |

Spaces are allowed; AOS-CX stores and shows the value unquoted.

## SNMPv3 users and secrets

User definitions and secrets are split, following the same pattern as
OSPF MD5 keys (`ospf_auth_keys`, see
[OSPF_CONFIGURATION.md](OSPF_CONFIGURATION.md#interface-md5-authentication)):
the structure lives in plain group_vars, only the secrets in a vault.

```yaml
# group_vars/aoscx/vars.yml
snmpv3_users:
  - name: snmplab
    auth_protocol: sha      # md5|sha|sha224|sha256|sha384|sha512
    priv_protocol: aes      # aes|aes192|aes256|des
    access_level: ro        # ro|rw (default ro)
snmpv3_user_keys: "{{ vault_snmpv3_user_keys }}"
```

```yaml
# group_vars/aoscx/vault.yml (ansible-vault encrypted)
vault_snmpv3_user_keys:
  snmplab:
    auth_pass:
      secret: "AQBapYhC..."
      encrypted: true       # AOS-CX ciphertext
    priv_pass:
      secret: "AQBapQYf..."
      encrypted: true
```

A key may also be given as a plain string, which is treated as
`encrypted: false` (plaintext).

Validation fails the play before anything is pushed when a user has an
unknown protocol or access level, `priv_protocol` without
`auth_protocol`, a missing key, or a duplicate name. `md5` and `des`
produce a warning (weak protocols) but are accepted.

The user push task is `no_log: true` (hardcoded).

### Getting the ciphertext

Create the user once on a switch with plaintext passphrases and read the
ciphertext back from the running-config:

```text
snmpv3 user snmplab auth sha auth-pass plaintext <auth> priv aes priv-pass plaintext <priv> access-level ro
show running-config | include snmpv3
```

The ciphertext depends on the switch's export password; devices sharing
the same (default) export password accept the same ciphertext.

## Change detection and idempotency

With REST API fact gathering (`aoscx_gather_facts_rest_api: true`), the
role reads the device's SNMP state into `aoscx_snmp_facts` and
`get_snmp_changes` pushes only what differs:

| Setting              | REST source                                         | Compared                         |
|----------------------|-----------------------------------------------------|----------------------------------|
| Agent VRF            | `/system/vrfs` → `snmp_enable`                      | desired VRF enabled               |
| Location / contact   | `/system` → `other_config.system_location` / `system_contact` | string equality        |
| SNMPv3 users         | `/system/snmpv3_users?depth=2`                      | see below                         |

SNMPv3 users are compared on presence, `auth_protocol`, `priv_protocol`
and `access_level`. Passphrases are compared **only for ciphertext keys**
(`encrypted: true`): the REST API returns the same ciphertext as the
running-config and the vault, so the comparison is exact. **Plaintext
passphrases are never compared** — the device only holds ciphertext, so
no comparison is possible (see CLAUDE.md §4.7). A plaintext user whose
protocols and access level match is left alone, so the run stays
idempotent, but changing *only* a plaintext passphrase is not detected.
To rotate a plaintext passphrase, remove the user from the device (or
switch to ciphertext) so it is pushed again.

Without REST facts, every line is pushed with `aoscx_config`
`match: line`, which compares against the running-config:

- Ciphertext keys are idempotent. The user line is rendered exactly as
  AOS-CX shows it (verified on 10.16): `access-level ro` is the default
  and not shown, so the role only emits `access-level rw`.
- Plaintext keys report `changed` on every run, because a plaintext line
  never matches the ciphertext in the running-config. This is a platform
  limitation, not a bug.

REST fact gathering works under `--check`, so a check run previews the
real changes, including cleanup.

SNMP facts are gathered whenever SNMP variables are set, in
`aoscx_idempotent_mode`, and in `aoscx_test_mode` (even with no SNMP
variables, so report playbooks can verify that nothing is configured).
Report playbooks can reuse `resolve_snmp_vrf`, `build_snmp_system_location`
and `get_snmp_changes` on `aoscx_snmp_facts` to report drift without
pushing anything.

## Cleanup

With `aoscx_idempotent_mode: true` **and** REST facts, the role removes
SNMP state that is not in the variables, after pushing the desired state
(so a moved agent VRF is added before the old one is removed):

| Device state                          | Removal line                     |
|---------------------------------------|----------------------------------|
| SNMPv3 user not in `snmpv3_users`     | `no snmpv3 user <name>`          |
| `snmp-server vrf` other than desired  | `no snmp-server vrf <vrf>`       |
| location set, none desired            | `no snmp-server system-location` |
| contact set, none desired             | `no snmp-server system-contact`  |

When **no** SNMP variable is set (e.g. commented out in group_vars), the
feature still runs in idempotent mode with an empty desired state, so all
of the above is removed: every SNMPv3 user, every agent VRF, location and
contact. Outside idempotent mode, no SNMP variables means the feature is
skipped and the device is left as is.

To keep SNMP that is managed outside this role while running in
idempotent mode, set `aoscx_configure_snmp: false`.

## Known limitations

- Cleanup needs REST facts; without them nothing is removed.
- Changing a user's protocols requires the new line to be pushed;
  AOS-CX replaces the user definition.
- SNMPv1/v2c communities, traps and notification hosts are not
  configured.
