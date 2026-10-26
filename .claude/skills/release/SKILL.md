---
name: release
description: Cut a new release of the aopdal.aruba_cx_switch role — choose the SemVer bump, move CHANGELOG [Unreleased] into a version section, bump VERSION, sync docs, and open the develop→main PR that triggers the release workflow. Use when the user asks to release, tag, bump the version or prepare a release PR.
disable-model-invocation: true
---

# Release the role

Full background: `docs/RELEASE_PROCESS.md`. The `VERSION` file is the
version source of truth (this is a role, not a collection — no
`galaxy.yml`). Merging a change to `VERSION` on `main` makes
`.github/workflows/release.yml` create the `v<version>` tag and GitHub
Release from the matching CHANGELOG section.

## 1. Check the state

- Work on `develop`, up to date with `origin/develop`, clean tree.
- `git log $(git describe --tags --abbrev=0)..HEAD --oneline` — the
  commits since the last release.
- Compare against `## [Unreleased]` in `CHANGELOG.md`. Every user-visible
  commit (`feat:`, `fix:`, behaviour changes) should have an entry; point
  out any that are missing and offer to add them.

## 2. Choose the version

From `cat VERSION`, propose a bump and confirm it with the user:

- Patch: fixes, docs, build/dev-tooling only.
- Minor: any `feat:` / new variable / new feature.
- Major: breaking change (`feat!:`, removed variable, changed default
  behaviour). CHANGELOG must call the break out explicitly.

## 3. Edit

- `CHANGELOG.md`: keep an empty `## [Unreleased]` heading and insert
  `## [X.Y.Z] - YYYY-MM-DD` (today's date) below it with the moved
  content. Category order: Added, Changed, Deprecated, Removed, Fixed,
  Security. Drop empty categories.
- `VERSION`: the new version, single line, no `v` prefix.
- `make docs-sync` (updates `docs/CHANGELOG.md` and `docs/index.md`).

## 4. Verify

- `make lint && make test-unit && make syntax` must pass.

## 5. Commit and PR (confirm with the user before each)

- Commit `VERSION`, `CHANGELOG.md`, `docs/CHANGELOG.md`, `docs/index.md`
  with message `chore: release version X.Y.Z`.
- Push `develop`, then open a PR `develop` → `main` titled
  `chore: release vX.Y.Z` with the version's CHANGELOG section as body.
- Do not merge it unless the user says so. After merge, check with
  `gh run list --workflow=release.yml` and `gh release view vX.Y.Z`.

Troubleshooting (tag exists, empty notes, workflow not triggered) is in
`docs/RELEASE_PROCESS.md`.
