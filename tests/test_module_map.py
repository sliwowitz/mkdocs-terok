# SPDX-FileCopyrightText: 2026 Jiri Vyskocil
# SPDX-License-Identifier: 0BSD

"""Tests for the module map generator."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from mkdocs_terok.module_map import (
    FileType,
    ModuleMapConfig,
    _classify,
    _collect_py_files,
    _detect_package_root,
    _domain_groups,
    _extract_docstrings,
    _file_to_layer,
    _group_by_directory,
    _group_by_tach,
    _module_label,
    _parse_tach,
    _render_catalog,
    _render_layer,
    _render_module,
    _render_narrative,
    _render_waypoint,
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


def test_module_label_init_file() -> None:
    """__init__.py labels use the package name, not __init__."""
    pkg = Path("/src/mypackage")
    assert _module_label(pkg / "core" / "__init__.py", pkg) == "core"


def test_module_label_root_init() -> None:
    """Root __init__.py uses the package directory name."""
    pkg = Path("/src/mypackage")
    assert _module_label(pkg / "__init__.py", pkg) == "mypackage"


# ── _detect_package_root ────────────────────────────────


def test_detect_package_root_single_package(tmp_path: Path) -> None:
    """Single package directory is detected as the package root."""
    pkg = tmp_path / "src" / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").touch()
    assert _detect_package_root(tmp_path / "src") == pkg


def test_detect_package_root_nonexistent_dir() -> None:
    """Non-existent src_root is returned as-is."""
    missing = Path("/nonexistent/src")
    assert _detect_package_root(missing) == missing


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
    module_doc, classes, func_count = _extract_docstrings(src)
    assert module_doc == "Module docstring."
    assert classes == [("Foo", "Foo does things."), ("Bar", "")]
    assert func_count == 0


def test_extract_docstrings_syntax_error(tmp_path: Path) -> None:
    """Syntax errors produce empty results without crashing."""
    src = tmp_path / "broken.py"
    src.write_text("def f(:\n")
    module_doc, classes, func_count = _extract_docstrings(src)
    assert module_doc == ""
    assert classes == []
    assert func_count == 0


def test_extract_docstrings_counts_public_functions(tmp_path: Path) -> None:
    """Public function count excludes private (underscore-prefixed) functions."""
    src = tmp_path / "funcs.py"
    src.write_text(
        dedent('''\
        """Module with functions."""

        def public_one(): pass
        def public_two(): pass
        def _private(): pass
        async def public_async(): pass
    ''')
    )
    _, _, func_count = _extract_docstrings(src)
    assert func_count == 3


# ── _collect_py_files ───────────────────────────────────


def test_collect_py_files_includes_init(tmp_path: Path) -> None:
    """__init__.py files are included in collection."""
    (tmp_path / "__init__.py").touch()
    (tmp_path / "core.py").touch()
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "__init__.py").touch()
    (sub / "engine.py").touch()

    files = _collect_py_files(tmp_path)
    names = [f.name for f in files]
    assert "__init__.py" in names
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
        source_roots=["src"],
        config_dir=Path("/"),
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


def test_parse_tach_valid(tmp_path: Path) -> None:
    """Valid tach.toml is parsed into a _TachConfig."""
    tach = tmp_path / "tach.toml"
    tach.write_text(
        dedent("""\
        layers = ["cli", "core"]

        [[modules]]
        path = "pkg.core"
        layer = "core"
    """)
    )
    result = _parse_tach(tach)
    assert result is not None
    assert result.layers == ["cli", "core"]
    assert result.module_layers == {"pkg.core": "core"}


def test_parse_tach_no_layers(tmp_path: Path) -> None:
    """tach.toml without layers key returns None."""
    tach = tmp_path / "tach.toml"
    tach.write_text("exact = true\n")
    assert _parse_tach(tach) is None


def test_parse_tach_invalid_toml(tmp_path: Path) -> None:
    """Malformed TOML returns None without crashing."""
    tach = tmp_path / "tach.toml"
    tach.write_text("{{invalid toml}}")
    assert _parse_tach(tach) is None


def test_group_by_tach_unassigned_files(tmp_path: Path) -> None:
    """Files not matching any tach module go into (other) group."""
    src = tmp_path / "src"
    pkg = src / "otherpkg"
    pkg.mkdir(parents=True)
    (pkg / "mystery.py").write_text('"""Mystery module."""\n')

    tach = _TachConfig(
        layers=["core"],
        module_layers={"mypkg.core": "core"},
        source_roots=["src"],
        config_dir=tmp_path,
    )
    py_files = _collect_py_files(pkg)
    layers = _group_by_tach(py_files, tach)
    layer_names = [name for name, _files in layers]

    assert "(other)" in layer_names


def test_group_by_tach_orders_by_layer(tmp_path: Path) -> None:
    """Files are grouped and ordered according to the tach layers list."""
    src = tmp_path / "src"
    pkg = src / "mypkg"
    for subdir in ("common", "core", "lib", "cli"):
        d = pkg / subdir
        d.mkdir(parents=True)
        (d / f"{subdir}_mod.py").write_text(f'"""Module in {subdir}."""\n')

    tach = _TachConfig(
        layers=["cli", "support", "core", "common"],
        module_layers={
            "mypkg.common": "common",
            "mypkg.core": "core",
            "mypkg.lib": "support",
            "mypkg.cli": "cli",
        },
        source_roots=["src"],
        config_dir=tmp_path,
    )
    py_files = _collect_py_files(pkg)
    layers = _group_by_tach(py_files, tach)
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


def test_render_module_class_without_docstring(tmp_path: Path) -> None:
    """Classes without docstrings are skipped in rendering."""
    src = tmp_path / "sparse.py"
    src.write_text(
        dedent('''\
        """Module doc."""

        class Documented:
            """Has a docstring."""

        class Bare:
            pass
    ''')
    )
    result = _render_module(tmp_path, src)
    assert result is not None
    assert "**Documented**" in result
    assert "Bare" not in result


def test_render_layer_empty_when_no_docs(tmp_path: Path) -> None:
    """Layer with only undocumented files returns empty list."""
    src = tmp_path / "bare.py"
    src.write_text("x = 1\n")
    assert _render_layer(tmp_path, tmp_path, "empty_layer", [src]) == []


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


def test_generate_module_map_with_tach(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When tach.toml is present, layers are ordered by its layers list."""
    pkg = tmp_path / "src" / "mypkg"
    for sub in ("common", "core"):
        d = pkg / sub
        d.mkdir(parents=True)
        (d / "__init__.py").touch()
        (d / f"{sub}_mod.py").write_text(f'"""The {sub} module."""\n')
    (pkg / "__init__.py").touch()

    tach = tmp_path / "tach.toml"
    tach.write_text(
        dedent("""\
        source_roots = ["src"]
        layers = ["core", "common"]

        [[modules]]
        path = "mypkg.common"
        layer = "common"

        [[modules]]
        path = "mypkg.core"
        layer = "core"
    """)
    )

    monkeypatch.chdir(tmp_path)
    config = ModuleMapConfig(src_root=tmp_path / "src", title="Tach Map")
    result = generate_module_map(config)

    # tach layers are ["core", "common"], reversed → common first
    common_pos = result.index("## common")
    core_pos = result.index("## core")
    assert common_pos < core_pos


