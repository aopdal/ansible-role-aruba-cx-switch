# Release Process

Comprehensive guide to the automated release process for the Aruba CX Switch Ansible Role.

## Overview

The release process is fully automated using GitHub Actions. When code is merged to the `main` branch, an automated workflow:

1. Determines the next version number
2. Updates `VERSION` and `CHANGELOG.md`
3. Creates a Git tag
4. Creates a GitHub Release with release notes
5. (Future) Publishes to Ansible Galaxy

**Note**: Ansible Galaxy publishing is currently disabled and will be enabled when ready for public release.

---

## Quick Start

### Automatic Release (Recommended)

1. Ensure `CHANGELOG.md` has content under `[Unreleased]` section
2. Merge your PR to `main` branch
3. The release workflow automatically creates a patch release (e.g., `0.1.0` → `0.1.1`)

### Manual Release

Trigger a release manually with custom version:

```bash
# Via GitHub UI:
# Go to Actions → Release → Run workflow
# - Choose branch: main
# - Version: (optional) e.g., 1.0.0
# - Release type: major|minor|patch

# Via GitHub CLI:
gh workflow run release.yml \
  --ref main \
  -f version=1.0.0 \
  -f release_type=minor
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

- **Patch**: `1.0.0` → `1.0.1` - Bug fix, documentation update
- **Minor**: `1.0.1` → `1.1.0` - New feature (e.g., OSPF support)
- **Major**: `1.1.0` → `2.0.0` - Breaking change (e.g., API change)

### Current Version

The current version is stored in [`VERSION`](../VERSION) file:

```
0.1.0
```

**Note**: This is an Ansible **Role** (not a Collection), so we use a simple `VERSION` file instead of `galaxy.yml`.

---

## Changelog Management

All changes are tracked in [`CHANGELOG.md`](../CHANGELOG.md) following [Keep a Changelog](https://keepachangelog.com/) format.

### Changelog Structure

```markdown
# Changelog

## [Unreleased]

### Added
- New features go here

### Changed
- Changes to existing functionality

### Deprecated
- Soon-to-be removed features

### Removed
- Removed features

### Fixed
- Bug fixes

### Security
- Security improvements

## [1.0.0] - 2025-01-15

### Added
- Initial release
```

### Adding Changes

**Before merging to main**, add your changes to the `[Unreleased]` section:

```markdown
## [Unreleased]

### Added
- **OSPF configuration support** - Complete implementation of OSPF filters
  - Interface selection via custom fields
  - Area-based configuration
  - Configuration validation
```

### Categories

Use these categories in order:

1. **Added** - New features
2. **Changed** - Changes to existing functionality
3. **Deprecated** - Soon-to-be removed features
4. **Removed** - Removed features
5. **Fixed** - Bug fixes
6. **Security** - Security vulnerability fixes

### Writing Good Changelog Entries

**Good Examples:**

```markdown
### Added
- **L3 interface support** - IPv4/IPv6 configuration on physical and VLAN interfaces
  - VRF support with automatic built-in VRF filtering
  - Dual-stack configuration support
  - Comprehensive categorization filters (7 categories)

### Fixed
- **VLAN interface creation** - Fixed issue where VLAN interfaces (SVIs) were incorrectly targeted for creation
  - Skip VLAN interface creation attempts (managed by VLAN module)
  - Add debug logging for skipped VLAN interfaces
```

**Bad Examples:**

```markdown
### Added
- Added stuff
- Updates
- Fixed a bug
```

---

## Release Workflow

### Automatic Release Workflow

Triggered on push to `main` branch:

```yaml
# .github/workflows/release.yml
on:
  push:
    branches:
      - main
```

**Steps:**

1. **Checkout Code** - Fetches full git history
2. **Determine Version** - Auto-increments patch version
3. **Update VERSION** - Sets new version
4. **Update CHANGELOG.md** - Moves `[Unreleased]` to versioned section
5. **Commit Changes** - Commits version files
6. **Create Tag** - Tags commit with `v{version}`
7. **Create Release** - Creates GitHub release with notes
8. **Summary** - Displays release summary in Actions UI

### Manual Release Workflow

Triggered via GitHub Actions UI or CLI:

**Parameters:**

- **version** (optional) - Explicit version (e.g., `1.0.0`)
- **release_type** (optional) - `major`, `minor`, or `patch` (default: `patch`)

**Logic:**

- If `version` provided: Use that version
- If `version` empty: Auto-increment based on `release_type`

### Version Determination

```python
# Current version: 1.2.3

