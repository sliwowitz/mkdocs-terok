# SPDX-FileCopyrightText: 2026 Jiri Vyskocil
# SPDX-License-Identifier: 0BSD

"""Tests for the MkDocs TerokPlugin."""

from __future__ import annotations

from contextlib import ExitStack
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


def _fake_file(cfg: object, uri: str, **kw: object) -> SimpleNamespace:
    """Stub for ``File.generated`` that captures the src_uri."""
    return SimpleNamespace(src_uri=uri, **kw)


def _run_on_files(
    plugin: TerokPlugin,
    config: SimpleNamespace,
    *extra_patches: tuple[str, object],
) -> list[str]:
    """Run ``on_files`` with patched ``File.generated`` and return generated URIs.

    *extra_patches* are ``(target, return_value_or_side_effect)`` pairs applied
    alongside the ``File`` patch.  If the value is callable it is used as
    ``side_effect``; otherwise as ``return_value``.
    """
    files = MagicMock()
    appended: list[object] = []
    files.append = appended.append

    with ExitStack() as stack:
        mock_file = stack.enter_context(patch("mkdocs_terok.plugin.File"))
        for target, value in extra_patches:
            kw = {"side_effect": value} if callable(value) else {"return_value": value}
            stack.enter_context(patch(target, **kw))

        mock_file.generated = MagicMock(side_effect=_fake_file)
        plugin.on_files(files, config=config)

    return [f.src_uri for f in appended if hasattr(f, "src_uri")]


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

    def test_empty_string_optional_paths_coerced_to_none(self) -> None:
        """Empty strings for optional path settings should not create Path('.')."""
        plugin = _make_plugin(
            quality_report=True,
            quality_report_codecov_treemap_path="",
            test_map=True,
            test_map_integration_dir="",
        )
        # Verify via the generator config construction (mock generators to inspect args)

        qr_result = SimpleNamespace(markdown="# QR\n", companion_files={})
        with ExitStack() as stack:
            stack.enter_context(patch("mkdocs_terok.plugin.File"))
            mock_qr = stack.enter_context(
                patch(
                    "mkdocs_terok.quality_report.generate_quality_report",
                    return_value=qr_result,
                )
            )
            mock_tm = stack.enter_context(
                patch("mkdocs_terok.test_map.generate_test_map", return_value="# TM\n")
            )
            plugin.on_files(MagicMock(), config=_make_config())

        # QualityReportConfig should have codecov_treemap_path=None, not Path(".")
        qr_config = mock_qr.call_args[0][0]
        assert qr_config.codecov_treemap_path is None

        # TestMapConfig should have integration_dir=None, not Path(".")
        tm_config = mock_tm.call_args[1]["config"]
        assert tm_config.integration_dir is None


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
        uris = _run_on_files(_make_plugin(), _make_config())
        # Two asset files only (CSS + JS)
        assert len(uris) == 2

    def test_no_assets_when_disabled(self) -> None:
        """No files when both assets and generators are disabled."""
        uris = _run_on_files(
            _make_plugin(inject_css=False, inject_js=False),
            _make_config(),
        )
        assert len(uris) == 0


class TestOnFilesCiMap:
    """CI map generation via on_files."""

    def test_generates_ci_map(self) -> None:
        """Enabling ci_map should produce a virtual file at the configured path."""
        uris = _run_on_files(
            _make_plugin(ci_map=True),
            _make_config(),
            ("mkdocs_terok.ci_map.generate_ci_map", "# CI Map\n"),
        )
        assert "ci-map.md" in uris


class TestOnFilesQualityReport:
    """Quality report generation via on_files."""

    @staticmethod
    def _mock_result(**overrides: object) -> SimpleNamespace:
        return SimpleNamespace(
            markdown=overrides.get("markdown", "# QR\n"),
            companion_files=overrides.get("companion_files", {}),
        )

    def test_generates_report_with_companion(self) -> None:
        """Quality report should produce the main file and companion files."""
        result = self._mock_result(companion_files={"coverage_treemap.svg": "<svg/>"})
        uris = _run_on_files(
            _make_plugin(quality_report=True),
            _make_config(use_directory_urls=True),
            ("mkdocs_terok.quality_report.generate_quality_report", result),
        )
        assert "quality-report.md" in uris
        assert "quality-report/coverage_treemap.svg" in uris

    def test_companion_path_no_directory_urls(self) -> None:
        """Companion files should land next to the report when use_directory_urls=False."""
        result = self._mock_result(companion_files={"treemap.svg": "<svg/>"})
        uris = _run_on_files(
            _make_plugin(quality_report=True),
            _make_config(use_directory_urls=False),
            ("mkdocs_terok.quality_report.generate_quality_report", result),
        )
        assert "treemap.svg" in uris

    def test_companion_path_index_md_report(self) -> None:
        """Companion files for index.md reports should use parent dir, not index/."""
        result = self._mock_result(companion_files={"treemap.svg": "<svg/>"})
        uris = _run_on_files(
            _make_plugin(quality_report=True, quality_report_path="reports/index.md"),
            _make_config(use_directory_urls=True),
            ("mkdocs_terok.quality_report.generate_quality_report", result),
        )
        assert "reports/treemap.svg" in uris
        assert "reports/index/treemap.svg" not in uris


class TestOnFilesTestMap:
    """Test map generation via on_files."""

    def test_generates_test_map(self) -> None:
        """Enabling test_map should produce a virtual file."""
        uris = _run_on_files(
            _make_plugin(test_map=True, test_map_integration_dir="tests"),
            _make_config(),
            ("mkdocs_terok.test_map.generate_test_map", "# Tests\n"),
        )
        assert "test-map.md" in uris


class TestOnFilesModuleMap:
    """Module map generation via on_files."""

    def test_generates_module_map(self) -> None:
        """Enabling module_map should produce a virtual file."""
        uris = _run_on_files(
            _make_plugin(module_map=True, module_map_title="Mod Map"),
            _make_config(),
            ("mkdocs_terok.module_map.generate_module_map", "# Mod Map\n"),
        )
        assert "module-map.md" in uris


class TestOnFilesRefPages:
    """Reference page generation via on_files."""

    def test_generates_ref_pages_with_summary(self) -> None:
        """Enabling ref_pages should produce doc files and a SUMMARY.md."""
        fake_entries = [
            (("mypkg",), "reference/mypkg/index.md"),
            (("mypkg", "core"), "reference/mypkg/core.md"),
        ]

        def fake_generate(cfg, *, write_file, set_edit_path):
            for parts, p in fake_entries:
                write_file(p, f"::: {'.'.join(parts)}")
            return fake_entries

        uris = _run_on_files(
            _make_plugin(ref_pages=True),
            _make_config(),
            ("mkdocs_terok.ref_pages.generate_ref_pages", fake_generate),
        )
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
