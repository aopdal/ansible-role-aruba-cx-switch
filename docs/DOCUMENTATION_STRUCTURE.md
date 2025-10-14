# Documentation Structure

## Overview

All documentation is organized in the `docs/` folder following MkDocs conventions.

## File Organization

```
ansible-role-aruba-cx-switch/
├── README.md                    ← Repository README (GitHub, Ansible Galaxy)
├── mkdocs.yml                   ← MkDocs configuration
└── docs/                        ← ALL documentation files
    ├── index.md                 ← Copy of README.md for MkDocs home page
    ├── CHANGELOG.md             ← Version history
    ├── CONTRIBUTING.md          ← Contribution guidelines
    ├── QUICKSTART.md
    ├── NETBOX_INTEGRATION.md
    ├── BGP_HYBRID_CONFIGURATION.md
    ├── EVPN_VXLAN_CONFIGURATION.md
    └── ... (all other docs)
```

## Why This Structure?

### ✅ Standard MkDocs Convention

MkDocs expects all documentation in `docs/` folder:
- Easier to configure
- No path confusion
- Clear separation of docs from code

### ✅ Clean Repository Root

Only essential files at root:
- `README.md` - For GitHub/Ansible Galaxy
- `mkdocs.yml` - MkDocs configuration
- Role files (tasks/, defaults/, etc.)

### ✅ Single Source for Documentation

All docs in one place:
- Easy to find
- Easy to maintain
- Easy to navigate

## Special Files

### README.md (Root) vs docs/index.md

**Two copies of the same content:**

| File | Purpose | Displayed On |
|------|---------|--------------|
| `README.md` | Repository README | GitHub, Ansible Galaxy, git clones |
| `docs/index.md` | MkDocs home page | Documentation website |

**Why both?**
- GitHub looks for `README.md` at root
- MkDocs looks in `docs/` folder
- They should contain the same content

**Keeping in sync:**
```bash
# Manual sync
cp README.md docs/index.md

# Or use Makefile
make docs-sync
```

### CHANGELOG.md and CONTRIBUTING.md

**Moved to docs/ folder:**
- Previously at root (common for roles)
- Now in `docs/` (MkDocs convention)
- Still accessible via MkDocs navigation

**Benefits:**
- Consistent structure
- No warnings from MkDocs
- Easier to link between docs

## MkDocs Configuration

### docs_dir Setting

```yaml
# mkdocs.yml
docs_dir: docs  # All documentation in docs/ folder
```

### Navigation Paths

All paths are **relative to docs/ folder**:

```yaml
nav:
  - Home: index.md                           # docs/index.md
  - Getting Started:
      - Quick Start: QUICKSTART.md           # docs/QUICKSTART.md
  - NetBox Integration:
      - Integration Reference: NETBOX_INTEGRATION.md  # docs/NETBOX_INTEGRATION.md
  - Contributing:
      - Guide: CONTRIBUTING.md               # docs/CONTRIBUTING.md
      - Changelog: CHANGELOG.md              # docs/CHANGELOG.md
```

**Note:** No `docs/` prefix needed in paths!

## Linking Between Documents

### In Markdown Files

Links are relative to current file location:

```markdown
<!-- In docs/BGP_HYBRID_CONFIGURATION.md -->
See [NetBox Integration](NETBOX_INTEGRATION.md) for setup.

<!-- In docs/EVPN_VXLAN_CONFIGURATION.md -->
See [BGP Configuration](BGP_HYBRID_CONFIGURATION.md) for BGP setup.
```

### In MkDocs Navigation

Use filename only (relative to docs/):

```yaml
- BGP Setup: BGP_HYBRID_CONFIGURATION.md
```

## Adding New Documentation

### 1. Create File in docs/

```bash
cd docs/
vim MY_NEW_FEATURE.md
```

### 2. Add to mkdocs.yml Navigation

```yaml
nav:
  - Configuration:
      - My New Feature: MY_NEW_FEATURE.md
```

