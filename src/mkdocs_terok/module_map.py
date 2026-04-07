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
from enum import Enum, auto
from pathlib import Path


@dataclass(frozen=True)
class ModuleMapConfig:
    """Configuration for the module map generator."""

    src_root: Path = field(default_factory=lambda: Path.cwd() / "src")
    tach_path: Path | None = None
    no_tach: bool = False
    title: str = "Module Map"


def generate_module_map(config: ModuleMapConfig | None = None) -> str:
    """Generate a module map page from source docstrings.

    Returns a markdown string with module and class docstrings grouped
    by architectural layer.
    """
    cfg = config or ModuleMapConfig()
    pkg_root = (
        cfg.src_root
        if (cfg.src_root / "__init__.py").is_file()
        else _detect_package_root(cfg.src_root)
    )
    layers, label_root = _discover_layers(
        cfg.src_root, pkg_root, tach_path=cfg.tach_path, no_tach=cfg.no_tach
    )
    return _render(pkg_root, label_root, layers, cfg.title)


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
    *,
    tach_path: Path | None = None,
    no_tach: bool = False,
) -> tuple[list[tuple[str, list[Path]]], Path]:
    """Discover source files grouped by architectural layer.

    With ``tach.toml``: assigns each file to a layer via longest-prefix
    match on ``[[modules]]`` entries, then orders layers per the
    ``layers`` list.

    Without: groups by subdirectory, sorted alphabetically.

    Returns ``(layers, label_root)`` where *label_root* is the base path
    for computing dotted module labels — the tach source root when tach
    is active, or *pkg_root* otherwise.
    """
    py_files = _collect_py_files(pkg_root)
    if not no_tach:
        if tach_path:
            tach = _parse_tach(tach_path)
            if tach is None:
                raise ValueError(f"Could not load tach config: {tach_path}")
        else:
            tach = _read_tach_config(src_root)
        if tach:
            tach_src = _resolve_tach_src_root(tach)
            return _group_by_tach(py_files, tach), tach_src
    return _group_by_directory(py_files, pkg_root), pkg_root


def _collect_py_files(pkg_root: Path) -> list[Path]:
    """Collect all ``.py`` files under *pkg_root*, including ``__init__.py``."""
    return sorted(pkg_root.rglob("*.py"))


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
    source_roots: list[str] = field(default_factory=lambda: ["."])
    config_dir: Path = field(default_factory=Path.cwd)  # directory containing tach.toml


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

    raw_roots = data.get("source_roots", ["."])
    source_roots = raw_roots if isinstance(raw_roots, list) else ["."]
    return _TachConfig(
        layers=layers,
        module_layers=module_layers,
        source_roots=source_roots,
        config_dir=path.parent,
    )


def _resolve_tach_src_root(tach: _TachConfig) -> Path:
    """Resolve the source root directory from tach configuration.

    Uses the first ``source_roots`` entry relative to the tach.toml
    directory.  Falls back to the tach.toml directory itself.
    """
    for root in tach.source_roots:
        candidate = (tach.config_dir / root).resolve()
        if candidate.is_dir():
            return candidate
    return tach.config_dir


def _group_by_tach(
    py_files: list[Path],
    tach: _TachConfig,
) -> list[tuple[str, list[Path]]]:
    """Assign files to tach layers and order by the ``layers`` list.

    tach defines layers top-down (highest first), but a module map
    reads better foundation-first, so we reverse the order.
    """
    tach_src = _resolve_tach_src_root(tach)
    layer_files: dict[str, list[Path]] = {}
    unassigned: list[Path] = []

    for path in py_files:
        layer = _file_to_layer(path, tach_src, tach)
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
    try:
        rel = path.relative_to(src_root)
    except ValueError:
        return None
    parts = rel.with_suffix("").parts
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    dotted = ".".join(parts)

    best_match = ""
    best_layer = None
    for mod_path, layer in tach.module_layers.items():
        if (dotted == mod_path or dotted.startswith(mod_path + ".")) and len(mod_path) > len(
            best_match
        ):
            best_match = mod_path
            best_layer = layer

    return best_layer


