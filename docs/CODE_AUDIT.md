# Code Audit Report

**Date:** 2026-08-12
**Scope:** `tasks/`, `filter_plugins/`, `netbox_filters_lib/`, `templates/`,
`defaults/main.yml`, `meta/main.yml`, `tests/unit/`
**Repo revision:** `develop`

This document is a one-shot audit of the role for inconsistencies, duplicate
code, and suboptimal patterns. It is a snapshot — findings will drift as the
code evolves. Update or remove entries as they are addressed.

Findings are grouped by area and prioritized:

- **High** — measurable maintenance risk, latent bug, or convention violation
  called out in [../CLAUDE.md](../CLAUDE.md).
- **Medium** — real but non-urgent cleanup.
- **Low** — polish / consistency.

Status values: **Open** (not started), **Done** (fixed on `develop`).

---

## Executive summary

| # | Finding | Area | Priority | Status |
|---|---------|------|----------|--------|
| T1 | L3 wrapper task files (`configure_l3_{physical,lag,loopback,vlan,subinterface}.yml`) are near-duplicates of each other | Tasks | High | **Done** |
| T2 | L2 config duplication across `configure_l2_{physical,lag,mclag}.yml` (~180 LOC) | Tasks | High | **Done** |
| T3 | Deeply nested Jinja2 in `configure_l3_interfaces.yml` (`_needs_add`, `_l3_config_preview`) should live in a filter plugin | Tasks | High | **Done** |
| T4 | Unreferenced `configure_loopback.yml` duplicates functionality already in `configure_l3_interfaces.yml` | Tasks | High | **Done** |
| T5 | First `include_tasks` in `main.yml` (gather_facts) does not use `apply.tags` — inconsistent with the rest of the file | Tasks | Medium | **Done** |
| T6 | `ansible_run_tags` string-matching in `when:` for OSPF / BGP / VSX / static routes is fragile | Tasks | Medium | **Done** |
| T7 | Bare `is defined` on dicts/lists in `when:` — Ansible 2.19 deprecation | Tasks | Medium | **Done** |
| T8 | `ansible_connection` variable inconsistency (`{{ aoscx_connection_type }}` vs hardcoded `network_cli`) | Tasks | Medium | **Done** |
| T9 | `no_log` inconsistency (variable-gated vs hardcoded `true`) | Tasks | Medium | **Done** |
| F1 | Dead `FilterModule` in `netbox_filters_lib/l3_config_helpers.py` | Filters | High | **Done** |
| F2 | Missing unit test for `get_interface_ip_addresses` | Filters | High | **Done** |
| F3 | IPv4/IPv6/type-value normalization duplicated across ≥4 modules | Filters | High | **Done** |
| F4 | `interface_change_detection.py` is 1369 lines — split candidate | Filters | Medium | **Done** |
| F5 | `interface_change_detection.py` mutates input dicts (`_ip_changes`) — CLAUDE.md §4.3 says filters are pure | Filters | Medium | **Done** |
| F6 | Split `FilterModule` classes in `filter_plugins/` and `netbox_filters_lib/` — inconsistent public API surface | Filters | Medium | Open |
| J1 | OSPF interface auth block duplicated across `int_phys.j2`, `int_lag.j2`, `int_vlan.j2`, `int_loopback.j2` | Templates | High | **Done** |
| J2 | Hardcoded OSPF process ID `1` in interface templates | Templates | High | **Done** |
| J3 | Hardcoded loopback interface number `0` in `bgp.j2`, `int_phys.j2` | Templates | High | **N/A** |
| J4 | `ip helper-address` block duplicated across three interface templates | Templates | Medium | **Done** |
| M1 | Deprecated `aoscx_fast_mode` still documented in `defaults/main.yml` | Defaults | Low | **Done** |

Nothing critical was found in `meta/main.yml`; defaults hygiene is generally
good (all variables commented, `aoscx_` prefix consistent, spot-checked
variables are all referenced).

---

## 1. Tasks (`tasks/`)

### T1 — L3 wrapper task duplication (High)

**Status: Done.** The five wrappers were deleted and replaced by a single
`include_tasks` loop at the bottom of
[../tasks/configure_l3_interfaces.yml](../tasks/configure_l3_interfaces.yml)
that iterates over a static list of
`(interface_list, itype, vrf_type)` records — one per
`(physical|subinterface|vlan|lag|loopback) × (default|custom)` category —
and calls
[../tasks/configure_l3_interface_common.yml](../tasks/configure_l3_interface_common.yml)
for each. Include order (physical → subinterface → vlan → lag → loopback)
and the loopback-by-VRF split (`selectattr`/`rejectattr` on
`aoscx_builtin_vrfs`) are preserved. `when: item.list | length > 0` gates
each iteration. The original finding, preserved for context, follows.

Files:

- `../tasks/configure_l3_physical.yml` (deleted)
- `../tasks/configure_l3_lag.yml` (deleted)
- `../tasks/configure_l3_loopback.yml` (deleted)
- `../tasks/configure_l3_vlan.yml` (deleted)
- `../tasks/configure_l3_subinterface.yml` (deleted)

All five files are two-`include_tasks` wrappers around
[../tasks/configure_l3_interface_common.yml](../tasks/configure_l3_interface_common.yml),
differing only in `interface_type` and `vrf_type` variables passed into
`vars:`. Roughly 70 LOC of copy-paste scaffolding.

