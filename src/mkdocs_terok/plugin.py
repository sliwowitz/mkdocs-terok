# SPDX-FileCopyrightText: 2026 Jiri Vyskocil
# SPDX-License-Identifier: 0BSD

"""MkDocs plugin that wraps mkdocs-terok generators into a single ``terok`` plugin.

Adds ``File.generated()`` entries for CI maps, quality reports, test maps, and
API reference pages — eliminating the need for ``mkdocs-gen-files`` shim scripts.
Asset injection (CSS / JS) is handled automatically via ``on_config``.
"""

from __future__ import annotations

import logging
from pathlib import PurePosixPath

from mkdocs.config import config_options as c
from mkdocs.config.base import Config
from mkdocs.config.defaults import MkDocsConfig
from mkdocs.plugins import BasePlugin
from mkdocs.structure.files import File, Files

from mkdocs_terok import brand_css_path, mermaid_zoom_js_path

log = logging.getLogger(f"mkdocs.plugins.{__name__}")

# ---------------------------------------------------------------------------
# Plugin configuration schema
# ---------------------------------------------------------------------------


class TerokPluginConfig(Config):
    """Typed MkDocs configuration for the ``terok`` plugin."""

    # Asset injection
    inject_css = c.Type(bool, default=True)
    inject_js = c.Type(bool, default=True)

    # CI map
    ci_map = c.Type(bool, default=False)
    ci_map_path = c.Type(str, default="ci-map.md")

    # Quality report
    quality_report = c.Type(bool, default=False)
    quality_report_path = c.Type(str, default="quality-report.md")
    quality_report_complexity_threshold = c.Type(int, default=15)
    quality_report_graph_depth = c.Type(int, default=3)
    quality_report_vulture_min_confidence = c.Type(int, default=80)
    quality_report_file_level_loc = c.Type(bool, default=True)
    quality_report_include_layer_overview = c.Type(bool, default=False)
    quality_report_include_graph_coarsening = c.Type(bool, default=False)
    quality_report_src_label = c.Type(str, default="Source")
    quality_report_tests_label = c.Type(str, default="Tests")

    # Test map
    test_map = c.Type(bool, default=False)
    test_map_path = c.Type(str, default="test-map.md")
    test_map_show_markers = c.Type(bool, default=True)
    test_map_title = c.Type(str, default="Integration Test Map")
    test_map_integration_dir = c.Optional(c.Type(str))

    # Reference pages
    ref_pages = c.Type(bool, default=False)
    ref_pages_path = c.Type(str, default="reference")
    ref_pages_skip_patterns = c.ListOfItems(c.Type(str), default=["__main__", "resources"])


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------


