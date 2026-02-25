# Release Process

Guide to the release process for the Aruba CX Switch Ansible Role.

## Overview

Releases are created by updating the `VERSION` file and `CHANGELOG.md` in a pull request. When the PR is merged to `main`, a GitHub Actions workflow automatically creates a Git tag and GitHub Release from the current state — no direct pushes to `main` are needed.

**Release flow:**

1. Update `VERSION` and `CHANGELOG.md` in your PR
2. Merge PR to `main`
3. Workflow creates Git tag and GitHub Release automatically

---

## Quick Start

### Step-by-Step Release

```bash
# 1. Create a branch (or use your feature branch)
git checkout -b release/0.6.0

# 2. Bump the version
echo "0.6.0" > VERSION

# 3. Update CHANGELOG.md — move [Unreleased] content to new version
#    (see Changelog Management below)

# 4. Commit and push
git add VERSION CHANGELOG.md
git commit -m "chore: release version 0.6.0"
git push -u origin release/0.6.0

# 5. Create PR and merge
gh pr create --title "chore: release v0.6.0" --body "Bump version and changelog"

# 6. After merge → workflow creates tag v0.6.0 and GitHub Release
```

### Manual Trigger

You can also trigger the release workflow manually (e.g. if the VERSION was already updated in a previous PR):

```bash
# Via GitHub CLI
gh workflow run release.yml --ref main

# Via GitHub UI: Actions → Release → Run workflow
```

---

## Versioning

