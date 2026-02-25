# Release System Integration

How the release system components work together.

## Overview

The release system is designed to respect branch protection. The developer handles version bumps and changelog updates in a pull request. The automated workflow only creates tags and GitHub Releases — it never pushes commits to `main`.

## System Architecture

```mermaid
flowchart TD
    Dev[Developer Workflow]
    Dev_Details["1. Create feature branch<br/>2. Make changes<br/>3. Update CHANGELOG.md under [Unreleased]<br/>4. Bump VERSION file<br/>5. Move [Unreleased] to versioned section<br/>6. Create PR and merge to main"]

    Workflow[GitHub Actions: Release Workflow]
    Workflow_Details["Trigger: Push to main (VERSION changed) or manual<br/><br/>Steps:<br/>1. Run CI tests<br/>2. Read VERSION file<br/>3. Check if tag already exists<br/>4. Extract release notes from CHANGELOG.md<br/>5. Create Git tag (v{version})<br/>6. Create GitHub Release with notes"]

    Artifacts[Release Artifacts]
    Artifacts_Details["• Git Tag: v{version}<br/>• GitHub Release: Release notes + source code<br/>• No files modified on main"]

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

### 1. VERSION — Version Storage

**Purpose**: Single source of truth for current version

**Location**: `/VERSION`

**Format**:
```
0.5.0
```

**Updated by**: Developer (in PR, before merge)

**Read by**:
- Release workflow (to create the correct tag)
- Users (quick version check)

**Why not galaxy.yml?**: This is an Ansible **Role** (not a Collection). Roles use `meta/main.yml` for Galaxy metadata, not `galaxy.yml`. We use a simple `VERSION` file for version tracking.

---

### 2. CHANGELOG.md — Change Tracking

**Purpose**: Human-readable change history and release notes source

**Location**: `/CHANGELOG.md`

**Format**: [Keep a Changelog](https://keepachangelog.com/)

```markdown
## [Unreleased]

## [0.6.0] - 2026-03-15

### Added
- New features

## [0.5.0] - 2026-02-25
```

**Updated by**: Developer
- During development: add entries to `[Unreleased]`
- At release time: move `[Unreleased]` content to a versioned section

**Read by**:
- Release workflow (extracts release notes for the version)
- Users (understand changes between versions)
- Documentation site (via MkDocs)

---

### 3. Release Workflow — Automation Engine

**Purpose**: Create Git tags and GitHub Releases automatically

**Location**: `/.github/workflows/release.yml`

**Triggers**:
- Push to `main` when `VERSION` file changes
- Manual workflow dispatch

**What it does**:
- Reads VERSION file
- Checks if tag already exists (skip if so)
- Extracts release notes from CHANGELOG.md
- Creates annotated Git tag `v{version}`
- Creates GitHub Release with notes

**What it does NOT do**:
- Does not commit to `main`
- Does not modify VERSION or CHANGELOG.md
- Does not auto-increment versions

---

### 4. Git Tags — Version Markers

**Purpose**: Mark specific commits as releases

**Format**: `v{version}` (e.g., `v0.5.0`)

**Created by**: Release workflow (automated)

**Used for**:
- Checkout specific version
- Track release history
- GitHub Release association

---

### 5. GitHub Releases — Distribution

**Purpose**: Provide downloadable releases with notes

**Created by**: Release workflow (automated)

**Contains**:
- Release version and date
- Release notes (extracted from CHANGELOG.md)
- Source code (zip/tar.gz)
- Git tag reference

---

## Integration Flow

### Scenario: Feature Development to Release

```mermaid
flowchart TD
    Step1[Step 1: Develop Feature]
    Step1_Details["$ git checkout -b feature/ospf-support<br/>$ # ... develop feature ...<br/>$ vim CHANGELOG.md  # Add to [Unreleased]<br/>$ git commit -m 'feat: add OSPF support'"]

    Step2[Step 2: Prepare Release]
    Step2_Details["$ echo '0.6.0' > VERSION<br/>$ vim CHANGELOG.md  # Move [Unreleased] → [0.6.0]<br/>$ git commit -m 'chore: release version 0.6.0'<br/>$ git push"]

    Step3[Step 3: Create and Merge PR]
    Step3_Details["$ gh pr create --fill<br/># CI runs, review, merge to main"]

    Trigger[VERSION changed on main → triggers workflow]

    Step4[Step 4: Workflow Creates Release]
    Step4_Details["1. Read VERSION: 0.6.0<br/>2. Tag does not exist → proceed<br/>3. Extract notes from CHANGELOG.md<br/>4. Create tag: v0.6.0<br/>5. Create GitHub Release"]

    Step1 --> Step1_Details
    Step1_Details --> Step2
    Step2 --> Step2_Details
    Step2_Details --> Step3
    Step3 --> Step3_Details
    Step3_Details --> Trigger
    Trigger --> Step4
    Step4 --> Step4_Details

    style Step1 fill:#e3f2fd
    style Step2 fill:#f3e5f5
    style Step3 fill:#fff9c4
    style Trigger fill:#fff3e0
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
    VERSION --> |Updated by| Dev[Developer in PR]
    VERSION --> |Read by| RW[Release workflow]
    VERSION --> |Read by| Users[Users: quick version check]

    style VERSION fill:#e3f2fd
    style Dev fill:#f3e5f5
    style RW fill:#fff3e0
    style Users fill:#e8f5e9
