#!/bin/bash
# SSH Agent Reconnection Script for Dev Container
# Usage: ./reconnect-ssh.sh

echo "🔐 Reconnecting SSH Agent..."

# Method 1: Try VS Code's SSH agent socket
VSCODE_SSH_SOCK=$(find /tmp -name "vscode-ssh-auth-*.sock" 2>/dev/null | head -1)
if [ -n "$VSCODE_SSH_SOCK" ] && [ -S "$VSCODE_SSH_SOCK" ]; then
    export SSH_AUTH_SOCK="$VSCODE_SSH_SOCK"
    echo "✅ Connected to VS Code SSH agent: $SSH_AUTH_SOCK"
    if ssh-add -l >/dev/null 2>&1; then
        echo "✅ SSH keys available!"
        ssh-add -l
        # Make it permanent for this session
        echo "export SSH_AUTH_SOCK=$SSH_AUTH_SOCK" > ~/.ssh-env
        exit 0
    fi
fi

# Method 2: Try to reconnect to existing WSL2 agent
WSL_SSH_SOCK=$(find /mnt/wslg/runtime-dir -name "ssh-agent.sock" 2>/dev/null | head -1)
if [ -n "$WSL_SSH_SOCK" ] && [ -S "$WSL_SSH_SOCK" ]; then
    export SSH_AUTH_SOCK="$WSL_SSH_SOCK"
    echo "✅ Connected to WSL2 SSH agent: $SSH_AUTH_SOCK"
    if ssh-add -l >/dev/null 2>&1; then
        echo "✅ SSH keys available!"
        ssh-add -l
        # Make it permanent for this session
        echo "export SSH_AUTH_SOCK=$SSH_AUTH_SOCK" > ~/.ssh-env
        exit 0
    fi
fi

# Method 2: Try existing agent sockets in /tmp
for sock in /tmp/ssh-*/agent.*; do
    if [ -S "$sock" ]; then
        export SSH_AUTH_SOCK="$sock"
        echo "🔍 Trying agent socket: $sock"
        if ssh-add -l >/dev/null 2>&1; then
            echo "✅ SSH keys available!"
            ssh-add -l
            # Make it permanent for this session
            echo "export SSH_AUTH_SOCK=$SSH_AUTH_SOCK" > ~/.ssh-env
            exit 0
        fi
    fi
done

# Method 3: Start new agent and prompt for key
echo "🚀 Starting new SSH agent..."
eval $(ssh-agent -s)
echo "Please add your SSH key:"
ssh-add

echo "✅ SSH Agent reconnected!"
# Make it permanent for this session
echo "export SSH_AUTH_SOCK=$SSH_AUTH_SOCK" > ~/.ssh-env
ssh-add -l
