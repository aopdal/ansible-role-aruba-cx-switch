# Dev Container Setup

This project includes a VS Code Dev Container configuration that provides a complete, pre-configured development environment for working with the Aruba AOS-CX Switch Ansible role.

## What is a Dev Container?

A dev container is a Docker container configured with all the tools, libraries, and runtime needed for development. It provides a consistent, reproducible environment that works the same on Windows, Mac, and Linux.

## Files in `.devcontainer/`

- **`devcontainer.json`** - Main configuration
  - Python 3.12 base image
  - Docker-in-Docker support for Molecule tests
  - Pre-configured VS Code extensions
  - Automatic dependency installation
  - Custom VS Code settings for Ansible development

- **`Dockerfile`** - Custom container image
  - System dependencies (Docker, Git, network tools)
  - Pre-commit installation
  - Bash completion for Ansible
  - Helpful command aliases
  - Welcome message

- **`post-create.sh`** - Initialization script
  - Installs Python packages from `requirements-test.txt`
  - Installs Ansible collections from `requirements.yml`
  - Sets up pre-commit hooks
  - Shows quick start commands

## Quick Start

1. Install [VS Code](https://code.visualstudio.com/) and [Docker](https://www.docker.com/get-started)
2. Install the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
3. Open this project in VS Code
4. Click "Reopen in Container" when prompted (or F1 → "Dev Containers: Reopen in Container")
5. Wait 2-3 minutes for the initial build
6. Start developing — everything is ready

## What's Included

### Tools & Runtimes

- Python 3.12
- Ansible & ansible-lint
- Molecule with Docker driver
- yamllint
- pre-commit
- Git & Git LFS
- Docker-in-Docker (for Molecule tests)
- Network tools (ping, netcat, curl)

### VS Code Extensions

- `redhat.ansible` — Ansible syntax, validation, linting
- `redhat.vscode-yaml` — YAML language support and schemas
- `ms-python.python` — Python debugging and IntelliSense
- `ms-python.vscode-pylance` — Python type checking
- `ms-python.black-formatter` — Python formatting
- `charliermarsh.ruff` — Fast Python linting
- `eamodio.gitlens` — Git visualization
- `mhutchie.git-graph` — Git graph view
- `usernamehw.errorlens` — Inline error display
- `streetsidesoftware.code-spell-checker` — Spell checking
- `oderwat.indent-rainbow` — Indentation visualization

### Pre-configured VS Code Settings

- Python default interpreter set to venv
- Ansible validation enabled
- YAML schemas for Ansible files
- Format on save enabled
- 120-character ruler
- Terminal defaults

### Environment Variables

```bash
ANSIBLE_FORCE_COLOR=true        # Colored Ansible output
ANSIBLE_HOST_KEY_CHECKING=false # Skip SSH host key checking
PY_COLORS=1                     # Colored Python output
PYTHONUNBUFFERED=1              # Unbuffered Python output
```

### Helpful Aliases

```bash
ll                # ls -lah
ansible-test      # Shortcut for molecule test
ansible-converge  # Shortcut for molecule converge
```

## Testing in the Dev Container

All test commands work immediately — no venv activation needed:

```bash
make test-quick        # Lint + syntax check
make test-unit         # pytest unit tests
make test              # Full test suite including Molecule
make test-unit-coverage # Unit tests with HTML coverage report
ansible-lint
yamllint .
molecule test
pre-commit run --all-files
```

## Customization

### Add VS Code Extensions

Edit `.devcontainer/devcontainer.json`:

```json
{
  "customizations": {
    "vscode": {
      "extensions": [
        "your.extension-id"
      ]
    }
  }
}
```

### Add System Packages

Edit `.devcontainer/Dockerfile`:

```dockerfile
RUN apt-get update && apt-get install -y \
    your-package \
    && apt-get clean
```

### Change Python Version

Edit `.devcontainer/devcontainer.json`:

```json
{
  "build": {
    "args": {
      "VARIANT": "3.12"
    }
  }
}
```

## Comparison: Dev Container vs Traditional venv

| Aspect | Dev Container | Traditional venv |
|--------|--------------|------------------|
| Setup Time | 2-3 minutes (automatic) | 5-10 minutes (manual) |
| Consistency | Identical for all devs | Can vary by system |
| Dependencies | All included | Manual installation |
| VS Code Setup | Extensions included | Install separately |
| Isolation | Complete container | Python packages only |
| Cross-platform | Works everywhere | OS-specific issues |
| Onboarding | One click | Follow setup guide |
| Docker Required | Yes | No |

## Troubleshooting

### Container won't build

```bash
docker ps                     # Ensure Docker is running
docker system df              # Check disk space
docker system prune           # Clean up old images
# F1 → "Dev Containers: Rebuild Container"
```

### Container is slow

- Increase Docker memory/CPU in Docker Desktop settings
- On Windows, use WSL 2 backend
- Close other running containers

### Extensions not installing

- Rebuild container: F1 → "Dev Containers: Rebuild Container"
- Manually install via Extensions panel → "Install in Container"

### Port conflicts

Check `devcontainer.json` `forwardPorts` and verify the ports are free:

```bash
lsof -i :8080          # macOS/Linux
netstat -ano | findstr :8080  # Windows
```

## Resources

- [VS Code Dev Containers Documentation](https://code.visualstudio.com/docs/devcontainers/containers)
- [Dev Container Specification](https://containers.dev/)
- [Dev Containers Extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
- [Microsoft Dev Container Images](https://github.com/devcontainers/images)

See also [DEVELOPMENT.md](DEVELOPMENT.md) for the full development guide.
