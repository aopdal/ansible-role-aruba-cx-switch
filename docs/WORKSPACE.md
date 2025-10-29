# Multi-Folder Workspace Setup

This workspace includes multiple folders for convenient development across related projects.

## Quick Start

### Option 1: Open Workspace File (Recommended)

**Inside the devcontainer:**

1. **File** → **Open Workspace from File**
2. Select `ansible-workspace.code-workspace`
3. Click **Open**

Your Explorer will show all mounted folders! 🎉

### Option 2: Manual Setup

If you prefer to add folders manually:

1. **File** → **Add Folder to Workspace**
2. Browse to `/workspaces/aruba-role-testing`
3. Click **OK**
4. Repeat for other folders

## Included Folders

The workspace includes:

- **🎭 Ansible Role - Aruba CX Switch** (`.`)
    - The main role repository
    - Read/Write access

- **🧪 Test Environment** (`/workspaces/aruba-role-testing`)
    - Your testing environment with inventory and playbooks
    - Read/Write access
    - Location: `~/code/aruba-role-testing` on host

- **📚 Auto NetOps** (`/workspaces/auto-netops-ansible`)
    - Reference repository (read-only)
    - Location: `~/code/auto-netops-ansible` on host

## Customization

Edit `ansible-workspace.code-workspace` to:

```json
{
  "folders": [
    {
      "name": "My Custom Name",
      "path": "/workspaces/my-folder"
    }
  ]
}
```

Changes take effect after reloading: **F1** → **"Developer: Reload Window"**

## Adding Your Own Mounts

### Step 1: Add Mount to devcontainer.json

```json
"mounts": [
  "source=${localEnv:HOME}/my-project,target=/workspaces/my-project,type=bind"
]
```

### Step 2: Add to Workspace File

```json
{
  "folders": [
    {
      "name": "My Project",
      "path": "/workspaces/my-project"
    }
  ]
}
```

### Step 3: Rebuild Container

**F1** → **"Dev Containers: Rebuild Container"**

## Benefits

- ✅ See all projects in one Explorer view
- ✅ Search across multiple projects
- ✅ Share configuration between projects
- ✅ Navigate between related code easily
- ✅ Copy/paste between projects

## Troubleshooting

### Folder Not Showing

**Problem:** Mounted folder doesn't appear in Explorer

**Solution:**

1. Verify the mount exists: `ls /workspaces/`
2. Add to workspace: File → Add Folder to Workspace
3. Check `ansible-workspace.code-workspace` for correct path

### Permission Issues

**Problem:** Can't edit files in mounted folder

**Solution:**

Check folder ownership on host:

```bash
# On host machine
ls -la ~/code/aruba-role-testing
sudo chown -R $USER:$USER ~/code/aruba-role-testing
```

Then rebuild: **F1** → **"Dev Containers: Rebuild Container"**

### Mount Not Available

**Problem:** Folder doesn't exist at `/workspaces/folder-name`

**Solution:**

1. Check host path exists: `ls ~/code/aruba-role-testing`
2. Check `.devcontainer/devcontainer.json` mounts section
3. Rebuild container

## See Also

- [DEVCONTAINER_MOUNTS.md](DEVCONTAINER_MOUNTS.md) - Detailed mount configuration guide
- [DEVELOPMENT.md](DEVELOPMENT.md) - Development workflow
