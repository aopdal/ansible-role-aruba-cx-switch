# SSH Agent Quick Fix for Dev Container

## Problem
SSH agent suddenly stops working in dev container while it works fine in WSL2.

## Quick Solution ✅

### **Immediate Fix (One Command)**
```bash
export SSH_AUTH_SOCK=$(find /tmp -name "vscode-ssh-auth-*.sock" 2>/dev/null | head -1) && ssh-add -l
```

### **Step-by-Step Fix**

1. **Check what's broken:**
   ```bash
   ssh-add -l
   echo $SSH_AUTH_SOCK
   ```

2. **Find VS Code's SSH socket:**
   ```bash
   find /tmp -name "vscode-ssh-auth-*.sock"
   ```

3. **Connect to it:**
   ```bash
   export SSH_AUTH_SOCK=/tmp/vscode-ssh-auth-XXXXX.sock
   ssh-add -l
   ```

4. **Make it permanent for new terminals:**
   ```bash
   echo "export SSH_AUTH_SOCK=$(find /tmp -name "vscode-ssh-auth-*.sock" | head -1)" >> ~/.bashrc
   ```

## Why This Happens

VS Code creates its own SSH agent socket forwarding from WSL2 to the dev container. The socket path is:
- **Format**: `/tmp/vscode-ssh-auth-XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX.sock`
- **Created by**: VS Code's remote container extension
- **Forwards from**: WSL2's SSH agent
- **Problem**: The `SSH_AUTH_SOCK` environment variable points to the wrong/old path

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

The script now checks for VS Code's socket **first** before trying other methods:

1. ✅ VS Code SSH agent socket (`/tmp/vscode-ssh-auth-*.sock`)
2. ✅ WSL2 SSH agent socket (`/mnt/wslg/runtime-dir/ssh-agent.sock`)
3. ✅ Existing agent sockets in `/tmp/ssh-*/agent.*`
4. ✅ Start new agent as last resort

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

2. **Find the VS Code socket quickly:**
   ```bash
   env | grep REMOTE_CONTAINERS_SOCKETS
   ```

3. **Auto-fix on every shell startup:**
   Add to `~/.bashrc`:
   ```bash
   export SSH_AUTH_SOCK=$(find /tmp -name "vscode-ssh-auth-*.sock" 2>/dev/null | head -1)
   ```

## Related Files

- `.devcontainer/reconnect-ssh.sh` - Automated reconnection script
- `.devcontainer/ssh-agent-setup.sh` - Shell profile setup
- `.devcontainer/SSH_TROUBLESHOOTING.md` - Full troubleshooting guide
- `.devcontainer/devcontainer.json` - Dev container SSH configuration
