# SSH Agent Troubleshooting Guide for Dev Containers

## Problem Description
KeePassXC locks/unlocks causing SSH agent connection to break between Windows → WSL2 → Dev Container.

## Quick Diagnosis
```bash
# Check SSH agent status
ssh-add -l
echo $SSH_AUTH_SOCK
ls -la $SSH_AUTH_SOCK

# Check if socket is responsive
ssh-add -l >/dev/null 2>&1 && echo "✅ Working" || echo "❌ Broken"
```

## 🚀 **Quick Fixes** (Try in order)

### 1. **Reconnect Script** (Recommended)
```bash
# Use the provided reconnection script
/workspaces/ansible-role-aruba-cx-switch/.devcontainer/reconnect-ssh.sh

# Or create alias and use
alias ssh-reconnect="/workspaces/ansible-role-aruba-cx-switch/.devcontainer/reconnect-ssh.sh"
ssh-reconnect
```

### 2. **Manual WSL2 Agent Reconnection**
```bash
# Find WSL2 SSH agent socket
export SSH_AUTH_SOCK=$(find /mnt/wslg/runtime-dir -name "ssh-agent.sock" 2>/dev/null | head -1)
ssh-add -l
```

### 3. **Restart SSH Agent**
```bash
# Kill and restart
pkill -f ssh-agent
eval $(ssh-agent -s)
ssh-add
```

### 4. **Find Working Agent Socket**
```bash
# Search for working agent sockets
for sock in /tmp/ssh-*/agent.*; do
    if [ -S "$sock" ]; then
        SSH_AUTH_SOCK="$sock" ssh-add -l 2>/dev/null && {
            export SSH_AUTH_SOCK="$sock"
            echo "Found working agent: $sock"
            break
        }
    fi
done
```

## 🛠️ **Permanent Solutions**

### 1. **Auto-Reconnection Setup**
Add to your `~/.bashrc` or `~/.zshrc`:
```bash
# Source the SSH agent setup
source /workspaces/ansible-role-aruba-cx-switch/.devcontainer/ssh-agent-setup.sh
```

### 2. **KeePassXC SSH Agent Settings**
In KeePassXC:
- Tools → Settings → SSH Agent
- ✅ Enable SSH Agent integration
- ✅ Use OpenSSH for Windows instead of Pageant
- ✅ Add key to agent when database is opened/unlocked

### 3. **WSL2 SSH Agent Persistence**
In WSL2, add to `~/.bashrc`:
```bash
# Start SSH agent if not running
if ! pgrep -x ssh-agent > /dev/null; then
    eval $(ssh-agent -s) > /dev/null
fi

# Add KeePassXC integration
if command -v keepassxc.proxy >/dev/null 2>&1; then
    export SSH_AUTH_SOCK="$HOME/.ssh/agent.sock"
fi
```

### 4. **Dev Container SSH Agent Forwarding**
Ensure your `.devcontainer/devcontainer.json` includes:
```json
{
  "remoteEnv": {
    "SSH_AUTH_SOCK": "${localEnv:SSH_AUTH_SOCK}"
  },
  "mounts": [
    "source=/tmp,target=/tmp,type=bind"
  ]
}
```

## 🔍 **Debugging Steps**

### Windows Level
```powershell
# In PowerShell - check if agent is running
Get-Process ssh-agent
ssh-add -l
```

### WSL2 Level
```bash
# In WSL2 - check agent
ps aux | grep ssh-agent
ssh-add -l
echo $SSH_AUTH_SOCK
```

### Dev Container Level
```bash
# In Dev Container - full diagnostic
echo "SSH_AUTH_SOCK: $SSH_AUTH_SOCK"
ls -la $SSH_AUTH_SOCK 2>/dev/null || echo "Socket not found"
ssh-add -l 2>/dev/null || echo "Agent not responsive"
ps aux | grep ssh-agent
find /tmp -name "*ssh*" -type d 2>/dev/null
```

## 🎯 **Root Cause Solutions**

### Option A: **KeePassXC Agent Bridge**
Use a bridge service that maintains the SSH agent connection:
```bash
# Install ssh-agent-bridge (if available)
sudo apt update
sudo apt install socat

# Create persistent bridge
socat UNIX-LISTEN:/tmp/ssh-agent-bridge,fork UNIX-CONNECT:$SSH_AUTH_SOCK &
export SSH_AUTH_SOCK=/tmp/ssh-agent-bridge
```

### Option B: **Persistent SSH Agent Service**
Create a systemd service in WSL2 to keep SSH agent running:
```bash
# Create service file
sudo tee /etc/systemd/user/ssh-agent.service << EOF
[Unit]
Description=SSH Agent
Documentation=man:ssh-agent(1)

[Service]
Type=simple
Environment=SSH_AUTH_SOCK=%t/ssh-agent.socket
ExecStart=/usr/bin/ssh-agent -D -a %t/ssh-agent.socket
ExecReload=/bin/kill -HUP \$MAINPID
KillMode=mixed

[Install]
WantedBy=default.target
EOF

# Enable and start
systemctl --user enable ssh-agent.service
systemctl --user start ssh-agent.service
```

### Option C: **VS Code SSH Agent Extension**
Install VS Code extension for better SSH agent handling:
- **SSH Agent** extension by fabric-io-rodrigues
- **Remote - SSH** with proper agent forwarding

## 📝 **Prevention Tips**

1. **Lock KeePassXC Less**: Use longer auto-lock timeouts
2. **Use SSH Key Passphrases**: Less reliance on KeePassXC locking
3. **Multiple SSH Keys**: Have backup keys available
4. **SSH Config**: Use `AddKeysToAgent yes` in `~/.ssh/config`

## ⚡ **Emergency Workaround**
If nothing works, clone with HTTPS and use personal access token:
```bash
git remote set-url origin https://github.com/aopdal/ansible-role-aruba-cx-switch.git
# Then use GitHub personal access token for authentication
```

## 🚨 **When to Reload Dev Container**
Only reload if:
- Dev container networking is completely broken
- File system mounts are corrupted
- Container process table is corrupted
- SSH fixes above don't work after 5+ minutes

The SSH agent issue is usually fixable without full container reload! 🎯
