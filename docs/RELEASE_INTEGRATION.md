# Release System Integration

How the automated release system components work together.

## Overview

The release system consists of several interconnected components that automate versioning, changelog management, and release creation without publishing to Ansible Galaxy (yet).

## System Architecture

```mermaid
flowchart TD
    Dev[Developer Workflow]
    Dev_Details["1. Create feature branch<br/>2. Make changes<br/>3. Update CHANGELOG.md under [Unreleased]<br/>4. Create PR and merge to main"]

    Workflow[GitHub Actions: Release Workflow]
    Workflow_Details["Trigger: Push to main or manual dispatch<br/><br/>Steps:<br/>1. Checkout code (full history)<br/>2. Determine version (auto-increment or manual)<br/>3. Update galaxy.yml with new version<br/>4. Update CHANGELOG.md ([Unreleased] → [Version])<br/>5. Extract release notes from changelog<br/>6. Commit version changes<br/>7. Create Git tag (v{version})<br/>8. Create GitHub Release with notes"]

    Artifacts[Release Artifacts]
    Artifacts_Details["• Git Tag: v{version}<br/>• GitHub Release: Release notes + source code<br/>• Updated galaxy.yml: version field<br/>• Updated CHANGELOG.md: versioned entry"]

    Dev --> Dev_Details
    Dev_Details --> Workflow
    Workflow --> Workflow_Details
    Workflow_Details --> Artifacts
    Artifacts --> Artifacts_Details

    style Dev fill:#e1f5ff
    style Workflow fill:#fff3e0
    style Artifacts fill:#e8f5e9
    style Dev_Details fill:#f0f0f0
    style Workflow_Details fill:#f0f0f0
    style Artifacts_Details fill:#f0f0f0
```

---

## Component Details

### 1. VERSION - Version Storage

**Purpose**: Single source of truth for current version

**Location**: `/VERSION`

**Format**:
```
0.1.0
```

**Updated By**: Release workflow (automated)

**Read By**:
- Release workflow (to determine current version)
- Users (quick version check)

**Why not galaxy.yml?**: This is an Ansible **Role** (not a Collection). Roles use `meta/main.yml` for Galaxy metadata, not `galaxy.yml`. We use a simple `VERSION` file for version tracking.

**Example Flow**:
```mermaid
flowchart TD
    Initial[Initial: 0.1.0]
    Workflow[Workflow runs<br/>patch release]
    Updated[Updated: 0.1.1]

    Initial --> Workflow
    Workflow --> Updated

    style Initial fill:#e3f2fd
    style Workflow fill:#fff3e0
    style Updated fill:#e8f5e9
```

---

### 2. CHANGELOG.md - Change Tracking

**Purpose**: Human-readable change history

**Location**: `/CHANGELOG.md`

