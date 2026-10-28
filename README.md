<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://terok-ai.github.io/terok/terok-logo-w.svg">
    <img src="https://terok-ai.github.io/terok/terok-logo-b.svg" alt="mkdocs-terok" width="120">
  </picture>
</p>

# mkdocs-terok

[![PyPI](https://img.shields.io/pypi/v/mkdocs-terok)](https://pypi.org/project/mkdocs-terok/)
[![License: 0BSD](https://img.shields.io/badge/License-0BSD-green.svg)](https://opensource.org/license/0bsd)
[![REUSE status](https://api.reuse.software/badge/github.com/terok-ai/mkdocs-terok)](https://api.reuse.software/info/github.com/terok-ai/mkdocs-terok)
[![codecov](https://codecov.io/gh/terok-ai/mkdocs-terok/graph/badge.svg)](https://codecov.io/gh/terok-ai/mkdocs-terok)

Shared [ProperDocs](https://properdocs.org/) documentation generators for terok projects.

Provides reusable modules for generating CI workflow maps, integration test maps,
module maps, code metrics reports, API reference pages, and config reference
documentation from Pydantic models. A built-in `terok` ProperDocs plugin drives
every generator except the config reference (which needs a consumer-supplied
Pydantic model); the generator modules themselves never import the doc engine and
can also be used standalone via `mkdocs-gen-files` shims.

The metrics report module can optionally parse output from
[scc](https://github.com/boyter/scc),
[complexipy](https://github.com/rohaquinlop/complexipy),
[tach](https://github.com/gauge-sh/tach),
[vulture](https://github.com/jendrikseipp/vulture), and
[docstr-coverage](https://github.com/HunterMcGushion/docstr_coverage).
When any of these tools is absent, the corresponding report section degrades
gracefully to a warning.

## Installation

Add to your project as a docs-build dependency.

**pip**:

```bash
pip install mkdocs-terok
```


**uv** — `pyproject.toml` (PEP 735 dependency group):

```toml
[dependency-groups]
docs = [
    "mkdocs-terok~=0.8.0",
]
```

The package installs ProperDocs and its core generator dependencies. Config
reference generation additionally requires consumer-supplied Pydantic v2.
Consumers must declare their theme and additional plugins in their own docs
requirements. This repository's `docs` group requires `mkdocs-material>=9.8.0`;
that group and its lockfile are not installed with the published package.
Upgrading `mkdocs-terok` alone does not upgrade Material in a consumer's lockfile.

## Configuration

Configured via the `terok` plugin in your `properdocs.yml`.  See this
repository's own [`properdocs.yml`](properdocs.yml) for a self-documenting
example that exercises most of the generators the package ships.

## License

[0BSD](https://opensource.org/license/0bsd) — use freely, no strings attached.
