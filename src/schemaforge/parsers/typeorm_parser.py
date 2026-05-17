"""Parser: TypeORM entity schema → SchemaForge IR."""
from __future__ import annotations

import contextlib
import re
from typing import Any

from ..ir import Column, ColumnType, Index, Schema, Table


class TypeORMParser:
    """Parse TypeORM entity TypeScript files into Schema IR."""

    _TYPE_MAP: dict[str, ColumnType] = {
        "int": ColumnType.INTEGER,
        "integer": ColumnType.INTEGER,
        "bigint": ColumnType.INTEGER,
        "smallint": ColumnType.INTEGER,
        "tinyint": ColumnType.INTEGER,
        "serial": ColumnType.INTEGER,
        "varchar": ColumnType.STRING,
        "char": ColumnType.STRING,
        "text": ColumnType.TEXT,
        "boolean": ColumnType.BOOLEAN,
        "bool": ColumnType.BOOLEAN,
        "float": ColumnType.FLOAT,
        "double": ColumnType.FLOAT,
        "real": ColumnType.FLOAT,
        "decimal": ColumnType.DECIMAL,
        "numeric": ColumnType.DECIMAL,
        "date": ColumnType.DATE,
        "time": ColumnType.TIME,
        "timestamp": ColumnType.DATETIME,
        "datetime": ColumnType.DATETIME,
        "blob": ColumnType.BLOB,
        "json": ColumnType.JSON,
        "jsonb": ColumnType.JSON,
        "uuid": ColumnType.UUID,
        "enum": ColumnType.ENUM,
    }

    def parse(self, text: str) -> Schema:
        """Parse TypeORM entity source into a Schema IR."""
        schema = Schema()

        # Split into entity classes (blocks starting with @Entity)
        entities = self._split_entities(text)
        for entity_block in entities:
            table = self._parse_entity(entity_block)
            if table:
                schema.tables.append(table)

        return schema

    def _split_entities(self, text: str) -> list[str]:
        """Split source text into individual entity blocks."""
        blocks: list[str] = []
        current = ""
        brace_depth = 0
        in_entity = False

        for line in text.split("\n"):
            stripped = line.strip()
            # Start of an entity
            if stripped.startswith("@Entity") or stripped.startswith("// @Entity"):
                in_entity = True
                current = line + "\n"
                continue

            if not in_entity:
                continue

            current += line + "\n"
            for ch in line:
                if ch == "{":
                    brace_depth += 1
                elif ch == "}":
                    brace_depth -= 1

            if brace_depth == 0 and in_entity and current.strip():
                blocks.append(current)
                current = ""
                in_entity = False

        # If file has no @Entity decorators, try class-based detection
        if not blocks:
            # Fallback: find class blocks with model-like decorators
            current = ""
            brace_depth = 0
            in_class = False
            for line in text.split("\n"):
                stripped = line.strip()
                # Detect @Entity, @ViewEntity, or bare class extends pattern
                if (
            (stripped.startswith("@") or stripped.startswith("export class"))
            and (stripped.startswith("export class") or "class " in stripped)
        ):
                    in_class = True
                    current = line + "\n"
                    brace_depth = 0
                    continue
                if not in_class:
                    continue
                current += line + "\n"
                for ch in line:
                    if ch == "{":
                        brace_depth += 1
                    elif ch == "}":
                        brace_depth -= 1
                if brace_depth == 0 and current.strip():
                    blocks.append(current)
                    current = ""
                    in_class = False

        return blocks

    def _parse_entity(self, block: str) -> Table | None:
        """Parse a single TypeORM entity block into a Table."""
        # Extract class name
        class_m = re.search(
            r"(?:export\s+)?(?:abstract\s+)?class\s+(\w+)",
            block,
        )
        if not class_m:
            return None

        table_name = class_m.group(1)
        # Check for @Entity decorator with custom name
        entity_m = re.search(
            r'@Entity\s*\(\s*(?:\{\s*(?:\w+\s*:\s*)?)?["\'](\w+)["\']',
            block,
        )
        if entity_m:
            table_name = entity_m.group(1)

        table = Table(name=table_name)

        # Extract column definitions and decorators
        # Look for lines with @Column, @PrimaryGeneratedColumn, @PrimaryColumn
        lines = block.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Multi-line @Column decorator
            if stripped.startswith("@PrimaryGeneratedColumn") or \
               stripped.startswith("@PrimaryColumn") or \
               stripped.startswith("@Column") or \
               stripped.startswith("@Index") or \
               stripped.startswith("@Unique"):
                decorator_lines = [stripped]
                # Collect multi-line decorator
                depth = stripped.count("(") - stripped.count(")")
                while depth > 0 and i + 1 < len(lines):
                    i += 1
                    decorator_lines.append(lines[i].strip())
                    depth += lines[i].count("(") - lines[i].count(")")
                decorator_text = " ".join(decorator_lines)

                # Look at next lines for the field declaration
                j = i + 1
                field_line = ""
                while j < len(lines):
                    next_line = lines[j].strip()
                    if not next_line or next_line.startswith("@"):
                        break
                    # Skip blank/comment lines between decorator and field
                    if next_line.startswith("//"):
                        j += 1
                        continue
                    field_line = next_line
                    break

                if decorator_text.startswith("@PrimaryGeneratedColumn") or \
                   decorator_text.startswith("@PrimaryColumn"):
                    col = self._parse_column_with_decorator(
                        decorator_text, field_line, is_pk=True
                    )
                    if col:
                        table.columns.append(col)
                elif decorator_text.startswith("@Column"):
                    col = self._parse_column_with_decorator(
                        decorator_text, field_line, is_pk=False
                    )
                    if col:
                        table.columns.append(col)
                elif decorator_text.startswith("@Index"):
                    idx = self._parse_index_decorator(decorator_text)
                    if idx:
                        table.indexes.append(idx)

            i += 1

        return table

    def _parse_column_with_decorator(
        self, decorator: str, field_line: str, is_pk: bool
    ) -> Column | None:
        """Parse a @Column or @PrimaryGeneratedColumn decorator + field."""
        if not field_line:
            return None

        # Parse field: name: Type [= value];
        field_m = re.match(r"(\w+)\s*(?::\s*(\w+))?\s*(?:=\s*(.+?))?\s*;?$", field_line)
        if not field_m:
            return None

        col_name = field_m.group(1)
        ts_type = (field_m.group(2) or "").lower()
        (field_m.group(3) or "").strip()

        # Extract from decorator options
        options = self._parse_decorator_options(decorator)

        col_type_str = options.get("type", "")
        col_type = ColumnType.CUSTOM
        if col_type_str:
            col_type = self._TYPE_MAP.get(col_type_str.lower(), ColumnType.CUSTOM)
        elif ts_type:
            # Map TypeScript types to column types
            ts_map = {
                "number": ColumnType.INTEGER,
                "string": ColumnType.STRING,
                "boolean": ColumnType.BOOLEAN,
                "date": ColumnType.DATETIME,
                "any": ColumnType.CUSTOM,
            }
            col_type = ts_map.get(ts_type, ColumnType.CUSTOM)
        else:
            # Default based on decorator
            col_type = ColumnType.INTEGER if is_pk else ColumnType.STRING

        type_args: dict[str, Any] = {}
        if "length" in options:
            with contextlib.suppress(ValueError, TypeError):
                type_args["length"] = int(options["length"])

        if col_type == ColumnType.DECIMAL:
            if "precision" in options:
                type_args["precision"] = int(options["precision"])
            if "scale" in options:
                type_args["scale"] = int(options["scale"])

        nullable = options.get("nullable", "false").lower() == "true"
        unique = options.get("unique", "false").lower() == "true"

        col = Column(
            name=col_name,
            type=col_type,
            type_args=type_args,
            primary_key=is_pk,
            nullable=nullable,
            unique=unique,
        )

        # Handle default
        if "default" in options:
            raw_default = options["default"]
            if isinstance(raw_default, str) and raw_default.startswith("() => "):
                # Function default (CURRENT_TIMESTAMP, etc.)
                fn_name = raw_default.replace("() => ", "").strip().strip('"\'')
                if fn_name.upper() in ("CURRENT_TIMESTAMP", "NOW()", "UUID"):
                    pass  # Skip DB-managed defaults
                else:
                    col.default = f"fn:{fn_name}"
            elif raw_default.lower() in ("true", "false"):
                col.default = raw_default.lower() == "true"
            elif raw_default.isdigit():
                col.default = int(raw_default)
            else:
                try:
                    col.default = float(raw_default)
                except ValueError:
                    col.default = raw_default.strip('"\'')

        # Handle custom type
        if col_type == ColumnType.CUSTOM and col_type_str:
            col.custom_type = col_type_str

        return col

    def _parse_decorator_options(self, decorator: str) -> dict[str, str]:
        """Parse options from a @Column({...}) or similar decorator.

        Handles both object literals and inline strings.
        """
        options: dict[str, str] = {}

        # Extract the content inside the outermost parens
        depth = 0
        start = -1
        for i, ch in enumerate(decorator):
            if ch == "(":
                if depth == 0:
                    start = i + 1
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and start >= 0:
                    inner = decorator[start:i].strip()
                    break

        if not inner:
            return self._parse_inline_options(decorator)

        # If it's a plain string (type name), handle it
        inner_stripped = inner.strip()
        if inner_stripped.startswith('"') or inner_stripped.startswith("'"):
            options["type"] = inner_stripped.strip('"\'')
            return options

        # If it's an object literal { ... }
        if inner_stripped.startswith("{"):
            # Remove braces
            obj_inner = inner_stripped[1:-1].strip()
            return self._parse_key_value_pairs(obj_inner)

        return options

    def _parse_inline_options(self, decorator: str) -> dict[str, str]:
        """Parse simple inline options like @PrimaryGeneratedColumn() or @Column('text')."""
        m = re.search(r"@\w+\(([^)]*)\)", decorator)
        if m:
            inner = m.group(1).strip()
            if inner:
                # Could be a string or inline object
                if inner.startswith('"') or inner.startswith("'"):
                    return {"type": inner.strip('"\'')}
                if inner.startswith("{"):
                    obj_inner = inner[1:-1].strip()
                    return self._parse_key_value_pairs(obj_inner)
        return {}

    def _parse_key_value_pairs(self, text: str) -> dict[str, str]:
        """Parse key: value pairs from an object literal."""
        options: dict[str, str] = {}
        # Use regex to find key: value pairs
        # Handle nested objects by tracking brace/paren depth
        i = 0
        while i < len(text):
            # Skip whitespace and commas
            while i < len(text) and text[i] in ", \t\n":
                i += 1
            if i >= len(text):
                break

            # Read key
            key_match = re.match(r"(\w+)\s*:", text[i:])
            if not key_match:
                i += 1
                continue

            key = key_match.group(1)
            i += key_match.end()

            # Skip whitespace
            while i < len(text) and text[i] in " \t\n":
                i += 1
            if i >= len(text):
                break

            # Read value (handle nested braces/parens/quotes)
            if text[i] in ('"', "'"):
                # Quoted string
                quote = text[i]
                i += 1
                val_start = i
                while i < len(text) and text[i] != quote:
                    if text[i] == "\\":
                        i += 1  # Skip escape
                    i += 1
                options[key] = text[val_start:i]
                i += 1  # Skip closing quote
            elif text[i] == "{":
                # Nested object — skip it
                depth = 0
                while i < len(text):
                    if text[i] == "{":
                        depth += 1
                    elif text[i] == "}":
                        depth -= 1
                        if depth == 0:
                            i += 1
                            break
                    i += 1
            elif text[i : i + 4].lower() == "true":
                options[key] = "true"
                i += 4
            elif text[i : i + 5].lower() == "false":
                options[key] = "false"
                i += 5
            elif text[i] == "(":
                # Function value like () => "CURRENT_TIMESTAMP"
                depth = 0
                val_start = i
                while i < len(text):
                    if text[i] == "(":
                        depth += 1
                    elif text[i] == ")":
                        depth -= 1
                        if depth == 0:
                            i += 1
                            break
                    i += 1
                options[key] = text[val_start:i].strip()
            else:
                # Number or bare identifier
                val_match = re.match(r"([\w.]+)", text[i:])
                if val_match:
                    options[key] = val_match.group(1)
                    i += val_match.end()
                else:
                    i += 1

        return options

    def _parse_index_decorator(self, decorator: str) -> Index | None:
        """Parse @Index decorator."""
        # @Index() — applies to the field below
        # @Index("idx_name", ["col1", "col2"]) — multi-column
        # @Index(["col1", "col2"]) — multi-column
        inner_match = re.search(r"@Index\(([^)]*)\)", decorator)
        if not inner_match:
            return Index()

        inner = inner_match.group(1).strip()
        if not inner:
            return Index()

        # Try to extract columns from array
        arr_match = re.search(r"\[([^\]]+)\]", inner)
        if arr_match:
            columns = [
                c.strip().strip('"\'') for c in arr_match.group(1).split(",")
            ]
        else:
            # Single field index — name is in quotes
            name_match = re.search(r'["\'](\w+)["\']', inner)
            columns = [name_match.group(1)] if name_match else []

        return Index(columns=columns)
