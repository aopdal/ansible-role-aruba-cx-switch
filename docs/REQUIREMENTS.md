# Requirements Files Reference

This project uses multiple requirements files for different purposes. This document explains each file and when to use it.

## Overview

| File | Purpose | When to Use |
|------|---------|-------------|
| `requirements.txt` | Runtime dependencies for using the role | **Always** - Required for role to function |
| `requirements.yml` | Ansible collections | **Always** - Required for role to function |
| `requirements-example.yml` | Ansible example requirements | Using the role |
| `requirements-test.txt` | Testing and development tools | Development and CI/CD only |
| `requirements-docs.txt` | Documentation generation | Documentation development only |


---

## requirements.txt

**Purpose:** Python libraries required for the role to function in production.

**Contains:**

- `ansible-core` >= 2.19.10, < 2.20.0 - Ansible automation platform (pinned to 2.19.x; arubanetworks.aoscx 4.5.1 is not compatible with newer cores)
- `ansible-lint` - Ansible best practices linter (unpinned; also present, version-pinned, in `requirements-test.txt` — see the note under [Version Pinning](#version-pinning))
- `pyaoscx` - Aruba AOS-CX Python SDK (required by arubanetworks.aoscx collection)
- `pynetbox` - NetBox API client (required by netbox.netbox collection)
- `paramiko` - SSH library (required by arubanetworks.aoscx collection)
- `ansible-pylibssh` - Python SSH wrapper (required by arubanetworks.aoscx collection)
- `requests` - HTTP library (required by both collections)
- `packaging` - Version parsing (required by netbox.netbox collection)
- `pytz` - Timezone support (required by netbox.netbox collection)

**Install:**

```bash
pip install -r requirements.txt
```

**Required for:**
- Running playbooks that use this role
- Production deployments
- Development and testing

---

## requirements.yml

**Purpose:** Ansible collections that this role depends on.

**Contains:**

- `arubanetworks.aoscx` >= 4.5.1 - Aruba AOS-CX modules
- `netbox.netbox` >= 3.23.0 - NetBox inventory and modules
- `ansible.utils` >= 6.0.0 - `ipaddr` and other filters used throughout tasks/templates
- `ansible.netcommon` >= 8.0.0 - Provides the `network_cli` connection plugin used by `aoscx_config`/`aoscx_command` tasks (see [CLAUDE.md §4.2](../CLAUDE.md))
- `community.docker` >= 3.10.2 - Molecule Docker driver (development/testing only)
- `ansible.posix` >= 1.4.0 - Development/testing only

**Install:**
```bash
ansible-galaxy collection install -r requirements.yml
```

**Required for:**
- Running playbooks that use this role
- Production deployments
- Development and testing

---

## requirements-test.txt

**Purpose:** Development, testing, and quality assurance tools.

**Contains:**

- `pytest` - Unit testing framework
- `pytest-cov` - Test coverage reporting
- `pytest-mock` - Mocking for tests
- `molecule` - Integration testing framework
- `molecule-plugins[docker]` - Docker driver for Molecule
- `ansible-lint` - Ansible best practices linter
- `yamllint` - YAML linting
- `jmespath` - JSON query language (for filter testing)
- `pre-commit` - Git hooks for code quality

**Install:**
```bash
pip install -r requirements-test.txt
```

**Required for:**

- Role development
- Running tests (pytest, molecule)
- Code quality checks (ansible-lint, yamllint)
- CI/CD pipelines
- Pre-commit hooks

**NOT required for:**

- Using the role in production
- Simple playbook execution

---

## requirements-docs.txt

**Purpose:** Documentation generation tools.

**Contains:**

- `mkdocs` - Static site generator
- `mkdocs-material` - Material theme for MkDocs
- `mkdocs-git-revision-date-localized-plugin` - Git-based date display
- `pymdown-extensions` - Markdown extensions

**Install:**
```bash
pip install -r requirements-docs.txt
```

**Required for:**

- Building documentation site (`mkdocs build`)
- Serving documentation locally (`mkdocs serve`)
- Documentation development

**NOT required for:**

- Using the role
- Running tests
- Reading documentation (Markdown files work without MkDocs)

---

## Quick Start

### For Users (Running the Role)

Install only what's needed to use the role:

```bash
# Install Ansible collections
ansible-galaxy collection install -r requirements.yml

# Install Python dependencies
pip install -r requirements.txt
```

### For Developers (Full Setup)

Install everything for development:

```bash
# Automated setup (recommended)
./setup-testing.sh

# Or manual setup
pip install -r requirements.txt        # Runtime dependencies
pip install -r requirements-test.txt   # Testing tools
ansible-galaxy collection install -r requirements.yml
pre-commit install
```

### For Documentation Contributors

Add documentation tools:

```bash
pip install -r requirements.txt        # Runtime dependencies
pip install -r requirements-docs.txt   # Documentation tools
make docs-serve                        # Start documentation server
```

---

## CI/CD Usage

### GitHub Actions Example

```yaml
- name: Install dependencies
  run: |
    pip install -r requirements.txt
    pip install -r requirements-test.txt
    ansible-galaxy collection install -r requirements.yml

- name: Run tests
  run: make test
```

### Testing Pipeline

```yaml
- name: Install test dependencies
  run: |
    pip install -r requirements-test.txt
    ansible-galaxy collection install -r requirements.yml

- name: Lint and test
  run: |
    ansible-lint
    yamllint .
    molecule test
```

---

## Dependency Management

### Updating Dependencies

Check for outdated packages:

```bash
pip list --outdated
```

Update specific package:

```bash
pip install --upgrade pyaoscx
```

Update collections:

```bash
ansible-galaxy collection install arubanetworks.aoscx --force
```

### Version Pinning

- **requirements.txt**: Uses minimum versions (`>=`) for flexibility, except `ansible-core` which is capped (`>=2.19.10,<2.20.0`) because arubanetworks.aoscx 4.5.1 isn't compatible with newer cores. `ansible-lint` is listed here unpinned (for convenience when installing just `requirements.txt`); it's also listed, version-pinned, in `requirements-test.txt` — if you install both, pip resolves to whichever pin is stricter, so keep the two roughly in sync when bumping either.
- **requirements-test.txt**: Uses minimum versions (`>=`) for flexibility, same as requirements.txt
- **requirements.yml**: Uses minimum versions (`>=`) for collections

### Testing New Versions

Always test in a virtual environment:

```bash
python -m venv test-env
source test-env/bin/activate  # Linux/Mac
test-env\Scripts\activate     # Windows

pip install -r requirements.txt
# Run tests
make test-quick
```

---

## Troubleshooting

### "Module not found" errors

Usually means runtime dependencies not installed:

```bash
pip install -r requirements.txt
```

### "Collection not found" errors

Collections not installed:

```bash
ansible-galaxy collection install -r requirements.yml
```

### "Command not found" (ansible-lint, molecule, etc.)

Testing dependencies not installed:

```bash
pip install -r requirements-test.txt
```

### Version conflicts

Use a fresh virtual environment:

```bash
deactivate  # If in a venv
rm -rf .venv
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-test.txt
```

---

## See Also

- [QUICKSTART.md](QUICKSTART.md) - Quick setup guide
- [DEVELOPMENT.md](DEVELOPMENT.md) - Detailed development guide
- [TESTING.md](TESTING.md) - Testing documentation
- [README.md](index.md) - Main documentation
