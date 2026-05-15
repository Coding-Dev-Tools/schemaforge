"""Parser: C# Entity Framework Core entity classes → SchemaForge IR.

Parses POCO entity classes with data annotations from C# source files
into the internal schema representation.
"""
from __future__ import annotations

import re
from typing import Any

from ..ir import Schema, Table, Column, ColumnType, Index


# Regex: extract class declaration and body
_CLASS_RE = re.compile(
    r'(?:\[Table\((?:"([^"]+)"|name:\s*"([^"]+)"(?:,\s*Schema\s*=\s*"([^"]+)")?)\)\])?\s*'
    r'(?:public\s+)?(?:partial\s+)?class\s+(\w+)(?:\s*:\s*\w+)?\s*\{',
    re.MULTILINE,
)

# Regex: extract property annotations (one annotation line per property)
_ANNOTATION_RE = re.compile(r'\[(\w+)(?:\(([^)]*)\))?\]')

# Regex: property declaration
_PROPERTY_RE = re.compile(
    r'(?:public\s+)?'
    r'(?P<type>[\w?<>[\]]+)\s+'  # Type: string, int?, List<int>
    r'(?P<name>\w+)\s*'
    r'\{\s*get;\s*set;\s*\}'
    r'(?:\s*=\s*[^;]+;)?'  # Optional default
)

# Map C# types to ColumnType
_CS_TYPE_MAP: dict[str, ColumnType] = {
    "int": ColumnType.INTEGER,
    "int?": ColumnType.INTEGER,
    "long": ColumnType.INTEGER,
    "long?": ColumnType.INTEGER,
    "short": ColumnType.INTEGER,
    "short?": ColumnType.INTEGER,
    "byte": ColumnType.INTEGER,
    "byte?": ColumnType.INTEGER,
    "Guid": ColumnType.UUID,
    "Guid?": ColumnType.UUID,
    "string": ColumnType.STRING,
    "string?": ColumnType.STRING,
    "decimal": ColumnType.DECIMAL,
    "decimal?": ColumnType.DECIMAL,
    "float": ColumnType.FLOAT,
    "float?": ColumnType.FLOAT,
    "double": ColumnType.FLOAT,
    "double?": ColumnType.FLOAT,
    "bool": ColumnType.BOOLEAN,
    "bool?": ColumnType.BOOLEAN,
    "DateTime": ColumnType.DATETIME,
    "DateTime?": ColumnType.DATETIME,
    "DateOnly": ColumnType.DATE,
    "DateOnly?": ColumnType.DATE,
    "TimeOnly": ColumnType.TIME,
    "TimeOnly?": ColumnType.TIME,
    "byte[]": ColumnType.BLOB,
}


def _clean_type(raw: str) -> str:
    """Normalize C# type string (remove List<>, IEnumerable<>, etc.)."""
    raw = raw.strip()
    # Handle nullable: string? → string
    raw = raw.rstrip("?")
    # Handle generic collections: List<string> → string
    for prefix in ("List<", "ICollection<", "IEnumerable<", "IList<"):
        if raw.startswith(prefix) and raw.endswith(">"):
            raw = raw[len(prefix) : -1]
            break
    return raw.strip()


class EntityFrameworkParser:
    """Parse C# Entity Framework entity classes into Schema IR."""

    def parse(self, text: str) -> Schema:
        """Parse C# source text into a Schema IR."""
        schema = Schema()
        tables: dict[str, Table] = {}

        # Remove single-line comments for cleaner parsing
        text = re.sub(r"//.*$", "", text, flags=re.MULTILINE)

        # Find all class definitions
        for m in _CLASS_RE.finditer(text):
            table_name = m.group(1) or m.group(2) or ""
            class_name = m.group(4)
            if not class_name:
                continue

            if not table_name:
                table_name = class_name  # Default to class name

            table = Table(name=table_name)
            class_start = m.end()

            # Find class body end (brace matching)
            depth = 1
            body_end = class_start
            for i in range(class_start, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        body_end = i
                        break

            class_body = text[class_start:body_end]

            # Track annotations for each property
            lines = class_body.split("\n")
            current_annotations: list[tuple[str, str]] = []

            for line in lines:
                stripped = line.strip()

                # Collect annotation lines
                if stripped.startswith("["):
                    for ann in _ANNOTATION_RE.finditer(stripped):
                        current_annotations.append(
                            (ann.group(1), ann.group(2) or "")
                        )
                    continue

                # Skip non-property lines
                prop_m = _PROPERTY_RE.match(stripped)
                if not prop_m:
                    continue

                # Parse property
                cs_type = prop_m.group("type")
                prop_name = prop_m.group("name")

                col = self._property_to_column(
                    prop_name, cs_type, current_annotations
                )
                if col:
                    table.columns.append(col)

                current_annotations = []

            if table.columns:
                schema.tables.append(table)

        return schema

    def _property_to_column(
        self,
        name: str,
        cs_type: str,
        annotations: list[tuple[str, str]],
    ) -> Column | None:
        """Convert a C# property to a Column IR."""
        # Check nullability from type suffix BEFORE cleaning
        cs_type_stripped = cs_type.strip()
        is_nullable_type = cs_type_stripped.endswith("?")
        clean = _clean_type(cs_type)

        col_type = _CS_TYPE_MAP.get(clean, ColumnType.CUSTOM)
        type_args: dict[str, Any] = {}
        nullable = is_nullable_type
        is_pk = False
        is_unique = False
        max_length: int | None = None
        has_required = False
        default_val: Any = None
        custom_type = ""

        for ann_name, ann_args in annotations:
            if ann_name == "Key":
                is_pk = True
            elif ann_name == "Required":
                has_required = True
            elif ann_name == "MaxLength":
                try:
                    max_length = int(ann_args)
                except (ValueError, TypeError):
                    pass
            elif ann_name == "StringLength":
                try:
                    max_length = int(ann_args.split(",")[0].strip())
                except (ValueError, TypeError):
                    pass
            elif ann_name == "Column":
                # Parse Column arguments like Column("name") or Column(TypeName="jsonb")
                if ann_args and not "=" in ann_args:
                    pass  # Column name override — skip for now
            elif ann_name == "Index":
                is_unique = "Unique" in ann_args or "IsUnique=true" in ann_args.replace(" ", "")
            elif ann_name == "Table":
                pass  # Already handled at class level

        # Handle C# naming conventions
        col_name = self._to_snake(name)

        if col_type == ColumnType.STRING and max_length:
            type_args["length"] = max_length
        elif col_type == ColumnType.CUSTOM:
            custom_type = cs_type

        return Column(
            name=col_name,
            type=col_type,
            type_args=type_args,
            nullable=nullable and not is_pk and not has_required,
            primary_key=is_pk,
            unique=is_unique,
            default=default_val,
            custom_type=custom_type,
        )

    def _to_snake(self, name: str) -> str:
        """Convert PascalCase or camelCase to snake_case."""
        result = re.sub(r"([A-Z])", r"_\1", name).lower().lstrip("_")
        # Handle consecutive uppercase (e.g. "URLHelper" → "url_helper")
        result = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", result).lower()
        result = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", result).lower()
        return result.strip("_")
