# SSH Agent Auto-Reconnection for Dev Container
# Add this to ~/.bashrc or ~/.zshrc

# Function to check and reconnect SSH agent
check_ssh_agent() {
    # Check if SSH agent is working
    if ! ssh-add -l >/dev/null 2>&1; then
        echo "⚠️  SSH agent not responding, attempting reconnection..."

        # Try mounted SSH agent socket first (devcontainer mount)
        if [ -S "/ssh-agent" ]; then
            export SSH_AUTH_SOCK="/ssh-agent"
            if ssh-add -l >/dev/null 2>&1; then
                echo "✅ Reconnected to mounted SSH agent"
                return 0
            else
                echo "⚠️  /ssh-agent exists but not working"
                echo "   Check host SSH agent: ssh-add -l"
            fi
        fi

        # Fallback: Try VS Code's dynamic SSH agent socket
        VSCODE_SSH_SOCK=$(find /tmp -name "vscode-ssh-auth-*.sock" 2>/dev/null | head -1)
        if [ -n "$VSCODE_SSH_SOCK" ] && [ -S "$VSCODE_SSH_SOCK" ]; then
            export SSH_AUTH_SOCK="$VSCODE_SSH_SOCK"
            if ssh-add -l >/dev/null 2>&1; then
                echo "✅ Reconnected to VS Code SSH agent"
                return 0
            fi
        fi

        echo "❌ Could not reconnect SSH agent"
        echo "   1. Ensure SSH agent is running on host: eval \$(ssh-agent -s)"
        echo "   2. Add your key on host: ssh-add ~/.ssh/id_ed25519"
        echo "   3. Rebuild devcontainer to remount: F1 → 'Rebuild Container'"
    fi
}

# Auto-check SSH agent on shell startup
check_ssh_agent

# Alias for manual reconnection
alias ssh-reconnect="/workspaces/ansible-role-aruba-cx-switch/.devcontainer/reconnect-ssh.sh"
alias ssh-check="ssh-add -l"