**Suggested fix.** Replace the five wrappers with a single loop in
`configure_l3_interfaces.yml` over a static list of `(interface_type,
vrf_type, source_list_var)` tuples, calling `configure_l3_interface_common.yml`
via `include_tasks` with `loop:`.

### T2 — L2 interface config duplication (High)

**Status: Done.** `configure_l2_lag.yml` and `configure_l2_mclag.yml` were
collapsed into a single parameterized
[../tasks/configure_l2_lag_common.yml](../tasks/configure_l2_lag_common.yml)
that takes `l2_lag_kind` (`lag` or `mclag`) and `l2_lag_parent_suffix` (`''`
or `' multi-chassis'`) as inputs. Source lists are looked up via
`l2_interfaces[l2_lag_kind ~ '_access']` etc.
[../tasks/configure_l2_interfaces.yml](../tasks/configure_l2_interfaces.yml)
now includes the common file twice with different `vars:`.
[../tasks/configure_l2_physical.yml](../tasks/configure_l2_physical.yml) was
intentionally left alone: it uses the higher-level
`arubanetworks.aoscx.aoscx_l2_interface` module (not `aoscx_config` CLI),
so unifying it would regress from a declarative module to raw CLI. The
original finding, preserved for context, follows.

Files:

- [../tasks/configure_l2_physical.yml](../tasks/configure_l2_physical.yml)
- `../tasks/configure_l2_lag.yml` (deleted)
- `../tasks/configure_l2_mclag.yml` (deleted)

Each file contains the same five tasks (access, tagged w/ untagged, tagged w/o
untagged, tagged-all w/ untagged, tagged-all w/o untagged). Only the interface
header string (`interface X`, `interface lag X`, `interface lag X
multi-chassis`) and the source list (`l2_interfaces.physical_*`,
`l2_interfaces.lag_*`, `l2_interfaces.mclag_*`) differ.

**Suggested fix.** Parameterize the interface header and source list, then
delete two of the three files. `configure_l2_interfaces.yml` is already the
orchestrator include from `main.yml`; the split into physical/lag/mclag
belongs *inside* it as a loop or single templated task, not as three
separate files.

### T3 — Deeply nested Jinja2 in `configure_l3_interfaces.yml` (High)

**Status: Done.** Two new pure filters in
[../netbox_filters_lib/l3_config_helpers.py](../netbox_filters_lib/l3_config_helpers.py)
replace the two Jinja blocks:

- `should_add_interface_ip(interface, address)` — replaces the 5-deep
  `_needs_add` ternary in the `Process each interface with IPs` task. The
  `_needs_add` field in `item_combo` is now
  `{{ item.0 | should_add_interface_ip(item.1.address) }}`. VRF-change
  short-circuit, IPv4 diff, and IPv6-with/without-enhanced-facts semantics
  are preserved exactly.
- `build_l3_config_preview(l3_interfaces, aoscx_builtin_vrfs, l3_counters_enable=True)`
  — replaces the ~15-line `_l3_config_preview` `set_fact` block. Iterates
  every `(interface_type, VRF)` category, calls `group_interface_ips` +
  `build_l3_config_lines`, keys by `format_interface_name` — identical to
  the previous inline Jinja. The `set_fact` is now a single-line filter
  call. The `Debug - Show L3 config lines to be applied` task that
  consumes `_l3_config_preview` is unchanged.

25 new unit tests in
[../tests/unit/test_l3_config_helpers.py](../tests/unit/test_l3_config_helpers.py)
cover both filters (13 for `should_add_interface_ip`, 12 for
`build_l3_config_preview`) — total suite 687 → 712. The original finding,
preserved for context, follows.

- [../tasks/configure_l3_interfaces.yml](../tasks/configure_l3_interfaces.yml) lines ~51–98: the `_needs_add` ternary is five levels deep.
- Same file lines ~244–315: the `_l3_config_preview` `set_fact` builds config
  strings via a ~70-line Jinja2 template embedded in YAML.

Complex conditional logic in Jinja is unreviewable and untestable. CLAUDE.md
already established the pattern of moving this into
[../netbox_filters_lib/l3_config_helpers.py](../netbox_filters_lib/l3_config_helpers.py);
these two blocks are exceptions to that pattern.

**Suggested fix.** Add two filters:

- `should_add_interface_ip(interface, address)` — replaces `_needs_add`.
- `build_l3_config_preview(interfaces, ...)` — replaces `_l3_config_preview`,
  reusing the existing `group_interface_ips` + `build_l3_config_lines`
  helpers already in `l3_config_helpers.py`.

Both should get unit tests before the tasks are switched over.

### T4 — Unreferenced `configure_loopback.yml` (High)

**Status: Done.** `tasks/configure_loopback.yml` was deleted. Loopback
creation continues to run through `configure_l3_interfaces.yml` →
`configure_l3_loopback.yml` → `configure_l3_interface_common.yml`
(`aoscx_interface`). The original finding, preserved for context, follows.

`tasks/configure_loopback.yml` was not included from `tasks/main.yml` or any other task file. Loopback creation is
already handled by `configure_l3_interfaces.yml` (via `configure_l3_loopback.yml`
→ `configure_l3_interface_common.yml`, which invokes `aoscx_interface`).

