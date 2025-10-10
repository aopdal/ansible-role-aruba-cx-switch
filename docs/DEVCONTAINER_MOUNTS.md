# Adding Additional Folders to Devcontainer Workspace

This guide explains how to access other folders/projects alongside your role in the devcontainer.

## Why You Might Need This

- Access your test environment (e.g., `~/code/aruba-role-testing`)
- Work with multiple related repositories
- Share configuration files or scripts
- Access NetBox data or other resources

## Method 1: Mount Additional Folders (Recommended)

### Step 1: Edit `.devcontainer/devcontainer.json`

Add the `mounts` section:

```jsonc
{
  "name": "Ansible Role Development - Aruba AOS-CX",
  "build": { ... },

  "mounts": [
    // Mount your test environment
    "source=${localEnv:HOME}/code/aruba-role-testing,target=/workspaces/aruba-role-testing,type=bind",

    // Mount another project
    "source=${localEnv:HOME}/projects/netbox-data,target=/workspaces/netbox-data,type=bind,readonly"
  ],

  "features": { ... }
}
```

### Step 2: Rebuild Container

1. Press **F1**
2. Type: **"Dev Containers: Rebuild Container"**
3. Press Enter

### Step 3: Access Your Folder

The folder will be available at `/workspaces/your-folder-name`:

```bash
cd /workspaces/aruba-role-testing
ls -la
```

### Mount Syntax

```
"source=SOURCE_PATH,target=TARGET_PATH,type=bind[,readonly][,consistency=CONSISTENCY]"
```

**Parameters:**
- `source`: Path on your host machine
  - Use `${localEnv:HOME}` for home directory
  - Use `${localWorkspaceFolder}` for current workspace
  - Use absolute path like `/home/username/project`

- `target`: Path inside the container (usually `/workspaces/folder-name`)

- `type=bind`: Mount type (bind, volume, tmpfs)

- `readonly` (optional): Mount as read-only

- `consistency` (optional): `cached`, `delegated`, or `consistent` (for Mac performance)

### Examples

```jsonc
"mounts": [
  // Basic mount
  "source=${localEnv:HOME}/test-env,target=/workspaces/test-env,type=bind",

  // Read-only mount
  "source=${localEnv:HOME}/shared-config,target=/workspaces/config,type=bind,readonly",

  // With consistency (Mac performance)
  "source=${localEnv:HOME}/large-project,target=/workspaces/large-project,type=bind,consistency=cached",

  // Absolute path
  "source=/opt/shared/tools,target=/workspaces/tools,type=bind",

  // Environment variable
  "source=${localEnv:PROJECT_DIR},target=/workspaces/project,type=bind"
]
```

## Method 2: Multi-Root Workspace (Show Mounts in Explorer)

To see mounted folders in the VS Code Explorer sidebar, use a workspace file.

### Step 1: Create Workspace File

A workspace file `ansible-workspace.code-workspace` is already provided in the repository:

```json
{
  "folders": [
    {
      "name": "🎭 Ansible Role - Aruba CX Switch",
      "path": "."
    },
    {
      "name": "🧪 Test Environment",
      "path": "/workspaces/aruba-role-testing"
    },
    {
      "name": "📚 Auto NetOps (read-only)",
      "path": "/workspaces/auto-netops-ansible"
    }
  ],
  "settings": {
    "python.defaultInterpreterPath": "/usr/local/bin/python"
  }
}
```

### Step 2: Open Workspace in Devcontainer

**Inside the devcontainer:**

1. **File** → **Open Workspace from File**
2. Select `ansible-workspace.code-workspace`
3. Click **Open**

The Explorer will now show all three folders! 🎉

**Result:**
```
EXPLORER
├── 🎭 Ansible Role - Aruba CX Switch
│   ├── tasks/
│   ├── defaults/
│   └── ...
├── 🧪 Test Environment
│   ├── inventory/
│   ├── playbooks/
│   └── ...
└── 📚 Auto NetOps (read-only)
    ├── roles/
    └── ...
```

### Step 3: Customize Folder Names

Edit `ansible-workspace.code-workspace` to:
- Change folder display names (the `name` field)
- Add emojis for visual distinction
- Remove folders you don't need

**Note:** After editing the workspace file, reload the window (F1 → "Developer: Reload Window") to see changes.

