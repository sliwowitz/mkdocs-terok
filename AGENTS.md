# Agent Guide (mkdocs-terok)

## Purpose

`mkdocs-terok` provides shared MkDocs documentation generators for terok projects.
It produces strings/results that consumers wrap in thin mkdocs-gen-files shims.

## Technology Stack

- **Language**: Python 3.12+
- **Package Manager**: Poetry
- **Testing**: pytest with coverage
- **Linting/Formatting**: ruff
- **Documentation**: N/A (library is self-documenting via docstrings)

## Build, Lint, and Test Commands

```bash
make lint       # Run linter (required before every commit)
make format     # Auto-fix lint issues if lint fails
make test       # Run full test suite with coverage
make docstrings # Check docstring coverage (minimum 95%)
make deadcode   # Find dead code
make reuse      # Check REUSE (SPDX license/copyright) compliance
make check      # Run lint + test + docstrings + deadcode + reuse
```

## Coding Standards

- **Style**: Follow ruff configuration in `pyproject.toml`
- **Line length**: 100 characters
- **Type hints**: Use Python 3.12+ type hints
- **Docstrings**: Required for all public functions, classes, and modules (95% min)
- **SPDX headers**: Every `.py` file must have an SPDX header
- **No runtime dependency on mkdocs**: Library produces strings; consumers handle I/O
