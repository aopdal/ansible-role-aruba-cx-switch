# Documentation Site

This role uses **MkDocs with Material theme** to generate a beautiful documentation site.

## Why MkDocs Instead of antsibull-docs?

While `antsibull-docs` is excellent for Ansible Collections (modules, plugins), this role benefits more from MkDocs because:

- ✅ **Rich narrative docs** - EVPN/VXLAN guides, BGP hybrid setup, migration guides0
- ✅ **Flexible organization** - Can structure docs to tell a story
- ✅ **Beautiful presentation** - Material theme is stunning
- ✅ **Easy maintenance** - All your existing `.md` files work directly
- ✅ **Code examples** - Excellent syntax highlighting for YAML/Jinja2

## Local Development

### Install dependencies

```bash
pip install -r requirements-docs.txt
```

### Serve locally

```bash
mkdocs serve
```

Visit http://127.0.0.1:8000 to see the live preview.

### Build static site

```bash
mkdocs build
```

Output will be in `site/` directory.

## Publishing

### For Private Repositories (Current Setup)

**GitHub Pages is NOT available** for private repos on the free plan. Instead, use local documentation:

```bash
# Live preview during development
make docs-serve
# Visit http://127.0.0.1:8000

# Build static site for local/internal hosting
make docs-build
# Output in site/ directory - can be hosted on internal web server
```

### For Public Repositories or Paid Plans

When the repo becomes public or you upgrade to a paid GitHub plan, documentation can be **automatically published** to GitHub Pages:

1. **Uncomment** the workflow in `.github/workflows/docs.yml`
2. **Enable GitHub Pages** in repo settings:
    - Go to Settings → Pages
    - Source: Deploy from a branch
    - Branch: `gh-pages` / (root)
    - Save
3. **Push changes** to trigger deployment
4. Site will be at: `https://aopdal.github.io/ansible-role-aruba-cx-switch`

The workflow will automatically deploy when you push changes to:

- `docs/**`
- `README.md`
- `CONTRIBUTING.md`
- `CHANGELOG.md`
- `mkdocs.yml`

## Configuration

### Site Structure

Configured in `mkdocs.yml`:

```yaml
nav:
  - Home: README.md
  - Getting Started:
    - Quick Start: docs/QUICKSTART.md
    - Setup Guide: docs/SETUP_COMPLETE.md
  - Configuration:
    - EVPN & VXLAN:
      - Overview: docs/EVPN_VXLAN_CONFIGURATION.md
      - Configuration Modes: docs/EVPN_VXLAN_MODES.md
      - Cleanup Process: docs/EVPN_VXLAN_CLEANUP_SUMMARY.md
    - BGP:
      - Configuration Guide: docs/BGP_CONFIGURATION.md
```

### Features Enabled

- **Navigation tabs** - Top-level sections in tabs
- **Search** - Full-text search with suggestions
- **Dark mode** - Automatic theme switching
- **Code copy** - Click to copy code blocks
- **Git info** - Shows when pages were last updated
- **Responsive** - Works great on mobile

## Writing Documentation

### Standard Markdown

Just write normal Markdown! All your existing docs work.

### Admonitions

```markdown
!!! note "This is a note"
    Additional information here

!!! warning "Important"
    Be careful with this setting

!!! tip "Pro Tip"
    Use idempotent mode for production
```

### Code Blocks with Highlighting

````markdown
```yaml
# Automatically highlighted
- name: Configure EVPN
  when:
    - aoscx_configure_evpn | bool
    - custom_fields.device_evpn | bool
```
````

### Tabs

```markdown
=== "Initial Deployment"
    ```yaml
    aoscx_idempotent_mode: false
    ```

=== "Ongoing Management"
    ```yaml
    aoscx_idempotent_mode: true
    ```
```

### Tables

Standard Markdown tables work great and look beautiful with Material theme.

## Adding New Pages

1. Create `.md` file in `docs/` directory
2. Add to `nav` section in `mkdocs.yml`
3. Commit and push - automatically deployed!

## Comparison: antsibull-docs vs MkDocs

| Feature | antsibull-docs | MkDocs Material |
|---------|----------------|-----------------|
| **Target** | Collections (modules/plugins) | Any docs (perfect for roles) |
| **Content** | Auto-extracted from code | Rich narrative docs |
| **Flexibility** | Structured/rigid | Very flexible |
| **Theme** | Ansible style | Material (beautiful!) |
| **Setup** | Collection required | Works with standalone role |
| **Your use case** | ❌ Overkill | ✅ Perfect fit |

## Best Practices

1. **Keep docs in `docs/`** - Clean separation
2. **Use descriptive filenames** - `EVPN_VXLAN_CONFIGURATION.md` not `config.md`
3. **Link between pages** - Use relative links: `[BGP Setup](BGP_CONFIGURATION.md)`
4. **Add examples** - Your YAML examples are excellent
5. **Update navigation** - Add new pages to `mkdocs.yml` nav section

## Example Output

Your docs will look like:

- **ansible.com documentation** (same Material theme!)
- **Beautiful navigation** with collapsible sections
- **Search** that actually works
- **Code examples** with syntax highlighting
- **Dark/light mode** toggle
- **Mobile responsive**

## Resources

- [MkDocs Documentation](https://www.mkdocs.org/)
- [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)
- [Markdown Guide](https://www.markdownguide.org/)

---

**TL;DR:** MkDocs is the better choice for this role because you have excellent narrative documentation that tells the story of BGP hybrid setup, EVPN/VXLAN configuration, and cleanup processes. antsibull-docs is designed for collections with lots of modules/plugins to document automatically.
