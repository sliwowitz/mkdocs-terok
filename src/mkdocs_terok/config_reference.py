# SPDX-FileCopyrightText: 2026 Jiri Vyskocil
# SPDX-License-Identifier: 0BSD

"""Pydantic model rendering engine for config reference documentation.

Provides functions to render Pydantic v2 ``BaseModel`` classes as Markdown
tables, annotated YAML examples, and JSON Schema dumps. The consumer keeps
its own models and field docs; only the rendering logic lives here.

.. note::
    Pydantic is imported at module level. This module is only useful to
    consumers that have Pydantic installed — import failure is acceptable
    for projects that don't use this feature.
"""

from __future__ import annotations

import io
import json
import types
import typing
from typing import get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import FieldInfo

_UNION_ORIGINS = {types.UnionType, typing.Union}


def _is_union(origin: object) -> bool:
    """Check if an origin represents a Union type (PEP 604 or typing.Union)."""
    return origin in _UNION_ORIGINS


def _type_str(field_info: FieldInfo) -> str:
    """Produce a human-readable type string from a Pydantic FieldInfo."""
    annotation = field_info.annotation
    if annotation is None:
        return "any"

    origin = get_origin(annotation)
    args = get_args(annotation)

    # Handle Union types: both `str | None` (PEP 604) and `Optional[str]` / `Union[...]`
    if _is_union(origin) and args:
        non_none = [a for a in args if a is not type(None)]
        has_none = type(None) in args
        type_parts = " or ".join(_simple_type_name(a) for a in non_none)
        return f"{type_parts} or null" if has_none else type_parts

    if origin is list:
        inner = _simple_type_name(args[0]) if args else "any"
        return f"list of {inner}"

    if origin is dict:
        return "mapping"

    return _simple_type_name(annotation)


def _simple_type_name(t: type) -> str:
    """Return a short name for a type."""
    names = {str: "string", int: "integer", bool: "boolean", float: "number"}
    return names.get(t, getattr(t, "__name__", str(t)))


def _factory_default_repr(field_info: FieldInfo) -> str:
    """Produce a default-value string for fields with ``default_factory``."""
    try:
        val = field_info.default_factory()  # type: ignore[misc]
        if isinstance(val, BaseModel):
            return "*section defaults*"
        if isinstance(val, list):
            return "``[]``"
        if isinstance(val, dict):
            return "``{}``"
    except Exception:
        pass
    return "*computed*"


def _scalar_default_repr(d: object) -> str:
    """Produce a default-value string for a scalar default."""
    if d is None:
        return "—"
    if isinstance(d, bool):
        return f"``{str(d).lower()}``"
    if isinstance(d, (int, float)):
        return f"``{d}``"
    if isinstance(d, str):
        return f'``"{d}"``' if d else "*empty*"
    return f"``{d}``"


def _default_repr(field_info: FieldInfo) -> str:
    """Produce a human-readable default value string."""
    if field_info.is_required():
        return "*required*"
    if field_info.default_factory is not None:
        return _factory_default_repr(field_info)
    return _scalar_default_repr(field_info.default)


def _unwrap_section_model(field_info: FieldInfo) -> type[BaseModel] | None:
    """Return the nested Pydantic model class, unwrapping Optional/Union if needed."""
    ann = field_info.annotation
    if ann is None:
        return None
    if _is_union(get_origin(ann)):
        non_none = [a for a in get_args(ann) if a is not type(None)]
        if len(non_none) == 1:
            ann = non_none[0]
    if isinstance(ann, type) and issubclass(ann, BaseModel):
        return ann
    return None


def _is_section_field(field_info: FieldInfo) -> bool:
    """Check if a field is a nested Pydantic section model."""
    return _unwrap_section_model(field_info) is not None


def _yaml_default(field_info: FieldInfo) -> str:
    """Return the YAML-formatted default value for a field."""
    if field_info.default_factory is not None:
        try:
            val = field_info.default_factory()
            if isinstance(val, list):
                return "[]"
            if isinstance(val, dict):
                return "{}"
        except Exception:
            pass
        return ""
    d = field_info.default
    if d is None:
        return ""
    if isinstance(d, bool):
        return str(d).lower()
    if isinstance(d, str):
        needs_quoting = not d or any(c in d for c in " :#{}[]'\"")
        if needs_quoting:
            if '"' in d:
                escaped = d.replace("'", "''")
                return f"'{escaped}'"
            return f'"{d}"'
        return d
    return str(d)


def _strip_rst(text: str) -> str:
    """Strip RST/Markdown inline markup for YAML comments."""
    return text.replace("``", "").replace("**", "")


def _md_escape(text: str) -> str:
    """Escape characters that would break a Markdown table cell."""
    return text.replace("|", r"\|").replace("\n", " ")


def _write_yaml_leaf(
    buf: io.StringIO, pad: str, name: str, field_info: FieldInfo, desc: str
) -> None:
    """Write a leaf field with its description comment to the YAML example."""
    if desc:
        buf.write(f"{pad}# {_strip_rst(desc)}\n")
    default = _yaml_default(field_info)
    buf.write(f"{pad}{name}: {default}\n" if default else f"{pad}{name}:\n")


