"""Generator: SchemaForge IR → GraphQL SDL.

Converts tables/columns into GraphQL Schema Definition Language
type definitions with enums, directives, and nullable/required annotations.
"""
from __future__ import annotations

from typing import Any

from ..ir import Schema, Table, Column, ColumnType
from ..type_config import EMPTY_CONFIG, TypeConfig

# ColumnType → GraphQL type mapping
_TYPE_TO_GRAPHQL: dict[ColumnType, str] = {
    ColumnType.STRING: "String",
    ColumnType.INTEGER: "Int",
    ColumnType.FLOAT: "Float",
    ColumnType.BOOLEAN: "Boolean",
    ColumnType.DATETIME: "DateTime",
    ColumnType.DATE: "Date",
    ColumnType.TIME: "Time",
    ColumnType.TEXT: "String",
    ColumnType.BLOB: "Byte",
    ColumnType.JSON: "JSON",
    ColumnType.UUID: "UUID",
    ColumnType.DECIMAL: "Decimal",
    ColumnType.ENUM: "String",  # Will be overridden in field generation
}

# CUSTOM types that should use a specific GraphQL scalar annotation
_CUSTOM_TO_SCALAR: dict[str, str] = {
    "JSON": "JSON",
    "Json": "JSON",
    "UUID": "UUID",
    "UID": "UUID",
    "Email": "String",
    "PhoneNumber": "String",
    "DateTime": "DateTime",
    "Date": "Date",
    "Time": "Time",
    "Decimal": "Decimal",
    "BigInt": "Int",
    "URI": "URI",
    "Upload": "Upload",
    "Void": "Void",
}


class GraphQLGenerator:
    """Convert Schema IR to GraphQL SDL."""

    def __init__(self, type_config: TypeConfig | None = None) -> None:
        """Initialize with optional custom type overrides.

        Args:
            type_config: Optional custom type mapping overrides.
        """
        self._type_config = type_config or EMPTY_CONFIG

    def generate(self, schema: Schema) -> str:
        """Generate a GraphQL SDL document from Schema IR.

        Args:
            schema: Schema IR with tables and enums.

        Returns:
            Formatted GraphQL SDL string.
        """
        parts: list[str] = []

        # Generate custom scalar declarations for types not in default set
        custom_scalars = self._collect_custom_scalars(schema)
        for scalar in sorted(custom_scalars):
            parts.append(f"scalar {scalar}")

        # Generate enums
        for enum_type in schema.enums:
            parts.append(self._enum_to_sdl(enum_type))

        # Generate types from tables
        for table in schema.tables:
            is_input = table.options.get("is_input") == "true"
            parts.append(self._table_to_sdl(table, is_input=is_input))

        return "\n\n".join(parts) + "\n"

    def _collect_custom_scalars(self, schema: Schema) -> set[str]:
        """Collect GraphQL scalar types that need explicit declaration.

        Returns:
            Set of scalar type names used in columns but not built-in.
        """
        built_in = {"String", "Int", "Float", "Boolean", "ID"}
        scalars: set[str] = set()

        for table in schema.tables:
            for col in table.columns:
                if col.custom_type and col.custom_type not in built_in:
                    gql = _CUSTOM_TO_SCALAR.get(col.custom_type)
                    if gql and gql not in built_in:
                        scalars.add(gql)

        return scalars

    def _enum_to_sdl(self, enum_type) -> str:
        """Convert an EnumType IR to a GraphQL enum definition.

        Args:
            enum_type: The enum type to convert.

        Returns:
            GraphQL enum definition string.
        """
        values = "\n  ".join(enum_type.values)
        return f"enum {enum_type.name} {{\n  {values}\n}}"

    def _table_to_sdl(self, table: Table, is_input: bool = False) -> str:
        """Convert a Table IR to a GraphQL type definition.

        Args:
            table: The table to convert.
            is_input: Whether to generate an 'input' vs 'type'.

        Returns:
            GraphQL type definition string.
        """
        keyword = "input" if is_input else "type"
        lines = [f"{keyword} {table.name} {{"]

        for col in table.columns:
            lines.append(f"  {self._field_to_sdl(col)}")

        lines.append("}")
        return "\n".join(lines)

    def _field_to_sdl(self, col: Column) -> str:
        """Convert a Column IR to a GraphQL field definition.

        Generates: fieldName: Type! @directive

        Args:
            col: The column to convert.

        Returns:
            GraphQL field definition string.
        """
        gql_type = self._resolve_graphql_type(col)
        field_def = f"{col.name}: {gql_type}"

        # Collect directives
        directives: list[str] = []

        if col.unique:
            directives.append("@unique")

        if col.primary_key and col.name == "id":
            directives.append("@id")

        # Comments
        if col.comment:
            directives.append(f'# {col.comment.replace(chr(10), " ")}')

        if directives:
            field_def += f" {' '.join(directives)}"

        return field_def

    def _resolve_graphql_type(self, col: Column) -> str:
        """Resolve a column's type to a GraphQL type string with ! annotation.

        Args:
            col: The column to resolve.

        Returns:
            GraphQL type string (e.g. 'String!', '[Item]', 'Int!').
        """
        # Check type_config override first
        if self._type_config:
            overridden = self._type_config.get_override(col, "graphql")
            if overridden:
                nullable_suffix = "!" if not col.nullable else ""
                return f"{overridden}{nullable_suffix}"

        base_type = self._base_graphql_type(col)

        # Nullable annotation: ! means required/non-null
        if not col.nullable:
            return f"{base_type}!"

        return base_type

    def _base_graphql_type(self, col: Column) -> str:
        """Resolve the base GraphQL type name for a column.

        Args:
            col: The column to resolve.

        Returns:
            Base GraphQL type name.
        """
        # STRING type with primary_key and name "id" → ID
        if col.type == ColumnType.STRING and col.primary_key and col.name == "id":
            return "ID"

        # Handle CUSTOM types
        if col.type == ColumnType.CUSTOM and col.custom_type:
            # Check if we have a known scalar mapping
            mapped = _CUSTOM_TO_SCALAR.get(col.custom_type)
            if mapped:
                return mapped
            return col.custom_type

        # Check type_config override
        if self._type_config:
            overridden = self._type_config.get_override(col, "graphql")
            if overridden:
                return overridden

        # Check if there's an enum with this name (handled at schema level)
        # Default type mapping
        return _TYPE_TO_GRAPHQL.get(col.type, "String")
