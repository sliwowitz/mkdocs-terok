.PHONY: all lint format test docstrings deadcode reuse check install install-dev clean spdx docs docs-serve

REPORTS_DIR ?= reports
COVERAGE_XML ?= $(REPORTS_DIR)/coverage.xml
JUNIT_XML ?= $(REPORTS_DIR)/tests.junit.xml

all: check

# Run linter and format checker (fast, run before commits)
lint:
	mkdir -p $(REPORTS_DIR)
	poetry run ruff check .
	poetry run ruff format --check .

# Auto-fix lint issues and format code
format:
	poetry run ruff check --fix .
	poetry run ruff format .

# Run tests with coverage
test:
	mkdir -p $(REPORTS_DIR)
	poetry run pytest tests/ --cov=mkdocs_terok --cov-report=term-missing --cov-report=xml:$(COVERAGE_XML) --junitxml=$(JUNIT_XML) -o junit_family=legacy

# Check docstring coverage (minimum 95%)
docstrings:
	poetry run docstr-coverage src/mkdocs_terok/ --fail-under=95

# Find dead code (cross-file, min 80% confidence)
deadcode:
	poetry run vulture src/mkdocs_terok/ --min-confidence 80

# Check REUSE (SPDX license/copyright) compliance
reuse:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	poetry run reuse lint

# Run all checks (equivalent to CI)
check: lint test docstrings deadcode reuse

# Install runtime dependencies only
install:
	poetry install --only main

# Install all dependencies (dev, test, docs)
install-dev:
	poetry install --with dev,test,docs

# Clean build artifacts
clean:
	rm -rf dist/ reports/ site/ .coverage .pytest_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Build documentation site
docs:
	poetry run mkdocs build --strict

# Serve documentation locally with live reload
docs-serve:
	poetry run mkdocs serve

# Add SPDX header to files.
spdx:
ifndef NAME
	$(error NAME is required — use the real name of the copyright holder, e.g. make spdx NAME="Real Human Name" FILES="src/mkdocs_terok/new_file.py")
endif
	poetry run reuse annotate --template compact --copyright "$(NAME)" --license Apache-2.0 $(FILES)
