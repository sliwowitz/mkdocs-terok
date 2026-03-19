# SPDX-FileCopyrightText: 2026 Jiri Vyskocil
# SPDX-License-Identifier: 0BSD

"""Shared MkDocs documentation generators for terok projects.

Provides reusable modules for CI maps, test maps, quality reports,
API reference pages, and Pydantic config reference rendering.
No runtime dependency on mkdocs or mkdocs-gen-files — each module
produces strings/results that consumers wrap in thin shims.
"""

from __future__ import annotations

from pathlib import Path

__version__ = "0.0.0"  # managed by poetry-dynamic-versioning


def brand_css_path() -> Path:
    """Return the filesystem path to the shared brand CSS file."""
    return Path(__file__).parent / "_assets" / "extra.css"


def mermaid_zoom_js_path() -> Path:
    """Return the filesystem path to the Mermaid diagram zoom script."""
    return Path(__file__).parent / "_assets" / "mermaid_zoom.js"
