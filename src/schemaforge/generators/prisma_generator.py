"""Generator: SchemaForge IR → Prisma schema."""
from __future__ import annotations

from ..ir import Column, ColumnType, Schema
from ..type_config import TypeConfig
from ._base import has_type_override, resolve_fn_default, resolve_type


class PrismaGenerator:
    """Convert Schema IR to Prisma schema format."""

    def __init__(self, type_config: TypeConfig | None = None) -> None:
        """Initialize with optional custom type overrides."""
        self._type_config = type_config

    _TYPE_MAP = {
        ColumnType.STRING: "String",
        ColumnType.INTEGER: "Int",
        ColumnType.FLOAT: "Float",
        ColumnType.BOOLEAN: "Boolean",
        ColumnType.DATETIME: "DateTime",
        ColumnType.DATE: "DateTime",
        ColumnType.TIME: "DateTime",
        ColumnType.TEXT: "String",
        ColumnType.BLOB: "Bytes",
        ColumnType.JSON: "Json",
        ColumnType.UUID: "String",
        ColumnType.ENUM: "String",
        ColumnType.DECIMAL: "Decimal",
    }

    def generate(self, schema: Schema) -> str:
        """Generate Prisma schema from IR."""
        parts: list[str] = []
        parts.append('generator client {\n  provider = "prisma-client-js"\n}')
        parts.append(
            'datasource db {\n  provider = "postgresql"\n'
            '  url      = env("DATABASE_URL")\n}'
        )

        # Generate enums
        for enum_type in schema.enums:
            values = "\n  ".join(enum_type.values)
            parts.append(f"enum {enum_type.name} {{\n  {values}\n}}")

        # Generate models
        for table in schema.tables:
            parts.append(self._generate_model(table))

        return "\n\n".join(parts)

    def _generate_model(self, table) -> str:
        lines = [f"model {table.name} {{"]
        for col in table.columns:
            lines.append(f"  {self._field_def(col)}")
        for idx in table.indexes:
            col_list = ", ".join(idx.columns)
            if idx.unique:
                lines.append(f"  @@unique([{col_list}])")
            else:
                lines.append(f"  @@index([{col_list}])")
        lines.append("}")
        return "\n".join(lines)

    def _field_def(self, col: Column) -> str:
        """Generate a Prisma field definition."""
        prisma_type = resolve_type(col, self._TYPE_MAP, fmt="prisma", type_config=self._type_config)

        # Handle String with length (Prisma uses @db.VarChar) — skip if overridden
        if col.type == ColumnType.STRING and "length" in col.type_args \
                and not has_type_override(col, "prisma", self._type_config):
            prisma_type = f"String @db.VarChar({col.type_args['length']})"

        annotations: list[str] = []
        if col.primary_key:
            annotations.append("@id")
            if col.type == ColumnType.INTEGER:
                annotations.append("@default(autoincrement())")

        if col.unique and not col.primary_key:
            annotations.append("@unique")

        # fn: defaults
        fn_default = resolve_fn_default(col, fn_wrapper="@default({})")
        if fn_default:
            annotations.append(fn_default)

        # Literal defaults (non-fn)
        if (col.default is not None
                and not (isinstance(col.default, str) and col.default.startswith("fn:"))
                and not col.primary_key):
                if isinstance(col.default, bool):
                    annotations.append(f"@default({str(col.default).lower()})")
                elif isinstance(col.default, str):
                    if col.default.endswith("()"):
                        annotations.append(f"@default({col.default})")
                    else:
                        annotations.append(f'@default("{col.default}")')
                else:
                    annotations.append(f"@default({col.default})")

        nullable_suffix = "?" if col.nullable else ""

        if annotations:
            return f"{col.name} {prisma_type}{nullable_suffix} {' '.join(annotations)}"
        return f"{col.name} {prisma_type}{nullable_suffix}"
