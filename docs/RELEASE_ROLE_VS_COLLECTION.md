# Ansible Role vs Collection - Release System

Explanation of the release system for Ansible Roles (not Collections).

## Issue Discovered

When running `pre-commit`, a `galaxy.yml` file was created (for Ansible Collections), but this project is an Ansible **Role**, not a Collection. This caused confusion because:

1. **Ansible Collections** use `galaxy.yml` for metadata and versioning
2. **Ansible Roles** use `meta/main.yml` for metadata

The `.ansible/collections/ansible_collections` directory was created by the build process, which is normal when testing with collections installed.

## Solution

Updated the release system to work correctly for Ansible Roles:

### ❌ Before (Incorrect - Collection Approach)

```
galaxy.yml                  # Collections use this
  namespace: aopdal
  name: aruba_cx_switch
  version: 0.1.0
  ...
```

### ✅ After (Correct - Role Approach)

```
VERSION                     # Simple version file
0.1.0

meta/main.yml              # Role metadata (existing)
galaxy_info:
  role_name: aruba_cx_switch
  namespace: aopdal
  ...
```

---

## Key Differences

### Ansible Collections

**Purpose**: Package multiple plugins, modules, roles together

**Structure**:
```
namespace/
  collection_name/
    galaxy.yml              ← Version here
    plugins/
    roles/
    playbooks/
```

**Galaxy Metadata**: `galaxy.yml`

**Publishing**: `ansible-galaxy collection publish`

**Example**: `arubanetworks.aoscx` (Collection)

### Ansible Roles (This Project)

**Purpose**: Reusable task automation for specific purpose

**Structure**:
```
ansible-role-name/
  meta/main.yml            ← Galaxy metadata here
  tasks/
  handlers/
  defaults/
  vars/
```

**Galaxy Metadata**: `meta/main.yml`

**Version Storage**: Custom (we use `VERSION` file)

**Publishing**: `ansible-galaxy role import`

**Example**: `aopdal.aruba_cx_switch` (Role)

---

## Release System Components

### 1. VERSION File (New)

**Purpose**: Single source of truth for version

**Location**: `/VERSION`

**Format**: Plain text, single line
```
0.1.0
```

**Why**: Simple, clear, works for roles

### 2. meta/main.yml (Existing)

**Purpose**: Ansible Galaxy role metadata

**Location**: `/meta/main.yml`

**Content**:
```yaml
galaxy_info:
  role_name: aruba_cx_switch
  namespace: aopdal
  author: Arne Opdal
  description: ...
  min_ansible_version: "2.12"
  ...
```

**Note**: Does NOT contain version (handled by `VERSION` file)

### 3. CHANGELOG.md (Existing)

**Purpose**: Human-readable change history

**Location**: `/CHANGELOG.md`

**Format**: Keep a Changelog

### 4. Release Workflow (Updated)

**File**: `.github/workflows/release.yml`

**Changes**:
- ✅ Reads from `VERSION` file (not `galaxy.yml`)
- ✅ Updates `VERSION` file (not `galaxy.yml`)
- ✅ Creates Git tags and GitHub releases
- ❌ Does NOT create `galaxy.yml`

---

## How Release Works for Roles

```
1. Developer updates CHANGELOG.md
         ↓
2. Merge to main
         ↓
3. Release workflow:
   - Read VERSION: 0.1.0
   - Increment: 0.1.0 → 0.1.1
   - Update VERSION file
   - Update CHANGELOG.md
   - Create tag: v0.1.1
   - Create GitHub Release
         ↓
4. When ready for Galaxy:
   - Use meta/main.yml for role metadata
   - VERSION is for internal tracking only
   - Import with: ansible-galaxy role import
```

---

## Publishing to Ansible Galaxy (Future)

When ready to publish this **Role** to Galaxy:

### Step 1: Verify meta/main.yml

```yaml
# meta/main.yml
galaxy_info:
  role_name: aruba_cx_switch
  namespace: aopdal
  # ... other metadata
```

### Step 2: Enable Galaxy Publishing

In `.github/workflows/ci.yml`, uncomment:

