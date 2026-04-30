# Testing Guide for ansible-role-aruba-cx-switch

This document describes the comprehensive testing infrastructure for the Aruba AOS-CX Switch Ansible role with **virtual environment isolation**.

## Table of Contents

- [Overview](#overview)
- [Testing Infrastructure](#testing-infrastructure)
- [Quick Start](#quick-start)
- [Prerequisites](#prerequisites)
- [Local Testing](#local-testing)
- [CI/CD Pipeline](#cicd-pipeline)
- [Test Types](#test-types)
- [Common Commands](#common-commands)
- [Troubleshooting](#troubleshooting)

## Overview

This role includes comprehensive CI/CD testing infrastructure with **8 layers of testing**:

1. ✅ **Python Unit Tests** (`pytest`) - 309 tests for filter plugins — see [UNIT_TESTING.md](UNIT_TESTING.md)
2. ✅ **YAML Linting** (`yamllint`) - Validates YAML syntax and style
3. ✅ **Ansible Linting** (`ansible-lint`) - Checks Ansible best practices
4. ✅ **Syntax Checking** - Validates playbook syntax (multiple Ansible versions)
5. ✅ **Molecule Testing** - Role integration testing (Docker-based)
6. ✅ **Integration Testing** - Full playbook testing
7. ✅ **Pre-commit Hooks** - Automated checks before commits
8. ✅ **CI/CD Pipeline** - GitHub Actions automation

### Key Benefits

- ✅ **Isolated Environment** - No conflicts with system packages
- ✅ **Multi-version Testing** - Tests across Ansible 2.14, 2.15, 2.16
- ✅ **Automated CI/CD** - Runs on every push/PR
- ✅ **Pre-commit Hooks** - Catch issues before commit
- ✅ **Easy Commands** - Simple Makefile interface
- ✅ **Comprehensive Docs** - Multiple detailed guides
- ✅ **Industry Best Practices** - Virtual envs, linting, testing
- ✅ **Auto Galaxy Release** - Publish automatically on main branch

## Testing Infrastructure

### Core Components (21 files)

1. **GitHub Actions CI/CD**
    - `.github/workflows/ci.yml` - Multi-stage pipeline (lint, syntax, molecule, integration, release)
    - `.github/ISSUE_TEMPLATE/bug_report.md` - Bug report template
    - `.github/ISSUE_TEMPLATE/feature_request.md` - Feature request template

2. **Testing Configuration**
    - `.ansible-lint` - Ansible best practices linting (production profile)
    - `.yamllint` - YAML syntax validation rules
    - `requirements-test.txt` - Python testing dependencies
    - `.pre-commit-config.yaml` - Pre-commit hook configuration

3. **Molecule Testing Framework**
    - `molecule/default/molecule.yml` - Test configuration
    - `molecule/default/converge.yml` - Role application test
    - `molecule/default/verify.yml` - Verification tests

4. **Test Playbooks**
    - `tests/test.yml` - Main test playbook with comprehensive mock data
    - `tests/integration.yml` - Integration test scenarios
    - `tests/inventory` - Test inventory file

5. **Developer Tools**
    - `Makefile` - 20+ convenient commands with venv integration
    - `setup-testing.sh` - Automated setup script (creates venv)
    - `.gitignore` - Enhanced for testing artifacts and venv

### File Structure

```
ansible-role-aruba-cx-switch/
├── .github/
│   ├── workflows/
│   │   └── ci.yml                    # CI/CD pipeline
│   └── ISSUE_TEMPLATE/
│       ├── bug_report.md
│       └── feature_request.md
├── molecule/
│   └── default/
│       ├── molecule.yml              # Molecule config
│       ├── converge.yml              # Test playbook
│       └── verify.yml                # Verification
├── tests/
│   ├── test.yml                      # Main test
│   ├── integration.yml               # Integration tests
│   └── inventory                     # Test inventory
├── .ansible-lint                     # Ansible linting rules
├── .yamllint                         # YAML linting rules
├── .pre-commit-config.yaml           # Pre-commit hooks
├── .gitignore                        # Enhanced
├── Makefile                          # Testing commands
├── setup-testing.sh                  # Setup script
├── requirements-test.txt             # Python test deps
├── TESTING.md                        # Testing guide
├── CONTRIBUTING.md                   # Contribution guide
├── QUICK_REFERENCE.md                # Quick commands
├── CHANGELOG.md                      # Version history
└── .venv/                            # Virtual environment (created by setup)
```

## Quick Start

### Option 1: Automatic (Recommended) ⚡

```bash
# One command setup
./setup-testing.sh

# Run tests (Makefile handles venv automatically)
make test-quick    # Fast: lint + syntax
make test          # Full: includes Molecule
```

### Option 2: Using Makefile 🛠️

```bash
# Setup
make setup         # Creates venv + installs deps

# Test
make lint          # All linting
make syntax        # Syntax check
make molecule-test # Molecule tests
make test-quick    # Quick tests
make test          # Full tests

# Utilities
make info          # Show venv status
make clean         # Clean artifacts
make clean-all     # Clean including venv
make help          # Show all commands
```

### Option 3: Manual Control 🔧

```bash
# Create and activate venv
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements-test.txt
ansible-galaxy collection install -r requirements.yml
pre-commit install

# Run tests
yamllint .
ansible-lint
ansible-playbook tests/test.yml --syntax-check
molecule test

# Deactivate when done
deactivate
```

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

### Python Unit Tests (Filter Plugins)

Located in: `tests/unit/`

**NEW**: Comprehensive unit tests for custom filter plugins using pytest.

The role includes **309 unit tests** covering all custom Ansible filters:

```bash
# Run all unit tests
pytest tests/unit/

# Run specific test file
pytest tests/unit/test_l3_config_helpers.py

# Run with coverage
pytest tests/unit/ --cov=filter_plugins --cov-report=html

# Run specific test categories
pytest tests/unit/ -m vlan      # VLAN filter tests
pytest tests/unit/ -m l3_config  # L3 config helper tests
pytest tests/unit/ -m utils      # Utility function tests
```

**Test Coverage**:
- `test_l3_config_helpers.py` - 56 tests for L3 configuration optimization
- `test_bgp_filters.py` - 41 tests for BGP session enrichment and policy collection
- `test_vlan_filters.py` - 40 tests for VLAN lifecycle management (incl. IGMP snooping)
- `test_interface_change_detection.py` - 31 tests for NetBox vs device change detection
- `test_utils.py` - 30 tests for utility functions
- `test_interface_filters.py` - 28 tests for interface categorization
- `test_vrf_filters.py` - 26 tests for VRF operations
- `test_rest_api_transforms.py` - 25 tests for REST API data normalization
- `test_comparison.py` - 17 tests for state comparison logic
- `test_ospf_filters.py` - 15 tests for OSPF configuration

**Configuration**: `pytest.ini` defines test discovery, markers, and coverage settings

### Molecule Tests (Role Validation)

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

## Common Commands

Quick reference for the most frequently used testing commands:

```bash
# Setup and info
make venv              # Create virtual environment
make setup             # Complete setup (venv + dependencies)
make info              # Show system and venv info
make help              # Show all commands

# Python Unit Tests (NEW)
pytest tests/unit/                           # Run all unit tests
pytest tests/unit/ -v                        # Verbose output
pytest tests/unit/ --cov=filter_plugins      # With coverage
pytest tests/unit/test_l3_config_helpers.py  # Specific test file
pytest tests/unit/ -m l3_config              # By marker

# Testing
make lint              # YAML + Ansible linting
make syntax            # Syntax check
make test-quick        # Quick tests (no Molecule)
make test              # Full test suite

# Molecule
make molecule-test     # Full Molecule test
make molecule-create   # Create test instance
make molecule-converge # Apply role
make molecule-verify   # Verify
make molecule-destroy  # Destroy instance

# Cleanup
make clean             # Clean test artifacts
make clean-all         # Clean everything including venv

# Pre-commit
make pre-commit-setup  # Install hooks
make pre-commit        # Run hooks on all files
```

For a complete command reference, see [QUICK_REFERENCE.md](QUICK_REFERENCE.md).

## Writing New Tests

### Adding Python Unit Tests for Filters

**NEW**: When adding new filter plugins, create comprehensive unit tests:

1. **Create test file** in `tests/unit/`:
   ```bash
   # Follow naming convention: test_<module_name>.py
   tests/unit/test_my_new_filters.py
   ```

2. **Structure your tests**:
   ```python
   """Unit tests for my new filters"""
   import pytest
   from netbox_filters_lib.my_new_filters import my_filter_function

   class TestMyFilterFunction:
       """Tests for my_filter_function"""

       def test_basic_functionality(self):
           """Test basic use case"""
           result = my_filter_function(input_data)
           assert result == expected_output

       def test_edge_cases(self):
           """Test edge cases"""
           assert my_filter_function([]) == []
           assert my_filter_function(None) == default_value
   ```

3. **Run your tests**:
   ```bash
   # Run just your new tests
   pytest tests/unit/test_my_new_filters.py -v

   # Run with coverage
   pytest tests/unit/test_my_new_filters.py --cov=filter_plugins.netbox_filters_lib.my_new_filters
   ```

4. **Add test markers** in `pytest.ini` if needed

**Best Practices**:
- Test normal inputs, edge cases, and error conditions
- Use descriptive test names: `test_<what>_<condition>`
- Aim for high code coverage (>80%)
- Test both expected behavior and failure modes

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

## Next Steps

### Initial Setup

1. **Review the setup**

   ```bash
   cat docs/TESTING.md
   cat docs/QUICK_REFERENCE.md
   make info
   ```

2. **Run initial setup**

   ```bash
   ./setup-testing.sh
   # OR
   make setup
   ```

3. **Test it works**

   ```bash
   make test-quick
   ```

4. **Setup pre-commit hooks**

   ```bash
   pre-commit install
   # OR
   make pre-commit-setup
   ```

5. **Commit and push to GitHub**

   ```bash
   git add .
   git commit -m "feat: add comprehensive CI/CD testing infrastructure"
   git push
   ```

6. **Configure GitHub Secrets** (for automatic releases)

    - Go to repository Settings → Secrets and variables → Actions
    - Add `GALAXY_API_KEY` with your Ansible Galaxy API token

### Daily Development Workflow

```bash
# Activate venv (if not using Makefile)
source .venv/bin/activate

# Make changes to role
# ... edit files ...

# Test locally
make test-quick

# Commit (pre-commit runs automatically)
git add .
git commit -m "feat: your change"

# Push (CI/CD runs automatically)
git push
```

### Before Pull Request

```bash
# Run full test suite
make test

# Check everything passes
make pre-commit
```

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
2. Review the [QUICK_REFERENCE.md](QUICK_REFERENCE.md) for common commands
3. Review CI/CD logs in GitHub Actions
4. Run tests with debug/verbose flags
5. Open an issue on GitHub with test output

### Related Documentation

- [UNIT_TESTING.md](UNIT_TESTING.md) - Filter plugin unit test reference (pytest)
- [TESTING_SCRIPTS.md](TESTING_SCRIPTS.md) - Helper scripts for test environment setup
- [CONTRIBUTING.md](CONTRIBUTING.md) - Contribution guidelines and workflow
- [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Quick command cheat sheet
- [CHANGELOG.md](CHANGELOG.md) - Version history and changes

---

**Happy Testing! 🧪✅**

All testing infrastructure is now in place with proper virtual environment isolation. Just run `./setup-testing.sh` to get started!
