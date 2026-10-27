---
name: add-feature
description: Step-by-step checklist for adding or extending a switch feature in the aopdal.aruba_cx_switch role (new configure_*.yml, NetBox-driven change detection, placement in tasks/main.yml, tags, defaults, docs, changelog, tests). Use when the user asks to add support for a new AOS-CX feature or setting, or to extend an existing one with new behaviour.
---

# Add a feature to the role

Work through these steps in order. CLAUDE.md holds the rules; this skill is
the procedure. A good reference implementation of a complete feature is
commit `cb0273c` (HPE Aruba Networking Central) — `git show --stat cb0273c`
lists every file a typical feature touches.

## 1. Discover

- Read `tasks/main.yml`, the closest existing `tasks/configure_*.yml`, and
  its `docs/` page before writing anything.
- Find out where the desired state lives in NetBox: device custom field
  (`custom_fields.device_*`), device tag, config context, interface data,
  or plugin data (netbox-bgp). Ask the user if it is not obvious.
- Find out how current state is read from the device: `aoscx_facts`,
  REST facts (`tasks/gather_facts_rest_api.yml`, see
  `docs/FACT_GATHERING.md`), or running-config. Prefer REST facts.
- Decide which module pushes it: a pyaoscx module (inherits the
  inventory connection) or `aoscx_config` (must set
  `vars: ansible_connection: network_cli` on the task).

## 2. Variables

- Add every new variable to `defaults/main.yml` with a comment (intent,
  valid values, version requirement). Prefix `aoscx_`; feature toggle is
  `aoscx_configure_<feature>`. Operator-set feature data in group_vars is
  unprefixed and named after its domain (`snmp_*`, `ospf_auth_keys`).
- Never introduce a variable only through `default(...)`.

## 3. Change detection (idempotency)

- Put the desired-vs-current comparison in a pure filter in
  `netbox_filters_lib/<topic>.py` (use the `add-filter` skill), returning
  only what needs to change. Tasks act on that diff only.
- For non-trivial features, add `tasks/identify_<feature>_changes.yml`
  that sets a `<feature>_changes` fact, mirroring
  `identify_ospf_changes.yml` / `identify_vrf_changes.yml`.
- In `aoscx_idempotent_mode`, decide what gets removed when it is no
  longer in NetBox, and gate removal on `aoscx_idempotent_mode | bool`.

### Secrets (passwords, shared secrets, keys)

If the feature carries a secret, follow CLAUDE.md §4.7:

- Detect changes on presence/enablement, never by comparing cleartext
  against device state.
- Support an `encrypted: true` ciphertext input if the platform accepts
  one, and document it as the idempotent path.
- Hardcode `no_log: true` on every task that sees the secret.
- State up front in the docs page that cleartext input shows
  `changed: true` on every run.

## 4. Task file

- `tasks/configure_<feature>.yml`: FQCN modules, sentence-case task names
  starting with a verb, `when:` expressions that resolve to booleans
  (`x | length > 0`, never a bare dict/list).
- Template support for the generated starting config (if relevant):
  add to the matching `templates/*.j2` (2-space indent, AOS-CX syntax).

## 5. Placement in tasks/main.yml

- Check the dependency table in CLAUDE.md §3. Place the include after
  every prerequisite (VRF-bound → after VRFs; per-interface → after the
  interfaces exist; cleanup → after re-gathered facts). No dependencies →
  base-system block.
- Use `ansible.builtin.include_tasks` with `apply: tags:` and the same
  tags on the include, with a feature tag plus a layer tag. Add a comment
  above the include saying what it depends on.
- Gate on the toggle (`aoscx_configure_<feature> | bool`) and the NetBox
  custom field / tag if one exists.
- If the feature is tag-dependent, follow `docs/TAG_DEPENDENT_INCLUDES.md`.
- Update the dependency table in CLAUDE.md §3 in the same change.

## 6. Tests

- Unit tests for every new filter in `tests/unit/test_<topic>.py`, using
  real (trimmed) REST/NetBox payloads where possible.
- Add new filter names to `EXPECTED_FILTER_NAMES` in
  `tests/unit/test_netbox_filters.py`.

## 7. Docs and changelog

- New or updated topic page under `docs/` (see the table in CLAUDE.md
  §4.5). A new page also gets a link in `docs/README_DOCS.md` and a `nav`
  entry in `zensical.toml`.
- New variables: README.md "Role Variables" plus the topic page.
- New custom fields / tags: `docs/NETBOX_INTEGRATION.md`.
- `CHANGELOG.md` under `## [Unreleased]` (Added/Changed/Fixed...), then
  `make docs-sync`.

## 8. Verify

Run the `pre-pr-check` skill. Then tell the user that real-device
validation (idempotency rerun) happens in the sibling `autotest-aoscx`
project. Do not modify it, or `aruba-role-testing`, unless asked.
