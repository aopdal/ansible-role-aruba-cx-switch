# syntax=docker/dockerfile:1
# Official slim Python image: far fewer packages (and CVEs) than the
# mcr.microsoft.com/devcontainers images. The common-utils feature in
# devcontainer.json adds sudo, locales and shell basics for the vscode user.
ARG VARIANT="3.12"
FROM python:${VARIANT}-slim

ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

# Install system dependencies. The upgrade pulls Debian security fixes the
# upstream base image has not picked up yet.
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y upgrade \
    && apt-get -y install --no-install-recommends \
    # Network tools for testing
    iputils-ping \
    netcat-openbsd \
    openssh-client \
    ca-certificates \
    curl \
    wget \
    # Build tools (Python packages without wheels)
    build-essential \
    # Git tools
    git \
    git-lfs \
    # Shell tools
    bash-completion \
    less \
    procps \
    vim \
    # Additional utilities
    jq \
    yamllint \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Create the dev user here (not only via common-utils) because the steps
# below write to its home directory before features run.
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m -s /bin/bash $USERNAME

# Set working directory
WORKDIR /workspace

# Install pre-commit (for git hooks). pip is upgraded for the same reason as apt.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir pre-commit

# Create directories for Ansible
RUN mkdir -p /home/vscode/.ansible/collections \
    && mkdir -p /home/vscode/.ansible/roles \
    && chown -R vscode:vscode /home/vscode/.ansible

# Set up bash completion for ansible commands
# Note: --completion flag requires argcomplete to be installed
# RUN echo 'source <(ansible --completion bash)' >> /home/vscode/.bashrc \
#     && echo 'source <(ansible-playbook --completion bash)' >> /home/vscode/.bashrc

# Configure git to be safe
RUN git config --system --add safe.directory '*'

# Add helpful aliases
RUN echo 'alias ll="ls -lah"' >> /home/vscode/.bashrc \
    && echo 'alias ansible-test="molecule test"' >> /home/vscode/.bashrc \
    && echo 'alias ansible-converge="molecule converge"' >> /home/vscode/.bashrc

# Set environment variables. /usr/local is root-owned, so post-create.sh's
# pip installs land in the user site; put its scripts on PATH.
ENV ANSIBLE_FORCE_COLOR=true
ENV ANSIBLE_HOST_KEY_CHECKING=false
ENV PY_COLORS=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/home/vscode/.local/bin:${PATH}"

# Switch to vscode user
USER vscode

# Add welcome message
RUN echo 'echo "🚀 Ansible Role Development Environment"' >> /home/vscode/.bashrc \
    && echo 'echo "📦 Python: $(python --version)"' >> /home/vscode/.bashrc \
    && echo 'echo "🔧 Quick commands: make test-quick, molecule test"' >> /home/vscode/.bashrc \
    && echo 'echo ""' >> /home/vscode/.bashrc
