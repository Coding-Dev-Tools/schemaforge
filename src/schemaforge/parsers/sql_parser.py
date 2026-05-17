"""Parser for SQL DDL into SchemaForge IR."""
from __future__ import annotations

import contextlib
import re
from typing import Any

from ..ir import Column, ColumnType, EnumType, Index, Schema, Table


class SQLParser:
    """Parse SQL DDL statements into a Schema IR."""

    # SQL function keywords that should be stored as fn: prefixed defaults
    _SQL_FN_KEYWORDS: set[str] = {
        "CURRENT_TIMESTAMP", "CURRENT_DATE", "CURRENT_TIME",
        "LOCALTIMESTAMP", "LOCALTIME",
        "NOW", "RANDOM", "GEN_RANDOM_UUID", "UUID",
        "RAND", "CURDATE", "CURTIME", "SYSDATE",
        "UTC_TIMESTAMP", "UTC_DATE", "UTC_TIME",
    }

    def parse(self, text: str) -> Schema:
        schema = Schema()

        # Split into statements
        statements = self._split_statements(text)

        for stmt in statements:
            stmt = stmt.strip()
            if not stmt:
                continue
            upper = stmt.upper()
            if (
                upper.startswith("CREATE TABLE")
                or upper.startswith("CREATE TEMPORARY TABLE")
                or upper.startswith("CREATE OR REPLACE TABLE")
            ):
                table = self._parse_create_table(stmt)
                if table:
                    schema.tables.append(table)
            elif upper.startswith("CREATE TYPE") and "AS ENUM" in stmt.upper():
                enum_type = self._parse_create_enum(stmt)
                if enum_type:
                    schema.enums.append(enum_type)

        return schema

    def _split_statements(self, text: str) -> list[str]:
        """Split SQL text into individual statements."""
        # Simple split on semicolons (handling quoted strings)
        statements = []
        current = ""
        in_string = False
        string_char = None
        i = 0
        while i < len(text):
            ch = text[i]
            if in_string:
                current += ch
                if ch == string_char and (i == 0 or text[i-1] != '\\'):
                    in_string = False
            elif ch in ("'", '"'):
                in_string = True
                string_char = ch
                current += ch
            elif ch == ';':
                statements.append(current.strip())
                current = ""
            else:
                current += ch
            i += 1
        remaining = current.strip()
        if remaining:
            statements.append(remaining)
        return statements

    def _parse_create_table(self, stmt: str) -> Table | None:
        """Parse a CREATE TABLE statement."""
        # Extract table name — support quoted/backtick identifiers
        m = re.match(
            r'CREATE\s+(?:TEMPORARY\s+)?(?:OR\s+REPLACE\s+)?'
            r'TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?'
            r'(?:`(\w+)`\.|"(\w+)"\.|(\w+)\.)?'
            r'`?"?([\w-]+)"?`?',
            stmt, re.IGNORECASE
        )
        if not m:
            return None
        # Schema qualifier could be backtick, double-quote, or bare
        schema_name = m.group(1) or m.group(2) or m.group(3)
        table_name = m.group(4)
        if schema_name:
            table_name = f"{schema_name}.{table_name}"

        # Extract columns between outermost parens
        paren_depth = 0
        start = -1
        for i, ch in enumerate(stmt):
            if ch == '(':
                if paren_depth == 0:
                    start = i + 1
                paren_depth += 1
            elif ch == ')':
                paren_depth -= 1
                if paren_depth == 0 and start >= 0:
                    body = stmt[start:i]
                    break

        if start < 0:
            return None

        # Extract MySQL table options after the closing paren (e.g. ENGINE=InnoDB AUTO_INCREMENT=1)
        table_options = self._parse_table_options(stmt[i+1:])

        table = Table(name=table_name, options=table_options)
        # Split body into lines/definitions
        definitions = self._split_definitions(body)

        for defn in definitions:
            defn = defn.strip()
            if not defn:
                continue
            upper = defn.upper()
            if upper.startswith("INDEX") or upper.startswith("KEY"):
                idx = self._parse_index_definition(defn)
                if idx:
                    table.indexes.append(idx)
            elif upper.startswith("UNIQUE"):
                idx = self._parse_index_definition(defn)
                if idx:
                    idx.unique = True
                    table.indexes.append(idx)
            elif upper.startswith("PRIMARY KEY"):
                pass  # PK handled via column constraints
            elif upper.startswith("CONSTRAINT"):
                pass  # Foreign keys, etc.
            elif upper.startswith("FOREIGN KEY") or upper.startswith("CHECK"):
                pass
            else:
                col = self._parse_column_def(defn)
                if col:
                    table.columns.append(col)

        return table

    def _split_definitions(self, body: str) -> list[str]:
        """Split CREATE TABLE body into individual definitions."""
        defs = []
        current = ""
        paren_depth = 0
        for ch in body:
            if ch == '(':
                paren_depth += 1
                current += ch
            elif ch == ')':
                paren_depth -= 1
                current += ch
            elif ch == ',' and paren_depth == 0:
                defs.append(current.strip())
                current = ""
            else:
                current += ch
        remaining = current.strip()
        if remaining:
            defs.append(remaining)
        return defs

    _TYPE_MAP: dict[str, ColumnType] = {
        "INT": ColumnType.INTEGER,
        "INTEGER": ColumnType.INTEGER,
        "BIGINT": ColumnType.INTEGER,
        "SMALLINT": ColumnType.INTEGER,
        "TINYINT": ColumnType.INTEGER,
        "SERIAL": ColumnType.INTEGER,
        "BIGSERIAL": ColumnType.INTEGER,
        "VARCHAR": ColumnType.STRING,
        "CHAR": ColumnType.STRING,
        "TEXT": ColumnType.TEXT,
        "BOOLEAN": ColumnType.BOOLEAN,
        "BOOL": ColumnType.BOOLEAN,
        "FLOAT": ColumnType.FLOAT,
        "DOUBLE": ColumnType.FLOAT,
        "REAL": ColumnType.FLOAT,
        "DECIMAL": ColumnType.DECIMAL,
        "NUMERIC": ColumnType.DECIMAL,
        "DATE": ColumnType.DATE,
        "TIME": ColumnType.TIME,
        "TIMESTAMP": ColumnType.DATETIME,
        "DATETIME": ColumnType.DATETIME,
        "BLOB": ColumnType.BLOB,
        "BYTEA": ColumnType.BLOB,
        "JSON": ColumnType.JSON,
        "JSONB": ColumnType.JSON,
        "UUID": ColumnType.UUID,
        "ENUM": ColumnType.ENUM,
    }

    def _parse_column_def(self, defn: str) -> Column | None:
        """Parse a column definition."""
        # Skip table constraints
        upper = defn.upper()
        if (
            any(kw in upper for kw in [
                "PRIMARY KEY", "FOREIGN KEY", "INDEX",
                "KEY", "CHECK", "UNIQUE", "CONSTRAINT",
            ])
            and (
                not defn.split()[0].isidentifier()
                or defn.split()[0].upper() in (
                    "PRIMARY", "FOREIGN", "INDEX",
                    "KEY", "CHECK", "UNIQUE", "CONSTRAINT",
                )
            )
        ):
            return None

        # Parse: column_name TYPE [(args)] [constraints...]
        tokens = defn.split()
        if not tokens:
            return None

        col_name = tokens[0]
        if col_name.startswith('"') or col_name.startswith('`') or col_name.startswith('['):
            col_name = col_name.strip('"`[]')

        # Find the type (skip quoted name)
        type_start = 1
        type_raw = tokens[type_start] if type_start < len(tokens) else "TEXT"

        # Handle type with parameters that may span multiple tokens (e.g. ENUM('a', 'b', 'c'))
        if type_raw.startswith(('ENUM(', 'enum(')) or (
            '(' in type_raw and ')' not in type_raw and type_start + 1 < len(tokens)
        ):
            while ')' not in type_raw and type_start + 1 < len(tokens):
                type_start += 1
                type_raw += " " + tokens[type_start]

        type_name = type_raw.split('(')[0].upper() if '(' in type_raw else type_raw.upper()

        col_type = self._TYPE_MAP.get(type_name, ColumnType.CUSTOM)

        # Extract type args
        type_args: dict[str, Any] = {}
        if '(' in type_raw:
            args_str = type_raw[type_raw.index('(')+1:type_raw.index(')')] if ')' in type_raw else ""
            if type_name == "ENUM":
                # Inline ENUM('a','b','c') — extract values via regex to handle multi-token args
                type_args["values"] = re.findall(r"'([^']*)'", args_str)
            if type_name in ("VARCHAR", "CHAR"):
                with contextlib.suppress(ValueError):
                    type_args["length"] = int(args_str)
            elif type_name in ("DECIMAL", "NUMERIC"):
                parts = args_str.split(',')
                if len(parts) >= 1:
                    with contextlib.suppress(ValueError):
                        type_args["precision"] = int(parts[0])
                if len(parts) >= 2:
                    with contextlib.suppress(ValueError):
                        type_args["scale"] = int(parts[1])

        # Parse constraints
        constraints = " ".join(tokens[type_start+1:]) if type_start + 1 < len(tokens) else ""

        is_pk = "PRIMARY KEY" in constraints.upper()
        is_not_null = "NOT NULL" in constraints.upper()

        col = Column(
            name=col_name,
            type=col_type,
            type_args=type_args,
            nullable=not (is_not_null or is_pk),
            unique="UNIQUE" in constraints.upper() and not is_pk,
            primary_key=is_pk,
        )

        # Extract default
        default_m = re.search(r"DEFAULT\s+(\S+)", constraints, re.IGNORECASE)
        if default_m:
            val = default_m.group(1)
            if val.upper() == "NULL":
                col.default = None
                col.nullable = True
            elif val.upper() in ("TRUE", "FALSE"):
                col.default = val.upper() == "TRUE"
            elif val.startswith("'") or val.startswith('"'):
                col.default = val.strip("'\"")
            else:
                # Strip trailing comma if accidentally included
                val = val.rstrip(",")
                # Check for SQL function calls like CURRENT_TIMESTAMP, now(), etc.
                upper_val = val.upper().rstrip(")")
                is_fn = (
                    upper_val in self._SQL_FN_KEYWORDS
                    or upper_val.rstrip("()") in self._SQL_FN_KEYWORDS
                    or re.match(r'^\w+\(', val)  # Any function call: nextval(), now(), etc.
                )
                if is_fn:
                    col.default = f"fn:{val}"
                else:
                    try:
                        col.default = int(val)
                    except ValueError:
                        try:
                            col.default = float(val)
                        except ValueError:
                            col.default = val

        # Extract comment
        comment_m = re.search(r"COMMENT\s+'(.+?)'", constraints, re.IGNORECASE)
        if comment_m:
            col.comment = comment_m.group(1)

        if col_type == ColumnType.CUSTOM:
            col.custom_type = type_raw.strip("()")

        return col

    def _parse_index_definition(self, defn: str) -> Index | None:
        """Parse an index definition."""
        m = re.search(r'(?:INDEX|KEY)\s+(\w+)\s*\(([^)]+)\)', defn, re.IGNORECASE)
        if m:
            name = m.group(1)
            columns = [c.strip().strip('"`[]') for c in m.group(2).split(',')]
            return Index(name=name, columns=columns, unique="UNIQUE" in defn.upper())
        return None

    def _parse_create_enum(self, stmt: str) -> EnumType | None:
        """Parse a CREATE TYPE ... AS ENUM statement."""
        m = re.match(
            r"CREATE\s+TYPE\s+(\w+)\s+AS\s+ENUM\s*\(([^)]+)\)",
            stmt, re.IGNORECASE
        )
        if m:
            name = m.group(1)
            values = re.findall(r"'([^']*)'", m.group(2))
            return EnumType(name=name, values=values)
        return None

    def _parse_table_options(self, after_paren: str) -> dict[str, str]:
        """Parse MySQL table options after the closing paren.

        Handles: ENGINE=InnoDB, AUTO_INCREMENT=1, DEFAULT CHARSET=utf8mb4,
        COLLATE=utf8mb4_unicode_ci, ROW_FORMAT=DYNAMIC, COMMENT='table comment'
        """
        text = after_paren.strip().rstrip(";").strip()
        if not text:
            return {}

        options: dict[str, str] = {}
        # Match table option key=value pairs (value may be quoted)
        # Also handle "DEFAULT CHARSET" as a single key
        i = 0
        while i < len(text):
            # Skip whitespace
            while i < len(text) and text[i] in (' ', '\t', '\n', '\r'):
                i += 1
            if i >= len(text):
                break

            # Check for "DEFAULT CHARSET" or "DEFAULT COLLATE" two-word keys
            remaining = text[i:]
            default_m = re.match(r'DEFAULT\s+(CHARSET|CHARACTER\s+SET|COLLATE)\s*=\s*', remaining, re.IGNORECASE)
            if default_m:
                key = f"DEFAULT {default_m.group(1).upper()}"
                val_start = i + default_m.end()
            else:
                # Single-word key: ENGINE, AUTO_INCREMENT, ROW_FORMAT, etc.
                key_m = re.match(r'(\w+)\s*=\s*', remaining)
                if not key_m:
                    # Try COMMENT 'xxx' (no equals)
                    comment_m = re.match(r"COMMENT\s+'([^']*)'", remaining, re.IGNORECASE)
                    if comment_m:
                        options["COMMENT"] = comment_m.group(1)
                        i += comment_m.end()
                        continue
                    break
                key = key_m.group(1).upper()
                val_start = i + key_m.end()

            # Extract value: could be quoted or unquoted
            val_rest = text[val_start:].lstrip()
            if val_rest and val_rest[0] in ("'", '"'):
                quote = val_rest[0]
                end = val_rest.find(quote, 1)
                if end > 0:
                    options[key] = val_rest[1:end]
                    i = val_start + end + 1
                else:
                    break
            else:
                # Unquoted value — grab until next space, semicolon, or end
                val_end = re.match(r'([^\s;]+)', val_rest)
                if val_end:
                    options[key] = val_end.group(1)
                    i = val_start + val_end.end()
                else:
                    break

        return options
