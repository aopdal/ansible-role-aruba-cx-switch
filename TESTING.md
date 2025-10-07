# Testing Guide for ansible-role-aruba-cx-switch

This document describes the comprehensive testing infrastructure for the Aruba AOS-CX Switch Ansible role.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Local Testing](#local-testing)
- [CI/CD Pipeline](#cicd-pipeline)
- [Test Types](#test-types)
- [Troubleshooting](#troubleshooting)

## Overview

This role includes multiple layers of testing:

1. **YAML Linting** - Validates YAML syntax and style
2. **Ansible Linting** - Checks Ansible best practices
3. **Syntax Checking** - Validates playbook syntax
4. **Molecule Testing** - Role integration testing
5. **Pre-commit Hooks** - Automated checks before commits

## Prerequisites

### 🚀 Option 1: Dev Container (Recommended)

The **easiest way** to run tests is using the VS Code Dev Container, which provides a pre-configured environment:

1. Install [VS Code](https://code.visualstudio.com/) and [Docker](https://www.docker.com/get-started)
2. Install the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
3. Open this folder in VS Code and click **"Reopen in Container"**
4. All dependencies are automatically installed! 🎉

**Benefits:**
- ✅ No manual setup required
- ✅ Consistent environment for all developers
- ✅ All tools pre-configured (Python, Ansible, Docker, linters)
- ✅ Pre-commit hooks automatically installed
- ✅ Works on Windows, Mac, and Linux

**To run tests in dev container:**
```bash
# All commands work out of the box
make test-quick
make test
molecule test
ansible-lint
```

### 📦 Option 2: Traditional Setup (Without Docker)

If you prefer not to use Docker or dev containers, you can set up a traditional virtual environment.

### Install Testing Dependencies

**IMPORTANT: All testing should be done in a virtual environment to avoid conflicts with system packages.**

```bash
# Quick setup with script (creates venv automatically)
./setup-testing.sh

# Manual setup
# 1. Create virtual environment
python3 -m venv .venv

# 2. Activate virtual environment
source .venv/bin/activate

# 3. Install Python testing requirements
pip install -r requirements-test.txt

# 4. Install Ansible collections
ansible-galaxy collection install -r requirements.yml

# 5. Install pre-commit hooks (optional but recommended)
pre-commit install
```

**Note:** Always activate the virtual environment before running tests:
```bash
source .venv/bin/activate
```

To deactivate when done:
```bash
deactivate
```

### System Requirements

- Python 3.9 or higher
- Python venv module (usually included with Python)
- Docker (for Molecule tests)
- Git
- Ansible 2.14 or higher (installed in venv)

## Local Testing

### Quick Test Suite

Run all tests locally (make sure virtual environment is activated):

```bash
# Activate virtual environment first
source .venv/bin/activate

# YAML linting
yamllint .

# Ansible linting
ansible-lint

# Syntax check
ansible-playbook tests/test.yml -i tests/inventory --syntax-check

# Full molecule test
molecule test

# Or use Makefile (handles venv automatically)
make test-quick
make test
```

### Individual Test Commands

#### 1. YAML Linting

Validates YAML syntax and formatting:

```bash
yamllint .
```

Configuration: `.yamllint`

#### 2. Ansible Linting

Checks Ansible best practices and potential issues:

```bash
# Run with default configuration
ansible-lint

# Run with specific profile
ansible-lint --profile production

# Fix auto-fixable issues
ansible-lint --fix
```

Configuration: `.ansible-lint`

#### 3. Syntax Checking

Validates playbook syntax without execution:

```bash
ansible-playbook tests/test.yml -i tests/inventory --syntax-check
```

#### 4. Molecule Testing

Molecule provides comprehensive role testing in isolated environments.

```bash
# Run full test sequence
molecule test

# Run individual steps
molecule create      # Create test instance
molecule converge    # Apply the role
molecule idempotence # Test idempotence
molecule verify      # Run verification tests
molecule destroy     # Clean up

# Debug mode
molecule --debug test

# Test with specific distro
MOLECULE_DISTRO=ubuntu2004 molecule test
```

Available distros:
- `ubuntu2404` (default)
- `ubuntu2204`
- `ubuntu2004`

Configuration: `molecule/default/molecule.yml`

#### 5. Pre-commit Hooks

Run all pre-commit checks:

```bash
# Run on all files
pre-commit run --all-files

# Run on staged files only
pre-commit run

# Run specific hook
pre-commit run ansible-lint
pre-commit run yamllint
```

Configuration: `.pre-commit-config.yaml`

## CI/CD Pipeline

The role uses GitHub Actions for continuous integration.

### Workflow: `.github/workflows/ci.yml`

The CI pipeline runs automatically on:
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop`
- Manual workflow dispatch

### Pipeline Stages

1. **Lint** - YAML and Ansible linting
2. **Syntax** - Syntax checks across multiple Ansible versions (2.14, 2.15, 2.16)
3. **Molecule** - Role testing in Docker containers
4. **Integration** - Integration test playbooks
5. **Release** - Automatic Galaxy release on main branch

### Viewing CI Results

Check the Actions tab in GitHub:
```
https://github.com/your-org/ansible-role-aruba-cx-switch/actions
```

## Test Types

### Unit Tests (Molecule)

Located in: `molecule/default/`

Tests individual role functionality in isolation:
- Role structure validation
- Task file existence
- Variable handling
- Template rendering

### Integration Tests

Located in: `tests/`

Tests role behavior with mock data:
- `tests/test.yml` - Main test playbook with comprehensive scenarios
- `tests/integration.yml` - Specific feature integration tests
- `tests/inventory` - Test inventory file

Run integration tests:
```bash
cd tests
ansible-playbook test.yml -i inventory -v
```

### Network Device Testing

For testing against real or simulated network devices:

```bash
# With GNS3/EVE-NG or physical switches
ansible-playbook tests/test.yml -i production_inventory --check

# Dry-run mode (no changes)
ansible-playbook tests/test.yml -i production_inventory --check --diff
```

## Test Data Structure

The role expects NetBox data structure. Example test data in `tests/test.yml`:

```yaml
netbox_vrfs:
  - name: "MGMT"
    rd: "65000:100"
    route_targets: ["65000:100"]

netbox_vlans:
  - vid: 100
    name: "DATA"

netbox_interfaces:
  - name: "1/1/1"
    type: "1000base-t"
    mode: "access"
    untagged_vlan:
      vid: 100
```

## Writing New Tests

### Adding Molecule Scenarios

Create a new scenario:

```bash
molecule init scenario <scenario-name>
```

Example scenarios:
- `default` - Basic role testing
- `idempotence` - Tests idempotent behavior
- `vsx` - Tests VSX configuration

### Adding Integration Tests

1. Create test playbook in `tests/`
2. Add test data structure
3. Run with: `ansible-playbook tests/your-test.yml -i tests/inventory`

## Troubleshooting

### Common Issues

#### Molecule Docker Connection Issues

```bash
# Check Docker is running
docker ps

# Clean up old containers
molecule destroy
docker system prune -f
```

#### Ansible Collection Not Found

```bash
# Reinstall collections
ansible-galaxy collection install -r requirements.yml --force
```

#### Linting Failures

```bash
# Auto-fix common issues
ansible-lint --fix

# Show only errors (not warnings)
ansible-lint --strict
```

#### Pre-commit Hook Failures

```bash
# Update hooks to latest versions
pre-commit autoupdate

# Clear cache and retry
pre-commit clean
pre-commit run --all-files
```

### Debug Mode

Enable debug output:

```bash
# Molecule
molecule --debug test

# Ansible
ansible-playbook tests/test.yml -vvv

# Ansible-lint
ansible-lint -v
```

## Test Coverage

Current test coverage:

- ✅ YAML syntax validation
- ✅ Ansible best practices linting
- ✅ Syntax checking across Ansible versions
- ✅ Role structure validation
- ✅ Task file validation
- ✅ Integration test playbooks
- ✅ Pre-commit hooks
- ⏳ Network device simulation (planned)
- ⏳ Performance testing (planned)

## Continuous Improvement

### Suggested Testing Workflow

1. **Before coding**: `pre-commit install`
2. **During development**: Run `yamllint` and `ansible-lint` frequently
3. **Before committing**: `pre-commit run --all-files`
4. **Before PR**: `molecule test`
5. **After PR merge**: CI/CD automatically runs full test suite

### Adding New Tests

When adding new features:

1. Add task tests in `molecule/default/verify.yml`
2. Add integration tests in `tests/`
3. Update this documentation
4. Ensure CI pipeline passes

## Resources

- [Ansible Lint Documentation](https://ansible-lint.readthedocs.io/)
- [Molecule Documentation](https://molecule.readthedocs.io/)
- [YAML Lint Documentation](https://yamllint.readthedocs.io/)
- [Pre-commit Documentation](https://pre-commit.com/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)

## Getting Help

If you encounter issues:

1. Check this documentation
2. Review CI/CD logs in GitHub Actions
3. Run tests with debug/verbose flags
4. Open an issue on GitHub with test output

---

**Happy Testing! 🧪✅**