**Format**: [Keep a Changelog](https://keepachangelog.com/)

```markdown
## [Unreleased]

### Added
- New features here

## [0.1.1] - 2025-01-15

### Fixed
- Bug fixes

## [0.1.0] - 2025-01-10

### Added
- Initial release
```

**Updated By**:
- Developers (add to [Unreleased])
- Release workflow (move [Unreleased] to version)

**Read By**:
- Release workflow (extract release notes)
- Users (understand changes)
- Documentation site (via mkdocs)

**Example Flow**:
```markdown
Before Release:
## [Unreleased]
### Added
- New OSPF support

After Release (v0.2.0):
## [Unreleased]

## [0.2.0] - 2025-01-15
### Added
- New OSPF support
```

---

### 3. Release Workflow - Automation Engine

**Purpose**: Orchestrate release process

**Location**: `/.github/workflows/release.yml`

**Triggers**:
- Push to `main` branch (automatic)
- Manual workflow dispatch (with parameters)

**Inputs** (manual trigger):
```yaml
version: ""                 # Optional: specific version
release_type: "patch"       # major|minor|patch
```

**Outputs**:
- Updated `galaxy.yml`
- Updated `CHANGELOG.md`
- Git tag `v{version}`
- GitHub Release

**Logic**:

```python
# Version Determination
if manual_version:
    new_version = manual_version
else:
    current = read_version_file()
    if release_type == "major":
        new_version = increment_major(current)
    elif release_type == "minor":
        new_version = increment_minor(current)
    else:  # patch
        new_version = increment_patch(current)

# Update Files
update_version_file(new_version)
update_changelog(new_version)
extract_release_notes(changelog)

# Git Operations
git_commit("chore: release version {new_version}")
git_tag("v{new_version}")
git_push()

# GitHub Release
create_github_release(
    tag="v{new_version}",
    notes=release_notes
)
```

---

### 4. Git Tags - Version Markers

**Purpose**: Mark specific commits as releases

**Format**: `v{version}` (e.g., `v1.0.0`)

**Created By**: Release workflow

**Used For**:
- Checkout specific version
- Track release history
- GitHub Release association

**Example**:
```bash
# List tags
$ git tag -l
v0.1.0
v0.1.1
v0.2.0

# Checkout specific version
$ git checkout v0.1.1

# View tag details
$ git show v0.1.1
```

---

### 5. GitHub Releases - Distribution

**Purpose**: Provide downloadable releases with notes

**Created By**: Release workflow

**Contains**:
- Release version and date
- Release notes (from CHANGELOG.md)
- Source code (zip/tar.gz)
- Git tag reference

**Example**:
```
Release v0.2.0
Published on Jan 15, 2025

# Release 0.2.0

### Added
- **OSPF configuration support** - Complete OSPF implementation
  - Interface selection and area assignment
  - Configuration validation
  - NetBox custom field integration

### Fixed
- **VLAN deletion** - Fixed VLAN 1 protection logic

Assets:
- Source code (zip)
- Source code (tar.gz)
```

---

## Integration Flow

### Scenario: Feature Development to Release

```mermaid
flowchart TD
    Step1[Step 1: Developer Creates Feature]
    Step1_Details["$ git checkout -b feature/ospf-support<br/>$ # ... develop feature ...<br/>$ vim CHANGELOG.md  # Add to [Unreleased]<br/>$ git commit -m 'feat: add OSPF support'<br/>$ git push"]

    Step2[Step 2: Create and Merge PR]
    Step2_Details["$ gh pr create --fill<br/># Review, approve, merge to main"]

    Trigger[Push to main triggers workflow]

    Step3[Step 3: Release Workflow Executes]
    Step3_Details["1. Read current version from galaxy.yml: 0.1.0<br/>2. Auto-increment (patch): 0.1.0 → 0.1.1<br/>3. Update galaxy.yml: version: 0.1.1<br/>4. Update CHANGELOG.md:<br/>   [Unreleased] → [0.1.1] - 2025-01-15<br/>5. Extract release notes from CHANGELOG<br/>6. Commit: 'chore: release version 0.1.1'<br/>7. Create tag: v0.1.1<br/>8. Push commit and tag<br/>9. Create GitHub Release"]

    Step4[Step 4: Release Available]
    Step4_Details["• GitHub Release: v0.1.1<br/>• Git Tag: v0.1.1<br/>• galaxy.yml: version: 0.1.1<br/>• CHANGELOG.md: [0.1.1] entry added"]

    Step1 --> Step1_Details
    Step1_Details --> Step2
    Step2 --> Step2_Details
    Step2_Details --> Trigger
    Trigger --> Step3
    Step3 --> Step3_Details
    Step3_Details --> Step4
    Step4 --> Step4_Details

    style Step1 fill:#e3f2fd
    style Step2 fill:#f3e5f5
    style Trigger fill:#fff9c4
    style Step3 fill:#fff3e0
    style Step4 fill:#e8f5e9
    style Step1_Details fill:#f5f5f5
    style Step2_Details fill:#f5f5f5
    style Step3_Details fill:#f5f5f5
    style Step4_Details fill:#f5f5f5
```

---

## File Dependencies

### VERSION File

```mermaid
graph TD
    VERSION[VERSION]
    VERSION --> |Updated by| RW1[Release workflow: version number]
    VERSION --> |Read by| RW2[Release workflow: current version]
    VERSION --> |Read by| Users1[Users: quick check]

    style VERSION fill:#e3f2fd
    style RW1 fill:#fff3e0
    style RW2 fill:#fff3e0
    style Users1 fill:#e8f5e9
```

### CHANGELOG.md

```mermaid
graph TD
    CHANGELOG[CHANGELOG.md]
    CHANGELOG --> |Updated by| Dev1[Developer: adds to Unreleased]
    CHANGELOG --> |Read by| RW3[Release workflow: extract notes]
    CHANGELOG --> |Updated by| RW4[Release workflow: version section]

    style CHANGELOG fill:#f3e5f5
    style Dev1 fill:#e3f2fd
    style RW3 fill:#fff3e0
    style RW4 fill:#fff3e0
```

### meta/main.yml

```mermaid
graph TD
    META[meta/main.yml]
    META --> |Updated by| Manual1[Manual: Galaxy metadata]
    META --> |Read by| Galaxy1[Ansible Galaxy: when publishing]

    style META fill:#fff3e0
    style Manual1 fill:#e3f2fd
    style Galaxy1 fill:#e0f2f1
```

### Release Workflow

```mermaid
graph TD
    WORKFLOW[.github/workflows/release.yml]
    WORKFLOW --> |Triggered by| Push[Git push to main]
    WORKFLOW --> |Reads| Read1[VERSION, CHANGELOG.md]
    WORKFLOW --> |Updates| Update1[VERSION, CHANGELOG.md]
    WORKFLOW --> |Creates| Create1[Git tags, GitHub Releases]
    WORKFLOW --> |Requires| Token[GITHUB_TOKEN: automatic]

    style WORKFLOW fill:#e8f5e9
    style Push fill:#fff9c4
    style Read1 fill:#e3f2fd
    style Update1 fill:#f3e5f5
    style Create1 fill:#fce4ec
    style Token fill:#fff3e0
```

### Git Tags

```mermaid
graph TD
    TAGS[Git Tags]
    TAGS --> |Created by| RW5[Release workflow]
    TAGS --> |Used by| Use1[GitHub Releases, version control]

    style TAGS fill:#fce4ec
    style RW5 fill:#e8f5e9
    style Use1 fill:#f1f8e9
```

### GitHub Releases

```mermaid
graph TD
    RELEASES[GitHub Releases]
    RELEASES --> |Created by| RW6[Release workflow]
    RELEASES --> |Contains| Content[Release notes, source code]

    style RELEASES fill:#f1f8e9
    style RW6 fill:#e8f5e9
    style Content fill:#e0f2f1
```

---

## Configuration Points

### Release Workflow Configuration

**File**: `.github/workflows/release.yml`

**Key Settings**:
```yaml
on:
  push:
    branches:
      - main              # Auto-trigger on main push
  workflow_dispatch:
    inputs:
      version: ...        # Manual version override
      release_type: ...   # major|minor|patch

permissions:
  contents: write         # Required for creating releases
  pull-requests: write    # Required for PR integration
```

### Version Configuration

**File**: `galaxy.yml`

```yaml
version: 0.1.0           # Current version (updated by workflow)
```

### Changelog Configuration

**File**: `CHANGELOG.md`

**Format Requirements**:
- Must have `[Unreleased]` section header
- Follow [Keep a Changelog](https://keepachangelog.com/) format
- Use standard categories: Added, Changed, Fixed, etc.

---

## Error Handling

### Workflow Failures

**Common Issues and Solutions**:

| Error | Cause | Solution |
|-------|-------|----------|
| Tag already exists | Version already released | Delete tag or use different version |
| No [Unreleased] section | CHANGELOG format issue | Add `[Unreleased]` header |
| Invalid YAML | Malformed galaxy.yml | Validate YAML syntax |
| Permission denied | Token issue | Check GITHUB_TOKEN permissions |

### Recovery Procedures

**Delete Failed Release**:
```bash
# Delete release
gh release delete v1.0.0 --yes

# Delete tag
git tag -d v1.0.0
git push origin :refs/tags/v1.0.0

# Reset VERSION if needed
git checkout HEAD~1 VERSION
git commit -m "chore: reset version"
git push
```

**Retry Release**:
```bash
# Fix issue (e.g., update CHANGELOG.md)
vim CHANGELOG.md
git add CHANGELOG.md
git commit -m "docs: fix changelog format"
git push

# Workflow reruns automatically
```

---

## Future: Ansible Galaxy Integration

When ready to publish to Ansible Galaxy:

### Step 1: Enable Publishing

Uncomment the Galaxy publishing job in `.github/workflows/ci.yml`:

```yaml
release:
  name: Release to Ansible Galaxy
  # ... (see ci.yml)
```

### Step 2: Add Secrets

Add `GALAXY_API_KEY` to repository secrets:

1. Generate key at https://galaxy.ansible.com/me/preferences
2. Add to GitHub: Settings → Secrets → Actions → New secret

### Step 3: Workflow Integration

```mermaid
flowchart TD
    RW[Release Workflow<br/>creates tag]
    CI[CI Workflow<br/>on tag push]
    PJ[Galaxy Publishing Job]
    GP[Role Published to Galaxy]

    RW --> CI
    CI --> PJ
    PJ --> GP

    style RW fill:#e8f5e9
    style CI fill:#fff3e0
    style PJ fill:#f3e5f5
    style GP fill:#e0f2f1
```

### Combined Flow

```mermaid
flowchart LR
    Developer --> PR[Pull Request]
    PR --> Main[Main Branch]
    Main --> ReleaseWF[Release Workflow]
    ReleaseWF --> Tag[Git Tag]
    Tag --> CI[CI Workflow]
    CI --> Galaxy[Ansible Galaxy]
    ReleaseWF --> GHRelease[GitHub Release]

    style Developer fill:#e3f2fd
    style PR fill:#f3e5f5
    style Main fill:#fff3e0
    style ReleaseWF fill:#e8f5e9
    style Tag fill:#fce4ec
    style CI fill:#f1f8e9
    style Galaxy fill:#e0f2f1
    style GHRelease fill:#fff9c4
```

---

## Monitoring and Verification

### Check Release Status

```bash
# View workflow runs
gh run list --workflow=release.yml

# View specific run
gh run view <run-id> --log

# List releases
gh release list

# View specific release
gh release view v1.0.0
```

### Verify Version Consistency

```bash
# Check VERSION file
cat VERSION

# Check latest tag
git describe --tags --abbrev=0

# Check latest release
gh release view --json tagName -q .tagName

# All should match!
```

### Audit Trail

```bash
# Release commits
git log --grep="chore: release version" --oneline

# Tags with dates
git log --tags --simplify-by-decoration --pretty="format:%ai %d"

# Full release history
gh release list --limit 100
```

---

## Best Practices

1. **Always Update CHANGELOG First** - Before merging to main
2. **Use Semantic Versioning** - MAJOR.MINOR.PATCH strictly
3. **Meaningful Release Notes** - Explain what changed and why
4. **Test Before Merge** - CI should be green
5. **One Feature Per Release** - Keep releases focused
6. **Tag Immutability** - Never modify released tags
7. **Version Alignment** - Keep all version sources in sync

---

## Troubleshooting Guide

### Workflow Not Running

**Check**:
```bash
# Verify workflow file exists
ls -la .github/workflows/release.yml

# Check workflow syntax
cat .github/workflows/release.yml | python -m yaml

# View workflow status
gh workflow view release.yml
```

### Version Not Updated

**Check**:
```bash
# Verify VERSION file exists
cat VERSION

# Check commit history
git log --oneline -5

# View workflow logs
gh run view --log
```

### Release Notes Empty

**Check**:
```bash
# Verify [Unreleased] section exists
grep -A 10 "\[Unreleased\]" CHANGELOG.md

# Check format
head -20 CHANGELOG.md
```

---

## See Also

- [Release Process - Full Guide](RELEASE_PROCESS.md)
- [Release Quick Reference](RELEASE_QUICK_REFERENCE.md)
- [CHANGELOG.md](../CHANGELOG.md)
- [Contributing Guide](CONTRIBUTING.md)
- [Semantic Versioning](https://semver.org/)
- [Keep a Changelog](https://keepachangelog.com/)