# ── File-type classification ───────────────────────────


class FileType(Enum):
    """Module classification heuristic for rendering style."""

    NARRATIVE = auto()
    CATALOG = auto()
    WAYPOINT = auto()


_WAYPOINT_SIGNALS = frozenset(
    {
        "facade",
        "re-export",
        "delegates",
        "coordinator",
        "dispatcher",
        "waypoint",
    }
)


def _classify(
    path: Path, module_doc: str, classes: list[tuple[str, str]], func_count: int
) -> FileType:
    """Classify a module as narrative, catalog, or waypoint.

    Heuristics (not assertions):
    - Waypoint: ``__init__.py`` with a docstring, or docstring contains
      delegation/facade language
    - Catalog: many types (>= 4), few public functions (<= 2)
    - Narrative: everything else
    """
    if path.name == "__init__.py" and module_doc:
        return FileType.WAYPOINT
    doc_lower = module_doc.lower()
    if any(signal in doc_lower for signal in _WAYPOINT_SIGNALS):
        return FileType.WAYPOINT
    if len(classes) >= 4 and func_count <= 2:
        return FileType.CATALOG
    return FileType.NARRATIVE


# ── Docstring extraction ────────────────────────────────


def _module_label(path: Path, pkg_root: Path) -> str:
    """Derive a dotted module label from a file path."""
    rel = path.relative_to(pkg_root)
    parts = rel.with_suffix("").parts
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) if parts else pkg_root.name


def _extract_docstrings(path: Path) -> tuple[str, list[tuple[str, str]], int]:
    """Extract module docstring, class docstrings, and public function count via AST.

    Returns ``(module_doc, [(class_name, class_doc), ...], public_func_count)``.
    Files with syntax errors return empty results.
    """
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        return ("", [], 0)

    module_doc = ast.get_docstring(tree) or ""
    classes: list[tuple[str, str]] = []
    func_count = 0
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            doc = ast.get_docstring(node) or ""
            classes.append((node.name, doc))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                func_count += 1

    return (module_doc, classes, func_count)


# ── Domain grouping ────────────────────────────────────


def _domain_groups(paths: list[Path], pkg_root: Path) -> list[tuple[str, list[Path]]]:
    """Group paths within a layer by domain subpackage.

    When a tach layer contains modules from multiple domain packages
    (e.g. ``nft/constants`` at foundation AND ``nft/rules`` at core),
    they are grouped under the domain name for contiguous rendering.

    Returns ``[("", paths)]`` when visual grouping is unnecessary:
    no subpackages exist, all files share one domain, or only one
    non-trivial group would be shown.
    """
    # Identify domain packages: paths with at least two components
    known_domains: set[str] = set()
    for path in paths:
        rel = path.relative_to(pkg_root)
        parts = rel.parts
        if len(parts) >= 2:
            # First directory component below pkg_root is a potential domain
            known_domains.add(parts[0])

    if not known_domains:
        return [("", paths)]

    # Assign each path to its domain group, preserving order
    groups: dict[str, list[Path]] = {}
    order: list[str] = []
    for path in paths:
        rel = path.relative_to(pkg_root)
        first = rel.parts[0] if len(rel.parts) >= 2 else ""
        group = first if first in known_domains else ""

        if group not in groups:
            order.append(group)
            groups[group] = []
        groups[group].append(path)

    # Single effective group → no visual grouping needed
    non_trivial = [g for g in order if g or len(groups.get("", [])) > 1]
    if len(non_trivial) <= 1:
        return [("", paths)]

    return [(g, groups[g]) for g in order]


# ── Markdown rendering ──────────────────────────────────


