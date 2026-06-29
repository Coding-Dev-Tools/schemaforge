"""Parser for Drizzle ORM TypeScript schemas into SchemaForge IR."""

from __future__ import annotations

import re
from typing import Any

from ..ir import Column, ColumnType, EnumType, Schema, Table

# Drizzle type name -> ColumnType mapping
_DRIZZLE_TYPE_MAP: dict[str, ColumnType] = {
    # PostgreSQL
    "serial": ColumnType.INTEGER,
    "bigserial": ColumnType.INTEGER,
    "integer": ColumnType.INTEGER,
    "bigint": ColumnType.INTEGER,
    "smallint": ColumnType.INTEGER,
    "int": ColumnType.INTEGER,
    "varchar": ColumnType.STRING,
    "char": ColumnType.STRING,
    "text": ColumnType.TEXT,
    "boolean": ColumnType.BOOLEAN,
    "bool": ColumnType.BOOLEAN,
    "real": ColumnType.FLOAT,
    "double": ColumnType.FLOAT,
    "doubleprecision": ColumnType.FLOAT,
    "float": ColumnType.FLOAT,
    "numeric": ColumnType.DECIMAL,
    "decimal": ColumnType.DECIMAL,
    "date": ColumnType.DATE,
    "time": ColumnType.TIME,
    "timestamp": ColumnType.DATETIME,
    "json": ColumnType.JSON,
    "jsonb": ColumnType.JSON,
    "uuid": ColumnType.UUID,
    "blob": ColumnType.BLOB,
    "bytea": ColumnType.BLOB,
    # MySQL
    "mediumint": ColumnType.INTEGER,
    "tinyint": ColumnType.INTEGER,
    "float8": ColumnType.FLOAT,
    "varbinary": ColumnType.BLOB,
    "binary": ColumnType.BLOB,
    # SQLite
    "integerval": ColumnType.INTEGER,
    "realval": ColumnType.FLOAT,
    "textval": ColumnType.TEXT,
    "blobval": ColumnType.BLOB,
}

# Dialect prefixes for table factory functions
_DIALECY_TABLE_FACTORY = {
    "pgTable": "pg",
    "mysqlTable": "mysql",
    "sqliteTable": "sqlite",
    "pgView": "pg",
    "mysqlView": "mysql",
    "sqliteView": "sqlite",
}


