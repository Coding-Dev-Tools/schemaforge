"""Generator: SchemaForge IR → TypeORM entity schema."""
from __future__ import annotations

from ..ir import Column, ColumnType, Schema
from ..type_config import TypeConfig
from ._base import resolve_type


class TypeORMGenerator:
    """Convert Schema IR to TypeORM entity TypeScript format."""

    def __init__(self, type_config: TypeConfig | None = None) -> None:
        """Initialize with optional custom type overrides."""
        self._type_config = type_config

    _TYPE_MAP: dict[ColumnType, str] = {
        ColumnType.STRING: "varchar",
        ColumnType.INTEGER: "integer",
        ColumnType.FLOAT: "float",
        ColumnType.BOOLEAN: "boolean",
        ColumnType.DATETIME: "timestamp",
        ColumnType.DATE: "date",
        ColumnType.TIME: "time",
        ColumnType.TEXT: "text",
        ColumnType.BLOB: "blob",
        ColumnType.JSON: "json",
        ColumnType.UUID: "uuid",
        ColumnType.ENUM: "enum",
        ColumnType.DECIMAL: "decimal",
    }

    _TS_TYPE_MAP: dict[ColumnType, str] = {
        ColumnType.STRING: "string",
        ColumnType.INTEGER: "number",
        ColumnType.FLOAT: "number",
        ColumnType.BOOLEAN: "boolean",
        ColumnType.DATETIME: "Date",
        ColumnType.DATE: "Date",
        ColumnType.TIME: "string",
        ColumnType.TEXT: "string",
        ColumnType.BLOB: "Buffer",
        ColumnType.JSON: "any",
        ColumnType.UUID: "string",
        ColumnType.ENUM: "string",
        ColumnType.DECIMAL: "number",
    }

    def generate(self, schema: Schema) -> str:
        """Generate TypeORM entities from schema IR."""
        parts: list[str] = ["import {"]

        imports = []
        if schema.tables:
            imports.append("Entity")
        has_pk = any(
            any(c.primary_key for c in t.columns) for t in schema.tables
        )
        if has_pk:
            imports.append("PrimaryGeneratedColumn")
        # Actually just always import Column since most tables have non-PK columns
        imports.append("Column")
        has_index = any(t.indexes for t in schema.tables)
        if has_index:
            imports.append("Index")
        has_unique = any(
            any(c.unique and not c.primary_key for c in t.columns)
            for t in schema.tables
        )
        if has_unique:
            imports.append("Unique")

        if len(imports) == 1 and imports[0] == "Entity":
            parts[0] = 'import { Entity, PrimaryGeneratedColumn, Column } from "typeorm";'
        else:
            parts[0] = (
                'import { '
                + ", ".join(sorted(set(imports)))
                + ' } from "typeorm";'
            )

        entities: list[str] = []
        for table in schema.tables:
            entities.append(self._generate_entity(table))

        parts.append("\n\n".join(entities))
        return "\n".join(parts)

    def _generate_entity(self, table) -> str:
        """Generate a single TypeORM entity class."""
        lines: list[str] = []

        # @Entity decorator
        lines.append("@Entity()")

        # Uniqueness constraints
        unique_cols = [
            c for c in table.columns if c.unique and not c.primary_key
        ]
        if unique_cols:
            col_names = ", ".join(f'"{c.name}"' for c in unique_cols)
            lines.append(f'@Unique({col_names})')

        # Class declaration
        lines.append(f"export class {table.name} {{")

        # Columns
        for col in table.columns:
            lines.extend(self._column_def(col))

        # Indexes
        for idx in table.indexes:
            col_list = ", ".join(f'"{c}"' for c in idx.columns)
            if idx.name:
                lines.append(f'    @Index("{idx.name}", [{col_list}])')
            else:
                lines.append(f"    @Index([{col_list}])")

        lines.append("}")
        return "\n".join(lines)

    def _column_def(self, col: Column) -> list[str]:
        """Generate decorator + field line for a column."""
        lines: list[str] = []
        options: dict[str, str] = {}

        # Determine TypeORM type
        col_type = resolve_type(col, self._TYPE_MAP, fmt="typeorm", type_config=self._type_config)

        # Primary key handling
        if col.primary_key:
            if col.type == ColumnType.INTEGER:
                lines.append("    @PrimaryGeneratedColumn()")
            else:
                options["type"] = col_type
                options_str = self._format_options(options)
                lines.append(f"    @PrimaryGeneratedColumn({options_str})")
        else:
            options["type"] = col_type

            # Type args
            if col.type == ColumnType.STRING and "length" in col.type_args:
                options["length"] = str(col.type_args["length"])
            elif col.type == ColumnType.DECIMAL:
                if "precision" in col.type_args:
                    options["precision"] = str(col.type_args["precision"])
                if "scale" in col.type_args:
                    options["scale"] = str(col.type_args["scale"])

            if col.nullable:
                options["nullable"] = "true"
            if col.unique and not col.primary_key:
                options["unique"] = "true"

            # Defaults
            if col.default is not None:
                if isinstance(col.default, bool):
                    options["default"] = str(col.default).lower()
                elif isinstance(col.default, str) and col.default.startswith("fn:"):
                    fn_name = col.default[3:]
                    options["default"] = f"() => \"{fn_name}\""
                elif isinstance(col.default, str):
                    options["default"] = f'"{col.default}"'
                elif isinstance(col.default, int | float):
                    options["default"] = str(col.default)

            options_str = self._format_options(options)
            lines.append(f"    @Column({options_str})")

        # Field declaration
        ts_type = self._TS_TYPE_MAP.get(col.type, "any")
        lines.append(f"    {col.name}: {ts_type};")

        return lines

    def _format_options(self, options: dict[str, str]) -> str:
        """Format column options dict as a TypeScript object literal."""
        if not options:
            return ""

        if len(options) == 1 and "type" in options:
            # Simple format: @Column("type")
            return f'"{options["type"]}"'

        # Object format: @Column({ key: value, ... })
        pairs: list[str] = []
        for key, value in options.items():
            pairs.append(f"    {key}: {value}")
        inner = ",\n".join(pairs)
        return "{\n" + inner + "\n}"