# Patch release (default)
1.2.3 → 1.2.4

# Minor release
1.2.3 → 1.3.0

# Major release
1.2.3 → 2.0.0

# Manual version
1.2.3 → 2.5.0 (if specified)
```

---

## GitHub Releases

Each release creates a GitHub Release with:

- **Tag**: `v{version}` (e.g., `v1.0.0`)
- **Release Name**: `Release v{version}`
- **Release Notes**: Extracted from `CHANGELOG.md`
- **Assets**: Source code (zip/tar.gz) - automatically added by GitHub

### Viewing Releases

```bash
# List releases
gh release list

# View specific release
gh release view v1.0.0

# Download release assets
gh release download v1.0.0
```

---

## Git Tags

Tags follow the format `v{version}`:

- `v0.1.0` - Initial development release
- `v1.0.0` - First stable release
- `v1.1.0` - Feature release
- `v2.0.0` - Major release

### Tag Management

```bash
# List tags
git tag -l

# View tag details
git show v1.0.0

# Checkout specific version
git checkout v1.0.0

# Delete tag (if needed)
git tag -d v1.0.0
git push origin :refs/tags/v1.0.0
```

---

## Ansible Galaxy Publishing

**Status**: Currently disabled

When ready for public release, uncomment the Galaxy publishing job in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml):

```yaml
release:
  name: Release to Ansible Galaxy
  runs-on: ubuntu-latest
  needs: [lint, syntax, molecule, integration]
  if: github.ref == 'refs/heads/main' && github.event_name == 'push'
  steps:
    # ... (see ci.yml for full configuration)
```

### Prerequisites for Galaxy Publishing

1. **Galaxy Namespace** - Claim `aopdal` namespace on Ansible Galaxy
2. **API Key** - Generate API key from https://galaxy.ansible.com/me/preferences
3. **GitHub Secret** - Add `GALAXY_API_KEY` to repository secrets
4. **Public Repository** - Ensure repository is public
5. **Role Quality** - Meet Ansible Galaxy quality standards

### Publishing Manually

```bash
# Login to Galaxy
ansible-galaxy login

# Import role
ansible-galaxy role import aopdal ansible-role-aruba-cx-switch

# Or use GitHub workflow
gh workflow run ci.yml
```

---

## Release Checklist

Use this checklist before creating a release:

### Pre-Release

- [ ] All tests passing (CI green)
- [ ] CHANGELOG.md updated with all changes
- [ ] Documentation updated
- [ ] Version number follows SemVer
- [ ] No uncommitted changes
- [ ] On `main` branch

### During Release

- [ ] Verify version number is correct
- [ ] Check CHANGELOG.md formatting
- [ ] Review release notes

### Post-Release

- [ ] GitHub Release created successfully
- [ ] Git tag created
- [ ] Version in galaxy.yml updated
- [ ] CHANGELOG.md has new `[Unreleased]` section
- [ ] (Future) Role published to Ansible Galaxy

---

## Common Scenarios

### Scenario 1: Regular Feature Release

```markdown
**Situation**: Added new OSPF configuration support

**Steps**:
1. Update CHANGELOG.md:
   ```markdown
   ## [Unreleased]

   ### Added
   - **OSPF configuration support** - New filters and tasks for OSPF
     - `select_ospf_interfaces()` filter
     - `extract_ospf_areas()` filter
     - OSPF interface configuration task
   ```

2. Merge PR to main
3. Workflow automatically creates v0.2.0 (minor release)
```

### Scenario 2: Critical Bug Fix

```markdown
**Situation**: Fixed critical VLAN deletion bug

**Steps**:
1. Create hotfix branch from main
2. Fix bug and update CHANGELOG.md:
   ```markdown
   ## [Unreleased]

   ### Fixed
   - **VLAN deletion** - Fixed issue where VLAN 1 was incorrectly deleted
   ```

3. Merge PR to main
4. Workflow automatically creates v0.1.1 (patch release)
```

### Scenario 3: Major Breaking Change

```markdown
**Situation**: Refactored role to use Ansible collections

**Steps**:
1. Update CHANGELOG.md:
   ```markdown
   ## [Unreleased]

   ### Changed
   - **BREAKING**: Migrated to Ansible collections
     - Requires Ansible 2.16+
     - Role variables renamed (see migration guide)
   ```

