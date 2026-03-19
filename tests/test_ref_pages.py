# SPDX-FileCopyrightText: 2026 Jiri Vyskocil
# SPDX-License-Identifier: 0BSD

"""Tests for the reference pages generator."""

from __future__ import annotations

from pathlib import Path

from mkdocs_terok.ref_pages import RefPagesConfig, generate_ref_pages


def test_generate_ref_pages_writes_stubs(tmp_path: Path) -> None:
    """Reference page generation should write mkdocstrings stubs."""
    src = tmp_path / "src"
    pkg = src / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("# init")
    (pkg / "module_a.py").write_text("# module a")
    (pkg / "module_b.py").write_text("# module b")

    written: dict[str, str] = {}
    edit_paths: dict[str, str] = {}

    config = RefPagesConfig(src_dir=src)
    entries = generate_ref_pages(
        config,
        write_file=lambda p, c: written.__setitem__(p, c),
        set_edit_path=lambda p, s: edit_paths.__setitem__(p, s),
    )

    assert len(entries) == 3  # __init__ (as index) + module_a + module_b
    assert ("mypkg",) in [parts for parts, _ in entries]
    assert ("mypkg", "module_a") in [parts for parts, _ in entries]
    assert ("mypkg", "module_b") in [parts for parts, _ in entries]

    assert written["reference/mypkg/index.md"] == "::: mypkg"
    assert written["reference/mypkg/module_a.md"] == "::: mypkg.module_a"

    # Nav entries should include the output prefix
    nav_paths = [path for _, path in entries]
    assert "reference/mypkg/index.md" in nav_paths
    assert "reference/mypkg/module_a.md" in nav_paths

    # Edit paths should point back to source
    assert edit_paths["reference/mypkg/module_a.md"] == "src/mypkg/module_a.py"


def test_generate_ref_pages_skips_patterns(tmp_path: Path) -> None:
    """Files matching skip_patterns should be excluded."""
    src = tmp_path / "src"
    pkg = src / "mypkg"
    (pkg / "resources").mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "__main__.py").write_text("")
    (pkg / "resources" / "helper.py").write_text("")
    (pkg / "real.py").write_text("")

    written: dict[str, str] = {}
    config = RefPagesConfig(src_dir=src, skip_patterns=("__main__", "resources"))
    entries = generate_ref_pages(
        config,
        write_file=lambda p, c: written.__setitem__(p, c),
        set_edit_path=lambda _p, _s: None,
    )

    module_names = [parts for parts, _ in entries]
    assert ("mypkg", "__main__") not in module_names
    assert ("mypkg", "resources", "helper") not in module_names
    assert ("mypkg", "real") in module_names


def test_generate_ref_pages_custom_prefix(tmp_path: Path) -> None:
    """Custom output_prefix should change the doc path prefix."""
    src = tmp_path / "src"
    pkg = src / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("")

    written: dict[str, str] = {}
    config = RefPagesConfig(src_dir=src, output_prefix="api")
    generate_ref_pages(
        config,
        write_file=lambda p, c: written.__setitem__(p, c),
        set_edit_path=lambda _p, _s: None,
    )

    assert "api/mypkg/mod.md" in written
