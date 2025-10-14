# Documentation Sync Note

## README.md and docs/index.md

**Important:** The root `README.md` and `docs/index.md` should be kept in sync.

### Why Two Files?

- **`README.md`** (root) - Displayed on GitHub repository page, Ansible Galaxy, etc.
- **`docs/index.md`** (docs folder) - Used as home page for MkDocs documentation site

### Keeping Them in Sync

When updating the README:

```bash
# Copy README to docs/index.md
cp README.md docs/index.md
```

Or use the Makefile target:

```bash
make sync-readme
```

### Why Not a Symlink?

Symlinks can cause issues with:
- Git on Windows
- MkDocs build process
- GitHub Pages deployment

So we use a copy instead. Just remember to sync when README changes!

### Automation Option

Consider adding a pre-commit hook or CI check to ensure they stay in sync:

```yaml
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: sync-readme
      name: Sync README to docs/index.md
      entry: bash -c 'cp README.md docs/index.md'
      language: system
      files: ^README\.md$
```