### Alternative: Add Folders Manually
  }
}
```

### Step 2: Open Workspace

1. File → Open Workspace from File
2. Select `ansible-workspace.code-workspace`
3. Reopen in Container when prompted

**Note:** With this method, only the first folder gets mounted in the container by default. You still need mounts for other folders.

## Method 3: Git Clone Inside Container

Clone additional repositories inside the container:

```bash
# Inside the devcontainer
cd /workspaces
git clone https://github.com/your-org/other-repo.git
cd other-repo
```

**Pros:**
- Simple, no configuration needed
- Works for any repository

**Cons:**
- Changes are lost when container is rebuilt (unless you commit them)
- Need to reclone after rebuild

## Method 4: Use `workspaceMount` for Main Folder

If you want to change where the **main** workspace folder is mounted:

```jsonc
{
  "workspaceMount": "source=${localWorkspaceFolder},target=/workspace/my-role,type=bind",
  "workspaceFolder": "/workspace/my-role",
  // ... rest of config
}
```

## Common Use Cases

### Use Case 1: Access Test Environment

```jsonc
"mounts": [
  "source=${localEnv:HOME}/code/aruba-role-testing,target=/workspaces/test-env,type=bind"
]
```

Then in your playbooks:
```yaml
# Use files from mounted test environment
inventory: /workspaces/test-env/inventory/hosts.yml
```

### Use Case 2: Share SSH Keys

```jsonc
"mounts": [
  "source=${localEnv:HOME}/.ssh,target=/home/vscode/.ssh,type=bind,readonly"
]
```

### Use Case 3: Share AWS/Cloud Credentials

```jsonc
"mounts": [
  "source=${localEnv:HOME}/.aws,target=/home/vscode/.aws,type=bind,readonly",
  "source=${localEnv:HOME}/.config/gcloud,target=/home/vscode/.config/gcloud,type=bind,readonly"
]
```

### Use Case 4: Development Scripts

```jsonc
"mounts": [
  "source=${localEnv:HOME}/scripts,target=/workspaces/scripts,type=bind,readonly"
]
```

## Best Practices

### 1. Use Environment Variables

```jsonc
// Set in your shell profile
export TEST_ENV_PATH="$HOME/code/aruba-role-testing"

// Then use in devcontainer.json
"mounts": [
  "source=${localEnv:TEST_ENV_PATH},target=/workspaces/test-env,type=bind"
]
```

### 2. Document Your Mounts

Add comments in devcontainer.json:

```jsonc
"mounts": [
  // Test environment - Required for running integration tests
  "source=${localEnv:HOME}/code/aruba-role-testing,target=/workspaces/test-env,type=bind",

  // Shared Ansible collections - Optional
  "source=${localEnv:HOME}/.ansible/collections,target=/workspaces/collections,type=bind,readonly"
]
```

### 3. Use Read-Only When Possible

Prevents accidental modifications:

```jsonc
"mounts": [
  "source=${localEnv:HOME}/config,target=/workspaces/config,type=bind,readonly"
]
```

### 4. Handle Missing Paths Gracefully

The container will fail to start if a mounted path doesn't exist. Options:

**Option A:** Create the path first
```bash
mkdir -p ~/code/aruba-role-testing
```

**Option B:** Use postCreateCommand to create it
```jsonc
"postCreateCommand": "mkdir -p /workspaces/test-env || true; bash .devcontainer/post-create.sh"
```

**Option C:** Document in README
```markdown
## Setup
Before opening in devcontainer, ensure these folders exist:
- `~/code/aruba-role-testing`
```

## Troubleshooting

### Mount Point Doesn't Exist

**Error:** `path ... does not exist`

**Solution:**
```bash
# On your host machine
mkdir -p ~/code/aruba-role-testing
```

### Permission Issues

**Error:** `permission denied`

**Solution 1:** Ensure folder is owned by your user:
```bash
sudo chown -R $USER:$USER ~/code/aruba-role-testing
```

**Solution 2:** Add to devcontainer.json:
```jsonc
"remoteUser": "vscode",
"containerUser": "vscode"
```

### Changes Not Appearing

**Solution:** Rebuild container:
1. F1 → "Dev Containers: Rebuild Container"

### Path with Spaces

Escape spaces or use quotes:
```jsonc
// Method 1: Escape
"source=${localEnv:HOME}/My\\ Projects/test,target=/workspaces/test,type=bind"

// Method 2: Quotes (may not work in all contexts)
"source=\"${localEnv:HOME}/My Projects/test\",target=/workspaces/test,type=bind"

// Best: Use paths without spaces
```

## Example Configuration

Here's a complete example for Ansible development:

```jsonc
{
  "name": "Ansible Role Development - Aruba AOS-CX",
  "build": {
    "dockerfile": "Dockerfile",
    "args": { "VARIANT": "3.12" }
  },

  "mounts": [
    // Test environment with inventory and playbooks
    "source=${localEnv:HOME}/code/aruba-role-testing,target=/workspaces/test-env,type=bind",

    // Shared Ansible collections (read-only)
    "source=${localEnv:HOME}/.ansible/collections,target=/workspaces/ansible-collections,type=bind,readonly",

    // SSH keys for connecting to switches
    "source=${localEnv:HOME}/.ssh,target=/home/vscode/.ssh,type=bind,readonly",

    // NetBox configuration data
    "source=${localEnv:HOME}/netbox-data,target=/workspaces/netbox-data,type=bind"
  ],

  "containerEnv": {
    "TEST_ENV_PATH": "/workspaces/test-env",
    "NETBOX_DATA_PATH": "/workspaces/netbox-data"
  },

  "postCreateCommand": "bash .devcontainer/post-create.sh",

  // ... rest of configuration
}
```

## See Also

- [VS Code Dev Containers Documentation](https://code.visualstudio.com/docs/devcontainers/containers)
- [Docker Bind Mounts](https://docs.docker.com/storage/bind-mounts/)
- [DEVELOPMENT.md](DEVELOPMENT.md) - General development guide
