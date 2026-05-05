.DEFAULT_GOAL := help

# ── help ──────────────────────────────────────────────────────────────────────

.PHONY: help
help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── install ───────────────────────────────────────────────────────────────────

.PHONY: install
install: ## Install spec-index globally via pipx
	pipx install .

.PHONY: install-dev
install-dev: ## Install in editable mode for development
	pip install -e .

.PHONY: reinstall
reinstall: ## Re-install after local changes (pipx --force)
	pipx install . --force

.PHONY: uninstall
uninstall: ## Remove the pipx-installed spec-index
	pipx uninstall ver-spec-helpers
