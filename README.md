# mkdocs-terok

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![REUSE](https://api.reuse.software/badge/github.com/terok-ai/mkdocs-terok)](https://api.reuse.software/info/github.com/terok-ai/mkdocs-terok)
[![codecov](https://codecov.io/gh/terok-ai/mkdocs-terok/graph/badge.svg)](https://codecov.io/gh/terok-ai/mkdocs-terok)

Shared MkDocs documentation generators for terok projects.

Provides reusable modules for generating CI workflow maps, integration test maps,
code quality reports, API reference pages, and config reference documentation from
Pydantic models. No runtime dependency on mkdocs or mkdocs-gen-files — the library
produces strings/results; consumers handle file I/O in thin shims.

The quality report module can optionally parse output from
[scc](https://github.com/boyter/scc),
[complexipy](https://github.com/rohaquinern/complexipy),
[tach](https://github.com/gauge-sh/tach),
[vulture](https://github.com/jendrikseipp/vulture), and
[docstr-coverage](https://github.com/HunterMcGushion/docstr_coverage).
When any of these tools is absent, the corresponding report section degrades
gracefully to a warning admonition.

## Installation

```toml
# In your project's pyproject.toml
[tool.poetry.group.docs.dependencies]
mkdocs-terok = {url = "https://github.com/terok-ai/mkdocs-terok/releases/download/v0.2.0/mkdocs_terok-0.2.0-py3-none-any.whl"}
```

## License

Apache-2.0
