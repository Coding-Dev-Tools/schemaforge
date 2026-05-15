"""Generator: SchemaForge IR → Django model schema."""
from __future__ import annotations

from ..ir import Schema, Column, ColumnType

from ._base import resolve_type


class DjangoGenerator:
    """Convert Schema IR to Django model Python format."""

    _FIELD_MAP: dict[ColumnType, str] = {
        ColumnType.STRING: "CharField",
        ColumnType.INTEGER: "IntegerField",
        ColumnType.FLOAT: "FloatField",
        ColumnType.BOOLEAN: "BooleanField",
        ColumnType.DATETIME: "DateTimeField",
        ColumnType.DATE: "DateField",
        ColumnType.TIME: "TimeField",
        ColumnType.TEXT: "TextField",
        ColumnType.BLOB: "BinaryField",
        ColumnType.JSON: "JSONField",
        ColumnType.UUID: "UUIDField",
        ColumnType.ENUM: "CharField",
        ColumnType.DECIMAL: "DecimalField",
    }

    def generate(self, schema: Schema) -> str:
        """Generate Django models from schema IR."""
        parts: list[str] = [
            "from django.db import models",
            "from django.utils import timezone",
            "",
        ]

        for table in schema.tables:
            parts.append(self._generate_model(table))

        return "\n\n".join(parts)

    def _generate_model(self, table) -> str:
        """Generate a single Django model class."""
        lines: list[str] = []

        # Default ordering from indexes
        lines.append(f"class {table.name}(models.Model):")

        # Columns
        has_pk = any(c.primary_key for c in table.columns)
        for col in table.columns:
            if has_pk and col.primary_key and col.type == ColumnType.INTEGER:
                # AutoField for integer PKs (Django creates one by default)
                # Only generate explicit AutoField if name isn't 'id'
                if col.name != "id":
                    lines.append(f"    {col.name} = models.AutoField(primary_key=True)")
                continue
            lines.append(f"    {self._field_def(col)}")

        # Indexes
        for idx in table.indexes:
            if len(idx.columns) == 1:
                col = idx.columns[0]
                if idx.unique:
                    # Unique on single column is already handled via field option
                    pass
                else:
                    lines.append(
                        f"    {col} = models.{'IntegerField' if col else 'CharField'}("
                        f"db_index=True)"
                    )

        # Unique constraints (multi-column)
        unique_sets: list[list[str]] = []
        for idx in table.indexes:
            if idx.unique and len(idx.columns) > 1:
                unique_sets.append(idx.columns)

        if unique_sets:
            for us in unique_sets:
                cols_str = ", ".join(f"'{c}'" for c in us)
                lines.append("")
                lines.append("    class Meta:")
                lines.append(f"        unique_together = [{cols_str}]")
                break  # Only one Meta per class

        # String representation (optional, nice to have)
        first_str_col = None
        for col in table.columns:
            if col.type in (ColumnType.STRING, ColumnType.TEXT):
                first_str_col = col.name
                break
        if first_str_col:
            lines.append("")
            lines.append("    def __str__(self):")
            lines.append(f"        return self.{first_str_col}")

        return "\n".join(lines)

    def _field_def(self, col: Column) -> str:
        """Generate a Django model field definition."""
        django_field = resolve_type(col, self._FIELD_MAP)
        if not django_field.endswith("Field"):
            django_field = django_field + "Field"

        kwargs: list[str] = []

        # Type-specific args
        if col.type == ColumnType.STRING:
            length = col.type_args.get("length", 255)
            kwargs.append(f"max_length={length}")
        elif col.type == ColumnType.DECIMAL:
            precision = col.type_args.get("precision", 10)
            scale = col.type_args.get("scale", 2)
            kwargs.append(f"max_digits={precision}")
            kwargs.append(f"decimal_places={scale}")
        elif col.type == ColumnType.UUID:
            kwargs.append("default=uuid.uuid4")
            kwargs.append("editable=False")

        # Primary key
        if col.primary_key:
            kwargs.append("primary_key=True")

        # Nullable
        if col.nullable and not col.primary_key:
            kwargs.append("null=True")
            kwargs.append("blank=True")
        elif col.nullable:
            kwargs.append("null=True")

        # Unique
        if col.unique and not col.primary_key:
            kwargs.append("unique=True")

        # Defaults
        if col.default is not None:
            if isinstance(col.default, bool):
                kwargs.append(f"default={str(col.default).lower()}")
            elif isinstance(col.default, str) and col.default.startswith("fn:"):
                fn_name = col.default[3:]
                if fn_name == "auto_now_add":
                    kwargs.append("auto_now_add=True")
                elif fn_name == "auto_now":
                    kwargs.append("auto_now=True")
                else:
                    kwargs.append(f"default={fn_name}")
            elif isinstance(col.default, str):
                kwargs.append(f"default='{col.default}'")
            elif isinstance(col.default, (int, float)):
                kwargs.append(f"default={col.default}")

        if not kwargs:
            # For fields that need at least one arg (CharField)
            if django_field == "CharField":
                kwargs.append("max_length=255")

        if kwargs:
            return f"    {col.name} = models.{django_field}({', '.join(kwargs)})"
        return f"    {col.name} = models.{django_field}()"