The file's header comment says it "delegates to configure_l3_loopback.yml"
but the body actually creates loopbacks directly via `aoscx_interface`, so it
would double-configure if it were re-hooked up.

**Suggested fix.** Delete the file. If any historical usage exists in
downstream playbooks, add a deprecation note first.

### T5 — Inconsistent `include_tasks` shape in `main.yml` (Medium)

**Status: Done.** The `gather_facts` include in
[../tasks/main.yml](../tasks/main.yml) now uses the same
`include_tasks: { file:, apply: { tags: [...] } }` shape as every other
include in the file, so tags propagate to sub-tasks in `gather_facts.yml`.
The original finding, preserved for context, follows.

[../tasks/main.yml](../tasks/main.yml#L15-L21):

```yaml
- name: Include fact gathering tasks
  ansible.builtin.include_tasks: gather_facts.yml
  when:
    - aoscx_gather_facts | bool
  tags:
    - always
    - facts
    - gather
```

Every other include in the same file uses the
`include_tasks: { file: ..., apply: { tags: [...] } }` form. Tags on tasks
inside `gather_facts.yml` may not propagate as intended.

**Suggested fix.** Rewrite the include to match the rest of the file.

### T6 — Fragile `ansible_run_tags` string matching (Medium)

**Status: Done.** The five `"'X' in ansible_run_tags or 'routing' in
ansible_run_tags or 'all' in ansible_run_tags"` guards in
[../tasks/main.yml](../tasks/main.yml) (OSPF identify, OSPF config, static
routes, BGP, VSX) had exactly one real effect: preventing a `-t layer3`
run (or `-t ha` for VSX) from touching routing protocols even though
those includes declared themselves with `layer3` / `ha` in `apply.tags`.
Every other case was covered by Ansible's own tag filter.

Same protection is now achieved by *narrowing the tag list*: OSPF, BGP,
and static-routes includes drop `layer3` from both `apply.tags` and the
outer `tags:` list (they keep `[<feature>, routing]`). VSX already had
`[vsx, ha]` and no broader tag to worry about — the check was purely
redundant. All five string-matching `when:` lines are gone. Behavior is
identical for `no -t`, `-t vlans`, `-t <feature>`, `-t routing`, and
`-t ha`; the one case that changed is `-t layer3`, which now runs L3
interface config only — same as before, just via Ansible's own filter
instead of a role-level `when:` check.

[../docs/TAG_DEPENDENT_INCLUDES.md](TAG_DEPENDENT_INCLUDES.md) was
rewritten to describe the new mechanism (tag narrowing rather than
`ansible_run_tags` string matching). The original finding, preserved for
context, follows.

Occurrences in [../tasks/main.yml](../tasks/main.yml): OSPF identify + config
(lines ~419, 434), static routes (~486), BGP (~636), VSX (~654) each contain:

```yaml
- "'ospf' in ansible_run_tags or 'routing' in ansible_run_tags or 'all' in ansible_run_tags"
```

This duplicates Ansible's own tag filtering. When run without `-t`,
`ansible_run_tags` is `["all"]`, so the check passes — but it's brittle and
opaque: any include using this pattern silently skips itself if a caller
selects tags via `--tags` on the parent playbook without including the
listed ones, even though the `apply.tags` above already gates the include.

**Suggested fix.** Remove the string-matching lines. Rely on the `apply.tags`
declaration already present on each include. If certain features must be
opt-in even under `all`, gate them on a role variable, not on
`ansible_run_tags`.

### T7 — Bare `is defined` on dicts/lists in `when:` (Medium)

**Status: Done.** Scope narrowed on review — the Ansible 2.19 deprecation is
specifically about *implicit* dict/list truthiness in `when:`
(`when: my_dict`), not about `is defined`, which already returns a boolean.
Audit re-checked all `is defined` occurrences under `tasks/`; the only
semantically weak ones were in
[../tasks/configure_dns.yml](../tasks/configure_dns.yml):

- The 4-way OR guarding `Configure DNS settings` now checks explicit
  emptiness per shape (`| default('') | length > 0` for the domain string,
  `| default({}) | length > 0` for the three dicts). Previous form treated
  `dns_domain_name: null` in NetBox config_context as "configure DNS."
- `Configure DNS name servers per VRF` now gates on
  `dns_name_servers | default({}) | length > 0` and passes
  `default({}) | dict2items` to `loop:`, so `dns_name_servers: null`
  no longer crashes `dict2items`.

The two other examples originally listed —
`subinterface_parents_already_routed is not defined` in
`configure_physical_interfaces.yml` and `aoscx_rest_api_version is not defined`
in `gather_facts_rest_api.yml` — are scalar existence checks ("has this
fact/variable been set?"). `is not defined` on a scalar already returns a
boolean and expresses the intent correctly; they are **left as-is**.

The original finding, preserved for context, follows.

Per CLAUDE.md §4.2, `when` must resolve to a boolean; dicts/lists must not be
tested with `is defined` alone in Ansible 2.19+.

Examples:

- [../tasks/configure_dns.yml](../tasks/configure_dns.yml) — `when: dns_name_servers is defined`
- [../tasks/configure_physical_interfaces.yml](../tasks/configure_physical_interfaces.yml) — `when: subinterface_parents_already_routed is not defined`
- [../tasks/gather_facts_rest_api.yml](../tasks/gather_facts_rest_api.yml) — `when: aoscx_rest_api_version is not defined`

**Suggested fix.** Replace with `... | default([]) | length > 0` (list/dict)
or with an explicit boolean var.

### T8 — `ansible_connection` inconsistency (Medium)

**Status: Done.** The original audit direction was wrong — it assumed
`aoscx_connection_type` should be the standard. In practice this
role is typically driven from inventory / group_vars that set
`ansible_connection: arubanetworks.aoscx.aoscx` (pyaoscx REST) for AOS-CX
devices via the NetBox `platform`; the tasks that override to
`network_cli` are the ones invoking `aoscx_config` / `aoscx_command`, which
are CLI-only regardless of the device's default connection. Making those
tasks respect `aoscx_connection_type` (which by default resolves to
`network_cli`) would have masked a per-inventory override the user *did*
need to keep as pyaoscx, and setting the variable to anything else would
break `aoscx_config`.

All 34 sites that referenced `{{ aoscx_connection_type }}` were on
`arubanetworks.aoscx.aoscx_config` calls; they now hardcode
`ansible_connection: network_cli`. The three
`ansible.netcommon.network_cli` FQCN usages in
[../tasks/configure_ospf.yml](../tasks/configure_ospf.yml) were also
normalized to the short form for consistency with the rest of the file.
[../defaults/main.yml](../defaults/main.yml) now marks
`aoscx_connection_type` as deprecated (no runtime effect, kept for
backward compatibility with existing inventories that set it), the LAG
order test playbook drops its no-op override, and the code sample in
[l3_config_helpers.md](filter_plugins/l3_config_helpers.md) was updated
accordingly. The original finding, preserved for context, follows.

Most tasks set:

```yaml
vars:
  ansible_connection: "{{ aoscx_connection_type }}"
```

A few hardcode `network_cli` (e.g. `configure_ospf.yml`, `configure_ntp.yml`,
the final `save_when: modified` step in `main.yml`). One usage in
`configure_ospf.yml` even uses the FQCN
`ansible.netcommon.network_cli`.

**Suggested fix.** Standardize on `"{{ aoscx_connection_type }}"` unless a
task genuinely requires `network_cli` regardless of user preference, in
which case that requirement should be commented at the task.

### T9 — `no_log` inconsistency (Medium)

**Status: Done.** Reframed on review — the risk isn't aesthetic
inconsistency, it's that `no_log: "{{ aoscx_no_log | default(...) }}"`
on a task that sees a secret means a user flipping `aoscx_no_log: false`
for debugging leaks that secret on the next production run. The five
variable-gated sites all handled secrets:

- [../tasks/configure_bgp.yml](../tasks/configure_bgp.yml) lines 26 / 84 /
  97 — NetBox API calls sending the `NETBOX_TOKEN` in the
  `Authorization` header.
- [../tasks/configure_bgp.yml](../tasks/configure_bgp.yml) line 708 —
  AOS-CX REST login `uri` POSTing username/password.
- [../tasks/gather_facts_rest_api.yml](../tasks/gather_facts_rest_api.yml)
  line 194 — AOS-CX REST login `uri` POSTing username/password.

All five now hardcode `no_log: true`. Every other `no_log` in the role
was already hardcoded (`configure_bgp.yml:694,747`, `configure_ospf.yml:89`
for OSPF MD5 keys, `gather_facts_rest_api.yml:53,794`). No task carrying
a secret was missing `no_log` entirely. With no remaining consumers,
`aoscx_no_log` in [../defaults/main.yml](../defaults/main.yml) is now
marked deprecated (kept for backward compatibility, no runtime effect).
The new task-authoring rule was added to
[../CLAUDE.md](../CLAUDE.md) §4.2 so future features (AAA/RADIUS/TACACS+
shared secrets, SNMPv3 passphrases, local user passwords, BGP MD5, etc.)
follow the same pattern. The original finding, preserved for context,
follows.

Two patterns coexist:

- `no_log: "{{ aoscx_no_log | default(false) }}"` — e.g.
  `configure_bgp.yml` (early tasks).
- `no_log: true` — e.g. `configure_bgp.yml` (later tasks),
  `configure_ospf.yml`, `gather_facts_rest_api.yml`.

**Suggested fix.** Pick one. `no_log: true` is safer for known-sensitive
tasks (secrets, MD5 keys); `aoscx_no_log`-gated is fine for verbose but
non-sensitive tasks. Document which is which and split them consistently.

### Other tasks findings

- **`changed_when: false` inconsistency (Low).** Only
  `configure_evpn.yml`, `configure_vxlan.yml`, and
  `generate_template_config.yml` set it explicitly. Facts-gathering and
  change-identify tasks arguably should too, to keep the play summary
  honest.
- **`configure_l3_interfaces.yml` is 350+ lines and mixes eight phases**
  (assert → extract → IP processing → debug → categorize → loopback create →
  preview → sub-includes). After T3 lands, split the remainder along phase
  boundaries.
- **`configure_bgp.yml` is 900+ lines** but is well-sectioned; not urgent.

---

## 2. Filter plugins (`filter_plugins/`, `netbox_filters_lib/`)

### F1 — Dead `FilterModule` in `l3_config_helpers.py` (High)

**Status: Done.** The unused `FilterModule` class was deleted from
`netbox_filters_lib/l3_config_helpers.py`. The functions it exposed are
still re-exported from `filter_plugins/netbox_filters.py`. The original
finding, preserved for context, follows.

[../netbox_filters_lib/l3_config_helpers.py](../netbox_filters_lib/l3_config_helpers.py)
defines a `FilterModule` class at the bottom of the file. `netbox_filters_lib/`
is not on Ansible's filter plugin path (that's the whole point — see the
comment in [../netbox_filters_lib/README.md](../netbox_filters_lib/README.md)),
so the class is never loaded. The functions themselves are re-exported by
[../filter_plugins/netbox_filters.py](../filter_plugins/netbox_filters.py).

**Suggested fix.** Delete the `FilterModule` class (~8 lines). Keep only the
functions.

### F2 — Missing unit test for `get_interface_ip_addresses` (High)

**Status: Done.** Added
[../tests/unit/test_interface_ip_processing.py](../tests/unit/test_interface_ip_processing.py)
covering empty/`None` inputs, interface-ID matching, `mgmt_only` skip,
malformed IP objects, VRF resolution, IP role as dict vs. string, anycast
MAC extraction, and interface-type variants (25 tests). The original
finding, preserved for context, follows.

Public filter exported from
[../filter_plugins/netbox_filters.py](../filter_plugins/netbox_filters.py),
defined in
[../netbox_filters_lib/interface_ip_processing.py](../netbox_filters_lib/interface_ip_processing.py).
No corresponding file under `tests/unit/`. Every other public filter has at
least basic coverage. CLAUDE.md §4.3 requires a unit test for every public
filter.

**Suggested fix.** Add `tests/unit/test_interface_ip_processing.py`. Also
expand `get_vlans_needing_changes` and `get_vlans_needing_name_update` tests,
both of which are currently thin.

### F3 — Normalization / type-value duplication (High)

**Status: Done.** Added four canonical helpers to
[../netbox_filters_lib/utils.py](../netbox_filters_lib/utils.py):

- `is_ipv4_address(addr)` / `is_ipv6_address(addr)` — the single ``":" in
addr`` check that used to be inlined across ~15 sites.
- `get_interface_type_value(intf)` — extracts NetBox's `type.value`
  handling dict / bare-string / missing / non-dict input in one place.
- `normalize_ipv6(addr)` — canonical form for comparison, moved out of
  `interface_change_detection.py`.

[../netbox_filters_lib/l3_config_helpers.py](../netbox_filters_lib/l3_config_helpers.py)
now re-exports `is_ipv4_address` / `is_ipv6_address` from utils so the
public filter API (`filter_plugins/netbox_filters.py`) is unchanged.
[../netbox_filters_lib/interface_change_detection.py](../netbox_filters_lib/interface_change_detection.py)
imports `normalize_ipv6 as _normalize_ipv6` — all internal call sites keep
their original names. All type-value extractions in
`interface_categorization.py`, `interface_change_detection.py`,
`interface_ip_processing.py`, `comparison.py`, and `vlan_filters.py` were
replaced with `get_interface_type_value(intf)`; `bgp_filters.py` uses
`is_ipv6_address`.

Semantic clean-ups picked up along the way:

- `get_interface_type_value` returns the string when NetBox serialises
  `type` as a bare string (previously all consumers returned `None` in
  this case). `get_interface_ip_addresses`'s existing unit test
  `test_type_as_string_yields_none` was updated to
  `test_type_as_string_returns_string`. Real NetBox always returns the
  dict form; the bare-string path is a synthetic / defensive case.
- `_categorize_interface_for_changes` no longer early-returns when `type`
  is a bare string (same reasoning).

`port_access.py`'s `_norm_str` / `_norm_int` are port-access-specific
comparison helpers with no duplicates elsewhere; left alone per the
audit's "Optional" tag. 22 new unit tests in
[../tests/unit/test_utils.py](../tests/unit/test_utils.py) cover the four
new helpers. Total unit-test count: 665 → **687 passing**. The original
finding, preserved for context, follows.

The same "is this a dict with a `.value` key, or a bare string?" extraction
pattern appears in at least four modules:

- [../netbox_filters_lib/interface_categorization.py](../netbox_filters_lib/interface_categorization.py)
- [../netbox_filters_lib/interface_change_detection.py](../netbox_filters_lib/interface_change_detection.py)
- [../netbox_filters_lib/interface_ip_processing.py](../netbox_filters_lib/interface_ip_processing.py)
- [../netbox_filters_lib/l3_config_helpers.py](../netbox_filters_lib/l3_config_helpers.py)

Similarly, `is_ipv4_address` / `is_ipv6_address` (`":" in address` style
checks) are re-implemented in `l3_config_helpers.py` and inline in
`interface_change_detection.py`. `port_access.py` has `_norm_str` / `_norm_int`
that overlap with generic normalization concerns.

**Suggested fix.** Consolidate into
[../netbox_filters_lib/utils.py](../netbox_filters_lib/utils.py):

- `get_interface_type_value(intf)` — returns `type.value` if `type` is a
  dict, else `type` if str, else `None`.
- `is_ipv4(addr)`, `is_ipv6(addr)` — single canonical implementation.
- Optional: `normalize_value(v, kind)` covering the `_norm_*` cases.

Migrate call sites one module at a time; keep the old helpers as thin
delegators for one release if any are re-exported.

### F4 — `interface_change_detection.py` is too large (Medium)

**Status: Done.** Landed together with F5 (the extraction target and the
mutation fix are the same code). The IPv4/IPv6/VRF/encapsulation/
anycast/DHCP-relay comparison block — the densest ~610 lines of the old
~1180-line main function — moved to a new
[../netbox_filters_lib/interface_ip_comparisons.py](../netbox_filters_lib/interface_ip_comparisons.py)
as two functions:

- `compute_l3_ip_changes(nb_intf, device_intf, enhanced_intf, intf_name)` —
  everything that used to run under `if nb_intf.get("ip_addresses"):`
  (IPv4/IPv6 diffing, VRF-change short-circuit, sub-interface encapsulation
  VLAN drift, anycast/VSX virtual IP add+remove, link-local anycast
  detection).
- `compute_dhcp_relay_changes(nb_intf, intf_name, dhcp_relay_facts,
  ip_helper_addresses)` — the DHCP relay / ip helper-address block.

`_get_device_vrf_name` moved with them (only ever called from the VRF-change
check). `interface_change_detection.py` dropped from 1376 to 761 lines;
`interface_ip_comparisons.py` is 682 lines — both above the audit's ~600 LOC
target, but that reflects where the logic is actually cohesive (the IPv6/
anycast/link-local sections share several local variables — `enhanced_intf`,
`nb_ipv6`, `nb_anycast_ipv6_normalized` — that would have to be threaded
through extra function boundaries to chop further, at a net readability
loss) rather than an arbitrary line target. Both functions now have direct
unit test coverage in
[../tests/unit/test_interface_ip_comparisons.py](../tests/unit/test_interface_ip_comparisons.py)
(29 tests) — previously this logic was only reachable through
`get_interfaces_needing_config_changes()` end-to-end. The original finding,
preserved for context, follows.

1369 lines, single main function
`get_interfaces_needing_config_changes()` at ~1180 lines with six local
helpers. Hard to review, hard to test in isolation.

**Suggested fix.** Extract:

- `interface_ip_comparisons.py` — IPv4/IPv6 comparison (~lines 823–912),
  anycast/VSX virtual IP comparison (~lines 914–1020), DHCP relay
  comparison (~lines 1023–1065).
- Move `_normalize_ipv6` to `utils.py` (see F3).

Target: each module under ~600 LOC.

### F5 — Filters mutate their inputs (Medium)

**Status: Done.** Fixed via option 1 from the suggested fix, combined with
the F4 extraction: `get_interfaces_needing_config_changes()` now
shallow-copies each interface (`nb_intf = dict(nb_intf)`) at the top of its
per-interface loop, before any `_ip_changes` write. A shallow copy is
sufficient because every write in this function only ever assigns a fresh
top-level `_ip_changes` dict — no nested structure shared with the caller's
original object is ever mutated (verified by grepping for non-`_ip_changes`
`nb_intf[...]` assignments — there are none). The new
`compute_l3_ip_changes()`/`compute_dhcp_relay_changes()` helpers (see F4) are
themselves pure: they return `(needs_change, change_reasons, ip_changes)`
and the caller merges `ip_changes` onto its own copy's `_ip_changes` dict,
rather than either helper writing to `nb_intf` directly. `populate_ip_changes()`
in `utils.py` is unchanged (it's a generic mutate-the-dict-you're-given
helper used elsewhere too) — it's now only ever called with the loop's local
copy, not the caller's original object.

Downstream consumers are unaffected: `configure_l3_interfaces.yml` and
`l3_config_helpers.py` only ever read `_ip_changes` off entries in the
*returned* `interface_changes.*` categorized lists, never off the raw
`interfaces` variable — confirmed by grep before making the change. Four
new regression tests in
[../tests/unit/test_interface_change_detection.py](../tests/unit/test_interface_change_detection.py)
(`TestGetInterfacesNeedingConfigChangesDoesNotMutateInputs`) assert the
caller's original interface dicts are untouched after the call; all four
were verified to fail against the pre-fix code (temporarily reverted the
copy line to confirm) before being merged. The original finding, preserved
for context, follows.

`get_interfaces_needing_config_changes` writes `_ip_changes` back onto each
`nb_intf` dict rather than returning a transformed structure. This is
intentional — downstream tasks read `_ip_changes` from the same interface
object — but it contradicts the "filters are pure functions of their inputs"
rule in [../CLAUDE.md](../CLAUDE.md) §4.3.

**Suggested fix.** Either:

1. Return a new list of shallow-copied interface dicts with `_ip_changes`
   attached, or
2. Return a *separate* dict keyed by interface name → `_ip_changes` and let
   the task decide how to combine them.

If neither is feasible, add a module-level docstring documenting the
mutation as an explicit exception, and update CLAUDE.md §4.3 to name this
case. Do not leave the contradiction implicit.

### F6 — Split `FilterModule` classes (Medium)

Three `FilterModule` classes exist:

- [../filter_plugins/netbox_filters.py](../filter_plugins/netbox_filters.py) —
  the intended entry point (~65 exports).
- [../filter_plugins/rest_api_transforms.py](../filter_plugins/rest_api_transforms.py) —
  five REST-API transform filters, auto-discovered by Ansible but not
  re-exported by `netbox_filters.py`.
- [../netbox_filters_lib/l3_config_helpers.py](../netbox_filters_lib/l3_config_helpers.py) —
  dead (see F1).

This works because Ansible auto-discovers every `FilterModule` in
`filter_plugins/`, but it means there's no single grep-able list of what
this role exports.

**Suggested fix.** Import the five REST transforms into
`netbox_filters.py`'s `filters()` dict, then delete the second
`FilterModule` (or keep the file as a pure module of functions with no
`FilterModule` class). Delete the third per F1.

### Other filters findings

- **`sorted(list(x))` (Low).** Occurs in `vlan_filters.py`, `ospf_filters.py`,
  `interface_change_detection.py`. `sorted()` already returns a list.
- **Chained `.get(k, {}).get(...)` (Low).** Common in `ospf_filters.py`
  and `l3_config_helpers.py`. Defensible as defensive coding, but a single
  helper `safe_get(d, *keys, default=...)` in `utils.py` would remove
  ~15 verbose expressions.
- **Environment-variable reads** in `utils.py._debug` and `vrf_filters.py`
  are read-only debug hooks and acceptable exceptions to the "no I/O" rule.
- **All private helpers (`_normalize_ipv6`, `_iter_bgp_lines`,
  `_categorize_interface_for_changes`, `_norm_str`, `_norm_int`, etc.) are
  referenced** — no dead helpers found besides F1.

---

## 3. Templates (`templates/`)

### J1 — OSPF authentication block duplication (High)

The same ~20-line OSPF MD5 auth rendering block appears in:

- [../templates/int_phys.j2](../templates/int_phys.j2) — twice (lines ~76–95
  and ~128–147, once per L3 flavour handled in that template)
- [../templates/int_lag.j2](../templates/int_lag.j2) — lines ~96–115
- [../templates/int_vlan.j2](../templates/int_vlan.j2) — lines ~59–76
- [../templates/int_loopback.j2](../templates/int_loopback.j2) — smaller variant, line ~22

**Suggested fix.** Extract to a Jinja macro (e.g. `_macros_ospf.j2` with
`{% macro ospf_auth_block(intf) %}`) and `{% import %}` in each template.

### J2 — Hardcoded OSPF process ID `1` (High)

**Status: Done.** The five `ip ospf 1 area` occurrences in `int_phys.j2`
(x2), `int_lag.j2`, `int_vlan.j2`, and `int_loopback.j2` now render as
`ip ospf {{ ospf_process_id | default(1) }} area ...`, matching the CLI
command emitted by `templates/ospf.j2` and the filter-plugin path
(`build_l3_config_lines`) that already respect `ospf_process_id`. The
NetBox custom-field name (`if_ip_ospf_1_area`) still hardcodes the process
ID; renaming it is out of scope here and tracked separately in the note
below. The original finding, preserved for context, follows.

`ip ospf 1 area {{ ... }}` is hardcoded in `int_phys.j2`, `int_lag.j2`,
`int_vlan.j2`, `int_loopback.j2`. The tasks / filter plugins already respect
`ospf_process_id` (default 1), so the templates are the only place that
locks it in.

**Suggested fix.** Replace with
`ip ospf {{ ospf_process_id | default(1) }} area {{ ... }}` everywhere. Note
that the NetBox custom fields tied to process 1 (`if_ip_ospf_1_area`,
`if_ip_ospf_auth`, etc.) also need to be renamed or made
process-ID-agnostic before this is truly multi-process — track that
separately.

### J3 — Hardcoded loopback interface `0` (High)

**Status: N/A.** `bgp.j2` is leftover from an earlier template-based BGP
config approach that has since been superseded by
[../tasks/configure_bgp.yml](../tasks/configure_bgp.yml) driving the
netbox-bgp plugin directly. That whole file will be dropped or rebuilt as
part of a larger BGP-templating refactor and isn't worth touching in
isolation. `int_phys.j2`'s `ip unnumbered interface loopback 0` is a
device-side default that no operator has yet asked to configure
differently; leave until someone does. The original finding, preserved
for context, follows.

- [../templates/bgp.j2](../templates/bgp.j2) — `neighbor ... update-source loopback 0` (line ~7)
- [../templates/int_phys.j2](../templates/int_phys.j2) — `ip unnumbered interface loopback 0` (line ~40)

**Suggested fix.** Either add role variables
(`aoscx_bgp_update_source_loopback`, `aoscx_unnumbered_loopback`) with
default `0`, or document the assumption prominently in
[BASE_CONFIGURATION.md](BASE_CONFIGURATION.md) / [BGP_CONFIGURATION.md](BGP_CONFIGURATION.md).

### J4 — `ip helper-address` block duplication (Medium)

**Status: Done.** Extracted into `ip_helpers(intf)` in
[../templates/_macros_interface.j2](../templates/_macros_interface.j2)
alongside the OSPF macro. `int_phys.j2`, `int_lag.j2`, and `int_vlan.j2`
now call `{{ m.ip_helpers(intf) }}` where they previously inlined the
VRF lookup + sorted `ip helper-address` loop. See J1 for the full
verification approach; the same equivalence check covered helpers. The
original finding, preserved for context, follows.

The same VRF-lookup + sorted iteration block appears in `int_phys.j2` (twice),
`int_lag.j2`, and `int_vlan.j2`:

```jinja2
{% set _vrf = (intf.vrf.name | default('default')) | replace('Global', 'default') %}
{% set _helpers = (ip_helper_addresses | default({})).get(_vrf, {}) %}
{% for idx in _helpers.keys() | sort %}
   ip helper-address {{ _helpers[idx] }}
{% endfor %}
```

**Suggested fix.** Extract to a macro alongside the OSPF auth macro from J1.

### Other templates findings

- **Whitespace consistency (Low).** Mix of `{% if` and `{%if` across
  templates. Prefer `{% if` with the leading space.
- **Trailing blank lines (Low).** `dns.j2`, `aoscx.j2`, `int_vxlan.j2` emit
  extra blank lines inside conditional blocks — harmless but noisy in
  generated config.
- **Runtime-generated variables used with `| default(...)`** —
  `ospf_auth_key_id`, `ip_helper_addresses`, `ospf_auth_keys`,
  `template_vlans`, `template_vrfs`, `ntp_vrf`, `mstp_*` — these are computed
  by tasks, not user-configured, and correctly *not* in `defaults/main.yml`
  per CLAUDE.md §4.1. No action needed.

---

## 4. Defaults & metadata

### M1 — Deprecated `aoscx_fast_mode` still surfaced (Low)

**Status: Done.** `aoscx_fast_mode` was deprecated in v0.7.0 (2026-03-28)
and has been through many minor releases since. The runtime debug warning
in [../tasks/main.yml](../tasks/main.yml) and the variable declaration in
[../defaults/main.yml](../defaults/main.yml) have both been removed. Docs
(`docs/PERFORMANCE_OPTIMIZATION.md`) already described it as removed, so
no doc changes were needed. The deprecation-pattern reference in
[../CLAUDE.md](../CLAUDE.md) §4.1 was repointed to the newer
`aoscx_connection_type` / `aoscx_no_log` deprecations (both no-op-since
this release, still declared for backward compatibility). The original
finding, preserved for context, follows.

`main.yml` prints a deprecation warning when `aoscx_fast_mode` is set, but the
variable is not in [../defaults/main.yml](../defaults/main.yml), so users
setting it don't get a deprecation from lint / doc scans until runtime.

**Suggested fix.** Either:

1. Add the variable to `defaults/main.yml` with a `# DEPRECATED: ...`
   comment (matches the pattern the docs already use), or
2. Delete the runtime warning task in `main.yml` — the variable has already
   been through a deprecation cycle per CHANGELOG.

### Other defaults / metadata findings

- Every declared variable in `defaults/main.yml` has an intent comment and
  uses the `aoscx_` prefix. Spot-checked variables were all referenced.
  Nothing to fix here.
- `meta/main.yml` is clean: `min_ansible_version: 2.18`, MIT license,
  correct collection deps, `dependencies: []`.

---

## 5. Suggested remediation order

Ranked by leverage (impact / effort):

1. ~~**F1** — delete dead `FilterModule` (5 minutes).~~ **Done.**
2. ~~**T4** — delete `configure_loopback.yml` (5 minutes, confirm nothing
   downstream calls it).~~ **Done.**
3. ~~**T5** — fix `gather_facts` include shape (5 minutes).~~ **Done.**
4. ~~**F2** — add missing `get_interface_ip_addresses` unit test.~~ **Done.**
5. ~~**J2** — de-hardcode OSPF process ID in templates.~~ **Done.**
6. ~~**T7** — sweep bare `is defined` on dicts/lists.~~ **Done.**
7. ~~**T8, T9** — sweep `ansible_connection` and `no_log` for consistency.~~ **Done.**
8. ~~**J1 + J4** — extract Jinja macros for OSPF auth + IP helper blocks.~~ **Done.**
9. ~~**F3** — consolidate normalization / type-value helpers into `utils.py`.~~ **Done.**
10. ~~**T6** — remove `ansible_run_tags` string matching.~~ **Done.**
11. ~~**T1 + T2** — collapse L2/L3 wrapper duplication.~~ **Done.**
12. ~~**T3** — move deep Jinja out of `configure_l3_interfaces.yml`.~~ **Done.**
13. ~~**F4** — split `interface_change_detection.py`.~~ **Done.**
14. ~~**F5** — resolve the "filters mutate inputs" contradiction (either fix
    the code or update CLAUDE.md).~~ **Done.**

Items 1–4 are near-free wins; items 5–8 are safe cleanup; items 9+ are
larger refactors that should each land as a standalone PR with tests.

---

## 6. Explicitly out of scope

- The Molecule scenario, integration playbooks under `tests/`, and the
  sibling `aruba-role-testing/` workspace were not audited.
- Runtime behavior against real AOS-CX devices was not tested — findings
  are static.
- Docs consistency (cross-links, coverage of each variable in
  `defaults/main.yml`) was not systematically checked.
