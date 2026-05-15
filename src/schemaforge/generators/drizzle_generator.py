"""Generator for Drizzle ORM TypeScript schema from SchemaForge IR."""
from __future__ import annotations

from ..ir import Schema, Table, Column, ColumnType, EnumType, Index

from ._base import resolve_fn_default
from ..type_config import TypeConfig


# ColumnType -> Drizzle type function mapping
_TYPE_TO_DRIZZLE: dict[ColumnType, str] = {
    ColumnType.STRING: "varchar",
    ColumnType.INTEGER: "integer",
    ColumnType.FLOAT: "real",
    ColumnType.BOOLEAN: "boolean",
    ColumnType.DATETIME: "timestamp",
    ColumnType.DATE: "date",
    ColumnType.TIME: "time",
    ColumnType.TEXT: "text",
    ColumnType.BLOB: "blob",
    ColumnType.JSON: "json",
    ColumnType.UUID: "uuid",
    ColumnType.ENUM: "varchar",  # Handled via pgEnum separately
    ColumnType.DECIMAL: "numeric",
    ColumnType.CUSTOM: "text",  # Fallback
}


class DrizzleGenerator:
    """Generate Drizzle ORM TypeScript schema from Schema IR."""

    def __init__(self, dialect: str = "pg", type_config: TypeConfig | None = None) -> None:
        """Initialize with dialect and optional custom type overrides.

        Args:
            dialect: Database dialect ('pg', 'mysql', or 'sqlite').
            type_config: Optional custom type mapping overrides.
        """
        self.dialect = dialect
        self._type_config = type_config

    def generate(self, schema: Schema) -> str:
        lines: list[str] = []

        # Collect imports
        imports = self._collect_imports(schema)
        lines.append(imports)
        lines.append("")

        # Generate enums (PostgreSQL only)
        if self.dialect == "pg" and schema.enums:
            for enum in schema.enums:
                lines.append(self._generate_enum(enum))
            lines.append("")

        # Generate tables
        for table in schema.tables:
            lines.append(self._generate_table(table, schema.enums))
            lines.append("")

        return "\n".join(lines)

    def _collect_imports(self, schema: Schema) -> str:
        """Generate the import statements."""
        table_func = f"{self.dialect}Table"
        type_imports: set[str] = {table_func}
        dialect_prefix = self.dialect

        # Determine dialect-specific import path
        if self.dialect == "pg":
            import_path = "drizzle-orm/pg-core"
        elif self.dialect == "mysql":
            import_path = "drizzle-orm/mysql-core"
        else:
            import_path = "drizzle-orm/sqlite-core"

        # Collect type function names needed
        has_fn_default = False
        for table in schema.tables:
            for col in table.columns:
                drizzle_type = self._get_drizzle_type(col)
                type_imports.add(drizzle_type)

                # Add serial for primary keys with integer type
                if col.primary_key and col.type == ColumnType.INTEGER and not col.default:
                    type_imports.add("serial")
                    type_imports.discard("integer")

                # Track if any fn: defaults need sql import
                if isinstance(col.default, str) and col.default.startswith("fn:"):
                    has_fn_default = True

        # Add sql import for function defaults
        if has_fn_default:
            type_imports.add("sql")

        # Add pgEnum if needed
        if self.dialect == "pg" and schema.enums:
            type_imports.add("pgEnum")

        imports_list = sorted(type_imports)
        return f"import {{ {', '.join(imports_list)} }} from '{import_path}';"

    def _get_drizzle_type(self, col: Column) -> str:
        """Get the Drizzle type function name for a column."""
        if col.primary_key and col.type == ColumnType.INTEGER and not col.default:
            return "serial"

        # Use varchar for string types with length
        if col.type == ColumnType.STRING:
            return "varchar"

        return _TYPE_TO_DRIZZLE.get(col.type, "text")

    def _generate_enum(self, enum: EnumType) -> str:
        """Generate a pgEnum declaration."""
        values = ", ".join(f"'{v}'" for v in enum.values)
        return f"export const {enum.name} = pgEnum('{enum.name}', [{values}]);"

    def _generate_table(self, table: Table, enums: list[EnumType]) -> str:
        """Generate a table definition."""
        table_func = f"{self.dialect}Table"
        # Use table name as variable name (camelCase)
        var_name = self._to_camel_case(table.name)

        lines = [f"export const {var_name} = {table_func}('{table.name}', {{"]

        enum_names = {e.name for e in enums}

        for col in table.columns:
            col_line = self._generate_column(col, enum_names)
            lines.append(f"  {col_line}")

        lines.append("});")
        return "\n".join(lines)

    def _generate_column(self, col: Column, enum_names: set[str]) -> str:
        """Generate a single column definition."""
        # Determine DB column name (from comment if stored)
        db_name = col.name
        if col.comment and col.comment.startswith("db_name:"):
            db_name = col.comment.split(":", 1)[1]

        # Type function call
        type_func = self._get_drizzle_type(col)

        # Build type arguments
        type_args = self._build_type_args(col, type_func)

        # Use enum type if this is an enum column
        if col.type == ColumnType.ENUM and col.custom_type in enum_names:
            # Reference the pgEnum variable
            base = f"{col.custom_type}('{db_name}')"
        elif type_args:
            base = f"{type_func}('{db_name}', {{ {type_args} }})"
        else:
            base = f"{type_func}('{db_name}')"

        # Build chain methods
        chain = []
        if not col.primary_key:
            if not col.nullable:
                chain.append(".notNull()")
            if col.unique:
                chain.append(".unique()")

        if col.default is not None:
            if isinstance(col.default, str) and col.default.startswith("fn:"):
                fn_val = col.default[3:]
                fn_upper = fn_val.upper().rstrip("()")
                if fn_upper == "CURRENT_TIMESTAMP":
                    chain.append(".default(sql`CURRENT_TIMESTAMP`)")
                elif fn_upper == "NOW":
                    chain.append(".defaultNow()")
                elif fn_val.endswith("()"):
                    chain.append(f".default(sql`{fn_val}`)")
                else:
                    chain.append(f".default(sql`{fn_val}`)")
            elif col.default == "now()":
                chain.append(".defaultNow()")
            elif isinstance(col.default, bool):
                chain.append(f".default({str(col.default).lower()})")
            elif isinstance(col.default, str):
                chain.append(f".default('{col.default}')")
            elif isinstance(col.default, (int, float)):
                chain.append(f".default({col.default})")
            else:
                chain.append(f".default({col.default})")

        if col.primary_key:
            chain.append(".primaryKey()")

        # Format: fieldName: typeFunc('name').notNull().primaryKey()
        result = f"{col.name}: {base}{''.join(chain)}"
        return result + ","

    def _build_type_args(self, col: Column, type_func: str) -> str:
        """Build type-specific arguments like { length: 255 }."""
        args = []
        if "length" in col.type_args:
            args.append(f"length: {col.type_args['length']}")
        if "precision" in col.type_args:
            args.append(f"precision: {col.type_args['precision']}")
        if "scale" in col.type_args:
            args.append(f"scale: {col.type_args['scale']}")

        return ", ".join(args)  # Join with ", " for proper spacing

    def _to_camel_case(self, name: str) -> str:
        """Convert snake_case table name to camelCase variable name."""
        parts = name.split("_")
        return parts[0] + "".join(p.capitalize() for p in parts[1:])