# ── _classify ──────────────────────────────────────────


def test_classify_waypoint_from_docstring() -> None:
    """Modules whose docstring contains delegation language are waypoints."""
    p = Path("mod.py")
    assert (
        _classify(p, "Public API facade. Delegates to collaborators.", [], 0) == FileType.WAYPOINT
    )
    assert _classify(p, "Waypoint for the nft subsystem.", [], 0) == FileType.WAYPOINT
    assert _classify(p, "Re-export public symbols.", [], 0) == FileType.WAYPOINT


def test_classify_waypoint_from_init() -> None:
    """__init__.py with a docstring is always classified as waypoint."""
    init = Path("pkg/__init__.py")
    assert _classify(init, "Some package.", [], 5) == FileType.WAYPOINT
    # Without a docstring, __init__.py falls through to default
    assert _classify(init, "", [], 0) == FileType.NARRATIVE


def test_classify_catalog_from_class_count() -> None:
    """Modules with many classes and few functions are catalogs."""
    p = Path("types.py")
    classes = [("A", "a"), ("B", "b"), ("C", "c"), ("D", "d")]
    assert _classify(p, "Types module.", classes, 0) == FileType.CATALOG
    assert _classify(p, "Types module.", classes, 2) == FileType.CATALOG
    # Too many functions → narrative
    assert _classify(p, "Types module.", classes, 3) == FileType.NARRATIVE


