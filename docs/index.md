# mkdocs-terok

Shared MkDocs documentation generators for terok projects.

## Overview

`mkdocs-terok` produces Markdown strings and structured results that consumers
wrap in thin [mkdocs-gen-files](https://github.com/oprypin/mkdocs-gen-files) shims.
The library has **no runtime dependency on MkDocs** — it handles content generation only.

## Modules

| Module | Purpose |
|--------|---------|
| `mkdocs_terok` | Package root — exports `brand_css_path()` |
| `mkdocs_terok.ref_pages` | Generate API reference pages from source tree |
| `mkdocs_terok.ci_map` | Parse and visualize GitHub Actions workflows |
| `mkdocs_terok.quality_report` | Code quality analysis — optionally parses output from [scc](https://github.com/boyter/scc), [complexipy](https://github.com/rohaquinern/complexipy), [tach](https://github.com/gauge-sh/tach), [vulture](https://github.com/jendrikseipp/vulture), and [docstr-coverage](https://github.com/HunterMcGushion/docstr_coverage) (sections degrade gracefully when tools are absent) |
| `mkdocs_terok.test_map` | Generate test suite maps with marker extraction |
| `mkdocs_terok.config_reference` | Render Pydantic models as config documentation |

## Dogfooding

This documentation site **uses mkdocs-terok on itself**. Every generator in the
library is exercised against this very repository. The shim scripts live in
`docs/` and demonstrate the minimal glue code consumers need to write.

The [Config Reference Demo](config-reference.md) uses a Star Trek-themed Pydantic
model to exercise all three renderers (`render_model_tables`, `render_yaml_example`,
`render_json_schema`).