```

### CHANGELOG.md

```mermaid
graph TD
    CHANGELOG[CHANGELOG.md]
    CHANGELOG --> |Updated by| Dev[Developer in PR]
    CHANGELOG --> |Read by| RW[Release workflow: extract notes]
    CHANGELOG --> |Read by| Users[Users: change history]

    style CHANGELOG fill:#f3e5f5
    style Dev fill:#e3f2fd
    style RW fill:#fff3e0
    style Users fill:#e8f5e9
```

### Release Workflow

```mermaid
graph TD
    WORKFLOW[.github/workflows/release.yml]
    WORKFLOW --> |Triggered by| Push[Push to main with VERSION change]
    WORKFLOW --> |Reads| Files[VERSION, CHANGELOG.md]
    WORKFLOW --> |Creates| Outputs[Git tag, GitHub Release]
    WORKFLOW --> |Requires| Token[GITHUB_TOKEN: automatic]

    style WORKFLOW fill:#e8f5e9
    style Push fill:#fff9c4
    style Files fill:#e3f2fd
    style Outputs fill:#fce4ec
    style Token fill:#fff3e0
```

---

## Configuration

### Release Workflow Configuration

**File**: `.github/workflows/release.yml`

**Key settings**:
```yaml
on:
  push:
    branches:
      - main
    paths:
      - VERSION            # Only triggers when VERSION changes
  workflow_dispatch:       # Manual trigger

permissions:
  contents: write          # Required for creating tags and releases
```

### Branch Protection Compatibility

The workflow works with branch protection because:
- It never pushes **commits** to `main` (which would require a PR)
- It only pushes **tags** (`refs/tags/*`), which are not restricted by the pull request rule
- The `GITHUB_TOKEN` has `contents: write` permission, which is sufficient for tags

---

## Error Handling

### Common Issues

| Error | Cause | Solution |
|-------|-------|----------|
| Tag already exists | Version already released | Delete tag or bump VERSION to next version |
| Empty release notes | No matching section in CHANGELOG | Add a `## [x.y.z] - date` section matching VERSION |
| Workflow not triggered | VERSION not in changed files | Ensure VERSION was modified in the merged PR |
| CI tests failed | Code issues | Fix tests, update PR, re-merge |

### Recovery Procedures

**Delete a failed release**:
```bash
gh release delete v0.6.0 --yes
git tag -d v0.6.0
git push origin :refs/tags/v0.6.0

# Re-trigger
gh workflow run release.yml --ref main
```

---

## Future: Ansible Galaxy Integration

When ready to publish to Ansible Galaxy, add a publishing step to the release workflow:

```yaml
- name: Import role to Ansible Galaxy
  run: >-
    ansible-galaxy role import
    --api-key ${{ secrets.GALAXY_API_KEY }}
    aopdal ansible-role-aruba-cx-switch
```

This uses `role import` (not `collection publish`) because this is an Ansible Role.

---

## See Also

- [Release Process — Full Guide](RELEASE_PROCESS.md)
- [Release Quick Reference](RELEASE_QUICK_REFERENCE.md)
- [CHANGELOG.md](../CHANGELOG.md)
- [Contributing Guide](CONTRIBUTING.md)
- [Semantic Versioning](https://semver.org/)
- [Keep a Changelog](https://keepachangelog.com/)