def _render_section_table(
    buf: io.StringIO,
    model_class: type[BaseModel],
    prefix: str,
    *,
    field_docs: dict[str, str] | None = None,
    heading_level: int = 3,
) -> None:
    """Render a Markdown table for one section model, recursing into sub-sections."""
    if field_docs is None:
        field_docs = {}
    hashes = "#" * heading_level
    section_name = prefix.rstrip(".")
    buf.write(f"{hashes} `{section_name}:`\n\n")

    leaf_fields: list[tuple[str, str, FieldInfo]] = []
    sub_sections: list[tuple[str, type[BaseModel]]] = []

    for name, field_info in model_class.model_fields.items():
        sub_model = _unwrap_section_model(field_info)
        if sub_model is not None:
            sub_sections.append((name, sub_model))
        else:
            leaf_fields.append((name, prefix + name, field_info))

    if leaf_fields:
        buf.write("| Key | Type | Default | Description |\n")
        buf.write("|-----|------|---------|-------------|\n")
        for name, dotpath, fi in leaf_fields:
            type_s = _type_str(fi)
            default_s = _default_repr(fi)
            desc = _md_escape(field_docs.get(dotpath, fi.description or ""))
            buf.write(f"| `{name}` | {type_s} | {default_s} | {desc} |\n")
        buf.write("\n")

    for name, sub_model in sub_sections:
        _render_section_table(
            buf,
            sub_model,
            f"{prefix}{name}.",
            field_docs=field_docs,
            heading_level=heading_level + 1,
        )


def render_model_tables(
    model_class: type[BaseModel],
    *,
    field_docs: dict[str, str] | None = None,
    heading_level: int = 3,
) -> str:
    """Render Markdown tables for all sections of a Pydantic model.

    Args:
        model_class: The top-level Pydantic model class.
        field_docs: Mapping of ``"section.field"`` dotpaths to descriptions.
        heading_level: Starting heading level for section headers.

    Returns:
        Markdown string with section tables.
    """
    if field_docs is None:
        field_docs = {}
    buf = io.StringIO()

    leaf_fields: list[tuple[str, FieldInfo]] = []
    sections: list[tuple[str, type[BaseModel]]] = []

    for name, field_info in model_class.model_fields.items():
        sub_model = _unwrap_section_model(field_info)
        if sub_model is not None:
            sections.append((name, sub_model))
        else:
            leaf_fields.append((name, field_info))

    if leaf_fields:
        hashes = "#" * heading_level
        buf.write(f"{hashes} Top-level keys\n\n")
        buf.write("| Key | Type | Default | Description |\n")
        buf.write("|-----|------|---------|-------------|\n")
        for name, fi in leaf_fields:
            type_s = _type_str(fi)
            default_s = _default_repr(fi)
            desc = _md_escape(field_docs.get(name, fi.description or ""))
            buf.write(f"| `{name}` | {type_s} | {default_s} | {desc} |\n")
        buf.write("\n")

    for name, sub_model in sections:
        _render_section_table(
            buf, sub_model, f"{name}.", field_docs=field_docs, heading_level=heading_level
        )

    return buf.getvalue()


def _render_yaml_fields(
    buf: io.StringIO,
    model_class: type[BaseModel],
    prefix_path: str = "",
    *,
    field_docs: dict[str, str] | None = None,
    indent: int = 0,
) -> None:
    """Render a full annotated YAML example, using dotpath for doc lookup."""
    if field_docs is None:
        field_docs = {}
    pad = "  " * indent
    for name, field_info in model_class.model_fields.items():
        dotpath = f"{prefix_path}.{name}" if prefix_path else name
        desc = field_docs.get(dotpath, field_info.description or "")

        sub_model = _unwrap_section_model(field_info)
        if sub_model is not None:
            if desc:
                buf.write(f"{pad}# {_strip_rst(desc)}\n")
            buf.write(f"{pad}{name}:\n")
            _render_yaml_fields(
                buf,
                sub_model,
                prefix_path=dotpath,
                field_docs=field_docs,
                indent=indent + 1,
            )
            buf.write("\n")
        else:
            _write_yaml_leaf(buf, pad, name, field_info, desc)


def render_yaml_example(
    model_class: type[BaseModel],
    *,
    field_docs: dict[str, str] | None = None,
) -> str:
    """Render a full annotated YAML example for a Pydantic model.

    Args:
        model_class: The Pydantic model class.
        field_docs: Mapping of ``"section.field"`` dotpaths to descriptions.

    Returns:
        YAML string with annotated fields and descriptions.
    """
    buf = io.StringIO()
    _render_yaml_fields(buf, model_class, field_docs=field_docs)
    return buf.getvalue()


def render_json_schema(
    model_class: type[BaseModel],
    *,
    title: str = "",
) -> str:
    """Render the JSON Schema for a Pydantic model.

    Args:
        model_class: The Pydantic model class.
        title: Optional title to inject into the schema.

    Returns:
        Pretty-printed JSON Schema string.
    """
    schema = model_class.model_json_schema(mode="validation")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    if title:
        schema["title"] = title
    return json.dumps(schema, indent=2) + "\n"
