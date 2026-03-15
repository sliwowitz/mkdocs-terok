# SPDX-FileCopyrightText: 2026 Jiri Vyskocil
# SPDX-License-Identifier: Apache-2.0

"""Generate code reference pages via callbacks, without mkdocs_gen_files dependency.

Walks a ``src/`` layout and emits ``::: module.path`` stubs. The consumer
provides ``write_file`` and ``set_edit_path`` callbacks that bridge to
mkdocs-gen-files (or any other I/O layer).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class RefPagesConfig:
    """Configuration for reference page generation.

    Attributes:
        src_dir: Path to the ``src/`` directory containing Python packages.
        skip_patterns: Module path components to skip (e.g. ``__main__``,
            ``resources``).
        output_prefix: Directory prefix for generated doc pages.
    """

    src_dir: Path = field(default_factory=lambda: Path("src"))
    skip_patterns: Sequence[str] = ("__main__", "resources")
    output_prefix: str = "reference"


def generate_ref_pages(
    config: RefPagesConfig,
    *,
    write_file: Callable[[str, str], None],
    set_edit_path: Callable[[str, str], None],
) -> list[tuple[tuple[str, ...], str]]:
    """Generate reference pages and return nav entries.

    Walks ``config.src_dir`` for ``*.py`` files, writes ``::: module`` stubs
    via the ``write_file`` callback, and records edit paths via
    ``set_edit_path``.

    Args:
        config: Reference page configuration.
        write_file: Callback ``(doc_path, content)`` to write a doc page.
        set_edit_path: Callback ``(doc_path, source_path)`` to set the
            edit link for a doc page.

    Returns:
        List of ``(nav_parts, doc_path_posix)`` tuples for building a
        literate nav.
    """
    entries: list[tuple[tuple[str, ...], str]] = []

    for path in sorted(config.src_dir.rglob("*.py")):
        module_path = path.relative_to(config.src_dir).with_suffix("")
        doc_path = path.relative_to(config.src_dir).with_suffix(".md")
        full_doc_path = Path(config.output_prefix) / doc_path

        parts = tuple(module_path.parts)

        if any(skip in parts for skip in config.skip_patterns):
            continue

        if parts[-1] == "__init__":
            parts = parts[:-1]
            if not parts:
                continue
            doc_path = doc_path.with_name("index.md")
            full_doc_path = full_doc_path.with_name("index.md")

        ident = ".".join(parts)
        write_file(full_doc_path.as_posix(), f"::: {ident}")
        set_edit_path(full_doc_path.as_posix(), path.relative_to(config.src_dir.parent).as_posix())
        entries.append((parts, doc_path.as_posix()))

    return entries