class TerokPlugin(BasePlugin[TerokPluginConfig]):
    """MkDocs plugin that drives mkdocs-terok generators."""

    def on_config(self, config: MkDocsConfig) -> MkDocsConfig:
        """Inject brand CSS and Mermaid zoom JS into the site configuration."""
        css_uri = "_assets/extra.css"
        js_uri = "_assets/mermaid_zoom.js"

        if self.config.inject_css and css_uri not in config.extra_css:
            config.extra_css.append(css_uri)

        if self.config.inject_js and js_uri not in [
            s if isinstance(s, str) else getattr(s, "path", s) for s in config.extra_javascript
        ]:
            config.extra_javascript.append(js_uri)

        return config

    def on_files(self, files: Files, /, *, config: MkDocsConfig) -> Files:
        """Generate virtual files for each enabled generator."""
        if self.config.inject_css:
            files.append(
                File.generated(config, "_assets/extra.css", abs_src_path=str(brand_css_path()))
            )
        if self.config.inject_js:
            files.append(
                File.generated(
                    config, "_assets/mermaid_zoom.js", abs_src_path=str(mermaid_zoom_js_path())
                )
            )

        if self.config.ci_map:
            self._generate_ci_map(files, config)
        if self.config.quality_report:
            self._generate_quality_report(files, config)
        if self.config.test_map:
            self._generate_test_map(files, config)
        if self.config.ref_pages:
            self._generate_ref_pages(files, config)

        return files

    # -- private generators -------------------------------------------------

    def _generate_ci_map(self, files: Files, config: MkDocsConfig) -> None:
        """Emit a virtual CI map page from GitHub Actions workflows."""
        from mkdocs_terok.ci_map import generate_ci_map

        markdown = generate_ci_map()
        files.append(File.generated(config, self.config.ci_map_path, content=markdown))
        log.info("Generated %s", self.config.ci_map_path)

    def _generate_quality_report(self, files: Files, config: MkDocsConfig) -> None:
        """Emit quality report page and companion files (e.g. treemap SVGs)."""
        from mkdocs_terok.quality_report import QualityReportConfig, generate_quality_report

        qr_config = QualityReportConfig(
            complexity_threshold=self.config.quality_report_complexity_threshold,
            graph_depth=self.config.quality_report_graph_depth,
            vulture_min_confidence=self.config.quality_report_vulture_min_confidence,
            file_level_loc=self.config.quality_report_file_level_loc,
            include_layer_overview=self.config.quality_report_include_layer_overview,
            include_graph_coarsening=self.config.quality_report_include_graph_coarsening,
            src_label=self.config.quality_report_src_label,
            tests_label=self.config.quality_report_tests_label,
        )
        result = generate_quality_report(qr_config)
        report_path = self.config.quality_report_path
        files.append(File.generated(config, report_path, content=result.markdown))

        for name, content in result.companion_files.items():
            if config.use_directory_urls:
                companion_uri = str(PurePosixPath(report_path).with_suffix("") / name)
            else:
                companion_uri = str(PurePosixPath(report_path).parent / name)
            files.append(File.generated(config, companion_uri, content=content))

        log.info("Generated %s", report_path)

    def _generate_test_map(self, files: Files, config: MkDocsConfig) -> None:
        """Emit a virtual test map page from pytest collection."""
        from pathlib import Path

        from mkdocs_terok.test_map import TestMapConfig, generate_test_map

        integration_dir = (
            Path(self.config.test_map_integration_dir)
            if self.config.test_map_integration_dir is not None
            else None
        )
        tm_config = TestMapConfig(
            show_markers=self.config.test_map_show_markers,
            title=self.config.test_map_title,
            integration_dir=integration_dir,
        )
        markdown = generate_test_map(config=tm_config)
        files.append(File.generated(config, self.config.test_map_path, content=markdown))
        log.info("Generated %s", self.config.test_map_path)

    def _generate_ref_pages(self, files: Files, config: MkDocsConfig) -> None:
        """Emit API reference stubs and a literate-nav SUMMARY.md."""
        from mkdocs_terok.ref_pages import RefPagesConfig, generate_ref_pages

        rp_config = RefPagesConfig(
            skip_patterns=tuple(self.config.ref_pages_skip_patterns),
            output_prefix=self.config.ref_pages_path,
        )

        def write_file(doc_path: str, content: str) -> None:
            """Callback that appends a generated File to the files collection."""
            files.append(File.generated(config, doc_path, content=content))

        entries = generate_ref_pages(
            rp_config,
            write_file=write_file,
            set_edit_path=lambda _doc, _src: None,
        )

        # Build literate-nav SUMMARY.md for the reference tree
        prefix = rp_config.output_prefix + "/"
        nav_lines = _build_literate_nav(entries, prefix)
        summary_path = f"{rp_config.output_prefix}/SUMMARY.md"
        files.append(File.generated(config, summary_path, content="".join(nav_lines)))
        log.info("Generated %d reference pages", len(entries))


def _build_literate_nav(entries: list[tuple[tuple[str, ...], str]], prefix: str) -> list[str]:
    """Build a literate-nav SUMMARY.md from ref_pages entries.

    Produces indented ``* [part](relative_path)`` lines mirroring
    ``mkdocs_gen_files.Nav.build_literate_nav()`` output.
    """
    lines: list[str] = []
    for parts, doc_path in entries:
        depth = len(parts) - 1
        indent = "    " * depth
        label = parts[-1]
        rel_path = doc_path.removeprefix(prefix)
        lines.append(f"{indent}* [{label}]({rel_path})\n")
    return lines
