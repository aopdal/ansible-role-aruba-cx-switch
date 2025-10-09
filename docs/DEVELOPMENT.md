# Development Guide

This guide covers everything you need to know to develop and contribute to the Aruba AOS-CX The dev container includes:

**Base Image:** Python 3.12 (Debian-based)

**Installed Tools:**
- Python 3.12 with pip
- Ansible & ansible-lintAnsible role.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Environment](#development-environment)
- [Project Structure](#project-structure)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Code Standards](#code-standards)
- [Troubleshooting](#troubleshooting)

## Getting Started

### Choose Your Development Environment

You have two options for setting up your development environment:

#### 🚀 Option 1: Dev Container (Recommended)

**Best for:** Most developers, especially those new to the project or working on multiple platforms.

**Advantages:**
- ✅ Zero configuration - everything just works
- ✅ Consistent environment across all developers
- ✅ No conflicts with system packages
- ✅ Automatic dependency installation
- ✅ Pre-configured VS Code extensions and settings
- ✅ Works on Windows, Mac, and Linux

**Requirements:**
- [VS Code](https://code.visualstudio.com/)
- [Docker Desktop](https://www.docker.com/get-started)
- [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

**Setup:**
1. Install the prerequisites above
2. Clone the repository
3. Open the folder in VS Code
4. When prompted, click **"Reopen in Container"**
   - Or press `F1` → type "Dev Containers: Reopen in Container"
5. Wait for the container to build (first time takes 2-3 minutes)
6. You're ready to develop! All dependencies are installed automatically.

**What's Included:**
- Python 3.12 with all testing packages
- Ansible and required collections
- Docker-in-Docker for Molecule testing
- Pre-commit hooks
- All VS Code extensions for Ansible development
- Configured linters and formatters

#### 📦 Option 2: Traditional Virtual Environment

**Best for:** Developers who prefer local setup or don't have Docker available.

**Requirements:**
- Python 3.9 or higher
- Python venv module
- Git
- Docker (optional, for Molecule tests)

**Quick Setup:**
```bash
# Use the setup script (recommended)
./setup-testing.sh

# This will:
# - Create a virtual environment in .venv/
# - Install all Python dependencies
# - Install Ansible collections
# - Set up pre-commit hooks
```

**Manual Setup:**
```bash
# 1. Create virtual environment
python3 -m venv .venv

# 2. Activate virtual environment
source .venv/bin/activate  # Linux/Mac
# Or on Windows:
# .venv\Scripts\activate

# 3. Upgrade pip
pip install --upgrade pip

# 4. Install Python dependencies
pip install -r requirements-test.txt

# 5. Install Ansible collections
ansible-galaxy collection install -r requirements.yml

# 6. Install pre-commit hooks (optional but recommended)
pre-commit install
```

**Remember:** Always activate the virtual environment before working:
```bash
source .venv/bin/activate
```

To deactivate when done:
```bash
deactivate
```

## Development Environment

### Dev Container Details

The dev container includes:

**Base Image:** Python 3.11 (Debian-based)

**Installed Tools:**
- Python 3.11 with pip
- Ansible and ansible-lint
- yamllint
- molecule with Docker driver
- pre-commit
- Git with Git LFS
- Network tools (ping, netcat, curl)
- Text editors (vim)
- Utilities (jq, bash-completion)

**VS Code Extensions:**
- Ansible (redhat.ansible) - Syntax highlighting and validation
- YAML (redhat.vscode-yaml) - YAML language support
- Python (ms-python.python) - Python development
- Pylance (ms-python.vscode-pylance) - Python type checking
- Black Formatter (ms-python.black-formatter) - Code formatting
- Ruff (charliermarsh.ruff) - Fast Python linting
- GitLens (eamodio.gitlens) - Enhanced Git features
- Error Lens (usernamehw.errorlens) - Inline error display
- Code Spell Checker (streetsidesoftware.code-spell-checker)

**Environment Variables:**
```bash
ANSIBLE_FORCE_COLOR=true
ANSIBLE_HOST_KEY_CHECKING=false
PY_COLORS=1
PYTHONUNBUFFERED=1
```

**Useful Aliases:**
```bash
ansible-test      # Runs molecule test
ansible-converge  # Runs molecule converge
ll                # List files with details
```

### Customizing the Dev Container

You can customize the dev container by editing `.devcontainer/devcontainer.json`:

```jsonc
{
  // Add additional VS Code extensions
  "customizations": {
    "vscode": {
      "extensions": [
        "your.extension-id"
      ]
    }
  },

  // Add additional features
  "features": {
    "ghcr.io/devcontainers/features/node:1": {}
  }
}
```

## Project Structure

```
ansible-role-aruba-cx-switch/
├── .devcontainer/              # Dev container configuration
│   ├── devcontainer.json       # VS Code dev container config
│   ├── Dockerfile              # Custom container image
│   └── post-create.sh          # Post-creation setup script
├── defaults/
│   └── main.yml                # Default variables
├── files/                      # Static files
├── filter_plugins/             # Custom Jinja2 filters
│   └── netbox_filters.py       # NetBox-specific filters
├── handlers/                   # Ansible handlers
├── meta/
│   └── main.yml                # Role metadata
├── molecule/                   # Molecule test scenarios
│   └── default/
│       ├── converge.yml        # Test playbook
│       ├── molecule.yml        # Molecule configuration
│       ├── prepare.yml         # Preparation steps
│       └── verify.yml          # Verification tests
├── tasks/                      # Ansible tasks
│   ├── main.yml                # Main task orchestration
│   ├── configure_*.yml         # Configuration tasks
│   └── cleanup_*.yml           # Cleanup tasks
├── templates/                  # Jinja2 templates
├── tests/                      # Integration tests
│   ├── test.yml                # Test playbook
│   └── inventory               # Test inventory
├── vars/                       # Variables (higher precedence)
├── .ansible-lint               # Ansible-lint configuration
├── .pre-commit-config.yaml     # Pre-commit hooks configuration
├── .yamllint                   # YAML linting rules
├── requirements.yml            # Ansible collections
├── requirements-test.txt       # Python testing dependencies
├── Makefile                    # Common development tasks
├── README.md                   # Role documentation
├── docs/                       # Documentation
│   ├── DEVELOPMENT.md          # This file
│   ├── TESTING*.md             # Testing guides
│   └── ...                     # Other documentation
└── CONTRIBUTING.md             # Contribution guidelines
```

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make Your Changes

Edit the relevant files in the role structure:
- `tasks/*.yml` - Add or modify tasks
- `defaults/main.yml` - Add or change default variables
- `templates/*` - Add or modify Jinja2 templates
- `filter_plugins/*` - Add custom filters

### 3. Test Your Changes

```bash
# Quick tests (syntax and lint)
make test-quick

# Full test suite
make test

# Run specific test
ansible-lint
yamllint .
molecule test
```

### 4. Commit Your Changes

If you have pre-commit hooks installed (recommended), they'll run automatically:

```bash
git add .
git commit -m "Add new feature: description"
```

If pre-commit fails, fix the issues and commit again:

```bash
# See what needs fixing
pre-commit run --all-files

# Fix and commit again
git add .
git commit -m "Add new feature: description"
```

### 5. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub.

## Testing

See [TESTING.md](TESTING.md) for comprehensive testing documentation.

### Quick Test Commands

**In Dev Container:**
```bash
# All commands work out of the box
make test-quick          # Fast: lint + syntax check
make test                # Full: includes molecule tests
molecule test            # Full molecule test cycle
ansible-lint             # Ansible best practices
yamllint .               # YAML syntax and style
pre-commit run -a        # All pre-commit checks
```

**In Virtual Environment:**
```bash
# Activate venv first
source .venv/bin/activate

# Then run tests
make test-quick
make test
```

### Test Before Commit

Always run tests before committing:

```bash
# Minimum recommended
make test-quick

# Full test suite (recommended before PR)
make test
```

### Writing Tests

#### Molecule Tests

Edit `molecule/default/converge.yml` to add test scenarios:

```yaml
- name: Test new feature
  hosts: all
  tasks:
    - name: Include role with new feature
      ansible.builtin.include_role:
        name: aopdal.aruba_cx_switch
      vars:
        new_feature_var: true
```

#### Verification Tests

Edit `molecule/default/verify.yml` to add verification:

```yaml
- name: Verify new feature works
  ansible.builtin.assert:
    that:
      - some_condition
    fail_msg: "Feature didn't work as expected"
```

## Code Standards

### Ansible Best Practices

1. **Use Fully Qualified Collection Names (FQCN)**
   ```yaml
   # Good
   - name: Debug message
     ansible.builtin.debug:
       msg: "Hello"

   # Bad
   - name: Debug message
     debug:
       msg: "Hello"
   ```

2. **Always Name Your Tasks**
   ```yaml
   # Good
   - name: Configure VLAN 100
     arubanetworks.aoscx.aoscx_vlan:
       vlan_id: 100

   # Bad
   - arubanetworks.aoscx.aoscx_vlan:
       vlan_id: 100
   ```

3. **Use `when` Conditions Appropriately**
   ```yaml
   - name: Configure feature
     ansible.builtin.include_tasks: configure_feature.yml
     when: feature_enabled | bool
   ```

4. **Tag Your Tasks**
   ```yaml
   - name: Configure VLANs
     ansible.builtin.include_tasks: configure_vlans.yml
     tags:
       - vlans
       - layer2
   ```

5. **Use Variables from `defaults/main.yml`**
   - All user-configurable options should be in `defaults/main.yml`
   - Use descriptive variable names with `aoscx_` prefix
   - Provide sensible defaults

### YAML Style Guide

Follow the rules in `.yamllint`:

- **Indentation:** 2 spaces (never tabs)
- **Line length:** Max 120 characters
- **Quotes:** Use double quotes for strings
- **Lists:** Use the `-` syntax
- **Booleans:** Use `true/false` (not `yes/no`)

Example:
```yaml
---
# Good YAML style
- name: Configure interface
  arubanetworks.aoscx.aoscx_interface:
    name: "1/1/1"
    enabled: true
    description: "Access port for VLAN 100"
  when: configure_interfaces | bool
```

### Python Style Guide (for Filters/Plugins)

- Follow PEP 8
- Use type hints where possible
- Document functions with docstrings
- Keep functions focused and small

Example:
```python
def get_vlan_name(vlan_id: int, vlans: list) -> str:
    """
    Get VLAN name by ID from NetBox VLAN list.

    Args:
        vlan_id: The VLAN ID to search for
        vlans: List of VLAN dictionaries from NetBox

    Returns:
        VLAN name or empty string if not found
    """
    for vlan in vlans:
        if vlan.get('vid') == vlan_id:
            return vlan.get('name', '')
    return ''
```

### Documentation Standards

1. **README.md** - User-facing documentation
   - Clear feature list
   - Installation instructions
   - Usage examples
   - Variable reference

2. **Task Comments** - Explain complex logic
   ```yaml
   # VRFs must be configured before L3 interfaces
   # because interfaces need to reference existing VRFs
   - name: Include VRF configuration
     ansible.builtin.include_tasks: configure_vrfs.yml
   ```

3. **Variable Documentation** - In `defaults/main.yml`
   ```yaml
   # Enable VLAN configuration management
   # Set to false to skip VLAN configuration entirely
   aoscx_configure_vlans: true
   ```

## Troubleshooting

### Common Issues

#### Dev Container Won't Build

**Problem:** Container fails to build or start

**Solutions:**
```bash
# Rebuild container from scratch
# In VS Code: F1 → "Dev Containers: Rebuild Container"

# Or from command line:
docker-compose -f .devcontainer/docker-compose.yml build --no-cache

# Check Docker is running
docker ps

# Check Docker disk space
docker system df
docker system prune  # Clean up if needed
```

#### Virtual Environment Issues

**Problem:** Import errors or missing packages

**Solutions:**
```bash
# Ensure venv is activated
source .venv/bin/activate

# Reinstall dependencies
pip install --upgrade pip
pip install -r requirements-test.txt

# Reinstall collections
ansible-galaxy collection install -r requirements.yml --force
```

#### Molecule Tests Fail

**Problem:** Molecule tests fail or can't connect to Docker

**Solutions:**
```bash
# Check Docker is running
docker ps

# Clean up molecule instances
molecule destroy

# Run with debug output
molecule --debug test

# Check Docker permissions (Linux)
sudo usermod -aG docker $USER
# Then log out and back in
```

#### Pre-commit Hooks Fail

**Problem:** Pre-commit hooks fail with errors

**Solutions:**
```bash
# Update pre-commit hooks
pre-commit autoupdate

# Reinstall hooks
pre-commit uninstall
pre-commit install

# Run manually to see errors
pre-commit run --all-files

# Skip hooks temporarily (not recommended)
git commit --no-verify
```

#### Ansible-lint Errors

**Problem:** Ansible-lint reports errors

**Solutions:**
```bash
# Run with detailed output
ansible-lint --verbose

# Auto-fix some issues
ansible-lint --fix

# Check specific file
ansible-lint tasks/main.yml

# Update ansible-lint
pip install --upgrade ansible-lint
```

### Getting Help

1. **Check existing documentation:**
   - [README.md](README.md) - Role usage
   - [TESTING.md](TESTING.md) - Testing guide
   - [CONTRIBUTING.md](CONTRIBUTING.md) - Contribution guidelines

2. **Check issues:**
   - Search GitHub issues for similar problems
   - Create a new issue with detailed information

3. **Debug output:**
   ```bash
   # Ansible verbose output
   ansible-playbook -vvv playbook.yml

   # Molecule debug output
   molecule --debug test

   # Python debugging
   python -m pdb script.py
   ```

## Tips and Best Practices

### Development Tips

1. **Use the Makefile**
   ```bash
   make test-quick  # Fast feedback
   make test        # Full validation
   make help        # See all targets
   ```

2. **Test incrementally**
   - Test after each significant change
   - Don't wait until everything is done
   - Fix issues early

3. **Use molecule converge for iteration**
   ```bash
   molecule create    # Create once
   molecule converge  # Test changes quickly
   molecule verify    # Check results
   molecule destroy   # Clean up when done
   ```

4. **Check syntax before running**
   ```bash
   ansible-playbook --syntax-check playbook.yml
   ansible-lint playbook.yml
   ```

5. **Use VS Code features**
   - Hover over modules for documentation
   - Use IntelliSense for autocomplete
   - Use integrated terminal
   - Install recommended extensions

### Git Workflow Tips

1. **Commit often with clear messages**
   ```bash
   git commit -m "feat: add VLAN cleanup task"
   git commit -m "fix: handle missing VRF gracefully"
   git commit -m "docs: update README with new variable"
   ```

2. **Use conventional commits**
   - `feat:` - New feature
   - `fix:` - Bug fix
   - `docs:` - Documentation only
   - `test:` - Adding tests
   - `refactor:` - Code refactoring
   - `chore:` - Maintenance tasks

3. **Keep changes focused**
   - One feature per branch
   - One logical change per commit
   - Review your own PR before submitting

### Performance Tips

1. **Cache dependencies in CI**
   - Dev container caches layers
   - Molecule reuses containers

2. **Run only needed tests**
   ```bash
   # Quick feedback loop
   yamllint tasks/new_file.yml
   ansible-lint tasks/new_file.yml

   # Full test when ready
   make test
   ```

3. **Use parallel testing when possible**
   - Molecule can test multiple platforms
   - Pre-commit runs checks in parallel

## Resources

### Ansible Resources

- [Ansible Documentation](https://docs.ansible.com/)
- [Ansible Best Practices](https://docs.ansible.com/ansible/latest/user_guide/playbooks_best_practices.html)
- [Ansible Lint Rules](https://ansible-lint.readthedocs.io/)
- [Molecule Documentation](https://molecule.readthedocs.io/)

### Aruba AOS-CX Resources

- [AOS-CX Ansible Collection](https://galaxy.ansible.com/arubanetworks/aoscx)
- [AOS-CX Collection Documentation](https://arubanetworks.github.io/aoscx-ansible-collection/)
- [AOS-CX REST API Guide](https://www.arubanetworks.com/techdocs/)

### NetBox Resources

- [NetBox Documentation](https://docs.netbox.dev/)
- [NetBox Ansible Collection](https://docs.ansible.com/ansible/latest/collections/netbox/netbox/)
- [PyNetBox Documentation](https://pynetbox.readthedocs.io/)

### Dev Container Resources

- [Dev Containers Documentation](https://code.visualstudio.com/docs/devcontainers/containers)
- [Dev Container Specification](https://containers.dev/)
- [Dev Containers Extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

---

## Quick Reference

### Essential Commands

```bash
# Dev Container
# F1 → "Dev Containers: Reopen in Container"

# Virtual Environment
source .venv/bin/activate

# Testing
make test-quick              # Fast tests
make test                    # Full tests
ansible-lint                 # Lint Ansible
yamllint .                   # Lint YAML
molecule test                # Full molecule cycle
pre-commit run --all-files   # All pre-commit checks

# Molecule Development
molecule create              # Create test instance
molecule converge            # Apply role
molecule verify              # Run verification
molecule destroy             # Clean up

# Git
git checkout -b feature/name # Create branch
git add .                    # Stage changes
git commit -m "message"      # Commit
git push origin feature/name # Push

# Help
make help                    # See all make targets
molecule --help              # Molecule help
ansible-lint --help          # Ansible-lint help
```

---

**Happy coding! 🚀**

Need help? Check [TESTING.md](TESTING.md) or open an issue on GitHub.
