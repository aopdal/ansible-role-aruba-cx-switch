# Contributing to ansible-role-aruba-cx-switch

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to this Ansible role.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Testing Requirements](#testing-requirements)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Documentation](#documentation)

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on what is best for the community
- Show empathy towards other contributors

## Getting Started

### Prerequisites

- Git
- Python 3.9+
- Ansible 2.14+
- Docker (for Molecule tests)
- Basic understanding of Ansible roles and network automation

### Setup Development Environment

1. **Fork and Clone**

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/YOUR-USERNAME/ansible-role-aruba-cx-switch.git
cd ansible-role-aruba-cx-switch
```

2. **Setup Virtual Environment and Install Dependencies**

```bash
# Quick setup (recommended)
./setup-testing.sh

# Or use Makefile
make setup

# Or manually
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-test.txt
ansible-galaxy collection install -r requirements.yml
pre-commit install
```

3. **Verify Setup**

```bash
# Activate venv
source .venv/bin/activate

# Run quick tests
make test-quick
```

**Important:** Always activate the virtual environment before working:
```bash
source .venv/bin/activate
```

## Development Workflow

### 1. Create a Branch

```bash
# For new features
git checkout -b feature/your-feature-name

# For bug fixes
git checkout -b fix/issue-description

# For documentation
git checkout -b docs/what-you-are-documenting
```

### 2. Make Changes

Follow these guidelines:

- Write clear, concise commit messages
- Keep commits focused on a single change
- Test your changes locally
- Update documentation as needed

### 3. Test Your Changes

```bash
# Run linting
make lint

# Run syntax check
make syntax

# Run full test suite
make test

# Or run individual tests
make yamllint
make ansible-lint
make molecule-test
```

### 4. Commit Changes

```bash
# Pre-commit hooks will run automatically
git add .
git commit -m "feat: add support for X"

# Commit message format:
# <type>: <description>
#
# Types: feat, fix, docs, style, refactor, test, chore
```

## Testing Requirements

All contributions must pass the following tests:

### Required Tests

1. **YAML Lint** - `make yamllint`
2. **Ansible Lint** - `make ansible-lint`
3. **Syntax Check** - `make syntax`
4. **Pre-commit Hooks** - `make pre-commit`

### Recommended Tests

5. **Molecule Tests** - `make molecule-test`
6. **Integration Tests** - `make integration`

### Test Coverage

- All new features must include tests
- Bug fixes should include regression tests
- Update `molecule/` tests for new functionality
- Add integration tests in `tests/` directory

See [TESTING.md](TESTING.md) for detailed testing instructions.

## Pull Request Process

### Before Submitting

1. ✅ All tests pass locally
2. ✅ Code follows style guidelines
3. ✅ Documentation is updated
4. ✅ Commit messages are clear
5. ✅ Branch is up to date with main

### Submitting a PR

1. **Push to Your Fork**

```bash
git push origin feature/your-feature-name
```

2. **Create Pull Request**

- Go to the original repository on GitHub
- Click "New Pull Request"
- Select your fork and branch
- Fill out the PR template

3. **PR Description Should Include**

- Clear description of changes
- Related issue numbers (e.g., "Fixes #123")
- Testing performed
- Screenshots (if applicable)
- Breaking changes (if any)

### PR Review Process

- Maintainers will review your PR
- CI/CD pipeline must pass
- Address any review comments
- Once approved, maintainers will merge

### After Merge

- Delete your feature branch
- Pull the latest main branch
- Your contribution will be in the next release! 🎉

## Coding Standards

### Ansible Best Practices

```yaml
# ✅ Good
- name: Configure VLAN
  arubanetworks.aoscx.aoscx_vlan:
    vlan_id: 100
    name: "DATA"
    state: present

# ❌ Bad
- aoscx_vlan: vlan_id=100 name=DATA state=present
```

### Style Guidelines

1. **YAML Formatting**
   - Use 2 spaces for indentation
   - Use `---` document start marker
   - Quote strings with special characters
   - Line length: max 160 characters

2. **Naming Conventions**
   - Use snake_case for variables: `aoscx_vlan_id`
   - Use descriptive names: `configure_vlans.yml` not `vlans.yml`
   - Prefix role variables: `aoscx_*`

3. **Task Structure**
   - Always include `name:` for tasks
   - Use FQCN for modules: `ansible.builtin.debug`
   - Group related tasks in separate files

4. **Documentation**
   - Document all variables in `defaults/main.yml`
   - Include examples in README.md
   - Add comments for complex logic

### Python Code (filter_plugins/)

```python
# Follow PEP 8
# Use type hints
# Include docstrings
# Run: black filter_plugins/

def my_filter(value: str) -> str:
    """
    Brief description.

    Args:
        value: Input value

    Returns:
        Processed value
    """
    return value.upper()
```

## Documentation

### Update Documentation

When making changes, update relevant documentation:

- `README.md` - User-facing features
- `TESTING.md` - Testing procedures
- `CHANGELOG.md` - User-visible changes
- `defaults/main.yml` - Variable documentation
- Inline comments - Complex logic

### Documentation Style

- Use clear, concise language
- Include code examples
- Add screenshots for UI changes
- Link to related documentation

## Release Process

Maintainers handle releases:

1. Update version in `galaxy.yml`
2. Update `CHANGELOG.md`
3. Create git tag: `vX.Y.Z`
4. GitHub Actions publishes to Ansible Galaxy

## Getting Help

- 📖 Read [TESTING.md](TESTING.md) for testing help
- 🐛 Open an issue for bugs
- 💡 Open an issue for feature requests
- 💬 Comment on existing issues for questions

## Recognition

Contributors will be:
- Listed in CHANGELOG.md
- Recognized in release notes
- Added to GitHub contributors list

Thank you for contributing! 🎉