class DrizzleParser:
    """Parse Drizzle ORM TypeScript schema files into a Schema IR."""

    def parse(self, text: str) -> Schema:
        schema = Schema()

        # Find all table definitions: pgTable('name', { ... }) or mysqlTable etc.
        table_pattern = re.compile(
            r"(?:export\s+)?(?:const\s+)?(\w+)\s*=\s*"
            r"(pgTable|mysqlTable|sqliteTable)\s*\(\s*"
            r"['\"](\w+)['\"]\s*,\s*\{",
            re.MULTILINE,
        )

        # Also find pgEnum declarations
        enum_pattern = re.compile(
            r"(?:export\s+)?(?:const\s+)?(\w+)\s*=\s*"
            r"pgEnum\s*\(\s*"
            r"['\"](\w+)['\"]\s*,\s*\[([^\]]*)\]",
            re.MULTILINE,
        )

        for m in enum_pattern.finditer(text):
            m.group(1)
            enum_name = m.group(2)
            values_str = m.group(3)
            values = [
                v.strip().strip("'\"") for v in values_str.split(",") if v.strip()
            ]
            schema.enums.append(EnumType(name=enum_name, values=values))

        for m in table_pattern.finditer(text):
            m.group(1)
            factory = m.group(2)
            table_name = m.group(3)
            start_pos = m.end()

            # Find the matching closing brace for the column definition object
            columns_text = self._extract_columns_block(text, start_pos)
            if columns_text is None:
                continue

            table = Table(name=table_name)

            # Parse individual column definitions
            for col_match in self._parse_columns(columns_text, factory):
                table.columns.append(col_match)

            schema.tables.append(table)

        return schema

    def _extract_columns_block(self, text: str, start_pos: int) -> str | None:
        """Extract the text between the opening { and its matching closing }.

        Note: start_pos points to the character right after the regex match,
        which ended right after the opening { was consumed. So the block
        starts at start_pos.
        """
        depth = 1  # We already consumed the opening {
        i = start_pos
        block_start = start_pos

        while i < len(text) and depth > 0:
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            elif ch in ("'", '"', "`"):
                # Skip string literals
                quote = ch
                i += 1
                while i < len(text) and text[i] != quote:
                    if text[i] == "\\":
                        i += 1
                    i += 1
            i += 1

        if depth != 0:
            return None

        return text[block_start : i - 1]

    def _parse_columns(self, columns_text: str, factory: str) -> list[Column]:
        """Parse column definitions from the columns block."""
        columns = []

        # Split on commas that are at the top level (not inside parentheses)
        col_defs = self._split_column_defs(columns_text)

        for col_def in col_defs:
            col_def = col_def.strip()
            if not col_def or col_def.startswith("//") or col_def.startswith("/*"):
                continue
            col = self._parse_single_column(col_def, factory)
            if col:
                columns.append(col)

        return columns

    def _split_column_defs(self, text: str) -> list[str]:
        """Split column definitions on top-level commas."""
        defs = []
        current = ""
        depth = 0
        in_string = False
        string_char = None
        i = 0

        while i < len(text):
            ch = text[i]
            if in_string:
                current += ch
                if ch == string_char and (i == 0 or text[i - 1] != "\\"):
                    in_string = False
            elif ch in ("'", '"', "`"):
                in_string = True
                string_char = ch
                current += ch
            elif ch == "(":
                depth += 1
                current += ch
            elif ch == ")":
                depth -= 1
                current += ch
            elif ch == "," and depth == 0:
                defs.append(current.strip())
                current = ""
            else:
                current += ch
            i += 1

        remaining = current.strip()
        if remaining:
            defs.append(remaining)
        return defs

    def _parse_single_column(self, col_def: str, factory: str) -> Column | None:
        """Parse a single column definition like: name: varchar('name', { length: 255 }).notNull()"""
        # Match pattern: fieldName: typeFunc('col_name', ...)
        # e.g. id: serial('id').primaryKey()
        # e.g. name: varchar('name', { length: 255 }).notNull()

        m = re.match(
            r"(\w+)\s*:\s*(\w+)\s*\(\s*['\"]([^'\"]+)['\"]",
            col_def,
        )
        if not m:
            return None

        field_name = m.group(1)
        type_func = m.group(2).lower()
        col_name = m.group(3)

        # Map type function to ColumnType
        col_type = _DRIZZLE_TYPE_MAP.get(type_func, ColumnType.CUSTOM)

        # Parse type args from the rest of the definition
        rest = col_def[m.end() :]
        type_args: dict[str, Any] = {}

        # Extract { length: N }
        length_m = re.search(r"length\s*:\s*(\d+)", rest)
        if length_m:
            type_args["length"] = int(length_m.group(1))

        # Extract { precision: N, scale: N }
        precision_m = re.search(r"precision\s*:\s*(\d+)", rest)
        if precision_m:
            type_args["precision"] = int(precision_m.group(1))
        scale_m = re.search(r"scale\s*:\s*(\d+)", rest)
        if scale_m:
            type_args["scale"] = int(scale_m.group(1))

        # Parse chain methods: .notNull(), .primaryKey(), .unique(), .default(value), .defaultNow()
        is_not_null = ".notNull()" in rest or ".notnull()" in rest.lower()
        is_pk = ".primaryKey()" in rest
        is_unique = ".unique()" in rest

        # Parse default value
        default = None
        default_m = re.search(r"\.default\(([^)]+)\)", rest)
        if default_m:
            default_val = default_m.group(1).strip()
            if default_val.lower() == "null":
                default = None
            elif default_val.lower() in ("true", "false"):
                default = default_val.lower() == "true"
            elif default_val.startswith("'") or default_val.startswith('"'):
                default = default_val.strip("'\"")
            else:
                try:
                    default = int(default_val)
                except ValueError:
                    try:
                        default = float(default_val)
                    except ValueError:
                        default = default_val
        elif ".defaultNow()" in rest:
            default = "now()"

        # Handle enum type
        custom_type = ""
        if col_type == ColumnType.CUSTOM:
            custom_type = type_func

        col = Column(
            name=field_name,
            type=col_type,
            type_args=type_args,
            nullable=not is_not_null and not is_pk,
            unique=is_unique,
            primary_key=is_pk,
            default=default,
            comment="",
            custom_type=custom_type,
        )

        # Store the DB column name if different from field name
        if col_name != field_name:
            col.comment = f"db_name:{col_name}"

        return col
