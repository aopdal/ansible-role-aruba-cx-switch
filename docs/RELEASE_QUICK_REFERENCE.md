# Release Quick Reference

One-page cheat sheet for the release process.

## TL;DR

1. Use conventional commit messages (`feat:`, `fix:`, etc.)
2. Update `CHANGELOG.md` under `[Unreleased]`
3. Merge to `main`
4. Release workflow analyzes commits and creates appropriate release automatically

---

## Commit Message Format

Use conventional commits to automatically determine release type:

```bash
# Minor version bump (new feature)
git commit -m "feat: add anycast gateway support"

# Patch version bump (bug fix)
git commit -m "fix: correct ipaddr filter usage"

# Major version bump (breaking change)
git commit -m "feat!: redesign configuration API"
```

**Commit Prefixes:**
- `feat:` → Minor version bump (0.1.x → 0.2.0)
- `fix:` → Patch version bump (0.1.x → 0.1.y)
- `feat!:` or `BREAKING CHANGE:` → Major version bump (0.x.x → 1.0.0)
- `chore:`, `docs:`, `style:` → Patch version bump

---

## Automatic Release

```bash
# 1. Update CHANGELOG.md
vim CHANGELOG.md  # Add your changes under [Unreleased]

# 2. Commit with conventional commit message
git add CHANGELOG.md
git commit -m "feat: add new OSPF configuration support"
git push

# 3. Create and merge PR
gh pr create --fill
gh pr merge --merge

# ✅ Done! Workflow analyzes commits and creates release
#    In this case: feat: → Minor version bump
```

---

## Manual Release

### Via GitHub UI

1. Go to **Actions** → **Release** → **Run workflow**
2. Choose branch: `main`
3. Set version (optional): `1.0.0`
4. Set release type: `major` | `minor` | `patch`
5. Click **Run workflow**

### Via GitHub CLI

```bash
# Auto-detect from commits (recommended)
gh workflow run release.yml --ref main

# Force minor release (0.1.0 → 0.2.0)
gh workflow run release.yml --ref main -f release_type=minor

# Force major release (0.1.0 → 1.0.0)
gh workflow run release.yml --ref main -f release_type=major

# Force patch release (0.1.0 → 0.1.1)
gh workflow run release.yml --ref main -f release_type=patch

# Specific version (override auto-detection)
gh workflow run release.yml --ref main -f version=1.0.0
```

---

## Changelog Format

```markdown
## [Unreleased]

### Added
- **Feature name** - Brief description
  - Detail 1
  - Detail 2

### Changed
- **What changed** - Why it changed

### Fixed
- **Bug description** - How it was fixed

## [1.0.0] - 2025-01-15
...
```

### Categories (in order)

1. **Added** - New features
2. **Changed** - Changes to existing features
3. **Deprecated** - Soon-to-be removed
4. **Removed** - Removed features
5. **Fixed** - Bug fixes
6. **Security** - Security fixes

---

## Versioning

```
MAJOR.MINOR.PATCH
```

**Automatic (Conventional Commits):**
- `feat:` → **Minor** (`0.1.0` → `0.2.0`) - New features
- `fix:` → **Patch** (`0.1.0` → `0.1.1`) - Bug fixes
- `feat!:` or `BREAKING CHANGE:` → **Major** (`0.1.0` → `1.0.0`) - Breaking changes

**Manual Override:**
- **Patch** (`0.1.0` → `0.1.1`) - Bug fixes, docs
- **Minor** (`0.1.0` → `0.2.0`) - New features, backward compatible
- **Major** (`0.1.0` → `1.0.0`) - Breaking changes

---

## Common Tasks

### View Current Version

```bash
# From VERSION file
cat VERSION

# From git tags
git tag -l | tail -1
```

### List Releases

```bash
# GitHub releases
gh release list

# Git tags
git tag -l
```

### View Release

```bash
# Specific release
gh release view v1.0.0

# Latest release
gh release view --web
```

### Check Workflow Status

```bash
# List workflow runs
gh run list --workflow=release.yml

# View specific run
gh run view <run-id>

# Watch run
gh run watch
```

---

## Troubleshooting

### Release Failed

```bash
# View workflow logs
gh run list --workflow=release.yml --limit 1
gh run view <run-id> --log-failed

# Common issues:
# - No [Unreleased] section in CHANGELOG.md
# - Invalid YAML in galaxy.yml
# - Tag already exists
```

### Delete Tag

```bash
# Local
git tag -d v1.0.0

# Remote
git push origin :refs/tags/v1.0.0

# Both
git tag -d v1.0.0 && git push origin :refs/tags/v1.0.0
```

### Delete Release

```bash
# Delete release and tag
gh release delete v1.0.0 --yes
git push origin :refs/tags/v1.0.0
```

---

## Files Modified

- `VERSION` - Version number updated
- `CHANGELOG.md` - [Unreleased] → [Version]
- Git tags - New tag `v{version}`
- GitHub Releases - New release created

**Note**: This is an Ansible Role, not a Collection. We use `VERSION` file instead of `galaxy.yml`.

---

## Pre-Release Checklist

- [ ] `CHANGELOG.md` updated
- [ ] CI passing (all tests green)
- [ ] Documentation updated
- [ ] On `main` branch
- [ ] No uncommitted changes

---

## Example Workflow

```bash
# Feature branch
git checkout -b feature/new-thing

# Develop...
# ...

# Update changelog
cat >> CHANGELOG.md << 'EOF'
### Added
- **New thing** - Does cool stuff
EOF

# Commit and PR
git add .
git commit -m "feat: add new thing"
gh pr create --fill

# Merge to main (via PR)
# → Automatic release!
```

---

## Quick Links

- [Full Documentation](RELEASE_PROCESS.md)
- [Changelog](CHANGELOG.md)
- [Current Version](../VERSION)
- [Releases](https://github.com/aopdal/ansible-role-aruba-cx-switch/releases)
- [Workflow](../.github/workflows/release.yml)
