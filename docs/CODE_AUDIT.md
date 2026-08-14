# Code Audit Report

**Original audit date:** 2026-08-12
**Trimmed:** 2026-08-13 — 19 of the 20 original findings were resolved; the
verbose per-finding writeups were removed to keep this page from going
stale. See the [resolved findings log](#resolved-findings-log) below for a
one-line-per-finding record, and git history / `git log --all -- docs/CODE_AUDIT.md`
for the full original text if needed.

**Scope:** `tasks/`, `filter_plugins/`, `netbox_filters_lib/`, `templates/`,
`defaults/main.yml`, `meta/main.yml`, `tests/unit/`

This document is a one-shot audit of the role for inconsistencies, duplicate
code, and suboptimal patterns. It is a snapshot — findings will drift as the
code evolves. Update or remove entries as they are addressed.

---

## Open findings

### F6 — Split `FilterModule` classes (Medium)

Three `FilterModule` classes exist:

- [../filter_plugins/netbox_filters.py](../filter_plugins/netbox_filters.py) —
  the intended entry point (62 exports).
- [../filter_plugins/rest_api_transforms.py](../filter_plugins/rest_api_transforms.py) —
  five REST-API transform filters, auto-discovered by Ansible but not
  re-exported by `netbox_filters.py`.
- ~~[../netbox_filters_lib/l3_config_helpers.py](../netbox_filters_lib/l3_config_helpers.py) — dead (see resolved finding F1).~~ Removed; no longer applies.

This works because Ansible auto-discovers every `FilterModule` in
`filter_plugins/`, but it means there's no single grep-able list of what
this role exports.

**Suggested fix.** Import the five REST transforms into
`netbox_filters.py`'s `filters()` dict, then delete the second
`FilterModule` (or keep the file as a pure module of functions with no
`FilterModule` class).

---

## Resolved findings log

All resolved via the changes recorded in [CHANGELOG.md](CHANGELOG.md) and
git history. Kept as a one-line index so a future audit doesn't re-flag
the same thing; full original writeups are in git history if the "why"
is needed again.

| ID | Finding | Area | Status |
|----|---------|------|--------|
| T1 | L3 wrapper task files were near-duplicates of each other | Tasks | Done — collapsed into a single reusable task |
| T2 | L2 config duplication across `configure_l2_{physical,lag,mclag}.yml` | Tasks | Done |
| T3 | Deeply nested Jinja2 in `configure_l3_interfaces.yml` should live in a filter | Tasks | Done — moved to `l3_config_helpers.py` |
| T4 | Unreferenced `configure_loopback.yml` duplicated `configure_l3_interfaces.yml` | Tasks | Done — deleted |
| T5 | First `include_tasks` in `main.yml` didn't use `apply.tags` | Tasks | Done |
| T6 | `ansible_run_tags` string-matching in `when:` was fragile | Tasks | Done — replaced by tag-narrowing, see [TAG_DEPENDENT_INCLUDES.md](TAG_DEPENDENT_INCLUDES.md) |
| T7 | Bare `is defined` on dicts/lists in `when:` (Ansible 2.19 deprecation) | Tasks | Done |
| T8 | `ansible_connection` variable inconsistency (`aoscx_connection_type` vs hardcoded `network_cli`) | Tasks | Done — all `aoscx_config`/`aoscx_command` tasks hardcode `network_cli`; `aoscx_connection_type` deprecated |
| T9 | `no_log` inconsistency (variable-gated vs hardcoded `true`) | Tasks | Done — all secret-touching tasks hardcode `no_log: true`; `aoscx_no_log` deprecated |
| F1 | Dead `FilterModule` in `netbox_filters_lib/l3_config_helpers.py` | Filters | Done — deleted |
| F2 | Missing unit test for `get_interface_ip_addresses` | Filters | Done |
| F3 | IPv4/IPv6/type-value normalization duplicated across ≥4 modules | Filters | Done — consolidated into `utils.py` |
| F4 | `interface_change_detection.py` was 1,369 lines, one ~1,180-line function | Filters | Done — split out `interface_ip_comparisons.py` |
| F5 | `interface_change_detection.py` mutated input dicts, contra CLAUDE.md §4.3 | Filters | Done — landed with F4 |
| J1 | OSPF authentication block duplicated across 4 templates | Templates | Done — extracted to `ospf_interface()` macro in `_macros_interface.j2` |
| J2 | OSPF process ID hardcoded to `1` in templates | Templates | Done — templates now use `ospf_process_id \| default(1)` |
| J3 | Loopback interface `0` hardcoded (`bgp.j2`, `int_phys.j2`) | Templates | N/A — `bgp.j2` is dead code slated for removal/rebuild; `int_phys.j2`'s usage is an accepted device-side default |
| J4 | `ip helper-address` block duplicated across 3 templates | Templates | Done — extracted to `ip_helpers()` macro in `_macros_interface.j2` |
| M1 | Deprecated `aoscx_fast_mode` still surfaced a runtime warning | Defaults | Done — variable and warning removed after its deprecation cycle completed |

---

## Explicitly out of scope

- The Molecule scenario, integration playbooks under `tests/`, and the
  sibling `aruba-role-testing/` workspace were not audited.
- Runtime behavior against real AOS-CX devices was not tested — findings
  are static.
- Docs consistency (cross-links, coverage of each variable in
  `defaults/main.yml`) was not systematically checked in the original
  pass — see the 2026-08-13 documentation review (referenced from
  [CHANGELOG.md](CHANGELOG.md) Unreleased) for that coverage instead.
