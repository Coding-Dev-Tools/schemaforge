"""Parser: JSON Schema → SchemaForge IR.

Maps a JSON Schema document with ``$defs`` (or standalone schema)
into tables/columns, where each definition becomes a table and
each property becomes a column with appropriate type mapping.
"""

from __future__ import annotations

import json
from typing import Any

from ..ir import Column, ColumnType, Schema, Table

# Mapping from JSON Schema types (+ format) to ColumnType
_TYPE_MAP: dict[str, dict[str, ColumnType]] = {
    "string": {
        "": ColumnType.STRING,
        "date-time": ColumnType.DATETIME,
        "date": ColumnType.DATE,
        "time": ColumnType.TIME,
        "uuid": ColumnType.UUID,
        "email": ColumnType.STRING,
        "uri": ColumnType.STRING,
        "byte": ColumnType.STRING,
        "binary": ColumnType.BLOB,
        "password": ColumnType.STRING,
        "hostname": ColumnType.STRING,
        "ipv4": ColumnType.STRING,
        "ipv6": ColumnType.STRING,
    },
    "integer": {"": ColumnType.INTEGER},
    "number": {"": ColumnType.DECIMAL},
    "boolean": {"": ColumnType.BOOLEAN},
    "object": {"": ColumnType.JSON},
    "array": {"": ColumnType.JSON},
    "null": {"": ColumnType.STRING},  # null alone = no constraint
}


def _infer_enum(col_type: str, schema: dict[str, Any], col: Column) -> None:
    """Promote STRING column to ENUM if schema has enum values."""
    if col_type != "string":
        return
    enum_vals = schema.get("enum")
    if enum_vals and isinstance(enum_vals, list):
        col.type = ColumnType.ENUM
        col.type_args["values"] = [str(v) for v in enum_vals]


class JSONSchemaParser:
    """Parse a JSON Schema document into a Schema IR."""

    def parse(self, text: str) -> Schema:
        """Parse JSON Schema text into Schema IR.

        Args:
            text: JSON Schema string.

        Returns:
            Schema IR with tables derived from ``$defs``
            or from the single top-level object schema.
        """
        data = json.loads(text)
        schema = Schema()

        defs = data.get("$defs", data.get("definitions", {}))
        if defs:
            for name, definition in defs.items():
                table = self._parse_definition(name, definition)
                if table:
                    schema.tables.append(table)
        else:
            # Single schema — treat as one table
            table_name = data.get("title", "Root")
            table = self._parse_definition(table_name, data)
            if table:
                schema.tables.append(table)

        return schema

    def _parse_definition(self, name: str, definition: dict[str, Any]) -> Table | None:
        """Parse a JSON Schema definition into a Table IR.

        Args:
            name: Definition/table name.
            definition: JSON Schema object defining the shape.

        Returns:
            Table IR, or None if the definition has no properties.
        """
        properties = definition.get("properties", {})
        required_set = set(definition.get("required", []))

        if not properties and "type" not in definition:
            return None

        columns: list[Column] = []
        for prop_name, prop_schema in properties.items():
            if not isinstance(prop_schema, dict):
                continue
            col = self._parse_property(prop_name, prop_schema)
            if prop_name in required_set:
                col.nullable = False
            else:
                col.nullable = True
            columns.append(col)

        # Collect `description` as table comment
        comment = definition.get("description", "")

        # Collect enum types if any inline definitions have them
        # (per-definition enums are already captured in _parse_property)

        if not columns:
            return None

        return Table(
            name=_to_table_name(name),
            columns=columns,
            comment=comment,
        )

    def _parse_property(self, name: str, schema: dict[str, Any]) -> Column:
        """Parse a JSON Schema property into a Column IR.

        Args:
            name: Property/column name.
            schema: JSON Schema object for this property.

        Returns:
            Column IR with resolved type, defaults, and constraints.
        """
        col_type = schema.get("type", "string")
        fmt = schema.get("format", "")

        # Resolve ColumnType from type + format
        fmt_map = _TYPE_MAP.get(col_type, {})
        resolved = fmt_map.get(fmt, fmt_map.get("", ColumnType.STRING))

        type_args: dict[str, Any] = {}
        custom_type = ""

        # Handle $ref — treat as CUSTOM type
        ref = schema.get("$ref", "")
        if ref:
            resolved = ColumnType.CUSTOM
            custom_type = ref.split("/")[-1]  # e.g. "#/$defs/foo" → "foo"

        # Handle oneOf/anyOf with null — nullable
        nullable = schema.get("nullable", False)
        one_of = schema.get("oneOf", [])
        any_of = schema.get("anyOf", [])
        if one_of:
            types = [o.get("type", "") for o in one_of if isinstance(o, dict)]
            if "null" in types:
                nullable = True
                non_null = [t for t in types if t != "null"]
                if non_null:
                    fmt_map2 = _TYPE_MAP.get(non_null[0], {})
                    resolved = fmt_map2.get("", ColumnType.STRING)
        elif any_of:
            types = [o.get("type", "") for o in any_of if isinstance(o, dict)]
            if "null" in types:
                nullable = True
                non_null = [t for t in types if t != "null"]
                if non_null:
                    fmt_map2 = _TYPE_MAP.get(non_null[0], {})
                    resolved = fmt_map2.get("", ColumnType.STRING)

        # Handle string maxLength → type_args
        max_length = schema.get("maxLength")
        if col_type == "string" and max_length and isinstance(max_length, int):
            type_args["length"] = max_length

        # Handle default
        default = schema.get("default")

        # Handle enum
        col_obj = Column(
            name=name,
            type=resolved,
            type_args=type_args,
            nullable=nullable,
            default=default,
            comment=schema.get("description", ""),
            custom_type=custom_type,
        )
        _infer_enum(col_type, schema, col_obj)

        return col_obj


def _to_table_name(name: str) -> str:
    """Convert a JSON Schema definition key to a table name.

    Strips common prefixes like "I" (interface) and converts
    PascalCase to snake_case.
    """
    # Strip leading "I" for TypeScript-style interfaces
    if name.startswith("I") and len(name) > 1 and name[1].isupper():
        name = name[1:]
    return name
