# Release Quick Reference

One-page cheat sheet for the release process.

## TL;DR

1. Update `CHANGELOG.md` — move `[Unreleased]` content to a new version section
2. Update `VERSION` file with the new version number
3. Merge PR to `main`
4. Workflow creates Git tag and GitHub Release automatically

---

## Step-by-Step Release

```bash
# 1. Bump version
echo "0.6.0" > VERSION

# 2. Update CHANGELOG.md
#    Move [Unreleased] entries → [0.6.0] - YYYY-MM-DD
vim CHANGELOG.md

# 3. Commit, push, create PR
git add VERSION CHANGELOG.md
git commit -m "chore: release version 0.6.0"
git push
gh pr create --title "chore: release v0.6.0" --fill

# 4. Merge PR → workflow creates tag + release
gh pr merge --merge
```

---

## Manual Trigger

If VERSION was already updated in a previous PR:

```bash
# Via CLI
gh workflow run release.yml --ref main

# Via UI: Actions → Release → Run workflow
```

---

## Changelog Format

```markdown
## [Unreleased]

## [0.6.0] - 2026-03-15

### Added
- **Feature name** - Brief description
  - Detail 1
  - Detail 2

### Fixed
- **Bug description** - How it was fixed

## [0.5.0] - 2026-02-25
...
```

### Categories (in order)

1. **Added** — New features
2. **Changed** — Changes to existing features
3. **Deprecated** — Soon-to-be removed
4. **Removed** — Removed features
5. **Fixed** — Bug fixes
6. **Security** — Security fixes

---

## Versioning

```
MAJOR.MINOR.PATCH
```

- **Patch** (`0.5.0` → `0.5.1`) — Bug fixes, docs
- **Minor** (`0.5.1` → `0.6.0`) — New features, backward compatible
- **Major** (`0.6.0` → `1.0.0`) — Breaking changes

---

## Common Tasks

### View Current Version

```bash
cat VERSION
git describe --tags --abbrev=0
```

### List Releases

```bash
gh release list
git tag -l
```

### Check Workflow Status

```bash
gh run list --workflow=release.yml
gh run view <run-id> --log
```

### Delete a Release

```bash
gh release delete v0.6.0 --yes
git tag -d v0.6.0
git push origin :refs/tags/v0.6.0
```

---

## Workflow Trigger

The release workflow runs when:

| Trigger | Condition |
|---------|-----------|
| Push to `main` | `VERSION` file was changed |
| Manual dispatch | `workflow_dispatch` from UI or CLI |

The workflow **only creates tags and releases**. It never commits to `main`.

---

## Files Modified in a Release

| File | Updated by | When |
|------|-----------|------|
| `VERSION` | Developer | In PR, before merge |
| `CHANGELOG.md` | Developer | In PR, before merge |
| Git tag | Workflow | After merge (automated) |
| GitHub Release | Workflow | After merge (automated) |

---

## Pre-Release Checklist

- [ ] `VERSION` bumped to new version
- [ ] `CHANGELOG.md` updated — `[Unreleased]` moved to versioned section
- [ ] CI passing (all tests green)
- [ ] Documentation updated if needed

---

## Quick Links

- [Full Documentation](RELEASE_PROCESS.md)
- [Release Integration](RELEASE_INTEGRATION.md)
- [Changelog](../CHANGELOG.md)
- [Current Version](../VERSION)
- [Releases](https://github.com/aopdal/ansible-role-aruba-cx-switch/releases)
- [Workflow](../.github/workflows/release.yml)
