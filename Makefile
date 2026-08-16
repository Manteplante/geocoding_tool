.DEFAULT_GOAL := help
.PHONY: help install install-dev hooks format format-check lint lint-fix check \
        test smoke cov ci register-kernel notebook clean-notebook geocoder-notebook \
        clean-cache clean build

UV ?= uv
KERNEL_NAME ?= geocoding-tool
KERNEL_DISPLAY ?= geocoding-tool (.venv)
# IPC (Unix domain sockets), not TCP: jupyter_client defaults kernel comms to
# loopback TCP, which ipykernel itself warns is unencrypted and sniffable by
# anything else on the host. IPC sockets are filesystem-permission gated and
# never touch the network stack, so this removes the exposure rather than
# silencing the warning. The explicit `ip` path works around a jupyter_client
# bug where transport=ipc alone falls back to a bare relative socket path
# (e.g. `kernel-ipc-1`) that the client and kernel resolve differently against
# their own cwd, so they never actually connect.
JUPYTER_RUNTIME_DIR := $(CURDIR)/.cache/jupyter-runtime
NBCONVERT_IPC_FLAGS = --KernelManager.transport=ipc --KernelManager.ip=$(JUPYTER_RUNTIME_DIR)/kernel-ipc

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

register-kernel: ## Register the project .venv as a Jupyter kernel (idempotent)
	$(UV) run python -m ipykernel install --user --name $(KERNEL_NAME) --display-name "$(KERNEL_DISPLAY)"

notebook: register-kernel ## Scaffold a new notebook locally: prompts for data/ or geocoding/, then a filename
	KERNEL_NAME=$(KERNEL_NAME) KERNEL_DISPLAY="$(KERNEL_DISPLAY)" $(UV) run python scripts/new_notebook.py

clean-notebook: register-kernel ## Run data/cleaner_example.ipynb end-to-end -> data/output/example_clean.csv
	@mkdir -p $(JUPYTER_RUNTIME_DIR)
	$(UV) run jupyter nbconvert --to notebook --execute --inplace \
		--ExecutePreprocessor.kernel_name=$(KERNEL_NAME) \
		$(NBCONVERT_IPC_FLAGS) \
		data/cleaner_example.ipynb

geocoder-notebook: clean-notebook ## Run geocoding/geocoder_example.ipynb end-to-end (live Nominatim, 5 free calls)
	@mkdir -p $(JUPYTER_RUNTIME_DIR)
	$(UV) run jupyter nbconvert --to notebook --execute --inplace \
		--ExecutePreprocessor.kernel_name=$(KERNEL_NAME) \
		$(NBCONVERT_IPC_FLAGS) \
		geocoding/geocoder_example.ipynb

clean-cache: ## Drop cached geocoding results (forces fresh, billable lookups)
	rm -rf .cache/

##@ Housekeeping

clean: ## Remove build, test and tooling artefacts
	rm -rf dist/ build/ *.egg-info .pytest_cache .ruff_cache .coverage htmlcov
	find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} +

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} \
	/^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2 } \
	/^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(MAKEFILE_LIST)
