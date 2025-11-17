# SSH Agent Quick Fix for Dev Container

## Problem
SSH agent suddenly stops working in dev container while it works fine in WSL2.

## Quick Solution ✅

### **Immediate Fix (One Command)**
```bash
# The dev container mounts SSH agent at /ssh-agent
export SSH_AUTH_SOCK=/ssh-agent && ssh-add -l

# Fallback if mount not available: find VS Code socket
export SSH_AUTH_SOCK=$(find /tmp -name "vscode-ssh-auth-*.sock" 2>/dev/null | head -1) && ssh-add -l
```

### **Step-by-Step Fix**

1. **Check what's broken:**
   ```bash
   ssh-add -l
   echo $SSH_AUTH_SOCK
   ls -la $SSH_AUTH_SOCK
   ```

2. **Try the mounted SSH agent first (new approach):**
   ```bash
   export SSH_AUTH_SOCK=/ssh-agent
   ssh-add -l
   ```

3. **Fallback: Find VS Code's dynamic SSH socket:**
   ```bash
   find /tmp -name "vscode-ssh-auth-*.sock"
   export SSH_AUTH_SOCK=/tmp/vscode-ssh-auth-XXXXX.sock
   ssh-add -l
   ```

4. **Make it permanent for new terminals:**
   ```bash
   # Prefer mounted agent (set by devcontainer.json)
   echo "export SSH_AUTH_SOCK=/ssh-agent" >> ~/.bashrc
   ```

## Why This Happens

The dev container now uses a direct SSH agent socket mount:
- **Mount point**: `/ssh-agent` (configured in `devcontainer.json`)
- **Source**: `${localEnv:SSH_AUTH_SOCK}` from your host/WSL2
- **Environment**: `SSH_AUTH_SOCK=/ssh-agent` is set automatically
- **Benefit**: More reliable than VS Code's dynamic sockets

**Fallback**: VS Code still creates dynamic sockets if needed:
- **Format**: `/tmp/vscode-ssh-auth-XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX.sock`
- **Created by**: VS Code's remote container extension
- **Problem**: The `SSH_AUTH_SOCK` environment variable might point to wrong/old path

## Automated Solution

Use the reconnection script:
```bash
/workspaces/ansible-role-aruba-cx-switch/.devcontainer/reconnect-ssh.sh
```

Or use the alias:
```bash
ssh-reconnect
```

## Prevention

The script now checks for the mounted agent **first** before trying fallback methods:

1. ✅ Mounted SSH agent socket (`/ssh-agent`) - **New approach**
2. ✅ VS Code SSH agent socket (`/tmp/vscode-ssh-auth-*.sock`) - Fallback
3. ✅ Start new agent as last resort

The dev container configuration (`devcontainer.json`) mounts your host SSH agent directly at `/ssh-agent`.

## Verification

After reconnecting, verify it works:
```bash
# Check keys are loaded
ssh-add -l

# Test GitHub connection
ssh -T git@github.com

# Test git operations
git fetch --dry-run
```

## Environment Info

The dev container has these SSH-related environment variables:
```bash
SSH_AUTH_SOCK=/path/to/socket
REMOTE_CONTAINERS_SOCKETS=["/tmp/vscode-ssh-auth-XXX.sock",...]
```

The `REMOTE_CONTAINERS_SOCKETS` variable contains the actual VS Code socket path!

## Pro Tips

1. **Quick check if SSH works:**
   ```bash
   ssh-add -l && echo "✅ Working" || echo "❌ Broken"
   ```

2. **Check the mounted SSH agent:**
   ```bash
   ls -la /ssh-agent
   SSH_AUTH_SOCK=/ssh-agent ssh-add -l
   ```

3. **Find the VS Code socket quickly (fallback):**
   ```bash
   env | grep REMOTE_CONTAINERS_SOCKETS
   find /tmp -name "vscode-ssh-auth-*.sock"
   ```

4. **Verify devcontainer mount:**
   ```bash
   echo "Host SSH_AUTH_SOCK: $(echo $SSH_AUTH_SOCK)"
   echo "Container mount: /ssh-agent"
   [ -S /ssh-agent ] && echo "✅ Mount exists" || echo "❌ Mount missing"
   ```

## Related Files

- `.devcontainer/reconnect-ssh.sh` - Automated reconnection script
- `.devcontainer/ssh-agent-setup.sh` - Shell profile setup
- `.devcontainer/SSH_TROUBLESHOOTING.md` - Full troubleshooting guide
- `.devcontainer/devcontainer.json` - Dev container SSH configuration
