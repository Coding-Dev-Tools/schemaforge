"""Generator: SchemaForge IR → C# Entity Framework Core entity classes."""

from __future__ import annotations

from ..ir import Column, ColumnType, Schema
from ._base import resolve_type


class EntityFrameworkGenerator:
    """Convert Schema IR to C# Entity Framework Core entity classes."""

    _TYPE_MAP: dict[ColumnType, str] = {
        ColumnType.STRING: "string",
        ColumnType.INTEGER: "int",
        ColumnType.FLOAT: "double",
        ColumnType.BOOLEAN: "bool",
        ColumnType.DATETIME: "DateTime",
        ColumnType.DATE: "DateOnly",
        ColumnType.TIME: "TimeOnly",
        ColumnType.TEXT: "string",
        ColumnType.BLOB: "byte[]",
        ColumnType.JSON: "string",
        ColumnType.UUID: "Guid",
        ColumnType.ENUM: "string",
        ColumnType.DECIMAL: "decimal",
    }

    def __init__(self, type_config=None):
        """Initialize generator with optional type config."""
        self.type_config = type_config

    def generate(self, schema: Schema) -> str:
        """Generate C# entity classes from schema IR."""
        parts: list[str] = [
            "using System;",
            "using System.ComponentModel.DataAnnotations;",
            "using System.ComponentModel.DataAnnotations.Schema;",
            "",
            "namespace SchemaForge.Models;",
            "",
        ]

        for table in schema.tables:
            parts.append(self._generate_class(table))

        return "\n".join(parts)

    def _generate_class(self, table) -> str:
        """Generate a single entity class."""
        lines: list[str] = []

        # [Table] annotation if name differs from class name
        class_name = self._to_pascal(table.name)
        if table.name.lower() != class_name.lower():
            lines.append(f'[Table("{table.name}")]')

        lines.append(f"public class {class_name}")
        lines.append("{")

        for col in table.columns:
            lines.append(f"    {self._property_def(col)}")

        lines.append("}")
        return "\n".join(lines)

    def _property_def(self, col: Column) -> str:
        """Generate a C# property with data annotations."""
        annotations: list[str] = []
        cs_type = resolve_type(col, self._TYPE_MAP)
        prop_name = self._to_pascal(col.name)

        # Data annotations
        if col.primary_key:
            annotations.append("[Key]")

        if not col.nullable and not col.primary_key:
            annotations.append("[Required]")

        if col.type == ColumnType.STRING and "length" in col.type_args:
            annotations.append(f"[MaxLength({col.type_args['length']})]")

        if col.type == ColumnType.DECIMAL:
            p = col.type_args.get("precision", 10)
            s = col.type_args.get("scale", 2)
            annotations.append(f'[Column(TypeName = "decimal({p},{s})")]')

        if col.unique and not col.primary_key:
            # EF Index attribute
            pass  # Handled at the DbContext level, not on properties

        # Handle nullable reference types
        is_nullable = col.nullable and cs_type != "byte[]"
        cs_type_str = f"{cs_type}?" if is_nullable else cs_type

        # Default value
        default_str = ""
        if col.default is not None:
            if isinstance(col.default, bool):
                default_str = f" = {str(col.default).lower()};"
            elif isinstance(col.default, str) and col.default.startswith("fn:"):
                pass  # Skip function defaults in C#
            elif isinstance(col.default, str):
                default_str = f' = "{col.default}";'
            elif isinstance(col.default, int | float):
                default_str = f" = {col.default};"

        ann_str = " ".join(annotations)
        if ann_str:
            ann_str += "\n    "

        # Use List<T> for JSON columns (simple approximation)
        if col.type == ColumnType.JSON:
            cs_type_str = "string"

        return f"{ann_str}public {cs_type_str} {prop_name} {{ get; set; }}{default_str}"

    def _to_pascal(self, name: str) -> str:
        """Convert snake_case to PascalCase."""
        parts = name.split("_")
        return "".join(p.capitalize() for p in parts if p)
