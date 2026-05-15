"""Generator: SchemaForge IR → Prisma schema."""
from __future__ import annotations

from ..ir import Schema, Column, ColumnType


class PrismaGenerator:
    """Convert Schema IR to Prisma schema format."""

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
        parts.append('datasource db {\n  provider = "postgresql"\n  url      = env("DATABASE_URL")\n}')

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
        if col.type == ColumnType.CUSTOM and col.custom_type:
            prisma_type = col.custom_type
        else:
            prisma_type = self._TYPE_MAP.get(col.type, "String")

        # Handle type args for String length
        if col.type == ColumnType.STRING and "length" in col.type_args:
            prisma_type = f"String @db.VarChar({col.type_args['length']})"

        annotations = []
        if col.primary_key:
            annotations.append("@id")
            if col.type == ColumnType.INTEGER:
                annotations.append("@default(autoincrement())")

        if col.unique and not col.primary_key:
            annotations.append("@unique")

        if col.default is not None:
            if isinstance(col.default, bool):
                annotations.append(f"@default({str(col.default).lower()})")
            elif isinstance(col.default, str) and col.default.startswith("fn:"):
                fn_expr = col.default[3:]
                # Map common SQL functions to Prisma equivalents
                fn_upper = fn_expr.upper().rstrip("()")
                if fn_upper in ("CURRENT_TIMESTAMP", "NOW"):
                    annotations.append("@default(now())")
                elif fn_upper == "CURRENT_DATE":
                    annotations.append("@default(now())")
                elif fn_upper == "RANDOM":
                    annotations.append("@default(autoincrement())")
                elif fn_expr.endswith("()"):
                    annotations.append(f"@default({fn_expr})")
                else:
                    annotations.append(f"@default({fn_expr})")
            elif isinstance(col.default, str):
                # Check if it looks like a function call
                if col.default.endswith("()"):
                    annotations.append(f"@default({col.default})")
                else:
                    annotations.append(f"@default(\"{col.default}\")")
            else:
                annotations.append(f"@default({col.default})")

        nullable_suffix = "?" if col.nullable else ""

        if annotations:
            return f"{col.name} {prisma_type}{nullable_suffix} {' '.join(annotations)}"
        return f"{col.name} {prisma_type}{nullable_suffix}"
