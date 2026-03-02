.PHONY: help install format lint typecheck test ci clean all

# --- ANSI Color Codes ---
BLUE=\033[1;34m
GREEN=\033[1;32m
YELLOW=\033[1;33m
NC=\033[0m # No Color

# --- Helper Macro for Clean Output ---
define PRINT_STAGE
	@echo "\n$(BLUE)=== $(1) ===$(NC)"
endef

# Default target
all: format lint typecheck test

help: ## Show this help menu
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies using uv
	$(call PRINT_STAGE, Installing Dependencies)
	uv sync --all-extras --dev

format: ## Auto-format Python code using Ruff
	$(call PRINT_STAGE, Formatting Code)
	uv run ruff check --fix .
	uv run ruff format .

lint: ## Run linters (Ruff and Markdown)
	$(call PRINT_STAGE, Running Linters)
	uv run ruff check .
	uv run ruff format --check .
	@if command -v markdownlint >/dev/null 2>&1; then \
		markdownlint "**/*.md" --ignore ".venv"; \
	elif command -v npx >/dev/null 2>&1; then \
		npx --yes markdownlint-cli "**/*.md" --ignore ".venv"; \
	else \
		echo "$(YELLOW)⚠ 'markdownlint' and 'npx' not found. Skipping markdownlint. (Requires Node.js or markdownlint-cli)$(NC)"; \
	fi

typecheck: ## Run static type checking with Mypy
	$(call PRINT_STAGE, Running Type Checks)
	uv run mypy .

test: ## Run the full automated testing matrix with coverage
	$(call PRINT_STAGE, Executing Testing Matrix)
	uv run pytest

ci: install lint typecheck test ## Run the exact pipeline executed by GitHub Actions
	@echo "\n$(GREEN)✔ Local CI pipeline completed successfully. Clear to push!$(NC)"

clean: ## Remove cache directories and test artifacts
	$(call PRINT_STAGE, Cleaning Workspace)
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	rm -rf htmlcov .coverage coverage.xml
	find . -type d -name "__pycache__" -exec rm -rf {} +
	@echo "$(GREEN)✔ Environment cleaned.$(NC)"
