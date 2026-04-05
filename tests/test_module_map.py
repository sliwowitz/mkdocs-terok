# SPDX-FileCopyrightText: 2026 Jiri Vyskocil
# SPDX-License-Identifier: 0BSD

"""Tests for the module map generator."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from mkdocs_terok.module_map import (
    ModuleMapConfig,
    _collect_py_files,
    _detect_package_root,
    _extract_docstrings,
    _file_to_layer,
    _group_by_directory,
    _group_by_tach,
    _module_label,
    _render_module,
    _TachConfig,
    generate_module_map,
)

# ── _module_label ───────────────────────────────────────


def test_module_label_strips_suffix_and_joins() -> None:
    """Dotted label is derived from the path relative to src root."""
    pkg = Path("/src/mypackage")
    assert _module_label(pkg / "core" / "engine.py", pkg) == "core.engine"


def test_module_label_single_file() -> None:
    """Top-level file produces a single-component label."""
    pkg = Path("/src/mypackage")
    assert _module_label(pkg / "utils.py", pkg) == "utils"


# ── _detect_package_root ────────────────────────────────


def test_detect_package_root_single_package(tmp_path: Path) -> None:
    """Single package directory is detected as the package root."""
    pkg = tmp_path / "src" / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").touch()
    assert _detect_package_root(tmp_path / "src") == pkg


def test_detect_package_root_no_package(tmp_path: Path) -> None:
    """Without a recognisable package, src_root is returned as-is."""
    src = tmp_path / "src"
    src.mkdir()
    assert _detect_package_root(src) == src


def test_detect_package_root_multiple_packages(tmp_path: Path) -> None:
    """Multiple packages: src_root returned (ambiguous, no auto-detect)."""
    src = tmp_path / "src"
    for name in ("pkg_a", "pkg_b"):
        d = src / name
        d.mkdir(parents=True)
        (d / "__init__.py").touch()
    assert _detect_package_root(src) == src


# ── _extract_docstrings ─────────────────────────────────


def test_extract_docstrings_module_and_classes(tmp_path: Path) -> None:
    """Module and class docstrings are extracted via AST."""
    src = tmp_path / "example.py"
    src.write_text(
        dedent('''\
        """Module docstring."""

        class Foo:
            """Foo does things."""
            pass

        class Bar:
            pass
    ''')
    )
    module_doc, classes = _extract_docstrings(src)
    assert module_doc == "Module docstring."
    assert classes == [("Foo", "Foo does things."), ("Bar", "")]


def test_extract_docstrings_syntax_error(tmp_path: Path) -> None:
    """Syntax errors produce empty results without crashing."""
    src = tmp_path / "broken.py"
    src.write_text("def f(:\n")
    module_doc, classes = _extract_docstrings(src)
    assert module_doc == ""
    assert classes == []


# ── _collect_py_files ───────────────────────────────────


def test_collect_py_files_skips_init(tmp_path: Path) -> None:
    """__init__.py files are excluded from collection."""
    (tmp_path / "__init__.py").touch()
    (tmp_path / "core.py").touch()
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "__init__.py").touch()
    (sub / "engine.py").touch()

    files = _collect_py_files(tmp_path)
    names = [f.name for f in files]
    assert "__init__.py" not in names
    assert "core.py" in names
    assert "engine.py" in names


# ── _group_by_directory ─────────────────────────────────


def test_group_by_directory_groups_correctly(tmp_path: Path) -> None:
    """Files are grouped by immediate subdirectory, top-level goes to (root)."""
    (tmp_path / "top.py").touch()
    sub = tmp_path / "core"
    sub.mkdir()
    (sub / "engine.py").touch()
    (sub / "utils.py").touch()

    files = _collect_py_files(tmp_path)
    groups = _group_by_directory(files, tmp_path)

    group_dict = dict(groups)
    assert "(root)" in group_dict
    assert "core" in group_dict
    assert len(group_dict["core"]) == 2


# ── tach integration ────────────────────────────────────


@pytest.fixture()
def tach_config() -> _TachConfig:
    """A tach config resembling terok-shield's layer structure."""
    return _TachConfig(
        layers=["cli", "support", "core", "common"],
        module_layers={
            "mypkg.common": "common",
            "mypkg.common.config": "common",
            "mypkg.core": "core",
            "mypkg.core.nft": "core",
            "mypkg.lib": "support",
            "mypkg.lib.audit": "support",
            "mypkg": "support",
            "mypkg.cli": "cli",
        },
    )


def test_file_to_layer_longest_prefix(tach_config: _TachConfig) -> None:
    """Layer assignment uses longest-prefix match on dotted module path."""
    src = Path("/src")
    assert _file_to_layer(src / "mypkg" / "common" / "config.py", src, tach_config) == "common"
    assert _file_to_layer(src / "mypkg" / "core" / "nft.py", src, tach_config) == "core"
    assert _file_to_layer(src / "mypkg" / "lib" / "audit.py", src, tach_config) == "support"
    assert _file_to_layer(src / "mypkg" / "cli" / "main.py", src, tach_config) == "cli"


def test_file_to_layer_unmatched_returns_none(tach_config: _TachConfig) -> None:
    """Files not matching any tach module return None."""
    src = Path("/src")
    assert _file_to_layer(src / "otherpkg" / "foo.py", src, tach_config) is None


def test_group_by_tach_orders_by_layer(tmp_path: Path, tach_config: _TachConfig) -> None:
    """Files are grouped and ordered according to the tach layers list."""
    src = tmp_path / "src"
    pkg = src / "mypkg"
    for subdir in ("common", "core", "lib", "cli"):
        d = pkg / subdir
        d.mkdir(parents=True)
        (d / f"{subdir}_mod.py").write_text(f'"""Module in {subdir}."""\n')

    py_files = _collect_py_files(pkg)
    layers = _group_by_tach(py_files, pkg, src, tach_config)
    layer_names = [name for name, _files in layers]

    assert layer_names == ["common", "core", "support", "cli"]


# ── _render_module ──────────────────────────────────────


def test_render_module_with_class(tmp_path: Path) -> None:
    """Modules with docstrings render as H3 + class entries."""
    src = tmp_path / "engine.py"
    src.write_text(
        dedent('''\
        """The engine module.

        Handles core logic.
        """

        class Engine:
            """Main engine.

            Processes all the things.
            """
            pass
    ''')
    )
    result = _render_module(tmp_path, src)
    assert result is not None
    assert "### `engine`" in result
    assert "The engine module." in result
    assert "**Engine** — Main engine." in result
    assert "> Processes all the things." in result


def test_render_module_no_docs(tmp_path: Path) -> None:
    """Modules without any docstrings return None."""
    src = tmp_path / "bare.py"
    src.write_text("x = 1\n")
    assert _render_module(tmp_path, src) is None


# ── generate_module_map (integration) ───────────────────


def test_generate_module_map_produces_markdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Full generation produces a markdown page with title and layer sections."""
    pkg = tmp_path / "src" / "mypkg"
    core = pkg / "core"
    core.mkdir(parents=True)
    (pkg / "__init__.py").touch()
    (core / "__init__.py").touch()
    (core / "engine.py").write_text('"""Core engine module."""\n')

    monkeypatch.chdir(tmp_path)
    config = ModuleMapConfig(src_root=tmp_path / "src", title="Test Module Map")
    result = generate_module_map(config)

    assert "# Test Module Map" in result
    assert "*Generated:" in result
    assert "### `core.engine`" in result
    assert "Core engine module." in result
