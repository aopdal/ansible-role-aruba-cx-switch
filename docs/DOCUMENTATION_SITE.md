# Documentation site

This role's documentation site is built with [Zensical](https://zensical.org/),
the static site generator from the team behind Material for MkDocs. The site
is configured in `zensical.toml` at the repository root and built from the
Markdown files in `docs/`.

## Why a site generator instead of antsibull-docs?

`antsibull-docs` targets Ansible collections and extracts module/plugin
documentation from code. This role is a standalone role whose value is in
narrative guides (EVPN/VXLAN, BGP, cleanup workflows), so a general-purpose
Markdown site generator fits better:

- All existing `.md` files work directly.
- Pages can be organised to tell a story rather than mirror code layout.
- Syntax highlighting for YAML/Jinja2, admonitions, tabs and Mermaid
  diagrams are built in.

## Local development

### Install dependencies

```bash
make docs-install   # pip install -r requirements-docs.txt
```

### Serve locally

```bash
make docs-serve     # zensical serve
```

Visit <http://127.0.0.1:8000> for a live preview that rebuilds on save.

### Build the static site

```bash
make docs-build     # zensical build --clean
```

Output is written to `site/` (git-ignored). The build reports broken links
and missing anchors; fix them before committing.

## Publishing

The site is published to a self-hosted web server by
`.github/workflows/deploy-docs.yml` on every push to `main` that touches the
documentation. See [GITHUB_ACTIONS_DEPLOYMENT.md](GITHUB_ACTIONS_DEPLOYMENT.md)
for the required secrets and server setup.

## Configuration

Everything lives in `zensical.toml`:

- `[project]` - site metadata, repository links and the `nav` tree.
- `[project.theme]` - theme features (navigation tabs/sections, search,
  code copy) and the light/dark palette.
- `[project.markdown_extensions]` - Python-Markdown and PyMdown extensions.

### Site structure

The navigation is an explicit list of inline tables:

```toml
nav = [
  { "Home" = "index.md" },
  { "Configuration" = [
    { "VRFs" = "VRF_CONFIGURATION.md" },
    { "BGP" = "BGP_CONFIGURATION.md" },
  ] },
]
```

### Features enabled

- **Navigation tabs** - top-level sections in tabs
- **Search** - full-text search with suggestions and highlighting
- **Dark mode** - light/dark palette toggle
- **Code copy** - click to copy code blocks
- **Mermaid** - diagrams rendered natively from ```` ```mermaid ```` fences
- **Responsive** - works on mobile

## Writing documentation

### Standard Markdown

Write normal Markdown; all existing docs work unchanged.

### Admonitions

```markdown
!!! note "This is a note"
    Additional information here

!!! warning "Important"
    Be careful with this setting
```

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

### Heading anchors

Zensical's heading slugs can differ from GitHub's. For example, GitHub turns
`` `foo.py` - Bar `` into `#foopy---bar` while Zensical produces
`#foopy-bar`. When a heading is the target of a cross-page link, avoid
` - ` separators (use `` `foo.py`: Bar `` instead) so the anchor is the same
in both places.

## Adding new pages

1. Create the `.md` file in `docs/`.
2. Add it to `nav` in `zensical.toml`.
3. Link it from [README_DOCS.md](README_DOCS.md).
4. Run `make docs-build` and fix any reported issues.

## Resources

- [Zensical documentation](https://zensical.org/docs/)
- [Markdown Guide](https://www.markdownguide.org/)
