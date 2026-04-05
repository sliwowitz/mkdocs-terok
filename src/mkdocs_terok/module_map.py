# SPDX-FileCopyrightText: 2026 Jiri Vyskocil
# SPDX-License-Identifier: 0BSD

"""Module map generator — module and class docstrings grouped by layer.

Walks the source tree, extracts module-level and class-level docstrings
via AST (no imports executed), and renders them as a single markdown
page.  When ``tach.toml`` is present, files are assigned to layers via
the ``[[modules]]`` entries and ordered by the ``layers`` list.
Otherwise files are grouped alphabetically by subdirectory.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class ModuleMapConfig:
    """Configuration for the module map generator."""

    src_root: Path = field(default_factory=lambda: Path.cwd() / "src")
    title: str = "Module Map"


def generate_module_map(config: ModuleMapConfig | None = None) -> str:
    """Generate a module map page from source docstrings.

    Returns a markdown string with module and class docstrings grouped
    by architectural layer.
    """
    cfg = config or ModuleMapConfig()
    pkg_root = _detect_package_root(cfg.src_root)
    layers = _discover_layers(cfg.src_root, pkg_root)
    return _render(pkg_root, layers, cfg.title)


# ── Package root detection ──────────────────────────────


def _detect_package_root(src_root: Path) -> Path:
    """Find the top-level Python package under *src_root*.

    If *src_root* contains exactly one directory with ``__init__.py``,
    returns that directory (the standard ``src/pkg/`` layout).
    Otherwise returns *src_root* itself.
    """
    if not src_root.is_dir():
        return src_root
    candidates = [
        d for d in sorted(src_root.iterdir()) if d.is_dir() and (d / "__init__.py").is_file()
    ]
    return candidates[0] if len(candidates) == 1 else src_root


# ── Layer discovery ─────────────────────────────────────


def _discover_layers(
    src_root: Path,
    pkg_root: Path,
) -> list[tuple[str, list[Path]]]:
    """Discover source files grouped by architectural layer.

    With ``tach.toml``: assigns each file to a layer via longest-prefix
    match on ``[[modules]]`` entries, then orders layers per the
    ``layers`` list.

    Without: groups by subdirectory, sorted alphabetically.
    """
    py_files = _collect_py_files(pkg_root)
    tach = _read_tach_config(src_root)
    if tach:
        return _group_by_tach(py_files, src_root, tach)
    return _group_by_directory(py_files, pkg_root)


def _collect_py_files(pkg_root: Path) -> list[Path]:
    """Collect all ``.py`` files under *pkg_root*, skipping ``__init__.py``."""
    return [f for f in sorted(pkg_root.rglob("*.py")) if f.name != "__init__.py"]


def _group_by_directory(
    py_files: list[Path],
    pkg_root: Path,
) -> list[tuple[str, list[Path]]]:
    """Group files by their immediate subdirectory under *pkg_root*."""
    groups: dict[str, list[Path]] = {}
    for path in py_files:
        rel = path.relative_to(pkg_root)
        group = rel.parts[0] if len(rel.parts) > 1 else "(root)"
        groups.setdefault(group, []).append(path)
    return sorted(groups.items())


# ── tach.toml integration ──────────────────────────────


@dataclass(frozen=True)
class _TachConfig:
    """Parsed subset of tach.toml relevant to layer ordering."""

    layers: list[str]
    module_layers: dict[str, str]  # dotted module path → layer name


def _read_tach_config(src_root: Path) -> _TachConfig | None:
    """Read layer ordering and module assignments from ``tach.toml``.

    Looks for ``tach.toml`` in *src_root*'s parent (the project root)
    and in the current working directory.  Returns ``None`` when the
    file is missing or has no ``layers`` key.
    """
    for candidate in (src_root.parent / "tach.toml", Path.cwd() / "tach.toml"):
        if candidate.is_file():
            return _parse_tach(candidate)
    return None


def _parse_tach(path: Path) -> _TachConfig | None:
    """Parse a ``tach.toml`` file into a :class:`_TachConfig`."""
    try:
        import tomllib

        data = tomllib.loads(path.read_text())
    except Exception:  # noqa: BLE001
        return None

    layers = data.get("layers")
    if not isinstance(layers, list):
        return None

    module_layers: dict[str, str] = {}
    for mod in data.get("modules", []):
        mod_path = mod.get("path", "")
        layer = mod.get("layer", "")
        if mod_path and layer:
            module_layers[mod_path] = layer

    return _TachConfig(layers=layers, module_layers=module_layers)


def _group_by_tach(
    py_files: list[Path],
    src_root: Path,
    tach: _TachConfig,
) -> list[tuple[str, list[Path]]]:
    """Assign files to tach layers and order by the ``layers`` list.

    tach defines layers top-down (highest first), but a module map
    reads better foundation-first, so we reverse the order.
    """
    layer_files: dict[str, list[Path]] = {}
    unassigned: list[Path] = []

    for path in py_files:
        layer = _file_to_layer(path, src_root, tach)
        if layer:
            layer_files.setdefault(layer, []).append(path)
        else:
            unassigned.append(path)

    ordered: list[tuple[str, list[Path]]] = []
    for layer in reversed(tach.layers):
        if layer in layer_files:
            ordered.append((layer, layer_files.pop(layer)))

    # Layers not in the ordering list, plus unassigned files
    for layer in sorted(layer_files):
        ordered.append((layer, layer_files[layer]))
    if unassigned:
        ordered.append(("(other)", unassigned))

    return ordered


def _file_to_layer(path: Path, src_root: Path, tach: _TachConfig) -> str | None:
    """Determine which tach layer a file belongs to via longest-prefix match."""
    rel = path.relative_to(src_root)
    dotted = ".".join(rel.with_suffix("").parts)

    best_match = ""
    best_layer = None
    for mod_path, layer in tach.module_layers.items():
        if (dotted == mod_path or dotted.startswith(mod_path + ".")) and len(mod_path) > len(
            best_match
        ):
            best_match = mod_path
            best_layer = layer

    return best_layer


# ── Docstring extraction ────────────────────────────────


def _module_label(path: Path, pkg_root: Path) -> str:
    """Derive a dotted module label from a file path."""
    rel = path.relative_to(pkg_root)
    return ".".join(rel.with_suffix("").parts)


def _extract_docstrings(path: Path) -> tuple[str, list[tuple[str, str]]]:
    """Extract module and class docstrings via AST.

    Returns ``(module_doc, [(class_name, class_doc), ...])``.
    Files with syntax errors return empty results.
    """
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        return ("", [])

    module_doc = ast.get_docstring(tree) or ""
    classes: list[tuple[str, str]] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            doc = ast.get_docstring(node) or ""
            classes.append((node.name, doc))

    return (module_doc, classes)


# ── Markdown rendering ──────────────────────────────────


def _render(
    pkg_root: Path,
    layers: list[tuple[str, list[Path]]],
    title: str,
) -> str:
    """Render extracted docstrings as a markdown page."""
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = [
        f"# {title}\n",
        f"*Generated: {now}*\n",
        "Module and class docstrings grouped by architectural layer.\n",
    ]

    for layer_name, paths in layers:
        layer_lines = _render_layer(pkg_root, layer_name, paths)
        if layer_lines:
            lines.extend(layer_lines)

    return "\n".join(lines)


def _render_layer(
    pkg_root: Path,
    layer_name: str,
    paths: list[Path],
) -> list[str]:
    """Render a single layer section.  Returns empty list if no docs found."""
    module_sections: list[str] = []

    for path in paths:
        if not path.is_file():
            continue
        section = _render_module(pkg_root, path)
        if section:
            module_sections.append(section)

    if not module_sections:
        return []

    lines = [f"---\n\n## {layer_name}\n"]
    lines.extend(module_sections)
    return lines


def _render_module(pkg_root: Path, path: Path) -> str | None:
    """Render a single module section.  Returns None if no docs found."""
    label = _module_label(path, pkg_root)
    module_doc, classes = _extract_docstrings(path)
    if not module_doc and not classes:
        return None

    parts: list[str] = [f"### `{label}`\n"]
    if module_doc:
        parts.append(f"{module_doc}\n")

    for cls_name, cls_doc in classes:
        if not cls_doc:
            continue
        first_line, _, rest = cls_doc.partition("\n")
        rest = rest.strip()
        parts.append(f"**{cls_name}** — {first_line}")
        if rest:
            for line in rest.splitlines():
                parts.append(f"> {line}" if line.strip() else ">")
        parts.append("")

    return "\n".join(parts)
