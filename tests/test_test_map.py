# SPDX-FileCopyrightText: 2026 Jiri Vyskocil
# SPDX-License-Identifier: 0BSD

"""Tests for the integration test map generator."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mkdocs_terok.test_map import (
    TestMapConfig,
    _ci_tier,
    _group_by_directory,
    _sorted_dirs,
    _test_row,
    generate_test_map,
)


def test_group_by_directory_groups_root_and_subdirs() -> None:
    """Collected node IDs should be grouped by the first integration path segment."""
    groups = _group_by_directory(
        [
            "tests/integration/tasks/test_lifecycle.py::test_create",
            "tests/integration/tasks/test_lifecycle.py::test_delete",
            "tests/integration/test_root.py::test_root_only",
        ]
    )

    assert groups == {
        "tasks": [
            "tests/integration/tasks/test_lifecycle.py::test_create",
            "tests/integration/tasks/test_lifecycle.py::test_delete",
        ],
        "(root)": ["tests/integration/test_root.py::test_root_only"],
    }


def test_sorted_dirs_orders_known_before_unknown() -> None:
    """Known directories should keep canonical order before unknown directories."""
    groups = {
        "launch": ["x"],
        "alpha": ["y"],
        "cli": ["z"],
        "projects": ["w"],
    }
    dir_order = ["cli", "projects", "tasks"]

    assert _sorted_dirs(groups, dir_order) == [
        "cli",
        "projects",
        "alpha",
        "launch",
    ]


def test_ci_tier_selects_most_restrictive() -> None:
    """CI tier should reflect the most restrictive marker present."""
    assert _ci_tier({"needs_podman", "needs_internet"}) == "podman"
    assert _ci_tier({"needs_internet"}) == "network"
    assert _ci_tier(set()) == "host"


@pytest.mark.parametrize(
    ("test_id", "show_markers", "expected"),
    [
        pytest.param(
            "tests/integration/tasks/test_lifecycle.py::TestLifecycle::test_create",
            False,
            "| `test_create` | `TestLifecycle` | `tests/integration/tasks/test_lifecycle.py` |",
            id="class-test-no-markers",
        ),
        pytest.param(
            "tests/integration/test_root.py::test_root_only",
            False,
            "| `test_root_only` | `` | `tests/integration/test_root.py` |",
            id="module-test-no-markers",
        ),
    ],
)
def test_test_row_without_markers(test_id: str, show_markers: bool, expected: str) -> None:
    """Formatted rows without markers should expose test, class, and file columns."""
    from pathlib import Path

    marker_cache: dict[str, dict[str, list[str]]] = {}
    assert _test_row(test_id, marker_cache, Path("."), show_markers=show_markers) == expected


def test_generate_test_map_renders_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """The generator should produce a valid Markdown report."""
    test_ids = ["tests/integration/cli/test_cli.py::test_help"]
    config = TestMapConfig(dir_order=["cli"], show_markers=False, title="Integration Test Map")

    class FixedDateTime:
        """Minimal datetime stub returning a deterministic UTC timestamp."""

        @staticmethod
        def now(_tz: object) -> datetime:
            """Return a fixed datetime for test stability."""
            return datetime(2026, 3, 15, 12, 0, tzinfo=UTC)

    monkeypatch.setattr("mkdocs_terok.test_map.datetime", FixedDateTime)

    report = generate_test_map(test_ids, config=config)

    assert "*Generated: 2026-03-15 12:00 UTC*" in report
    assert "**1 tests** across **1 directories**" in report
    assert "## `cli/`" in report
    assert "| `test_help` | `` | `tests/integration/cli/test_cli.py` |" in report


def test_generate_test_map_with_markers(monkeypatch: pytest.MonkeyPatch) -> None:
    """When show_markers is True, CI tier and markers columns should appear."""
    test_ids = ["tests/integration/cli/test_cli.py::test_help"]
    config = TestMapConfig(show_markers=True)

    class FixedDateTime:
        """Minimal datetime stub returning a deterministic UTC timestamp."""

        @staticmethod
        def now(_tz: object) -> datetime:
            """Return a fixed datetime for test stability."""
            return datetime(2026, 3, 15, 12, 0, tzinfo=UTC)

    monkeypatch.setattr("mkdocs_terok.test_map.datetime", FixedDateTime)
    monkeypatch.setattr(
        "mkdocs_terok.test_map._extract_markers",
        lambda _path: {"_module": ["needs_internet"]},
    )

    report = generate_test_map(test_ids, config=config)

    assert "| Test | Class | CI Tier | Markers |" in report
    assert "| `test_help` | `` | network | `needs_internet` |" in report