```yaml
release:
  name: Release to Ansible Galaxy
  ...
  - name: Trigger a new import on Ansible Galaxy
    run: >-
      ansible-galaxy role import
      --api-key ${{ secrets.GALAXY_API_KEY }}
      $(echo ${{ github.repository }} | cut -d/ -f1)
      $(echo ${{ github.repository }} | cut -d/ -f2)
```

**Note**: Uses `role import`, NOT `collection publish`

### Step 3: Manual Publishing

```bash
# Login to Galaxy
ansible-galaxy login

# Import role (NOT publish collection)
ansible-galaxy role import aopdal ansible-role-aruba-cx-switch

# Install role
ansible-galaxy role install aopdal.aruba_cx_switch
```

---

## Comparison Table

| Feature | Collection | Role (This Project) |
|---------|-----------|---------------------|
| **Metadata File** | `galaxy.yml` | `meta/main.yml` |
| **Version Storage** | `galaxy.yml` | `VERSION` file |
| **Structure** | namespace/name | author.role_name |
| **Publish Command** | `collection publish` | `role import` |
| **Install Command** | `collection install` | `role install` |
| **Can Contain Roles** | Yes (multiple) | Is a single role |
| **This Project** | ❌ No | ✅ Yes |

---

## What Gets Published to Galaxy

### For Ansible Roles (This Project)

**Metadata from**: `meta/main.yml`

**Version from**: Git tags (e.g., `v0.1.1`)

**Content**: Entire repository

**Galaxy URL**: `https://galaxy.ansible.com/aopdal/aruba_cx_switch`

**Install**: `ansible-galaxy role install aopdal.aruba_cx_switch`

**Requirements.yml**:
```yaml
roles:
  - name: aopdal.aruba_cx_switch
    version: 0.1.1
```

---

## Why .ansible/ Directory Exists

The `.ansible/` directory is created by:

1. **Pre-commit** - When running `ansible-lint`
2. **Testing** - When installing collection dependencies
3. **Development** - Normal Ansible behavior

**Structure**:
```
.ansible/
├── collections/
│   └── ansible_collections/    # Installed collections
│       ├── arubanetworks/
│       │   └── aoscx/
│       └── netbox/
│           └── netbox/
├── modules/                     # Cached modules
└── roles/                       # Cached roles
```

**Note**: This is normal and should be in `.gitignore`

---

## Verification

### Check Project Type

```bash
# Ansible Role indicators:
ls meta/main.yml              # ✅ Role metadata exists
ls galaxy.yml 2>/dev/null     # ❌ Should NOT exist (we removed it)
ls VERSION                    # ✅ Our version file exists

# Ansible Collection indicators:
ls galaxy.yml 2>/dev/null     # ❌ Should NOT exist for roles
ls plugins/ 2>/dev/null       # ❌ Collections have this
```

### Verify Release System

```bash
# Check version storage
cat VERSION                   # Should show: 0.1.0

# Check workflow
grep "VERSION" .github/workflows/release.yml  # ✅ Should reference VERSION
grep "galaxy.yml" .github/workflows/release.yml  # ❌ Should NOT exist

# Check documentation
grep -r "galaxy.yml" docs/ || echo "Correctly uses VERSION file"
```

---

## Summary

| Component | Collections | Roles (This Project) |
|-----------|------------|----------------------|
| **galaxy.yml** | ✅ Required | ❌ Removed |
| **meta/main.yml** | Optional | ✅ Required |
| **VERSION file** | Not used | ✅ Used for versioning |
| **Release workflow** | Updates galaxy.yml | ✅ Updates VERSION |
| **Publishing** | `collection publish` | `role import` |

**Conclusion**: This project is an Ansible **Role**, using `VERSION` file for version tracking and `meta/main.yml` for Galaxy metadata. The `galaxy.yml` file was incorrectly created and has been removed.

---

## See Also

- [Ansible Roles Documentation](https://docs.ansible.com/ansible/latest/user_guide/playbooks_reuse_roles.html)
- [Ansible Collections Documentation](https://docs.ansible.com/ansible/latest/user_guide/collections_using.html)
- [Galaxy Role Import](https://galaxy.ansible.com/docs/contributing/importing.html)
- [Release Process](RELEASE_PROCESS.md)
- [Release Integration](RELEASE_INTEGRATION.md)
