---
name: pre-pr-check
description: Run the aopdal.aruba_cx_switch PR gate (lint, unit tests, syntax, docs-sync) and review the pending diff against the role's conventions (FQCN, network_cli override for aoscx_config, hardcoded no_log on secrets, boolean when, declared variables, docs and changelog updated). Use before committing or opening a PR, or when the user asks whether a change is ready.
---

# Pre-PR check

## 1. Collect the diff

`git status` and `git diff` against the base (`develop`, or `main` for a
release PR), including untracked files. Note which areas changed.

## 2. Run the gate

```bash
make lint
```

```bash
make test-unit
```

```bash
make syntax
```

If `README.md` or `CHANGELOG.md` changed, run `make docs-sync` and check
that `docs/index.md` / `docs/CHANGELOG.md` are in the diff. If
`requirements*.txt` changed, also run `make audit`.

Report failures with the actual output and fix them (lint fixes are fine
to apply; ask before changing behaviour).

## 3. Review against conventions

Go through the diff and check each item; report as a short list of
pass / issue with `file:line`:

- [ ] Every module call uses FQCN.
- [ ] Every `aoscx_config` / `aoscx_command` task sets
      `vars: ansible_connection: network_cli` (short form). pyaoscx
      modules do not override `ansible_connection`. No use of
      `aoscx_connection_type`.
- [ ] Tasks that touch a secret (NetBox token, REST login, passwords,
      MD5/SNMPv3/AAA keys) have `no_log: true` hardcoded — not a variable.
- [ ] `when:` conditions resolve to booleans (`| length > 0`, `| bool`),
      no bare dicts/lists.
- [ ] Every new variable is declared in `defaults/main.yml` with a
      comment and documented in README "Role Variables". No variable that
      exists only via `default(...)`. Renamed/removed variables follow the
      deprecation pattern (CLAUDE.md §4.1).
- [ ] New includes in `tasks/main.yml` use `include_tasks` + `apply: tags`,
      have a feature and a layer tag, sit after their dependencies, and
      the CLAUDE.md §3 dependency table is updated. Ordering of existing
      includes is unchanged, or the change explains why.
- [ ] Change detection compares against gathered facts; no
      non-idempotent push without a pre-compare. Secrets are not compared
      against device state (§4.7).
- [ ] New/changed filters have unit tests and are in
      `EXPECTED_FILTER_NAMES`; called with pipe syntax, not `lookup()`.
- [ ] Matching `docs/` topic page is updated (CLAUDE.md §4.5 table).
- [ ] `CHANGELOG.md` `[Unreleased]` has an entry for user-visible changes.
- [ ] No edits to sibling repos `aruba-role-testing/` or `autotest-aoscx/`
      unless requested; no secrets or real device credentials in the diff.

## 4. Summarise

One line verdict (ready / not ready), the gate results, and the open
issues. Mention that real-device idempotency validation runs in
`autotest-aoscx` and is not covered by this check.