This project follows [Semantic Versioning](https://semver.org/) (SemVer):

```
MAJOR.MINOR.PATCH
  │     │     │
  │     │     └─ Patch: Bug fixes, small improvements
  │     └─────── Minor: New features, backward compatible
  └───────────── Major: Breaking changes
```

### Version Examples

- **Patch**: `0.5.0` → `0.5.1` — Bug fix, documentation update
- **Minor**: `0.5.1` → `0.6.0` — New feature (e.g., OSPF support)
- **Major**: `0.6.0` → `1.0.0` — Breaking change (e.g., API change)

### Current Version

The current version is stored in the [`VERSION`](../VERSION) file as a single line:

```
0.5.0
```

**Note**: This is an Ansible **Role** (not a Collection), so we use a simple `VERSION` file instead of `galaxy.yml`.

### Conventional Commits

While the release workflow no longer auto-determines version bumps from commits, conventional commits are still recommended for readable history:

| Commit Prefix | Meaning | Example |
|--------------|---------|---------|
| `feat:` | New feature | `feat: add anycast gateway support for SVIs` |
| `fix:` | Bug fix | `fix: correct ipaddr filter usage in L3 tasks` |
| `docs:` | Documentation | `docs: update OSPF configuration guide` |
| `chore:` | Maintenance | `chore: release version 0.6.0` |
| `feat!:` or `BREAKING CHANGE:` | Breaking change | `feat!: redesign configuration variable structure` |

---

## Changelog Management

All changes are tracked in [`CHANGELOG.md`](../CHANGELOG.md) following [Keep a Changelog](https://keepachangelog.com/) format.

### Adding Changes During Development

Add your changes to the `[Unreleased]` section as you work:

```markdown
## [Unreleased]

### Added
- **OSPF configuration support** - New filters and tasks for OSPF
  - Interface selection via custom fields
  - Area-based configuration
```

### Preparing a Release

When releasing, move the `[Unreleased]` content to a new version section:

**Before:**
```markdown
## [Unreleased]

### Added
- New OSPF support

## [0.5.0] - 2026-02-25
```

**After:**
```markdown
## [Unreleased]

## [0.6.0] - 2026-03-15

### Added
- New OSPF support

## [0.5.0] - 2026-02-25
```

Also update the comparison links at the bottom of the file.

### Categories

Use these categories in order:

1. **Added** — New features
2. **Changed** — Changes to existing functionality
3. **Deprecated** — Soon-to-be removed features
4. **Removed** — Removed features
5. **Fixed** — Bug fixes
6. **Security** — Security vulnerability fixes

---

## Release Workflow Details

### How It Works

The workflow (`.github/workflows/release.yml`) triggers on:

- **Push to `main`** when the `VERSION` file changes
- **Manual dispatch** (`workflow_dispatch`)

**Steps:**

1. **Run CI tests** — Lint, syntax check, unit tests must pass
2. **Read VERSION** — Gets the version string from the file
3. **Check tag** — Skips if `v{version}` tag already exists
4. **Extract release notes** — Pulls content from `CHANGELOG.md` for that version
5. **Create tag** — Annotated tag `v{version}`
6. **Create GitHub Release** — With release notes from the changelog

The workflow does **not** commit or push to `main`. It only creates tags and releases.

### Branch Protection Compatibility

The release workflow works with branch protection because it never pushes commits to protected branches. It only pushes tags, which are not restricted by the pull request requirement.

---

## GitHub Releases

Each release creates a GitHub Release with:

- **Tag**: `v{version}` (e.g., `v0.5.0`)
- **Release Name**: `Release v{version}`
- **Release Notes**: Extracted from `CHANGELOG.md`
- **Assets**: Source code (zip/tar.gz) — automatically added by GitHub

### Viewing Releases

```bash
# List releases
gh release list

# View specific release
gh release view v0.5.0

# Download release assets
gh release download v0.5.0
```

---

## Git Tags

Tags follow the format `v{version}`:

- `v0.5.0` — First public release
- `v0.6.0` — Feature release
- `v1.0.0` — First major stable release

### Tag Management

```bash
# List tags
git tag -l

# View tag details
git show v0.5.0

# Checkout specific version
git checkout v0.5.0

# Delete tag (if needed)
git tag -d v0.5.0
git push origin :refs/tags/v0.5.0
```

---

## Ansible Galaxy Publishing

**Status**: Not yet enabled

When ready to publish to Ansible Galaxy:

1. **Galaxy Namespace** — Claim `aopdal` namespace on Ansible Galaxy
2. **API Key** — Generate API key from https://galaxy.ansible.com/me/preferences
3. **GitHub Secret** — Add `GALAXY_API_KEY` to repository secrets
4. **Import**: `ansible-galaxy role import aopdal ansible-role-aruba-cx-switch`

---

## Release Checklist

### Pre-Release

- [ ] All tests passing (CI green)
- [ ] `CHANGELOG.md` updated — `[Unreleased]` content moved to new version section
- [ ] `VERSION` file updated with new version number
- [ ] Documentation updated if needed

### During Release

- [ ] Create PR with VERSION + CHANGELOG changes
- [ ] CI passes on PR
- [ ] Merge PR to main

### Post-Release

- [ ] GitHub Release created automatically
- [ ] Git tag created
- [ ] `CHANGELOG.md` has empty `[Unreleased]` section ready for next cycle

---

## Common Scenarios

### Scenario 1: Regular Feature Release

```
Situation: Added new OSPF configuration support

1. Develop on feature branch, update CHANGELOG.md [Unreleased]
2. When ready to release:
   - Update VERSION: 0.5.0 → 0.6.0
   - Move [Unreleased] to [0.6.0] section in CHANGELOG.md
3. Merge PR to main
4. Workflow creates v0.6.0 tag and release
```

### Scenario 2: Critical Bug Fix

```
Situation: Fixed critical VLAN deletion bug

1. Fix on hotfix branch, update CHANGELOG.md [Unreleased]
2. Update VERSION: 0.6.0 → 0.6.1
3. Move [Unreleased] to [0.6.1] section in CHANGELOG.md
4. Merge PR to main
5. Workflow creates v0.6.1 tag and release
```

### Scenario 3: Major Breaking Change

```
Situation: Refactored configuration variable structure

1. Develop on feature branch
2. Update VERSION: 0.6.1 → 1.0.0
3. Update CHANGELOG.md with breaking changes noted
4. Merge PR to main
5. Workflow creates v1.0.0 tag and release
```

---

## Troubleshooting

### Release Workflow Failed

**Check**:
- GitHub Actions logs for error details
- Ensure `CHANGELOG.md` has a section matching the version in `VERSION`

### Tag Already Exists

```bash
# Delete tag and re-trigger
gh release delete v0.6.0 --yes
git tag -d v0.6.0
git push origin :refs/tags/v0.6.0

# Re-trigger workflow
gh workflow run release.yml --ref main
```

### Release Notes Empty

The workflow extracts notes from `CHANGELOG.md` by matching the version header. Ensure:
- There is a `## [0.6.0] - YYYY-MM-DD` section in `CHANGELOG.md`
- Content exists between that header and the next version header

---

## Files Modified in a Release

| File | Who Updates | When |
|------|------------|------|
| `VERSION` | Developer (in PR) | Before merge |
| `CHANGELOG.md` | Developer (in PR) | Before merge |
| Git tag | Workflow (automated) | After merge |
| GitHub Release | Workflow (automated) | After merge |

---

## Best Practices

1. **Update CHANGELOG as you go** — Add entries to `[Unreleased]` during development
2. **Bump VERSION in the release PR** — Keep version bump as a clear, separate commit
3. **Use Semantic Versioning** — Follow SemVer strictly
4. **Write detailed notes** — Help users understand what changed
5. **Test before merge** — CI should be green
6. **Tag consistently** — Always use `v` prefix (e.g., `v0.6.0`)

---

## See Also

- [Semantic Versioning](https://semver.org/)
- [Keep a Changelog](https://keepachangelog.com/)
- [GitHub Releases Documentation](https://docs.github.com/en/repositories/releasing-projects-on-github)
- [Release Integration](RELEASE_INTEGRATION.md)
- [Release Quick Reference](RELEASE_QUICK_REFERENCE.md)
- [CHANGELOG.md](../CHANGELOG.md)
- [Contributing Guide](CONTRIBUTING.md)
