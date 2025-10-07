# Dev Container Configuration

This directory contains the VS Code Dev Container configuration for the Aruba AOS-CX Switch Ansible role.

## What is a Dev Container?

A dev container is a Docker container configured with all the tools, libraries, and runtime needed for development. It provides a consistent, reproducible development environment that works the same for everyone on any platform (Windows, Mac, Linux).

## Files in this Directory

- **`devcontainer.json`** - Main configuration file for VS Code Dev Containers
  - Defines the container configuration
  - Specifies VS Code extensions to install
  - Sets environment variables
  - Configures VS Code settings

- **`Dockerfile`** - Custom Docker image definition
  - Based on Microsoft's official Python dev container image
  - Installs system dependencies (Docker, Git, network tools)
  - Sets up bash completion and helpful aliases
  - Configures the vscode user

- **`post-create.sh`** - Post-creation setup script
  - Runs after the container is created
  - Installs Python packages from `requirements-test.txt`
  - Installs Ansible collections from `requirements.yml`
  - Sets up pre-commit hooks
  - Displays helpful information

## Quick Start

1. Install [VS Code](https://code.visualstudio.com/) and [Docker](https://www.docker.com/get-started)
2. Install the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
3. Open this project in VS Code
4. When prompted, click "Reopen in Container" (or press F1 → "Dev Containers: Reopen in Container")
5. Wait for the container to build (first time takes 2-3 minutes)
6. Start developing!

## What's Included

### Tools & Runtimes

- Python 3.12
- Ansible & ansible-lint
- Molecule (with Docker driver)
- yamllint
- pre-commit
- Git & Git LFS
- Docker-in-Docker (for Molecule tests)

### VS Code Extensions
- Ansible (syntax, validation, linting)
- YAML (language support, schemas)
- Python (debugging, IntelliSense)
- GitLens (Git visualization)
- Error Lens (inline error display)
- Code Spell Checker
- Ruff (Python linting)

### Environment Variables
```bash
ANSIBLE_FORCE_COLOR=true        # Colored Ansible output
ANSIBLE_HOST_KEY_CHECKING=false # Skip SSH host key checking
PY_COLORS=1                     # Colored Python output
PYTHONUNBUFFERED=1              # Unbuffered Python output
```

### Helpful Aliases
```bash
ll                # List files with details (ls -lah)
ansible-test      # Shortcut for molecule test
ansible-converge  # Shortcut for molecule converge
```

## Customization

You can customize the dev container by editing `devcontainer.json`:

### Add More VS Code Extensions

```json
{
  "customizations": {
    "vscode": {
      "extensions": [
        "existing.extensions",
        "your.new-extension"
      ]
    }
  }
}
```

### Add More Tools

Edit `Dockerfile` to install additional system packages:

```dockerfile
RUN apt-get update && apt-get install -y \
    your-package-here \
    && apt-get clean
```

### Change Python Version

Edit the `VARIANT` argument in `devcontainer.json`:

```json
{
  "build": {
    "args": {
      "VARIANT": "3.12"  // Change to desired Python version
    }
  }
}
```

## Troubleshooting

### Container Won't Build

1. Ensure Docker is running: `docker ps`
2. Rebuild from scratch: F1 → "Dev Containers: Rebuild Container"
3. Check Docker disk space: `docker system df`
4. Clean up old images: `docker system prune`

### Container is Slow

1. Increase Docker memory/CPU in Docker Desktop settings
2. On Windows, use WSL 2 backend
3. Close other Docker containers

### Extensions Not Installing

1. Check VS Code extension marketplace is accessible
2. Rebuild container: F1 → "Dev Containers: Rebuild Container"
3. Manually install: Extensions panel → Install in Container

### Port Conflicts

If you see port binding errors, check `devcontainer.json` `forwardPorts` and ensure they're not in use:

```bash
# Check what's using a port (example: port 8080)
lsof -i :8080  # macOS/Linux
netstat -ano | findstr :8080  # Windows
```

## Resources

- [VS Code Dev Containers Documentation](https://code.visualstudio.com/docs/devcontainers/containers)
- [Dev Container Specification](https://containers.dev/)
- [Dev Containers Extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
- [Microsoft Dev Container Images](https://github.com/devcontainers/images)

## Benefits Over Traditional Setup

| Aspect | Dev Container | Traditional venv |
|--------|--------------|------------------|
| Setup Time | 2-3 minutes (automatic) | 5-10 minutes (manual) |
| Consistency | ✅ Identical for all devs | ❌ Can vary by system |
| Dependencies | ✅ All included | ❌ Manual installation |
| Updates | ✅ Pull new container | ❌ Update each tool |
| Isolation | ✅ Complete isolation | ⚠️  Python packages only |
| Cross-platform | ✅ Works everywhere | ⚠️  OS-specific issues |
| Onboarding | ✅ One click | ❌ Follow setup guide |

---

**Happy Coding! 🚀**

For more information, see [DEVELOPMENT.md](../DEVELOPMENT.md) in the root directory.
