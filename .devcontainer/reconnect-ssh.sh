#!/bin/bash
# SSH Agent Reconnection Script for Dev Container
# Usage: source .devcontainer/reconnect-ssh.sh

echo "🔐 Reconnecting SSH Agent..."

# Method 1: Try mounted SSH agent socket at /ssh-agent
if [ -S "/ssh-agent" ]; then
    export SSH_AUTH_SOCK="/ssh-agent"
    echo "✅ Using mounted SSH agent: $SSH_AUTH_SOCK"
    if ssh-add -l >/dev/null 2>&1; then
        echo "✅ SSH keys available!"
        ssh-add -l
        # Make it permanent for this session
        echo "export SSH_AUTH_SOCK=/ssh-agent" > ~/.ssh-env
        return 0 2>/dev/null || exit 0
    else
        echo "⚠️  SSH agent socket exists but no keys available"
        echo "   Check SSH agent is running on host: ssh-add -l"
    fi
fi

# Method 2: Fallback - Try VS Code's dynamic SSH agent socket
VSCODE_SSH_SOCK=$(find /tmp -name "vscode-ssh-auth-*.sock" 2>/dev/null | head -1)
if [ -n "$VSCODE_SSH_SOCK" ] && [ -S "$VSCODE_SSH_SOCK" ]; then
    export SSH_AUTH_SOCK="$VSCODE_SSH_SOCK"
    echo "✅ Connected to VS Code SSH agent: $SSH_AUTH_SOCK"
    if ssh-add -l >/dev/null 2>&1; then
        echo "✅ SSH keys available!"
        ssh-add -l
        echo "export SSH_AUTH_SOCK=$SSH_AUTH_SOCK" > ~/.ssh-env
        return 0 2>/dev/null || exit 0
    fi
fi

# Method 3: Start new agent and prompt for key
echo "🚀 Starting new SSH agent..."
eval $(ssh-agent -s)
echo "Please add your SSH key:"
ssh-add

echo "✅ SSH Agent reconnected!"
# Make it permanent for this session
echo "export SSH_AUTH_SOCK=$SSH_AUTH_SOCK" > ~/.ssh-env
ssh-add -l
