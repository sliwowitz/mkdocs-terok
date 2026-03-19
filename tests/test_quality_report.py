# SPDX-FileCopyrightText: 2026 Jiri Vyskocil
# SPDX-License-Identifier: Apache-2.0

"""Tests for the quality report generator."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from mkdocs_terok.quality_report import (
    QualityReportConfig,
    QualityReportResult,
    _coarsen_graph,
    _coarsen_module,
    _nbsp_num,
    _section_boundary_check,
    _section_complexity,
    _section_dead_code,
    _section_dependency_diagram,
    _section_dependency_report,
    _section_docstring_coverage,
    _section_loc,
    generate_quality_report,
)


def test_nbsp_num_formats_thousands() -> None:
    """Non-breaking space thousand separators should be used."""
    assert _nbsp_num(1234567) == "1\u00a0234\u00a0567"
    assert _nbsp_num(42) == "42"


def test_coarsen_module_truncates_to_depth() -> None:
    """Module paths should be truncated to the specified depth."""
    assert _coarsen_module("terok.lib.core.config", 3) == "terok.lib.core"
    assert _coarsen_module("terok.cli", 3) == "terok.cli"


def test_coarsen_graph_collapses_edges() -> None:
    """Coarsened graph should merge sub-module edges and count duplicates."""
    lines = [
        "    terok.lib.core.a --> terok.lib.net.b",
        "    terok.lib.core.c --> terok.lib.net.d",
        "    terok.lib.core.x --> terok.lib.core.y",
    ]
    result = _coarsen_graph(lines, 3)
    assert "graph TD" in result[0]
    # Two edges from core→net should be collapsed with count
    assert any("|2|" in line for line in result)
    # Self-edges (core→core) should be dropped
    assert not any("terok.lib.core --> terok.lib.core" in line for line in result)


def test_generate_quality_report_returns_result(tmp_path: Path) -> None:
    """Report generation should return a QualityReportResult with markdown."""
    config = QualityReportConfig(
        root=tmp_path,
        src_dir=tmp_path / "src",
        tests_dir=tmp_path / "tests",
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()

    result = generate_quality_report(config)

    assert isinstance(result, QualityReportResult)
    assert "# Code Quality Report" in result.markdown
    assert "Generated:" in result.markdown


def test_quality_report_config_defaults() -> None:
    """Config should have sensible defaults."""
    config = QualityReportConfig()
    assert config.complexity_threshold == 15
    assert config.vulture_min_confidence == 80
    assert config.file_level_loc is True
    assert config.include_layer_overview is False
    assert config.include_graph_coarsening is False
    assert len(config.resolved_histogram_buckets) == 9


def test_quality_report_config_custom_buckets() -> None:
    """Custom histogram buckets should override defaults."""
    custom = [(0, 5), (6, 10), (11, 999)]
    config = QualityReportConfig(histogram_buckets=custom)
    assert config.resolved_histogram_buckets == custom


def test_quality_report_config_relative_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Relative root should be resolved to absolute, not cause path doubling."""
    project = tmp_path / "myproject"
    project.mkdir()
    monkeypatch.chdir(project)

    config = QualityReportConfig(root=Path("."), src_dir=Path("pkg"))
    assert config.root.is_absolute()
    assert config.resolved_src_dir == project / "pkg"
    assert config.resolved_tests_dir == project / "tests"


@pytest.mark.parametrize(
    ("treemap_exists", "codecov_repo", "expected_fragment"),
    [
        pytest.param(False, "", "not available", id="no-treemap-no-codecov"),
        pytest.param(False, "org/repo", "codecov.io", id="codecov-url-fallback"),
        pytest.param(True, "", 'data="coverage_treemap.svg"', id="bundled-svg"),
    ],
)
def test_coverage_treemap_variants(
    tmp_path: Path,
    treemap_exists: bool,
    codecov_repo: str,
    expected_fragment: str,
) -> None:
    """Coverage treemap section should handle different config combinations."""
    treemap_path = tmp_path / "treemap.svg" if treemap_exists else None
    if treemap_exists and treemap_path:
        treemap_path.write_text("<svg/>")

    config = QualityReportConfig(
        root=tmp_path,
        src_dir=tmp_path / "src",
        tests_dir=tmp_path / "tests",
        codecov_treemap_path=treemap_path,
        codecov_repo=codecov_repo,
    )
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "tests").mkdir(exist_ok=True)

    result = generate_quality_report(config)
    assert expected_fragment in result.markdown
    if treemap_exists:
        assert result.companion_files["coverage_treemap.svg"] == "<svg/>"


