"""Parser: Prisma schema → SchemaForge IR."""

from __future__ import annotations

from ..ir import Column, ColumnType, EnumType, Schema, Table


class PrismaParser:
    """Parse Prisma schema files into Schema IR."""

    _TYPE_MAP = {
        "String": ColumnType.STRING,
        "Int": ColumnType.INTEGER,
        "BigInt": ColumnType.INTEGER,
        "Float": ColumnType.FLOAT,
        "Boolean": ColumnType.BOOLEAN,
        "DateTime": ColumnType.DATETIME,
        "Json": ColumnType.JSON,
        "Bytes": ColumnType.BLOB,
        "Decimal": ColumnType.DECIMAL,
        "Unsupported": ColumnType.CUSTOM,
    }

    def parse(self, text: str) -> Schema:
        schema = Schema()

        # Find all model blocks
        lines = text.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("model ") or line.startswith("model\t"):
                # Parse model block
                model_name = line.split()[1]
                model_lines = []
                i += 1
                while i < len(lines):
                    line = lines[i].strip()
                    if line == "}":
                        break
                    if line and not line.startswith("//") and not line.startswith("#"):
                        model_lines.append(line)
                        i += 1
                table = self._parse_model(model_name, model_lines)
                if table:
                    schema.tables.append(table)
            elif line.startswith("enum ") or line.startswith("enum\t"):
                enum_name = line.split()[1]
                enum_values = []
                i += 1
                while i < len(lines):
                    line = lines[i].strip()
                    if line == "}":
                        break
                    if line and not line.startswith("//") and not line.startswith("#"):
                        enum_values.append(line.rstrip(",").strip())
                        i += 1
                schema.enums.append(EnumType(name=enum_name, values=enum_values))
            i += 1

        return schema

    def _parse_model(self, name: str, lines: list[str]) -> Table | None:
        """Parse a Prisma model block into a Table."""
        table = Table(name=name)

        for line in lines:
            # Skip decorators, comments, and block-level attributes
            stripped = line.strip()
            if (
                not stripped
                or stripped.startswith("@@")
                or stripped.startswith("//")
                or stripped.startswith("#")
            ):
                continue

            # Parse field: name type [modifiers...]
            parts = stripped.split()
            if len(parts) < 2:
                continue

            field_name = parts[0]
            field_type_raw = parts[1]

            # Handle nullable shorthand (e.g., "String?")
            is_nullable = field_type_raw.endswith("?")
            field_type_clean = field_type_raw.rstrip("?")
            if not field_type_clean:
                field_type_clean = field_type_raw

            constraints = " ".join(parts[2:]) if len(parts) > 2 else ""

            # Map Prisma type to ColumnType
            col_type = self._TYPE_MAP.get(field_type_clean, ColumnType.CUSTOM)

            type_args = {}
            if col_type == ColumnType.STRING and "@db.VarChar" in constraints:
                # Only capture length if explicitly constrained
                db_match = __import__("re").search(
                    r"@db\.VarChar\((\d+)\)", constraints
                )
                if db_match:
                    type_args["length"] = int(db_match.group(1))

            col = Column(
                name=field_name,
                type=col_type,
                type_args=type_args,
                primary_key="@id" in constraints or "id" in constraints.lower(),
                unique="@unique" in constraints,
                nullable=is_nullable or "optional" in constraints.lower(),
            )

            # Check for default values (handle nested parens)
            if "@default" in constraints:
                idx = constraints.index("@default(")
                rest = constraints[idx + len("@default(") :]
                depth = 1
                default_val = ""
                for ch in rest:
                    if ch == "(":
                        depth += 1
                    elif ch == ")":
                        depth -= 1
                        if depth == 0:
                            break
                    default_val += ch
                if default_val:
                    # Skip function-like defaults for scalar types
                    if default_val.endswith("()") or "(" in default_val:
                        # It's a function (autoincrement, uuid, etc.) — handle as special
                        if "autoincrement" in default_val:
                            col.default = None  # auto-increment, not a real default
                        elif "uuid" in default_val:
                            col.default = None
                        else:
                            col.default = f"fn:{default_val}"
                    elif default_val.isdigit():
                        col.default = int(default_val)
                    elif default_val.lower() in ("true", "false"):
                        col.default = default_val.lower() == "true"
                    elif default_val.lower() == "now()":
                        col.default = None  # handled by DB
                    else:
                        col.default = default_val.strip("\"'")
            if col_type == ColumnType.CUSTOM:
                col.custom_type = field_type_clean

            table.columns.append(col)

        return table
