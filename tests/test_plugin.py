# SPDX-FileCopyrightText: 2026 Jiri Vyskocil
# SPDX-License-Identifier: 0BSD

"""Tests for the MkDocs TerokPlugin."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from mkdocs_terok.plugin import TerokPlugin, _build_literate_nav

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(**overrides: object) -> SimpleNamespace:
    """Build a minimal MkDocs config stub (stricter than MagicMock)."""
    return SimpleNamespace(
        extra_css=list(overrides.get("extra_css", [])),
        extra_javascript=list(overrides.get("extra_javascript", [])),
        use_directory_urls=overrides.get("use_directory_urls", True),
    )


def _make_plugin(**overrides: object) -> TerokPlugin:
    """Instantiate a TerokPlugin with config defaults, applying overrides."""
    plugin = TerokPlugin()
    plugin.load_config(overrides)
    return plugin


# ---------------------------------------------------------------------------
# Config defaults
# ---------------------------------------------------------------------------


class TestConfigDefaults:
    """Verify that all generators default to disabled."""

    def test_generators_default_false(self) -> None:
        """All generator toggles should default to False."""
        plugin = _make_plugin()
        for key in ("ci_map", "quality_report", "test_map", "ref_pages"):
            assert getattr(plugin.config, key) is False, f"{key} should default to False"

    def test_asset_injection_default_true(self) -> None:
        """CSS and JS injection should default to True."""
        plugin = _make_plugin()
        assert plugin.config.inject_css is True
        assert plugin.config.inject_js is True


# ---------------------------------------------------------------------------
# on_config — asset injection
# ---------------------------------------------------------------------------


class TestOnConfig:
    """Verify CSS/JS injection into MkDocs config."""

    def test_injects_css_and_js(self) -> None:
        """Plugin should append asset URIs to extra_css / extra_javascript."""
        plugin = _make_plugin()
        config = _make_config()
        plugin.on_config(config)

        assert "_assets/extra.css" in config.extra_css
        assert "_assets/mermaid_zoom.js" in config.extra_javascript

    def test_no_duplicate_injection(self) -> None:
        """Calling on_config twice should not duplicate asset entries."""
        plugin = _make_plugin()
        config = _make_config()
        plugin.on_config(config)
        plugin.on_config(config)

        assert config.extra_css.count("_assets/extra.css") == 1
        assert config.extra_javascript.count("_assets/mermaid_zoom.js") == 1

    def test_skips_when_disabled(self) -> None:
        """Disabling inject_css/inject_js should suppress asset injection."""
        plugin = _make_plugin(inject_css=False, inject_js=False)
        config = _make_config()
        plugin.on_config(config)

        assert "_assets/extra.css" not in config.extra_css
        assert "_assets/mermaid_zoom.js" not in config.extra_javascript


# ---------------------------------------------------------------------------
# on_files — content generation
# ---------------------------------------------------------------------------


class TestOnFilesNoContent:
    """When all generators are disabled, on_files should add only asset files."""

    def test_no_content_files_when_all_disabled(self) -> None:
        """Only asset File objects should appear when generators are off."""
        plugin = _make_plugin()
        config = _make_config()
        files = MagicMock()
        appended: list[object] = []
        files.append = appended.append

        with patch("mkdocs_terok.plugin.File") as mock_file:
            mock_file.generated = MagicMock(side_effect=lambda *a, **kw: SimpleNamespace(**kw))
            plugin.on_files(files, config=config)

        # Two asset files only (CSS + JS)
        assert len(appended) == 2

    def test_no_assets_when_disabled(self) -> None:
        """No files when both assets and generators are disabled."""
        plugin = _make_plugin(inject_css=False, inject_js=False)
        config = _make_config()
        files = MagicMock()
        appended: list[object] = []
        files.append = appended.append

        with patch("mkdocs_terok.plugin.File") as mock_file:
            mock_file.generated = MagicMock(side_effect=lambda *a, **kw: SimpleNamespace(**kw))
            plugin.on_files(files, config=config)

        assert len(appended) == 0


class TestOnFilesCiMap:
    """CI map generation via on_files."""

    def test_generates_ci_map(self) -> None:
        """Enabling ci_map should produce a virtual file at the configured path."""
        plugin = _make_plugin(ci_map=True)
        config = _make_config()
        files = MagicMock()
        appended: list[object] = []
        files.append = appended.append

        with (
            patch("mkdocs_terok.plugin.File") as mock_file,
            patch("mkdocs_terok.ci_map.generate_ci_map", return_value="# CI Map\n"),
        ):
            mock_file.generated = MagicMock(
                side_effect=lambda cfg, uri, **kw: SimpleNamespace(src_uri=uri, **kw)
            )
            plugin.on_files(files, config=config)

        uris = [f.src_uri for f in appended if hasattr(f, "src_uri")]
        assert "ci-map.md" in uris


class TestOnFilesQualityReport:
    """Quality report generation via on_files."""

    def test_generates_report_with_companion(self) -> None:
        """Quality report should produce the main file and companion files."""
        plugin = _make_plugin(quality_report=True)
        config = _make_config(use_directory_urls=True)
        files = MagicMock()
        appended: list[object] = []
        files.append = appended.append

        mock_result = SimpleNamespace(
            markdown="# Quality Report\n",
            companion_files={"coverage_treemap.svg": "<svg/>"},
        )

        with (
            patch("mkdocs_terok.plugin.File") as mock_file,
            patch(
                "mkdocs_terok.quality_report.generate_quality_report",
                return_value=mock_result,
            ),
        ):
            mock_file.generated = MagicMock(
                side_effect=lambda cfg, uri, **kw: SimpleNamespace(src_uri=uri, **kw)
            )
            plugin.on_files(files, config=config)

        uris = [f.src_uri for f in appended if hasattr(f, "src_uri")]
        assert "quality-report.md" in uris
        # use_directory_urls=True → companion at quality-report/coverage_treemap.svg
        assert "quality-report/coverage_treemap.svg" in uris

    def test_companion_path_no_directory_urls(self) -> None:
        """Companion files should land next to the report when use_directory_urls=False."""
        plugin = _make_plugin(quality_report=True)
        config = _make_config(use_directory_urls=False)
        files = MagicMock()
        appended: list[object] = []
        files.append = appended.append

        mock_result = SimpleNamespace(
            markdown="# QR\n",
            companion_files={"treemap.svg": "<svg/>"},
        )

        with (
            patch("mkdocs_terok.plugin.File") as mock_file,
            patch(
                "mkdocs_terok.quality_report.generate_quality_report",
                return_value=mock_result,
            ),
        ):
            mock_file.generated = MagicMock(
                side_effect=lambda cfg, uri, **kw: SimpleNamespace(src_uri=uri, **kw)
            )
            plugin.on_files(files, config=config)

        uris = [f.src_uri for f in appended if hasattr(f, "src_uri")]
        # use_directory_urls=False → companion at treemap.svg (same directory as report root)
        assert "treemap.svg" in uris


class TestOnFilesTestMap:
    """Test map generation via on_files."""

    def test_generates_test_map(self) -> None:
        """Enabling test_map should produce a virtual file."""
        plugin = _make_plugin(test_map=True, test_map_integration_dir="tests")
        config = _make_config()
        files = MagicMock()
        appended: list[object] = []
        files.append = appended.append

        with (
            patch("mkdocs_terok.plugin.File") as mock_file,
            patch("mkdocs_terok.test_map.generate_test_map", return_value="# Tests\n"),
        ):
            mock_file.generated = MagicMock(
                side_effect=lambda cfg, uri, **kw: SimpleNamespace(src_uri=uri, **kw)
            )
            plugin.on_files(files, config=config)

        uris = [f.src_uri for f in appended if hasattr(f, "src_uri")]
        assert "test-map.md" in uris


class TestOnFilesRefPages:
    """Reference page generation via on_files."""

    def test_generates_ref_pages_with_summary(self) -> None:
        """Enabling ref_pages should produce doc files and a SUMMARY.md."""
        plugin = _make_plugin(ref_pages=True)
        config = _make_config()
        files = MagicMock()
        appended: list[object] = []
        files.append = appended.append

        fake_entries = [
            (("mypkg",), "reference/mypkg/index.md"),
            (("mypkg", "core"), "reference/mypkg/core.md"),
        ]

        with (
            patch("mkdocs_terok.plugin.File") as mock_file,
            patch(
                "mkdocs_terok.ref_pages.generate_ref_pages",
                side_effect=lambda cfg, *, write_file, set_edit_path: (
                    [write_file(p, f"::: {'.'.join(parts)}") for parts, p in fake_entries],
                    fake_entries,
                )[-1],
            ),
        ):
            mock_file.generated = MagicMock(
                side_effect=lambda cfg, uri, **kw: SimpleNamespace(src_uri=uri, **kw)
            )
            plugin.on_files(files, config=config)

        uris = [f.src_uri for f in appended if hasattr(f, "src_uri")]
        assert "reference/mypkg/index.md" in uris
        assert "reference/mypkg/core.md" in uris
        assert "reference/SUMMARY.md" in uris


# ---------------------------------------------------------------------------
# _build_literate_nav
# ---------------------------------------------------------------------------


class TestBuildLiterateNav:
    """Unit tests for the literate-nav builder."""

    def test_single_level(self) -> None:
        """Top-level entries should have no indentation."""
        entries = [(("mypkg",), "reference/mypkg/index.md")]
        lines = _build_literate_nav(entries, "reference/")
        assert lines == ["* [mypkg](mypkg/index.md)\n"]

    def test_nested_entries(self) -> None:
        """Nested modules should be indented proportionally."""
        entries = [
            (("mypkg",), "reference/mypkg/index.md"),
            (("mypkg", "sub"), "reference/mypkg/sub.md"),
            (("mypkg", "sub", "deep"), "reference/mypkg/sub/deep.md"),
        ]
        lines = _build_literate_nav(entries, "reference/")
        assert lines[0] == "* [mypkg](mypkg/index.md)\n"
        assert lines[1] == "    * [sub](mypkg/sub.md)\n"
        assert lines[2] == "        * [deep](mypkg/sub/deep.md)\n"

    def test_empty_entries(self) -> None:
        """No entries should produce no nav lines."""
        assert _build_literate_nav([], "reference/") == []
