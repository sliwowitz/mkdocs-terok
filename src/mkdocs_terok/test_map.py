# SPDX-FileCopyrightText: 2026 Jiri Vyskocil
# SPDX-License-Identifier: Apache-2.0

"""Generate a Markdown test map from pytest collection.

Runs ``pytest --collect-only -qq`` on an integration test directory and
groups the collected test IDs by subdirectory, producing Markdown tables
with optional marker extraction and CI tier columns.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class TestMapConfig:
    """Configuration for test map generation.

    Attributes:
        root: Project root directory.
        integration_dir: Integration test directory. Defaults to
            ``root / "tests" / "integration"``.
        dir_order: Canonical ordering for known test subdirectories.
        show_markers: Include CI tier and marker columns in the output.
        title: Page title for the generated Markdown.
    """

    root: Path = field(default_factory=Path.cwd)
    integration_dir: Path | None = None
    dir_order: Sequence[str] = ()
    show_markers: bool = True
    title: str = "Integration Test Map"

    @property
    def resolved_integration_dir(self) -> Path:
        """Return the integration test directory, with fallback to default."""
        if self.integration_dir is not None:
            return self.integration_dir
        return self.root / "tests" / "integration"


def collect_tests(*, config: TestMapConfig | None = None) -> list[str]:
    """Run pytest --collect-only and return the list of test node IDs.

    Args:
        config: Test map configuration. Uses defaults if ``None``.

    Raises:
        RuntimeError: If pytest collection fails (non-zero exit code).
    """
    if config is None:
        config = TestMapConfig()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-qq",
            "-p",
            "no:tach",
            str(config.resolved_integration_dir),
        ],
        capture_output=True,
        text=True,
        cwd=config.root,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        msg = (result.stdout + result.stderr).strip()
        raise RuntimeError(f"pytest collection failed (exit {result.returncode}):\n{msg}")
    return [line.strip() for line in result.stdout.splitlines() if "::" in line]


def _extract_markers(test_file: Path) -> dict[str, list[str]]:
    """Extract pytest markers from a test file, keyed by class or module.

    Buffers decorators until the next ``class`` declaration so markers
    above a class are correctly assigned to that class, not the previous one.
    """
    markers: dict[str, list[str]] = defaultdict(list)
    current_class = "_module"
    pending: list[str] = []
    if not test_file.is_file():
        return markers
    for line in test_file.read_text().splitlines():
        marker_match = re.match(r"^@pytest\.mark\.(\w+)", line.strip())
        if marker_match:
            pending.append(marker_match.group(1))
            continue
        class_match = re.match(r"^class (\w+)", line)
        if class_match:
            current_class = class_match.group(1)
            markers[current_class].extend(pending)
            pending.clear()
        elif pending and not line.strip().startswith("@"):
            markers[current_class].extend(pending)
            pending.clear()
    if pending:
        markers[current_class].extend(pending)
    return markers


def _ci_tier(env_markers: set[str]) -> str:
    """Derive the CI tier from a set of environment markers.

    Returns the most restrictive tier (podman > network > host).
    """
    if "needs_podman" in env_markers:
        return "podman"
    if "needs_internet" in env_markers:
        return "network"
    return "host"


def _group_by_directory(
    test_ids: list[str], integration_dir: Path | None = None
) -> dict[str, list[str]]:
    """Group test IDs by their integration test subdirectory."""
    # Build candidate prefixes: the integration dir path (absolute or relative) + fallback
    prefixes: list[str] = []
    if integration_dir is not None:
        prefixes.append(f"{integration_dir}/".replace("\\", "/"))
        # Also try the relative form (pytest emits relative paths)
        try:
            rel = integration_dir.relative_to(Path.cwd())
            prefixes.append(f"{rel}/".replace("\\", "/"))
        except ValueError:
            pass
    prefixes.append("tests/integration/")

    groups: dict[str, list[str]] = defaultdict(list)
    for tid in test_ids:
        file_path = tid.split("::")[0]
        rel = file_path
        for pfx in prefixes:
            if pfx in file_path:
                rel = file_path.replace(pfx, "", 1)
                break
        subdir = rel.split("/")[0] if "/" in rel else "(root)"
        groups[subdir].append(tid)
    return groups


def _sorted_dirs(groups: dict[str, list[str]], dir_order: Sequence[str]) -> list[str]:
    """Return directory names in canonical order, unknown dirs appended alphabetically."""
    known = [d for d in dir_order if d in groups]
    return known + sorted(d for d in groups if d not in dir_order)


def _dir_description(subdir: str, integration_dir: Path) -> str:
    """Read the README.md description for a test subdirectory."""
    readme = integration_dir / subdir / "README.md"
    if not readme.is_file():
        return ""
    lines = readme.read_text().strip().splitlines()
    return " ".join(ln.strip() for ln in lines[1:] if ln.strip())


def _test_row(
    tid: str,
    marker_cache: dict[str, dict[str, list[str]]],
    root: Path,
    *,
    show_markers: bool,
) -> str:
    """Format a single test ID as a Markdown table row."""
    parts = tid.split("::")
    file_path = parts[0]
    class_name = parts[1] if len(parts) > 2 else ""
    test_name = parts[-1]

    if not show_markers:
        return f"| `{test_name}` | `{class_name}` | `{file_path}` |"

    if file_path not in marker_cache:
        marker_cache[file_path] = _extract_markers(root / file_path)
    file_markers = marker_cache[file_path]

    all_markers = set(file_markers.get("_module", []))
    if class_name:
        all_markers.update(file_markers.get(class_name, []))
    env_markers = sorted(m for m in all_markers if m.startswith("needs_"))
    marker_str = ", ".join(f"`{m}`" for m in env_markers) if env_markers else ""
    tier = _ci_tier(all_markers)
    return f"| `{test_name}` | `{class_name}` | {tier} | {marker_str} |"


def generate_test_map(
    test_ids: list[str] | None = None,
    *,
    config: TestMapConfig | None = None,
) -> str:
    """Generate a Markdown test map grouped by directory.

    Args:
        test_ids: Optional pre-collected test IDs. If ``None``, runs
            ``pytest --collect-only`` to collect them.
        config: Configuration for the test map. Uses defaults if ``None``.

    Returns:
        Markdown string with the test map.
    """
    if config is None:
        config = TestMapConfig()
    if test_ids is None:
        test_ids = collect_tests(config=config)

    groups = _group_by_directory(test_ids, config.resolved_integration_dir)
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# {config.title}\n\n",
        f"*Generated: {now}*\n\n",
        f"**{len(test_ids)} tests** across **{len(groups)} directories**\n\n",
    ]

    for subdir in _sorted_dirs(groups, config.dir_order):
        lines.append(f"## `{subdir}/`\n\n")
        desc = _dir_description(subdir, config.resolved_integration_dir)
        if desc:
            lines.append(f"{desc}\n\n")

        if config.show_markers:
            lines.append("| Test | Class | CI Tier | Markers |\n")
            lines.append("|---|---|---|---|\n")
        else:
            lines.append("| Test | Class | File |\n")
            lines.append("|---|---|---|\n")

        marker_cache: dict[str, dict[str, list[str]]] = {}
        for tid in sorted(groups[subdir]):
            lines.append(
                _test_row(tid, marker_cache, config.root, show_markers=config.show_markers) + "\n"
            )
        lines.append("\n")

    return "".join(lines)
