# syntax=docker/dockerfile:1
ARG VARIANT="3.12"
FROM mcr.microsoft.com/devcontainers/python:${VARIANT}

# Install system dependencies
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends \
    # Network tools for testing
    iputils-ping \
    netcat-openbsd \
    curl \
    wget \
    # Build tools
    build-essential \
    # Git tools
    git \
    git-lfs \
    # Shell tools
    bash-completion \
    vim \
    # Additional utilities
    jq \
    yamllint

# Install Node.js 20.x LTS (separate layer to debug issues)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get update \
    && apt-get install -y nodejs \
    && node --version \
    && npm --version

# Clean up apt cache
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /workspace

# Install pre-commit (for git hooks)
RUN pip install --no-cache-dir pre-commit

# Create directories for Ansible
RUN mkdir -p /home/vscode/.ansible/collections \
    && mkdir -p /home/vscode/.ansible/roles \
    && chown -R vscode:vscode /home/vscode/.ansible

# Set up bash completion for ansible commands
RUN echo 'source <(ansible --completion bash)' >> /home/vscode/.bashrc \
    && echo 'source <(ansible-playbook --completion bash)' >> /home/vscode/.bashrc

# Configure git to be safe
RUN git config --system --add safe.directory '*'

# Add helpful aliases
RUN echo 'alias ll="ls -lah"' >> /home/vscode/.bashrc \
    && echo 'alias ansible-test="molecule test"' >> /home/vscode/.bashrc \
    && echo 'alias ansible-converge="molecule converge"' >> /home/vscode/.bashrc

# Set environment variables
ENV ANSIBLE_FORCE_COLOR=true
ENV ANSIBLE_HOST_KEY_CHECKING=false
ENV PY_COLORS=1
ENV PYTHONUNBUFFERED=1

# Switch to vscode user
USER vscode

# Add welcome message
RUN echo 'echo "🚀 Ansible Role Development Environment"' >> /home/vscode/.bashrc \
    && echo 'echo "📦 Python: $(python --version)"' >> /home/vscode/.bashrc \
    && echo 'echo "� Node.js: $(node --version)"' >> /home/vscode/.bashrc \
    && echo 'echo "📦 npm: $(npm --version)"' >> /home/vscode/.bashrc \
    && echo 'echo "�🔧 Quick commands: make test-quick, molecule test"' >> /home/vscode/.bashrc \
    && echo 'echo ""' >> /home/vscode/.bashrc
