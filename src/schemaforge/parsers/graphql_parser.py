"""Parser: GraphQL SDL → SchemaForge IR.

Maps GraphQL Schema Definition Language (SDL) type definitions
into schema tables/columns, supporting enums, directives, and
custom scalars.
"""
from __future__ import annotations

import re
from typing import Any

from ..ir import Column, ColumnType, EnumType, Schema, Table

# Regex to strip GraphQL comments
_COMMENT_RE = re.compile(r"#.*$", re.MULTILINE)

# Regex to extract directive annotations from a field line
_DIRECTIVE_RE = re.compile(r"@(\w+)(?:\(([^)]*)\))?")

# Map GraphQL built-in types + common custom scalars to ColumnType
_TYPE_MAP: dict[str, ColumnType] = {
    "String": ColumnType.STRING,
    "Int": ColumnType.INTEGER,
    "Float": ColumnType.FLOAT,
    "Boolean": ColumnType.BOOLEAN,
    "ID": ColumnType.STRING,
    "DateTime": ColumnType.DATETIME,
    "Date": ColumnType.DATE,
    "Time": ColumnType.TIME,
    "JSON": ColumnType.JSON,
    "Json": ColumnType.JSON,
    "BigInt": ColumnType.INTEGER,
    "Decimal": ColumnType.DECIMAL,
    "UUID": ColumnType.UUID,
    "URI": ColumnType.STRING,
    "Email": ColumnType.STRING,
    "PhoneNumber": ColumnType.STRING,
    "Timestamp": ColumnType.DATETIME,
    "Upload": ColumnType.BLOB,
    "Byte": ColumnType.BLOB,
    "Void": ColumnType.CUSTOM,
}

# Built-in scalars that should be kept as-is (not mapped to CUSTOM)
_BUILTIN_SCALARS = {
    "String", "Int", "Float", "Boolean", "ID",
}


