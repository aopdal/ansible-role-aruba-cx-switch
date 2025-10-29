# Quick Reference - Testing Commands

## Installation & Setup

```bash
# Quick setup - creates venv and installs everything
./setup-testing.sh

# Or use Makefile
make setup

# Manual venv setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-test.txt

# Install pre-commit hooks
pre-commit install
```

## Virtual Environment

```bash
# Activate virtual environment (REQUIRED before running tests)
source .venv/bin/activate

# Deactivate when done
deactivate

# Check if venv is active
which python  # Should show .venv/bin/python

# Delete and recreate venv
make clean-all
make venv
```

## Daily Development Commands

```bash
# Activate venv first!
source .venv/bin/activate

# Before committing
make lint                 # Run all linting
make test-quick          # Quick tests (lint + syntax)

# Pre-commit will auto-run on commit
git commit -m "your message"

# Manual pre-commit check
pre-commit run --all-files
```

## Tag Usage (Production Playbooks)

### Safe Day-to-Day Operations (Won't Touch Routing)

```bash
# Add VLANs (routing protocols skipped)
ansible-playbook configure_aoscx.yml -l switch-name -t vlans

# Update interfaces only
ansible-playbook configure_aoscx.yml -l switch-name -t interfaces

# Base configuration (banner, NTP, DNS, timezone)
ansible-playbook configure_aoscx.yml -l switch-name -t base_config

# LAG configuration
ansible-playbook configure_aoscx.yml -l switch-name -t lag
```

### High-Impact Changes (Require Explicit Tags)

```bash
# BGP configuration (tag-dependent - safe from accidental runs)
ansible-playbook configure_aoscx.yml -l switch-name -t bgp

# OSPF configuration (tag-dependent)
ansible-playbook configure_aoscx.yml -l switch-name -t ospf

# All routing protocols
ansible-playbook configure_aoscx.yml -l switch-name -t routing

# VSX high-availability (tag-dependent)
ansible-playbook configure_aoscx.yml -l switch-name -t vsx
```

### Full Configuration

```bash
# Everything (including routing protocols)
ansible-playbook configure_aoscx.yml -l switch-name

# Check mode (dry-run)
ansible-playbook configure_aoscx.yml -l switch-name --check

# See what tasks will run
ansible-playbook configure_aoscx.yml -l switch-name -t vlans --list-tasks
```

### Verify Tag Behavior

```bash
# Verify VLANs won't include routing (should be empty)
ansible-playbook configure_aoscx.yml -l switch-name -t vlans --list-tasks | grep -E "(BGP|OSPF|VSX)"

# Verify routing tag includes BGP and OSPF (should show 2 lines)
ansible-playbook configure_aoscx.yml -l switch-name -t routing --list-tasks | grep -E "(BGP|OSPF)"
```

### Important Notes

- **Tag-Dependent**: BGP, OSPF, VSX only run when:
    - Explicitly tagged (`-t bgp`, `-t routing`, `-t vsx`)
    - No tags specified (full run)
    - Never run with other tags like `-t vlans`
- **Always Safe**: VLANs, interfaces, LAGs never trigger routing changes
- **Cleanup**: Protected by `aoscx_idempotent_mode` variable

## Testing Commands

**Note:** Makefile handles venv automatically. For manual commands, activate venv first!

```bash
# Using Makefile (recommended - handles venv)
make lint                # yamllint + ansible-lint
make syntax              # Syntax check
make molecule-test       # Molecule tests
make integration         # Integration tests
make test-quick          # lint + syntax (fast)
make test                # All tests including molecule (slow)

# Manual commands (requires active venv)
source .venv/bin/activate
yamllint .               # YAML linting
ansible-lint             # Ansible linting
ansible-playbook tests/test.yml --syntax-check
molecule test            # Molecule tests
```

## Molecule Commands

```bash
# Full workflow
molecule test            # Complete test cycle

# Step by step
molecule create          # Create test container
molecule converge        # Apply role
molecule verify          # Run verifications
molecule destroy         # Clean up

# Debug
molecule --debug test    # Verbose output
molecule login           # SSH into test container
```

## Troubleshooting

```bash
# Clean everything
make clean

# Clean including venv
make clean-all

# Check system info and venv status
make info

# Recreate virtual environment
make clean-all
make venv
make install

# View test results
cat .molecule/default/ansible.log

# Docker issues
docker ps -a             # List containers
molecule destroy         # Clean molecule
docker system prune -f   # Clean Docker
```

## File Locations

| File | Purpose |
|------|---------|
| `.venv/` | Virtual environment (isolated Python) |
| `.ansible-lint` | Ansible linting rules |
| `.yamllint` | YAML linting rules |
| `.pre-commit-config.yaml` | Pre-commit hooks |
| `molecule/default/` | Molecule test scenario |
| `tests/test.yml` | Main test playbook |
| `requirements-test.txt` | Python test dependencies |

## CI/CD

```bash
# View workflow
cat .github/workflows/ci.yml

# Triggers automatically on:
# - Push to main/develop
# - Pull requests
# - Manual workflow dispatch
```

## Documentation

- `TESTING.md` - Full testing guide
- `CONTRIBUTING.md` - Contribution guidelines
- `README.md` - Role documentation

## Common Workflows

### Adding a New Feature

```bash
# 0. Activate venv
source .venv/bin/activate

# 1. Create branch
git checkout -b feature/my-feature

# 2. Make changes
# ... edit files ...

# 3. Test locally
make test-quick

# 4. Commit (pre-commit runs automatically)
git add .
git commit -m "feat: add my feature"

# 5. Push and create PR
git push origin feature/my-feature
```

### Fixing Lint Issues

```bash
# Activate venv
source .venv/bin/activate

# Auto-fix what's possible
ansible-lint --fix

# Check specific files
yamllint path/to/file.yml
ansible-lint path/to/playbook.yml

# Format Python code
black filter_plugins/
```

### Running Tests for Specific Ansible Version

```bash
# In CI, tests run on 2.14, 2.15, 2.16 automatically
# Locally with specific version:
pip install ansible-core==2.15.0
ansible-playbook tests/test.yml --syntax-check
```

## Help

```bash
make help                # Show all make commands
molecule --help          # Molecule help
ansible-lint --help      # Ansible-lint help
pre-commit --help        # Pre-commit help
```

## Links

- Testing Docs: `TESTING.md`
- Contributing: `CONTRIBUTING.md`
- GitHub Actions: `.github/workflows/ci.yml`
- Molecule Config: `molecule/default/molecule.yml`
