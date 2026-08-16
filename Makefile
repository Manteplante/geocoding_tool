.DEFAULT_GOAL := help
.PHONY: help install install-dev hooks format format-check lint lint-fix check \
        test smoke cov ci notebook clean-cache clean build

UV ?= uv

##@ Setup

install: ## Install runtime dependencies only
	$(UV) sync --no-dev

install-dev: ## Install runtime + dev dependencies
	$(UV) sync --group dev

hooks: ## Install the pre-commit git hooks
	$(UV) run pre-commit install

##@ Quality

format: ## Format code and notebooks in place
	$(UV) run ruff format .

format-check: ## Fail if anything is unformatted (CI)
	$(UV) run ruff format --check .

lint: ## Lint code and notebooks
	$(UV) run ruff check .

lint-fix: ## Lint and apply safe autofixes
	$(UV) run ruff check --fix .

check: format lint-fix ## Format + autofix in one go (use before committing)

##@ Test

test: ## Run the full offline test suite
	$(UV) run pytest

smoke: ## Fast end-to-end wiring check (no network, no cost)
	$(UV) run pytest -m smoke

cov: ## Run tests with a coverage report
	$(UV) run pytest --cov=geocoding_tool --cov-report=term-missing

##@ CI

ci: format-check lint test ## Exactly what GitHub Actions runs

build: ## Build the wheel + sdist
	$(UV) build

##@ Run

notebook: ## Open the geocoding notebook in Jupyter Lab
	$(UV) run --with jupyterlab jupyter lab geocoding/geocoder.ipynb

clean-cache: ## Drop cached geocoding results (forces fresh, billable lookups)
	rm -rf .cache/

##@ Housekeeping

clean: ## Remove build, test and tooling artefacts
	rm -rf dist/ build/ *.egg-info .pytest_cache .ruff_cache .coverage htmlcov
	find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} +

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} \
	/^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2 } \
	/^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(MAKEFILE_LIST)