class GraphQLParser:
    """Parse GraphQL SDL text into Schema IR."""

    def parse(self, text: str) -> Schema:
        """Parse GraphQL SDL into Schema IR.

        Args:
            text: GraphQL SDL string.

        Returns:
            Schema IR with tables and enums.
        """
        # Strip comments
        clean = _COMMENT_RE.sub("", text)
        schema = Schema()

        # Split into top-level blocks: everything between { }
        # but only at depth 1 — handle nested objects properly
        blocks = self._extract_blocks(clean)

        for kind, name, body, directives in blocks:
            if kind == "enum":
                values = self._parse_enum_body(body)
                schema.enums.append(EnumType(name=name, values=values))
            elif kind == "type":
                # Skip built-in types and query/mutation/subscription
                if name.lower() in ("query", "mutation", "subscription"):
                    continue
                table = self._parse_type(name, body, directives)
                if table:
                    schema.tables.append(table)
            elif kind == "input":
                # Input types become tables too (just with a note)
                table = self._parse_type(name, body, directives, is_input=True)
                if table:
                    schema.tables.append(table)

        return schema

    def _extract_blocks(self, text: str) -> list[tuple[str, str, str, list[str]]]:
        """Extract top-level blocks from GraphQL SDL.

        Returns:
            List of (kind, name, body_text, directives) tuples.
        """
        blocks: list[tuple[str, str, str, list[str]]] = []
        # Pattern: kind name [implements Interface] @directive { ... }
        # Also handles 'extend type Name { ... }'
        pattern = re.compile(
            r"(?P<kind>type|enum|input|interface|union|scalar|extend)\s+"
            r"(?:type\s+)?(?P<name>\w+)\s*"
            r"(?P<implements>implements\s+[^{]+)?"
            r"(?P<directives>[@\w()\[\]!,\s]+)?"
            r"(?P<body>\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\})?",
            re.MULTILINE,
        )

        for match in pattern.finditer(text):
            kind = match.group("kind")
            name = match.group("name")
            body_raw = match.group("body")
            dirs_raw = match.group("directives")

            # Extract directive names
            dirs: list[str] = []
            if dirs_raw:
                dirs = _DIRECTIVE_RE.findall(dirs_raw)
                dirs = [d[0] for d in dirs]

            # Clean body: strip outer braces
            body = ""
            if body_raw:
                body = body_raw[1:-1].strip()

            if kind == "extend":
                kind = "type"  # treat as type extension

            # Handle enums: some enums have inline body (deprecated)
            # and some are 'enum Name { VAL1 VAL2 }'
            if kind == "enum" and not body:
                # Try to find scalar values right after the name
                text[match.end():].strip()
                # Fallback: try matching enum values on the same line or next
                val_match = re.match(r"\s*\{([^}]+)\}", text[match.start():])
                if val_match:
                    body = val_match.group(1).strip()

            if name and (body or kind in ("scalar",)):
                blocks.append((kind, name, body, dirs))

        return blocks

    def _parse_enum_body(self, body: str) -> list[str]:
        """Parse enum body into value strings.

        Handles inline enum value annotations like:
          VALUE
          VALUE @deprecated(reason: "use X")
          VALUE  # trailing comments stripped already

        Returns:
            List of enum value names.
        """
        values: list[str] = []
        for line in body.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Strip directives from value
            value = line.split("@")[0].strip()
            if value:
                values.append(value)
        return values

    def _parse_type(
        self,
        name: str,
        body: str,
        directives: list[str],
        is_input: bool = False,
    ) -> Table | None:
        """Parse a GraphQL type/input definition into a Table.

        Args:
            name: Type name.
            body: Body text (fields).
            directives: Directive names on the type.
            is_input: Whether this is an input type.

        Returns:
            Table IR, or None if no fields.
        """
        if not body or not body.strip():
            return None

        fields = self._parse_fields(body, is_input=is_input)
        if not fields:
            return None

        return Table(
            name=name,
            columns=fields,
            options={"is_input": "true"} if is_input else {},
        )

    def _parse_fields(
        self, body: str, is_input: bool = False
    ) -> list[Column]:
        """Parse GraphQL type fields into Column IR.

        Each field line: name: Type! @directive
        Where ! means non-nullable.

        Args:
            body: Type body text (multi-line field definitions).
            is_input: Whether parsing input type fields.

        Returns:
            List of Column IR objects.
        """
        columns: list[Column] = []
        # Split by top-level commas or newlines — but not inside parens
        lines = body.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Skip field-level comments (already stripped above)
            # Parse: fieldName(TypeArgs): Type! @directive
            col = self._parse_field(line, is_input=is_input)
            if col:
                columns.append(col)

        return columns

    def _parse_field(self, line: str, is_input: bool = False) -> Column | None:
        """Parse a single GraphQL field definition into a Column.

        Examples:
          name: String!
          age: Int @deprecated
          items: [Item!]!
          role: Role!
          metadata: JSON

        Args:
            line: Single field definition line.
            is_input: Whether this is an input type field.

        Returns:
            Column IR, or None if parsing fails.
        """
        # Extract directives first
        dir_matches = _DIRECTIVE_RE.findall(line)
        dir_names = [d[0] for d in dir_matches]
        dir_args = {d[0]: d[1] for d in dir_matches if d[1]}

        # Strip directives from the field line
        clean_line = _DIRECTIVE_RE.sub("", line).strip()
        # Remove trailing commas/spaces
        clean_line = clean_line.rstrip(",").strip()

        # Split on first ':' to get name and type
        if ":" not in clean_line:
            return None

        name_part, type_part = clean_line.split(":", 1)
        field_name = name_part.strip()
        field_type_raw = type_part.strip()

        if not field_name or not field_type_raw:
            return None

        # Parse the GraphQL type (handle !, [], etc.)
        gql_type, nullable, is_list = self._parse_gql_type(field_type_raw)

        # Resolve to ColumnType
        col_type = _TYPE_MAP.get(gql_type)
        if col_type is None:
            # It's a reference to another type (or custom scalar)
            col_type = ColumnType.CUSTOM

        type_args: dict[str, Any] = {}
        custom_type = gql_type if col_type == ColumnType.CUSTOM else ""

        # Check for @unique directive
        unique = "@unique" in dir_names or "unique" in dir_names
        is_id = gql_type == "ID"

        # Handle default values from @default directive
        default = None
        for d_name, d_arg in dir_args.items():
            if d_name in ("default",) and d_arg:
                val = d_arg.strip().strip('"').strip("'")
                if val.isdigit():
                    default = int(val)
                elif val.lower() in ("true", "false"):
                    default = val.lower() == "true"
                else:
                    default = val

        # ID type with no other annotation becomes primary_key hint
        primary_key = is_id and not nullable

        col = Column(
            name=field_name,
            type=col_type,
            type_args=type_args,
            nullable=nullable,
            unique=unique,
            primary_key=primary_key,
            default=default,
            custom_type=custom_type,
        )

        return col

    def _parse_gql_type(self, raw: str) -> tuple[str, bool, bool]:
        """Parse a GraphQL type string into (base_type, nullable, is_list).

        Handles:
          String! → ("String", False, False)
          String  → ("String", True, False)
          [Item]  → ("Item", True, True)
          [Item!]! → ("Item", False, True)

        Args:
            raw: Raw GraphQL type string.

        Returns:
            Tuple of (base_type_name, nullable, is_list).
        """
        is_list = False
        nullable = True

        text = raw.strip()

        # Handle list type [Type]
        if text.startswith("[") and "]" in text:
            is_list = True
            # Extract inner type
            inner_start = text.index("[") + 1
            inner_end = text.index("]")
            inner = text[inner_start:inner_end].strip()
            # Check for outer trailing ! (field-level non-null)
            if text.endswith("!"):
                nullable = False
            # Get the base type name from inner (strip inner !)
            inner_type = inner.rstrip("!").strip()
            return (inner_type, nullable, is_list)
        else:
            # Check for trailing !
            if text.endswith("!"):
                nullable = False
                text = text[:-1].strip()
            return (text, nullable, is_list)
