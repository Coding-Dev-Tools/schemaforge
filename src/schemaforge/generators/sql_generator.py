"""Generator: SchemaForge IR → SQL DDL."""
from __future__ import annotations

from ..ir import Schema, Column, ColumnType


class SQLGenerator:
    """Convert Schema IR to SQL DDL statements."""

    _TYPE_REVERSE_MAP: dict[ColumnType, str] = {
        ColumnType.INTEGER: "INTEGER",
        ColumnType.STRING: "TEXT",
        ColumnType.TEXT: "TEXT",
        ColumnType.BOOLEAN: "BOOLEAN",
        ColumnType.FLOAT: "FLOAT",
        ColumnType.DECIMAL: "DECIMAL(10,2)",
        ColumnType.DATE: "DATE",
        ColumnType.DATETIME: "TIMESTAMP",
        ColumnType.TIME: "TIME",
        ColumnType.BLOB: "BLOB",
        ColumnType.JSON: "JSON",
        ColumnType.UUID: "UUID",
        ColumnType.ENUM: "VARCHAR(50)",
    }

    def generate(self, schema: Schema) -> str:
        """Generate SQL DDL from schema IR."""
        parts: list[str] = []

        # Generate ENUM types
        for enum_type in schema.enums:
            values = ", ".join(f"'{v}'" for v in enum_type.values)
            parts.append(f"CREATE TYPE {enum_type.name} AS ENUM ({values});")

        # Generate CREATE TABLE statements
        for table in schema.tables:
            parts.append(self._generate_create_table(table))

        return "\n\n".join(parts)

    def _generate_create_table(self, table) -> str:
        lines = [f"CREATE TABLE {table.name} ("]
        col_defs = []

        for col in table.columns:
            col_defs.append(f"    {self._column_def(col)}")

        for idx in table.indexes:
            col_list = ", ".join(idx.columns)
            idx_type = "UNIQUE INDEX" if idx.unique else "INDEX"
            idx_name = idx.name or f"idx_{'_'.join(idx.columns)}"
            col_defs.append(f"    {idx_type} {idx_name} ({col_list})")

        lines.append(",\n".join(col_defs))
        lines.append(")")

        # Append MySQL table options
        if table.options:
            opts = []
            for key, val in table.options.items():
                if key == "COMMENT":
                    opts.append(f"{key} '{val}'")
                elif key.startswith("DEFAULT "):
                    opts.append(f"{key}={val}")
                else:
                    opts.append(f"{key}={val}")
            lines[-1] += " " + " ".join(opts)

        lines[-1] += ";"
        return "\n".join(lines)

    def _column_def(self, col: Column) -> str:
        """Generate a single column definition."""
        if col.type == ColumnType.CUSTOM and col.custom_type:
            sql_type = col.custom_type
        elif col.type == ColumnType.ENUM and col.type_args.get("values"):
            # Inline ENUM('a','b','c')
            values = ", ".join(f"'{v}'" for v in col.type_args["values"])
            sql_type = f"ENUM({values})"
        elif col.type in self._TYPE_REVERSE_MAP:
            sql_type = self._TYPE_REVERSE_MAP[col.type]
            # Apply type args
            if col.type == ColumnType.STRING and "length" in col.type_args:
                sql_type = f"VARCHAR({col.type_args['length']})"
            elif col.type == ColumnType.DECIMAL:
                p = col.type_args.get("precision", 10)
                s = col.type_args.get("scale", 2)
                sql_type = f"DECIMAL({p},{s})"
        else:
            sql_type = "TEXT"

        parts = [col.name, sql_type]

        if col.primary_key:
            parts.append("PRIMARY KEY")
        if not col.nullable:
            parts.append("NOT NULL")
        if col.unique and not col.primary_key:
            parts.append("UNIQUE")
        if col.default is not None:
            if isinstance(col.default, bool):
                parts.append(f"DEFAULT {'TRUE' if col.default else 'FALSE'}")
            elif isinstance(col.default, (int, float)):
                parts.append(f"DEFAULT {col.default}")
            elif isinstance(col.default, str) and col.default.startswith("fn:"):
                fn_val = col.default[3:]
                parts.append(f"DEFAULT {fn_val}")
            else:
                parts.append(f"DEFAULT '{col.default}'")

        return " ".join(parts)
