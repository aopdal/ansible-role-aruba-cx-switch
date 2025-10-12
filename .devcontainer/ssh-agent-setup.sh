# SSH Agent Auto-Reconnection for Dev Container
# Add this to ~/.bashrc or ~/.zshrc

# Function to check and reconnect SSH agent
check_ssh_agent() {
    # Check if SSH agent is working
    if ! ssh-add -l >/dev/null 2>&1; then
        echo "⚠️  SSH agent not responding, attempting reconnection..."

        # Try to find WSL2 SSH agent socket
        WSL_SSH_SOCK=$(find /mnt/wslg/runtime-dir -name "ssh-agent.sock" 2>/dev/null | head -1)
        if [ -n "$WSL_SSH_SOCK" ] && [ -S "$WSL_SSH_SOCK" ]; then
            export SSH_AUTH_SOCK="$WSL_SSH_SOCK"
            if ssh-add -l >/dev/null 2>&1; then
                echo "✅ Reconnected to WSL2 SSH agent"
                return 0
            fi
        fi

        # Try existing agent sockets
        for sock in /tmp/ssh-*/agent.*; do
            if [ -S "$sock" ]; then
                export SSH_AUTH_SOCK="$sock"
                if ssh-add -l >/dev/null 2>&1; then
                    echo "✅ Reconnected to existing SSH agent"
                    return 0
                fi
            fi
        done

        echo "❌ Could not reconnect SSH agent. Run: /workspaces/ansible-role-aruba-cx-switch/.devcontainer/reconnect-ssh.sh"
    fi
}

# Auto-check SSH agent on shell startup
check_ssh_agent

# Alias for manual reconnection
alias ssh-reconnect="/workspaces/ansible-role-aruba-cx-switch/.devcontainer/reconnect-ssh.sh"
alias ssh-check="ssh-add -l"
