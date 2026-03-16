# SPDX-FileCopyrightText: 2026 Jiri Vyskocil
# SPDX-License-Identifier: Apache-2.0

"""Tests for the Pydantic config reference rendering engine."""

from __future__ import annotations

import json

from pydantic import BaseModel

from mkdocs_terok.config_reference import (
    render_json_schema,
    render_model_tables,
    render_yaml_example,
)


class _InnerModel(BaseModel):
    """A nested section model for testing."""

    timeout: int = 30
    enabled: bool = True


class _SampleModel(BaseModel):
    """A sample top-level config model for testing."""

    name: str
    count: int = 5
    tags: list[str] = []
    inner: _InnerModel = _InnerModel()


def test_render_model_tables_includes_fields() -> None:
    """Model tables should include all leaf fields with types and defaults."""
    result = render_model_tables(_SampleModel)

    assert "| `name` |" in result
    assert "| `count` |" in result
    assert "*required*" in result
    assert "``5``" in result
    assert "`inner:`" in result


def test_render_model_tables_with_field_docs() -> None:
    """Field docs should override empty descriptions."""
    docs = {"name": "The project name", "inner.timeout": "Shutdown timeout in seconds"}
    result = render_model_tables(_SampleModel, field_docs=docs)

    assert "The project name" in result
    assert "Shutdown timeout in seconds" in result


def test_render_yaml_example_produces_annotated_yaml() -> None:
    """YAML example should have uncommented fields with description comments."""
    result = render_yaml_example(_SampleModel)

    assert "name:" in result
    assert "count: 5" in result
    assert "inner:" in result
    assert "timeout: 30" in result
    assert "enabled: true" in result
    # Keys should NOT be commented out
    assert "# name:" not in result
    assert "# count:" not in result


def test_render_yaml_example_with_field_docs() -> None:
    """YAML example should include field doc comments."""
    docs = {"name": "The project name"}
    result = render_yaml_example(_SampleModel, field_docs=docs)

    assert "# The project name" in result


def test_render_json_schema_produces_valid_json() -> None:
    """JSON schema output should be valid JSON with required fields."""
    result = render_json_schema(_SampleModel, title="Test Schema")
    schema = json.loads(result)

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["title"] == "Test Schema"
    assert "properties" in schema


def test_render_model_tables_heading_level() -> None:
    """Custom heading level should be reflected in output."""
    result = render_model_tables(_SampleModel, heading_level=2)
    assert "## Top-level keys" in result