def _render(
    pkg_root: Path,
    label_root: Path,
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
        layer_lines = _render_layer(pkg_root, label_root, layer_name, paths)
        if layer_lines:
            lines.extend(layer_lines)

    return "\n".join(lines)


def _render_layer(
    pkg_root: Path,
    label_root: Path,
    layer_name: str,
    paths: list[Path],
) -> list[str]:
    """Render a single layer section with optional domain grouping.

    When a layer contains modules from multiple domain packages, each
    domain gets a ``###`` subheading and modules render at ``####`` depth.
    """
    groups = _domain_groups(paths, pkg_root)
    all_sections: list[str] = []

    for group_name, group_paths in groups:
        depth = 4 if group_name else 3
        sections: list[str] = []
        for path in group_paths:
            if not path.is_file():
                continue
            section = _render_module(label_root, path, depth=depth)
            if section:
                sections.append(section)
        if not sections:
            continue
        if group_name:
            heading = group_name.replace("_", " ").title()
            all_sections.append(f"### {heading}\n")
        all_sections.extend(sections)

    if not all_sections:
        return []

    lines = [f"---\n\n## {layer_name}\n"]
    lines.extend(all_sections)
    return lines


def _render_module(pkg_root: Path, path: Path, *, depth: int = 3) -> str | None:
    """Render a single module section.  Returns None if no docs found."""
    label = _module_label(path, pkg_root)
    module_doc, classes, func_count = _extract_docstrings(path)
    if not module_doc and not classes:
        return None

    file_type = _classify(path, module_doc, classes, func_count)
    renderer = _RENDERERS[file_type]
    return renderer(label, module_doc, classes, depth=depth)


def _render_narrative(
    label: str,
    module_doc: str,
    classes: list[tuple[str, str]],
    *,
    depth: int = 3,
) -> str:
    """Render a narrative module: prose intro, then class subsections."""
    hashes = "#" * depth
    parts: list[str] = [f"{hashes} `{label}`\n"]
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


def _render_catalog(
    label: str,
    module_doc: str,
    classes: list[tuple[str, str]],
    *,
    depth: int = 3,
) -> str:
    """Render a catalog module: prose intro, then compact type table."""
    hashes = "#" * depth
    parts: list[str] = [f"{hashes} `{label}` *(catalog)*\n"]
    if module_doc:
        parts.append(f"{module_doc}\n")
    documented = [(name, doc) for name, doc in classes if doc]
    if documented:
        parts.append("| Type | Description |")
        parts.append("|------|-------------|")
        for cls_name, cls_doc in documented:
            first_line = cls_doc.split("\n", 1)[0]
            parts.append(f"| `{cls_name}` | {first_line} |")
        parts.append("")
    return "\n".join(parts)


def _render_waypoint(
    label: str,
    module_doc: str,
    classes: list[tuple[str, str]],
    *,
    depth: int = 3,
) -> str:
    """Render a waypoint module: prose intro with collaborator map."""
    hashes = "#" * depth
    parts: list[str] = [f"{hashes} `{label}` *(waypoint)*\n"]
    if module_doc:
        parts.append(f"{module_doc}\n")
    documented = [(name, doc) for name, doc in classes if doc]
    for cls_name, cls_doc in documented:
        first_line = cls_doc.split("\n", 1)[0]
        parts.append(f"- **{cls_name}** — {first_line}")
    if documented:
        parts.append("")
    return "\n".join(parts)


_RENDERERS = {
    FileType.NARRATIVE: _render_narrative,
    FileType.CATALOG: _render_catalog,
    FileType.WAYPOINT: _render_waypoint,
}


# ── CLI ────────────────────────────────────────────────


def main() -> None:
    """Generate a module map from the command line."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Generate a module map from source docstrings.",
    )
    parser.add_argument("src_root", type=Path, help="Source root directory (e.g. src/pkg)")
    parser.add_argument("--tach", type=Path, default=None, help="Path to tach.toml")
    parser.add_argument("--no-tach", action="store_true", help="Disable tach layer ordering")
    parser.add_argument("--title", default="Module Map", help="Page title")
    parser.add_argument("-o", "--output", type=Path, default=None, help="Output file (stdout)")

    args = parser.parse_args()
    config = ModuleMapConfig(
        src_root=args.src_root.resolve(),
        tach_path=args.tach.resolve() if args.tach else None,
        no_tach=args.no_tach,
        title=args.title,
    )
    result = generate_module_map(config)

    if args.output:
        args.output.write_text(result)
        print(f"Written to {args.output}", file=sys.stderr)
    else:
        print(result)


if __name__ == "__main__":
    main()
