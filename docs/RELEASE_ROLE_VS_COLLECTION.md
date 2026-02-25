# Ansible Role vs Collection — Release System

Explanation of why this project uses a Role-based release system instead of a Collection-based one.

## This Project is an Ansible Role

This project is an Ansible **Role**, not a Collection. This distinction affects how versioning, metadata, and publishing work.

### Key Differences

| Feature | Collection | Role (This Project) |
|---------|-----------|---------------------|
| **Metadata file** | `galaxy.yml` | `meta/main.yml` |
| **Version storage** | `galaxy.yml` | `VERSION` file |
| **Structure** | `namespace.collection_name` | `author.role_name` |
| **Publish command** | `collection publish` | `role import` |
| **Install command** | `collection install` | `role install` |
| **Can contain roles** | Yes (multiple) | Is a single role |

---

## Release System Components

### 1. VERSION File

**Purpose**: Single source of truth for current version

**Location**: `/VERSION`

**Format**: Plain text, single line

```
0.5.0
```

**Updated by**: Developer in a pull request before merging to `main`.

### 2. meta/main.yml

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

**Note**: Does NOT contain version — that's handled by the `VERSION` file and Git tags.

### 3. CHANGELOG.md

**Purpose**: Human-readable change history

**Location**: `/CHANGELOG.md`

**Format**: [Keep a Changelog](https://keepachangelog.com/)

### 4. Release Workflow

**File**: `.github/workflows/release.yml`

**What it does**:
- Reads `VERSION` file (does not modify it)
- Extracts release notes from `CHANGELOG.md`
- Creates Git tag and GitHub Release
- Does **not** commit or push to `main`

---

## How a Release Works

```
1. Developer updates CHANGELOG.md and VERSION in a PR
         ↓
2. PR is reviewed, CI passes, merged to main
         ↓
3. Release workflow triggers (VERSION file changed):
   - Read VERSION: 0.6.0
   - Check tag v0.6.0 does not exist
   - Extract release notes from CHANGELOG.md
   - Create tag: v0.6.0
   - Create GitHub Release
         ↓
4. Release is available:
   - GitHub Release with notes
   - Git tag v0.6.0
   - No files modified on main
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

### Step 2: Add Galaxy API Key

1. Generate key at https://galaxy.ansible.com/me/preferences
2. Add to GitHub: Settings → Secrets → Actions → `GALAXY_API_KEY`

### Step 3: Add Publishing Step to Workflow

```yaml
- name: Import role to Ansible Galaxy
  run: >-
    ansible-galaxy role import
    --api-key ${{ secrets.GALAXY_API_KEY }}
    aopdal ansible-role-aruba-cx-switch
```

**Note**: Uses `role import`, NOT `collection publish`.

### Installing the Role

```bash
# Install from Galaxy
ansible-galaxy role install aopdal.aruba_cx_switch

# Install specific version
ansible-galaxy role install aopdal.aruba_cx_switch,v0.6.0

# In requirements.yml
roles:
  - name: aopdal.aruba_cx_switch
    version: 0.6.0
```

---

## Why .ansible/ Directory Exists

The `.ansible/` directory is created by normal Ansible operations (running `ansible-lint`, installing collection dependencies, testing). It should be in `.gitignore`.

---

## Verification

```bash
# Confirm this is a Role (not a Collection)
ls meta/main.yml              # ✅ Role metadata exists
ls galaxy.yml 2>/dev/null     # ❌ Should NOT exist
ls VERSION                    # ✅ Version file exists

# Check version
cat VERSION

# Check latest tag
git describe --tags --abbrev=0
```

---

## See Also

- [Ansible Roles Documentation](https://docs.ansible.com/ansible/latest/user_guide/playbooks_reuse_roles.html)
- [Ansible Collections Documentation](https://docs.ansible.com/ansible/latest/user_guide/collections_using.html)
- [Galaxy Role Import](https://galaxy.ansible.com/docs/contributing/importing.html)
- [Release Process](RELEASE_PROCESS.md)
- [Release Integration](RELEASE_INTEGRATION.md)