### 3. Link from Other Docs

```markdown
See [My New Feature](MY_NEW_FEATURE.md) for details.
```

## Directory Structure Benefits

### Before (Mixed Structure)

```
ansible-role-aruba-cx-switch/
├── README.md
├── CHANGELOG.md              ← At root
├── CONTRIBUTING.md           ← At root
├── mkdocs.yml
├── docs/
│   ├── QUICKSTART.md
│   ├── NETBOX_INTEGRATION.md
│   └── BGP_HYBRID_CONFIGURATION.md
└── tasks/
```

**Issues:**
- Mixed locations confusing
- MkDocs warnings for root files
- Harder to manage navigation

### After (All in docs/)

```
ansible-role-aruba-cx-switch/
├── README.md                 ← Only README at root
├── mkdocs.yml
├── docs/                     ← ALL docs here
│   ├── index.md              ← Copy of README
│   ├── CHANGELOG.md          ← Moved from root
│   ├── CONTRIBUTING.md       ← Moved from root
│   ├── QUICKSTART.md
│   ├── NETBOX_INTEGRATION.md
│   └── BGP_HYBRID_CONFIGURATION.md
└── tasks/
```

**Benefits:**
- ✅ All docs in one place
- ✅ No MkDocs warnings
- ✅ Standard convention
- ✅ Clean repository root

## Maintenance Tasks

### Sync README to docs/index.md

When you update `README.md`:

```bash
# Option 1: Makefile
make docs-sync

# Option 2: Manual
cp README.md docs/index.md

# Option 3: Git commit hook (automated)
# See docs/README_SYNC.md for setup
```

### Verify Documentation Structure

```bash
# Check for docs outside docs/ folder
find . -maxdepth 1 -name "*.md" -not -name "README.md"

# Should only show README.md
```

### Test MkDocs Build

```bash
# Build documentation
make docs-build

# Check for warnings
mkdocs build --strict

# Serve locally to verify
make docs-serve
```

## Migration Notes

### Files Moved

✅ `CHANGELOG.md` - Root → `docs/`
✅ `CONTRIBUTING.md` - Root → `docs/`
✅ `README.md` - Copied to `docs/index.md`

### mkdocs.yml Updates

✅ Added `docs_dir: docs`
✅ Changed `Home: README.md` to `Home: index.md`
✅ Updated all nav paths (removed `docs/` prefix)
✅ Updated `CONTRIBUTING.md` and `CHANGELOG.md` paths

### Makefile Updates

✅ Added `docs-sync` target for README synchronization

## Best Practices

### ✅ DO

- Keep all documentation in `docs/` folder
- Use relative links between docs
- Sync README.md to docs/index.md when updated
- Use descriptive filenames (e.g., `BGP_HYBRID_CONFIGURATION.md`)
- Add new docs to mkdocs.yml navigation

### ❌ DON'T

- Create documentation files at repository root
- Use absolute paths in links
- Forget to sync README.md to docs/index.md
- Use `docs/` prefix in mkdocs.yml nav paths
- Leave docs out of navigation

## Quick Reference

| Task | Command |
|------|---------|
| **Sync README** | `make docs-sync` |
| **View docs locally** | `make docs-serve` |
| **Build docs** | `make docs-build` |
| **Add new doc** | 1. Create in `docs/`<br>2. Add to `mkdocs.yml` nav |
| **Link between docs** | Use relative path: `[Text](OTHER_DOC.md)` |

## Related Documentation

- [DOCUMENTATION_SITE.md](DOCUMENTATION_SITE.md) - MkDocs usage guide
- [README_SYNC.md](README_SYNC.md) - README synchronization details
- [DOCUMENTATION_SITE_SETUP.md](DOCUMENTATION_SITE_SETUP.md) - Initial setup notes

---

**TL;DR:** All documentation is now in `docs/` folder following MkDocs conventions. Only `README.md` stays at root for GitHub/Ansible Galaxy. Run `make docs-sync` when README changes.
