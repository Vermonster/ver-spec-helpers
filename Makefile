.DEFAULT_GOAL := help

MODEL_ID  := sentence-transformers/all-MiniLM-L6-v2
MODEL_DIR := .ver-spec-helpers/models/all-MiniLM-L6-v2

# ── help ──────────────────────────────────────────────────────────────────────

.PHONY: help
help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── install ───────────────────────────────────────────────────────────────────

.PHONY: install
install: ## Install spec-index globally via pipx (recommended)
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

.PHONY: setup
setup: install download-model ## Full setup: install spec-index + download embedding model

# ── model ─────────────────────────────────────────────────────────────────────

.PHONY: download-model
download-model: $(MODEL_DIR) ## Download embedding model to models/ for offline use

$(MODEL_DIR):
	@echo "Downloading $(MODEL_ID) → $(MODEL_DIR) …"
	@mkdir -p .ver-spec-helpers/models
	python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('$(MODEL_ID)').save('$(MODEL_DIR)')"
	@echo "✓  Model saved to $(MODEL_DIR)"
