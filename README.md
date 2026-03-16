# mkdocs-terok

[![codecov](https://codecov.io/gh/terok-ai/mkdocs-terok/graph/badge.svg)](https://codecov.io/gh/terok-ai/mkdocs-terok)

Shared MkDocs documentation generators for terok projects.

Provides reusable modules for generating CI workflow maps, integration test maps,
code quality reports, API reference pages, and config reference documentation from
Pydantic models. No runtime dependency on mkdocs or mkdocs-gen-files — the library
produces strings/results; consumers handle file I/O in thin shims.

## Installation

```toml
# In your project's pyproject.toml
[tool.poetry.group.docs.dependencies]
mkdocs-terok = {url = "https://github.com/terok-ai/mkdocs-terok/releases/download/v0.1.0/mkdocs_terok-0.1.0-py3-none-any.whl"}
```

## License

Apache-2.0
