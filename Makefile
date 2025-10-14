.PHONY: help install test lint syntax molecule clean pre-commit all venv docs docs-serve docs-build docs-sync

# Default target
.DEFAULT_GOAL := help

# Virtual environment
VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
ACTIVATE := . $(VENV)/bin/activate

# Color output
BLUE := \033[0;34m
GREEN := \033[0;32m
RED := \033[0;31m
YELLOW := \033[0;33m
NC := \033[0m # No Color

help: ## Show this help message
	@echo '$(BLUE)Ansible Role Testing Commands$(NC)'
	@echo ''
	@echo 'Usage:'
	@echo '  make $(GREEN)<target>$(NC)'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ''
	@echo '$(YELLOW)Note: Most commands require virtual environment. Run "make venv" first.$(NC)'

venv: ## Create virtual environment
	@if [ ! -d "$(VENV)" ]; then \
		echo "$(BLUE)Creating virtual environment...$(NC)"; \
		python3 -m venv $(VENV); \
		$(PIP) install --upgrade pip; \
		echo "$(GREEN)✅ Virtual environment created at $(VENV)/$(NC)"; \
	else \
		echo "$(GREEN)✅ Virtual environment already exists$(NC)"; \
	fi

install: venv ## Install testing dependencies
	@echo "$(BLUE)Installing test dependencies in virtual environment...$(NC)"
	@$(ACTIVATE) && pip install -r requirements-test.txt
	@$(ACTIVATE) && ansible-galaxy collection install -r requirements.yml
	@echo "$(GREEN)✅ Dependencies installed$(NC)"

pre-commit-setup: venv ## Setup pre-commit hooks
	@echo "$(BLUE)Setting up pre-commit hooks...$(NC)"
	@$(ACTIVATE) && pre-commit install
	@echo "$(GREEN)✅ Pre-commit hooks installed$(NC)"

yamllint: venv ## Run YAML linting
	@echo "$(BLUE)Running yamllint...$(NC)"
	@$(ACTIVATE) && yamllint .
	@echo "$(GREEN)✅ YAML lint passed$(NC)"

ansible-lint: venv ## Run Ansible linting
	@echo "$(BLUE)Running ansible-lint...$(NC)"
	@$(ACTIVATE) && ansible-lint
	@echo "$(GREEN)✅ Ansible lint passed$(NC)"

lint: yamllint ansible-lint ## Run all linting (YAML + Ansible)
	@echo "$(GREEN)✅ All linting passed$(NC)"

syntax: venv ## Run syntax check
	@echo "$(BLUE)Running syntax check...$(NC)"
	@$(ACTIVATE) && ansible-playbook tests/test.yml -i tests/inventory --syntax-check
	@echo "$(GREEN)✅ Syntax check passed$(NC)"

molecule-create: venv ## Create molecule test instance
	@echo "$(BLUE)Creating molecule test instance...$(NC)"
	@$(ACTIVATE) && molecule create

molecule-converge: venv ## Run molecule converge
	@echo "$(BLUE)Running molecule converge...$(NC)"
	@$(ACTIVATE) && molecule converge

molecule-verify: venv ## Run molecule verify
	@echo "$(BLUE)Running molecule verify...$(NC)"
	@$(ACTIVATE) && molecule verify

molecule-test: venv ## Run full molecule test
	@echo "$(BLUE)Running full molecule test...$(NC)"
	@$(ACTIVATE) && molecule test
	@echo "$(GREEN)✅ Molecule test passed$(NC)"

molecule-destroy: venv ## Destroy molecule test instance
	@echo "$(BLUE)Destroying molecule test instance...$(NC)"
	@$(ACTIVATE) && molecule destroy

integration: venv ## Run integration tests
	@echo "$(BLUE)Running integration tests...$(NC)"
	@$(ACTIVATE) && ansible-playbook tests/test.yml -i tests/inventory -v
	@echo "$(GREEN)✅ Integration tests passed$(NC)"

pre-commit: venv ## Run pre-commit on all files
	@echo "$(BLUE)Running pre-commit hooks...$(NC)"
	@$(ACTIVATE) && pre-commit run --all-files
	@echo "$(GREEN)✅ Pre-commit checks passed$(NC)"

test-quick: lint syntax ## Quick test (lint + syntax, no molecule)
	@echo "$(GREEN)✅ Quick tests passed$(NC)"

test: lint syntax molecule-test ## Run all tests including molecule
	@echo "$(GREEN)✅ All tests passed$(NC)"

clean: ## Clean up test artifacts
	@echo "$(YELLOW)Cleaning up...$(NC)"
	rm -rf .cache .pytest_cache .molecule tests/output
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.retry" -delete 2>/dev/null || true
	@if [ -d "$(VENV)" ]; then $(ACTIVATE) && molecule destroy || true; fi
	@echo "$(GREEN)✅ Cleanup complete$(NC)"

clean-all: clean ## Clean everything including virtual environment
	@echo "$(YELLOW)Removing virtual environment...$(NC)"
	rm -rf $(VENV)
	@echo "$(GREEN)✅ Complete cleanup done$(NC)"

watch: ## Watch for changes and run lint (requires entr)
	@echo "$(BLUE)Watching for changes...$(NC)"
	@echo "$(YELLOW)Press Ctrl+C to stop$(NC)"
	@find . -name "*.yml" -o -name "*.yaml" | entr -c make lint

setup: install pre-commit-setup ## Complete setup (install deps + pre-commit)
	@echo "$(GREEN)✅ Setup complete! Run 'make test' to verify.$(NC)"

info: ## Display testing information
	@echo "$(BLUE)Testing Infrastructure Info$(NC)"
	@echo ""
	@echo "System Python: $$(python3 --version 2>&1)"
	@if [ -d "$(VENV)" ]; then \
		echo "Virtual Environment: ✅ $(VENV)/ (active)"; \
		echo "Venv Python: $$($(PYTHON) --version 2>&1)"; \
		echo "Ansible: $$($(ACTIVATE) && ansible --version | head -n1 2>&1 || echo 'Not installed in venv')"; \
		echo "Molecule: $$($(ACTIVATE) && molecule --version 2>&1 || echo 'Not installed in venv')"; \
		echo "Pre-commit: $$($(ACTIVATE) && pre-commit --version 2>&1 || echo 'Not installed in venv')"; \
	else \
		echo "Virtual Environment: ❌ Not created (run 'make venv')"; \
	fi
	@echo "Docker: $$(docker --version 2>&1 || echo 'Not installed')"
	@if [ -f "/.dockerenv" ] || grep -q docker /proc/1/cgroup 2>/dev/null; then \
		echo "Dev Container: ✅ Running in dev container"; \
	else \
		echo "Dev Container: ℹ️  Not running in dev container (optional)"; \
	fi
	@echo ""
	@echo "$(BLUE)Development Options:$(NC)"
	@echo "  🐳 Dev Container: Recommended - See .devcontainer/"
	@echo "  📦 Virtual Env: Alternative - Run './setup-testing.sh'"
	@echo ""
	@echo "$(BLUE)Test Coverage:$(NC)"
	@echo "  ✅ YAML linting (.yamllint)"
	@echo "  ✅ Ansible linting (.ansible-lint)"
	@echo "  ✅ Syntax checking"
	@echo "  ✅ Molecule testing (molecule/)"
	@echo "  ✅ Integration tests (tests/)"
	@echo "  ✅ Pre-commit hooks (.pre-commit-config.yaml)"
	@echo "  ✅ CI/CD pipeline (.github/workflows/ci.yml)"
	@echo ""
	@echo "$(BLUE)Documentation:$(NC)"
	@echo "  📚 QUICKSTART.md - Get started quickly"
	@echo "  📚 DEVELOPMENT.md - Complete development guide"
	@echo "  📚 TESTING.md - Testing instructions"
	@echo "  📚 README.md - Role usage and features"
	@echo "  📚 Run 'make docs-serve' for live preview"

docs-install: ## Install documentation dependencies
	@echo "$(BLUE)Installing documentation dependencies...$(NC)"
	@pip install -r requirements-docs.txt
	@echo "$(GREEN)✅ Documentation dependencies installed$(NC)"

docs-sync: ## Sync README.md to docs/index.md
	@echo "$(BLUE)Syncing README.md to docs/index.md...$(NC)"
	@cp README.md docs/index.md
	@# Fix links: Remove 'docs/' prefix since index.md is now inside docs/
	@sed -i 's|(docs/|(|g' docs/index.md
	@# Fix links: Make relative paths point to root files (tests/, defaults/, etc.)
	@sed -i 's|(tests/|(../tests/|g' docs/index.md
	@sed -i 's|(defaults/|(../defaults/|g' docs/index.md
	@sed -i 's|(testing-scripts/|(../testing-scripts/|g' docs/index.md
	@echo "$(GREEN)✅ README.md synced to docs/index.md with fixed links$(NC)"

docs-serve: ## Serve documentation locally at http://127.0.0.1:8000
	@echo "$(BLUE)Starting documentation server...$(NC)"
	@echo "$(GREEN)Visit: http://127.0.0.1:8000$(NC)"
	@mkdocs serve

docs-build: ## Build documentation static site
	@echo "$(BLUE)Building documentation...$(NC)"
	@mkdocs build
	@echo "$(GREEN)✅ Documentation built in site/ directory$(NC)"

docs: docs-serve ## Alias for docs-serve

all: clean setup test ## Clean, setup, and run all tests
	@echo "$(GREEN)🎉 All done!$(NC)"