# ---------------------------------------------------------------------------
# Graceful degradation — missing external tools
# ---------------------------------------------------------------------------

_FAIL = subprocess.CompletedProcess(
    args=("stub",), returncode=1, stdout="", stderr="command not found"
)


def _empty_project(tmp_path: Path) -> QualityReportConfig:
    """Create a minimal project tree with no external tools available."""
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    return QualityReportConfig(
        root=tmp_path,
        src_dir=tmp_path / "src",
        tests_dir=tmp_path / "tests",
    )


def test_loc_degrades_when_scc_missing(tmp_path: Path) -> None:
    """LoC section emits a warning when scc is not on PATH."""
    cfg = _empty_project(tmp_path)
    with patch("shutil.which", return_value=None):
        result = _section_loc(cfg)
    assert "!!! warning" in result
    assert "scc" in result


def test_complexity_degrades_when_complexipy_missing(tmp_path: Path) -> None:
    """Complexity section emits a warning when complexipy is absent."""
    cfg = _empty_project(tmp_path)
    with patch("mkdocs_terok.quality_report._run", return_value=_FAIL):
        result = _section_complexity(cfg)
    assert "!!! warning" in result
    assert "complexipy" in result.lower()


def test_dependency_diagram_degrades_when_tach_missing(tmp_path: Path) -> None:
    """Dependency diagram emits a warning when tach is not installed."""
    cfg = _empty_project(tmp_path)
    with patch("mkdocs_terok.quality_report._run", return_value=_FAIL):
        result = _section_dependency_diagram(cfg)
    assert "!!! warning" in result
    assert "tach" in result.lower()


def test_dependency_report_degrades_without_tach_toml(tmp_path: Path) -> None:
    """Module summary degrades when tach.toml is absent."""
    cfg = _empty_project(tmp_path)
    result = _section_dependency_report(cfg)
    assert "!!! warning" in result
    assert "tach.toml" in result


def test_boundary_check_degrades_when_tach_missing(tmp_path: Path) -> None:
    """Boundary check degrades when tach is not installed."""
    cfg = _empty_project(tmp_path)
    with patch("mkdocs_terok.quality_report._run", return_value=_FAIL):
        result = _section_boundary_check(cfg)
    assert "```" in result
    assert "command not found" in result


def test_dead_code_degrades_when_vulture_missing(tmp_path: Path) -> None:
    """Dead code section emits a warning when vulture fails."""
    cfg = _empty_project(tmp_path)
    with patch("mkdocs_terok.quality_report._run", return_value=_FAIL):
        result = _section_dead_code(cfg)
    assert "!!! warning" in result
    assert "vulture" in result.lower()


def test_docstring_coverage_degrades_when_tool_missing(tmp_path: Path) -> None:
    """Docstring section degrades when docstr-coverage is not installed."""
    cfg = _empty_project(tmp_path)
    with patch("mkdocs_terok.quality_report._run", return_value=_FAIL):
        result = _section_docstring_coverage(cfg)
    assert "```" in result
    assert "command not found" in result


def test_full_report_degrades_gracefully(tmp_path: Path) -> None:
    """Full report completes without error when no tools are available."""
    cfg = _empty_project(tmp_path)
    with (
        patch("shutil.which", return_value=None),
        patch("mkdocs_terok.quality_report._run", return_value=_FAIL),
    ):
        result = generate_quality_report(cfg)
    assert isinstance(result, QualityReportResult)
    assert "# Code Quality Report" in result.markdown
    assert "!!! warning" in result.markdown