2. Merge PR to main
3. **Manually trigger workflow** with release_type=major
4. Creates v1.0.0 (major release)
```

### Scenario 4: Custom Version Number

```markdown
**Situation**: Need to align with organizational versioning

**Steps**:
1. Update CHANGELOG.md with changes
2. Go to GitHub Actions → Release → Run workflow
3. Set version to "2.0.0"
4. Workflow creates v2.0.0
```

---

## Troubleshooting

### Release Workflow Failed

**Check**:
- GitHub Actions logs for error details
- Ensure `CHANGELOG.md` has `[Unreleased]` section
- Verify `galaxy.yml` exists and is valid YAML

**Common Errors**:

```bash
# Error: Tag already exists
# Solution: Delete tag and retry
git tag -d v1.0.0
git push origin :refs/tags/v1.0.0

# Error: CHANGELOG.md not found
# Solution: Ensure file exists in repo root
ls -la CHANGELOG.md

# Error: Invalid YAML in galaxy.yml
# Solution: Validate YAML syntax
yamllint galaxy.yml
```

### Version Not Incremented

**Check**:
- Workflow ran on `main` branch
- Previous version in `galaxy.yml` is valid
- Release type parameter is correct

### Release Notes Empty

**Check**:
- `[Unreleased]` section in CHANGELOG.md has content
- Content is between `[Unreleased]` and next version header
- CHANGELOG.md format matches Keep a Changelog spec

---

## Development Workflow

### Recommended Git Workflow

```bash
# 1. Create feature branch
git checkout -b feature/ospf-support

# 2. Develop feature
# ... make changes ...

# 3. Update CHANGELOG.md
cat >> CHANGELOG.md << 'EOF'
## [Unreleased]

### Added
- **OSPF configuration support** - Complete OSPF implementation
  - Interface selection and area assignment
  - Configuration validation
  - NetBox custom field integration
EOF

# 4. Commit and push
git add .
git commit -m "feat: add OSPF configuration support"
git push origin feature/ospf-support

# 5. Create Pull Request
gh pr create --title "feat: add OSPF configuration support" \
  --body "Implements OSPF configuration with NetBox integration"

# 6. After PR review and merge to main:
# → Workflow automatically creates release
```

### Conventional Commits (Optional)

While not required, following conventional commits helps with changelog generation:

```bash
# Feature
git commit -m "feat: add OSPF configuration support"

# Bug fix
git commit -m "fix: prevent VLAN 1 deletion"

# Documentation
git commit -m "docs: update OSPF configuration guide"

# Chore (no changelog entry)
git commit -m "chore: update dependencies"

# Breaking change
git commit -m "feat!: migrate to Ansible collections

BREAKING CHANGE: Requires Ansible 2.16+"
```

---

## Files Modified by Release Workflow

### VERSION

**Before Release**:
```
0.1.0
```

**After Release** (patch):
```
0.1.1
```

### CHANGELOG.md

**Before Release**:
```markdown
## [Unreleased]

### Added
- New OSPF support

## [0.1.0] - 2025-01-10
```

**After Release**:
```markdown
## [Unreleased]

## [0.1.1] - 2025-01-15

### Added
- New OSPF support

## [0.1.0] - 2025-01-10
```

---

## Best Practices

1. **Update CHANGELOG First** - Always update before merging to main
2. **Use Semantic Versioning** - Follow SemVer strictly
3. **Write Detailed Notes** - Help users understand changes
4. **Test Before Release** - Ensure CI passes
5. **Review Release Notes** - Check generated notes before publishing
6. **Tag Consistently** - Always use `v` prefix (e.g., `v1.0.0`)
7. **Communicate Breaking Changes** - Document migration steps
8. **Keep Versions Aligned** - All version files should match

---

## Future Enhancements

Planned improvements to the release process:

- [ ] Automated changelog generation from commit messages
- [ ] Release notes template customization
- [ ] Pre-release / beta version support
- [ ] Automated dependency updates
- [ ] Release approval workflow
- [ ] Multi-environment testing before release
- [ ] Rollback capability

---

## See Also

- [Semantic Versioning](https://semver.org/)
- [Keep a Changelog](https://keepachangelog.com/)
- [GitHub Releases Documentation](https://docs.github.com/en/repositories/releasing-projects-on-github)
- [Ansible Galaxy Documentation](https://galaxy.ansible.com/docs/)
- [CHANGELOG.md](../CHANGELOG.md)
- [Contributing Guide](CONTRIBUTING.md)
