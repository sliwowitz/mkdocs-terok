# Agent Guide (mkdocs-terok)

## Purpose

`mkdocs-terok` provides shared ProperDocs documentation generators for terok projects.
It produces strings/results that consumers wrap in thin mkdocs-gen-files shims.

The package name stays `mkdocs-terok` for install-path stability; internally the
plugin imports from `properdocs.*`. ProperDocs' plugin loader reads both
`mkdocs.plugins` and `properdocs.plugins` entry-point groups, so the
`[project.entry-points."mkdocs.plugins"]` declaration is preserved intentionally.

## Technology Stack

- **Language**: Python 3.12+
- **Package Manager**: uv
- **Testing**: pytest with coverage
- **Linting/Formatting**: ruff
- **Documentation**: N/A (library is self-documenting via docstrings)

## Build, Lint, and Test Commands

```bash
make lint       # Run linter (required before every commit)
make format     # Auto-fix lint issues if lint fails
make test-fast  # Only the tests affected by your branch diff (tach impact analysis)
make test       # Run full test suite with coverage
make docstrings # Check docstring coverage (minimum 95%)
make deadcode   # Find dead code
make reuse      # Check REUSE (SPDX license/copyright) compliance
make check      # Run lint + test + docstrings + deadcode + reuse
```

**During development, ALWAYS iterate with `make test-fast`.** Rerunning the
full suite after every edit is the single biggest time sink in agent dev
loops — don't do it; run the full `make test` exactly once, right before
committing. One exception: impact analysis follows the Python import graph
only, so after changing non-Python inputs (YAML, templates, shell scripts)
run the full `make test` — `make test-fast` would skip tests that are
actually affected.

## Coding Standards

- **Style**: Follow ruff configuration in `pyproject.toml`
- **Line length**: 100 characters
- **Type hints**: Use Python 3.12+ type hints
- **Docstrings**: Required for all public functions, classes, and modules (95% min)
- **Cross-references in docstrings**: use mkdocstrings autoref syntax `` [`Name`][module.path.Name] `` — never the Sphinx ``:class:`Name``` / ``:func:`name``` forms. Sphinx roles render as literal text on the rendered docs site (mkdocstrings doesn't process them). Prefer the explicit full path over the bare `` [`Name`][] `` autoref form: explicit paths keep `properdocs build --strict` green even when the symbol's short name isn't unique. For external symbols, use the dependency's own path (e.g. `` [`Sandbox`][terok_sandbox.Sandbox] ``, `` [`StreamReader`][asyncio.StreamReader] ``) — those resolve via the inventories listed in `properdocs.yml`.
- **SPDX headers**: Every `.py` file must have an SPDX header
- **Machine-read comments are ASCII-only**: a comment that a tool parses — a suppression marker (`# noqa`, `# nosec`, `# type: ignore`, `# pragma: no cover`, `# NOSONAR`) or another directive (`# fmt: off`, `# pylint: disable`) — uses ASCII only, its reason included.  Write `# noqa: BLE001 - reason` with a plain hyphen.  Keep commas out of a `noqa` reason: SonarCloud reads a comma as the start of another rule code, so use a semicolon.  Ordinary comments may use any UTF-8, and docstrings are welcome to use proper typography.
- **No runtime dependency on the doc engine in generator modules**: Only
  `plugin.py` imports `properdocs`; each generator module produces strings and
  consumers handle I/O

## Dependency Pinning & `pyproject.toml` Hygiene

**Version pinning policy.** Runtime/production dependencies — those pulled in
by a plain `pip install` / `pipx install` of this package (the
`[project].dependencies` table) — are pinned by the dependency's major
version:

- **Third-party, major 0 (`0.y.z`)** → pin to an **exact patch**
  (`pkg==0.y.z`). Pre-1.0 packages promise no compatibility across either
  minors *or* patches, so a floating range invites silent breakage.
- **Third-party, major ≥ 1** → **compatible-release at the tested
  baseline**: `pkg~=X.Y` where `X.Y` is the locked major.minor (floor =
  what we test against, cap = next major). Use the patch-series form
  `pkg~=X.Y.Z` only where a specific patch floor is required — note the
  PEP 440 truncation rule: the cap is one level above the last written
  component (`~=2.13` → `<3`, `~=8.2.5` → `<8.3`). Prefer `~=` over a
  hand-rolled `>=,<` pair: it states the baseline as one fact with the
  ceiling derived by construction, so the bounds cannot drift apart.
- **Sibling `terok-*` deps** → `~=0.y.z` (or their release-wheel URL pin).
  We guarantee patch-level API stability across the sibling packages, so
  the patch-series form is exactly right — do *not* exact-pin them (it
  would fight the multi-repo release/PR-chain flow).

Dev / test / docs / tooling dependencies (the `[dependency-groups]` tables)
are **exempt** — they are not shipped to installers and exact-pinning them is
an unwarranted maintenance burden the developers can absorb. After changing
any pin, run `uv lock` and commit `pyproject.toml` and `uv.lock`
together.

**Comment discipline in `pyproject.toml`.** The dependency tables stay
comment-free and self-documenting, apart from the standing policy pointer
above them. **Never** comment on why a dependency -- especially a sibling
`terok-*` package -- is pinned a certain way, and never mention dev-cycle
state (temporary git-branch pins, the multi-repo PR chain): cross-repo
merges are performed by a script that does not understand comments, so any
such note is carried straight into a production release. Keep pin
rationale in commit messages, PR descriptions, or this file. Ordinary
explanatory comments in `[tool.*]` sections are fine. `pyproject.toml`
stays ASCII-only.
