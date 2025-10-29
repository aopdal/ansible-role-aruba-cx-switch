# Documentation Sync Workflow

## Overview

The project uses **`make docs-sync`** to maintain consistency between `README.md` (root) and `docs/index.md` (MkDocs).

## How It Works

```bash
make docs-sync
```

**What happens:**

1. Copies `README.md` → `docs/index.md`
2. Fixes links automatically:

    - Removes `docs/` prefix: `docs/FILE.md` → `FILE.md`
    - Adds `../` to root paths: `tests/` → `../tests/`

## ⚠️ Important: Edit README.md First!

**Always edit the root `README.md` file, not `docs/index.md` directly!**

```
✅ CORRECT:
  1. Edit README.md
  2. Run make docs-sync
  3. Commit both files

❌ WRONG:
  1. Edit docs/index.md directly
  2. Run make docs-sync (overwrites your changes!)
```

## Link Format in README.md

When adding documentation links to `README.md`, use this format:

```markdown
### Configuration Guides

- **[docs/BASE_CONFIGURATION.md](docs/BASE_CONFIGURATION.md)** - Description
- **[docs/VLAN_CHANGE_IDENTIFICATION_WORKFLOW.md](docs/VLAN_CHANGE_IDENTIFICATION_WORKFLOW.md)** - Description
```

**After sync**, `docs/index.md` will have:

```markdown
### Configuration Guides

- **[docs/BASE_CONFIGURATION.md](BASE_CONFIGURATION.md)** - Description
- **[docs/VLAN_CHANGE_IDENTIFICATION_WORKFLOW.md](VLAN_CHANGE_IDENTIFICATION_WORKFLOW.md)** - Description
```

The `docs/` prefix is automatically removed because `index.md` is already inside the `docs/` directory.

## When to Run docs-sync

Run `make docs-sync` whenever you:

- ✅ Update `README.md` with new documentation links
- ✅ Change documentation structure in `README.md`
- ✅ Add new features to the role description
- ✅ Update badges or metadata in `README.md`

## Verification After Sync

Always verify the sync worked correctly:

```bash
# 1. Run sync
make docs-sync

# 2. Check the changes
git diff docs/index.md

# 3. Verify links work
make docs-serve
# Visit http://127.0.0.1:8000 and test links

# 4. Build documentation
make docs-build
```

## What's Safe to Edit Directly

### Edit `README.md` only:

- ✅ Documentation links
- ✅ Feature descriptions
- ✅ Getting started instructions
- ✅ Badges and metadata

### Edit other docs directly:

- ✅ `docs/README.md` - Documentation index
- ✅ `docs/VLAN_*.md` - VLAN guides
- ✅ `docs/BGP_*.md` - BGP guides
- ✅ Any other `docs/*.md` files (except `docs/index.md`)

### NEVER edit directly:

- ❌ `docs/index.md` - Always synced from `README.md`

## VLAN Documentation Example

When we added VLAN documentation, we:

1. **Added to `README.md`:**
   ```markdown
   ### Configuration Guides
   - **[docs/VLAN_CHANGE_IDENTIFICATION_WORKFLOW.md](docs/VLAN_CHANGE_IDENTIFICATION_WORKFLOW.md)** - VLAN management workflow
   ```

2. **Ran sync:**
   ```bash
   make docs-sync
   ```

3. **Result in `docs/index.md`:**
   ```markdown
   ### Configuration Guides
   - **[docs/VLAN_CHANGE_IDENTIFICATION_WORKFLOW.md](VLAN_CHANGE_IDENTIFICATION_WORKFLOW.md)** - VLAN management workflow
   ```

4. **Also updated separately:**
   - `docs/README.md` - Added full VLAN section
   - `mkdocs.yml` - Added VLAN navigation

## Makefile Target Details

```makefile
docs-sync: ## Sync README.md to docs/index.md
	@cp README.md docs/index.md
	@sed -i 's|(docs/|(|g' docs/index.md
	@sed -i 's|(tests/|(../tests/|g' docs/index.md
	@sed -i 's|(defaults/|(../defaults/|g' docs/index.md
	@sed -i 's|(testing-scripts/|(../testing-scripts/|g' docs/index.md
```

**sed commands:**

- `s|(docs/|(|g` - Remove `docs/` prefix from links
- `s|(tests/|(../tests/|g` - Add `../` to root directory links
- Similar for `defaults/` and `testing-scripts/`

## Troubleshooting

### Problem: Links broken after sync

**Cause:** Link format in `README.md` is incorrect

**Solution:**
```markdown
# ❌ Wrong - will break after sync
[File](FILE.md)

# ✅ Correct - will work after sync
[File](docs/FILE.md)
```

### Problem: Changes to docs/index.md lost

**Cause:** Edited `docs/index.md` directly, then ran `make docs-sync`

**Solution:**

1. Find your changes in git history: `git log -p docs/index.md`
2. Apply them to `README.md` instead
3. Run `make docs-sync` again

### Problem: Sync overwrites custom formatting

**Cause:** `docs/index.md` should be identical to `README.md` (with link fixes)

**Solution:**

- Keep custom content in separate files (e.g., `docs/README.md`)
- `docs/index.md` is only for the role's main README

## Best Practices

1. **Always sync before committing:**
   ```bash
   make docs-sync
   git add README.md docs/index.md
   git commit -m "docs: add VLAN documentation"
   ```

2. **Document in the right place:**

   - Role overview → `README.md` (syncs to `docs/index.md`)
   - Documentation index → `docs/README.md`
   - Feature guides → `docs/FEATURE_*.md`

3. **Test after sync:**
   ```bash
   make docs-sync
   make docs-serve
   # Test all links manually
   ```

4. **Keep both files in commits:**
   When editing `README.md`, always commit both files:
   ```bash
   git add README.md docs/index.md
   ```

## Related Files

- `Makefile` - Contains `docs-sync` target
- `README.md` - Source file (edit this)
- `docs/index.md` - Generated file (don't edit)
- `docs/README.md` - Documentation index (safe to edit)
- `mkdocs.yml` - MkDocs configuration

## Summary

✅ **DO:** Edit `README.md` → Run `make docs-sync` → Commit both files
❌ **DON'T:** Edit `docs/index.md` directly (will be overwritten)

The sync ensures the role's README and documentation site homepage stay in sync automatically! 🔄
