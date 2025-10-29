# .ansible/ Directory - Cache and Temporary Files

Explanation of the `.ansible/` directory created during development.

## What Is It?

The `.ansible/` directory is a **cache directory** created by various Ansible tools during development, testing, and linting. It's temporary and should never be committed to git.

## When Is It Created?

The `.ansible/` directory is automatically created by:

1. **ansible-lint** (via pre-commit hooks)

   - Caches module information for faster linting
   - Creates `.ansible/modules/`

2. **ansible-galaxy**

   - Caches installed collections
   - Creates `.ansible/collections/`

3. **Ansible playbook runs**

   - Caches roles during execution
   - Creates `.ansible/roles/`

## Directory Structure

```
.ansible/
├── collections/          # Cached Ansible collections
│   └── ansible_collections/
│       ├── arubanetworks/
│       │   └── aoscx/
│       └── netbox/
│           └── netbox/
├── modules/             # Cached module metadata (ansible-lint)
├── roles/               # Cached roles
└── .lock               # Lock file
```

## Why Does It Exist?

### Performance Optimization

Ansible tools cache information locally to improve performance:

- **ansible-lint**: Caches module documentation to avoid re-parsing on every run
- **ansible-galaxy**: Stores downloaded collections/roles locally
- **ansible-playbook**: Caches role dependencies

### Created By Pre-Commit

When you run `git commit`, the pre-commit hooks execute:

```bash
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: ansible-lint
      entry: ansible-lint
      # This creates .ansible/modules/
```

**This is completely normal and expected behavior.**

## Is It Safe?

**Yes, absolutely!** The `.ansible/` directory:

- ✅ Is generated automatically
- ✅ Is safe to delete (will be recreated)
- ✅ Is already in `.gitignore`
- ✅ Contains only cached/temporary data
- ❌ Should NOT be committed to git

## Verification

### Check .gitignore

```bash
# Verify it's ignored
grep "^.ansible/" .gitignore
# Output: .ansible/

# Verify git isn't tracking it
git status .ansible/
# Output: (should show nothing or "not tracked")
```

### Contents Are Safe

```bash
# Check what's inside (example)
ls -la .ansible/

# modules/ - Cached module info
ls .ansible/modules/

# collections/ - Downloaded collections
ls .ansible/collections/ansible_collections/
```

## Can I Delete It?

**Yes!** You can safely delete it anytime:

```bash
# Delete the entire directory
rm -rf .ansible/

# It will be recreated next time you run:
# - git commit (pre-commit hooks)
# - ansible-lint
# - ansible-playbook
# - ansible-galaxy install
```

## Should I Commit It?

**No!** The `.ansible/` directory should **never** be committed because:

1. **Large size** - Contains full collection/role copies
2. **Platform-specific** - May differ between systems
3. **Temporary** - Gets regenerated automatically
4. **No value** - Other users will have their own cache
5. **Already ignored** - `.gitignore` prevents accidental commits

## Troubleshooting

### .ansible/ Not Being Ignored

If git is trying to track `.ansible/`:

```bash
# Check .gitignore
cat .gitignore | grep ansible

# Should show:
# .ansible/

# If not, add it:
echo ".ansible/" >> .gitignore
git add .gitignore
git commit -m "chore: ensure .ansible/ is ignored"
```

### .ansible/ Already Committed (Oops!)

If you accidentally committed `.ansible/`:

```bash
# Remove from git (but keep locally)
git rm -r --cached .ansible/

# Commit the removal
git commit -m "chore: remove .ansible/ cache directory"

# Ensure .gitignore has it
echo ".ansible/" >> .gitignore
git add .gitignore
git commit -m "chore: ignore .ansible/ directory"
```

### Large .ansible/ Directory

If `.ansible/` is taking up too much space:

```bash
# Check size
du -sh .ansible/

# Clean it up
rm -rf .ansible/

# Or clean specific parts
rm -rf .ansible/collections/  # Remove cached collections
rm -rf .ansible/modules/      # Remove cached modules
rm -rf .ansible/roles/        # Remove cached roles
```

## Related Caching

Ansible uses several cache directories:

| Directory | Purpose | Should Ignore? |
|-----------|---------|----------------|
| `.ansible/` | Local cache | ✅ Yes |
| `~/.ansible/` | User cache | N/A (outside repo) |
| `.molecule/` | Molecule testing | ✅ Yes |
| `.pytest_cache/` | Pytest cache | ✅ Yes |
| `.cache/` | General cache | ✅ Yes |

All are already in `.gitignore`.

## Summary

**Question**: Is `.ansible/` created by `ansible-lint` correct?

**Answer**: **Yes!** This is completely normal and expected behavior.

**What it is**:

- Cache directory for Ansible tools
- Created by ansible-lint, ansible-galaxy, etc.
- Contains temporary/cached data

**What to do**:

- ✅ Nothing! It's already in `.gitignore`
- ✅ Safe to delete anytime (will be recreated)
- ❌ Don't commit it to git
- ❌ Don't worry about it

**When you see it**:

- After running `git commit` (pre-commit hooks)
- After running `ansible-lint`
- After running `ansible-galaxy install`
- After running Ansible playbooks

**Bottom line**: Ignore it (literally - it's in `.gitignore`). This is normal Ansible behavior.

## See Also

- [Ansible Configuration](https://docs.ansible.com/ansible/latest/reference_appendices/config.html)
- [ansible-lint Documentation](https://ansible-lint.readthedocs.io/)
- [.gitignore](../.gitignore) - Already configured correctly