def test_classify_narrative_default() -> None:
    """Modules that match no special pattern default to narrative."""
    p = Path("mod.py")
    assert _classify(p, "Regular module.", [("Foo", "foo")], 5) == FileType.NARRATIVE
    assert _classify(p, "", [], 0) == FileType.NARRATIVE


# ── Renderers ──────────────────────────────────────────


def test_render_narrative_output() -> None:
    """Narrative renderer produces prose with class blockquotes."""
    result = _render_narrative(
        "pkg.engine", "The engine.", [("Engine", "Main engine.\n\nDetails.")]
    )
    assert "### `pkg.engine`" in result
    assert "The engine." in result
    assert "**Engine** — Main engine." in result
    assert "> Details." in result


def test_render_catalog_output() -> None:
    """Catalog renderer produces a markdown table."""
    classes = [("Foo", "First."), ("Bar", "Second.")]
    result = _render_catalog("pkg.types", "Type definitions.", classes)
    assert "*(catalog)*" in result
    assert "| Type | Description |" in result
    assert "| `Foo` | First. |" in result
    assert "| `Bar` | Second. |" in result


def test_render_waypoint_output() -> None:
    """Waypoint renderer produces a bullet list."""
    classes = [("Shield", "Public API.")]
    result = _render_waypoint("pkg", "Facade. Delegates to collaborators.", classes)
    assert "*(waypoint)*" in result
    assert "- **Shield** — Public API." in result


def test_render_module_dispatches_by_type(tmp_path: Path) -> None:
    """_render_module classifies and dispatches to the correct renderer."""
    waypoint = tmp_path / "facade.py"
    waypoint.write_text('"""Public facade. Delegates to engine."""\n')
    result = _render_module(tmp_path, waypoint)
    assert result is not None
    assert "*(waypoint)*" in result

    catalog = tmp_path / "types.py"
    catalog.write_text(
        dedent('''\
        """Type definitions."""
        class A:
            """A."""
        class B:
            """B."""
        class C:
            """C."""
        class D:
            """D."""
    ''')
    )
    result = _render_module(tmp_path, catalog)
    assert result is not None
    assert "*(catalog)*" in result


def test_render_module_depth_parameter(tmp_path: Path) -> None:
    """Depth parameter controls heading level."""
    src = tmp_path / "mod.py"
    src.write_text('"""A module."""\n')
    result_h3 = _render_module(tmp_path, src, depth=3)
    result_h4 = _render_module(tmp_path, src, depth=4)
    assert result_h3 is not None
    assert result_h4 is not None
    assert result_h3.startswith("### ")
    assert result_h4.startswith("#### ")


# ── _domain_groups ─────────────────────────────────────


def test_domain_groups_multiple_domains(tmp_path: Path) -> None:
    """Files from multiple subpackages produce named groups."""
    nft = tmp_path / "nft"
    dns = tmp_path / "dns"
    nft.mkdir()
    dns.mkdir()
    paths = [
        nft / "constants.py",
        nft / "rules.py",
        dns / "resolver.py",
    ]
    for p in paths:
        p.touch()

    groups = _domain_groups(paths, tmp_path)
    group_names = [name for name, _ in groups]
    assert "nft" in group_names
    assert "dns" in group_names


def test_domain_groups_single_domain(tmp_path: Path) -> None:
    """Files from a single domain produce one unnamed group."""
    sub = tmp_path / "core"
    sub.mkdir()
    paths = [sub / "a.py", sub / "b.py"]
    for p in paths:
        p.touch()

    groups = _domain_groups(paths, tmp_path)
    assert len(groups) == 1
    assert groups[0][0] == ""


def test_domain_groups_flat_files(tmp_path: Path) -> None:
    """Files directly under pkg_root produce one unnamed group."""
    paths = [tmp_path / "a.py", tmp_path / "b.py"]
    for p in paths:
        p.touch()

    groups = _domain_groups(paths, tmp_path)
    assert len(groups) == 1
    assert groups[0][0] == ""


# ── CLI ────────────────────────────────────────────────


def test_main_writes_to_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI --output writes markdown to the specified file."""
    from mkdocs_terok.module_map import main

    pkg = tmp_path / "src" / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").touch()
    (pkg / "engine.py").write_text('"""Engine module."""\n')
    out = tmp_path / "output.md"

    monkeypatch.setattr("sys.argv", ["module_map", str(pkg), "--no-tach", "-o", str(out)])
    main()

    content = out.read_text()
    assert "# Module Map" in content
    assert "engine" in content
