# SPDX-FileCopyrightText: 2026 Jiri Vyskocil
# SPDX-License-Identifier: Apache-2.0

"""Tests for the quality report generator."""

from __future__ import annotations

from pathlib import Path

import pytest

from mkdocs_terok.quality_report import (
    QualityReportConfig,
    QualityReportResult,
    _coarsen_graph,
    _coarsen_module,
    _nbsp_num,
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


@pytest.mark.parametrize(
    ("treemap_exists", "codecov_repo", "codecov_token", "expected_fragment"),
    [
        pytest.param(False, "", "", "not available", id="no-treemap-no-codecov"),
        pytest.param(False, "org/repo", "tok", "codecov.io", id="codecov-url-fallback"),
    ],
)
def test_coverage_treemap_variants(
    tmp_path: Path,
    treemap_exists: bool,
    codecov_repo: str,
    codecov_token: str,
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
        codecov_token=codecov_token,
    )
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "tests").mkdir(exist_ok=True)

    result = generate_quality_report(config)
    assert expected_fragment in result.markdown
