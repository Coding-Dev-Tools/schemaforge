"""Parser: Prisma schema → SchemaForge IR."""
from __future__ import annotations

from ..ir import Schema, Table, Column, ColumnType, EnumType


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
                    l = lines[i].strip()
                    if l == "}":
                        break
                    if l and not l.startswith("//") and not l.startswith("#"):
                        model_lines.append(l)
                    i += 1
                table = self._parse_model(model_name, model_lines)
                if table:
                    schema.tables.append(table)
            elif line.startswith("enum ") or line.startswith("enum\t"):
                enum_name = line.split()[1]
                enum_values = []
                i += 1
                while i < len(lines):
                    l = lines[i].strip()
                    if l == "}":
                        break
                    if l and not l.startswith("//") and not l.startswith("#"):
                        enum_values.append(l.rstrip(",").strip())
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
            if not stripped or stripped.startswith("@@") or stripped.startswith("//") or stripped.startswith("#"):
                continue

            # Parse field: name type [modifiers...]
            parts = stripped.split()
            if len(parts) < 2:
                continue

            field_name = parts[0]
            field_type = parts[1]

            constraints = " ".join(parts[2:]) if len(parts) > 2 else ""

            # Map Prisma type to ColumnType
            col_type = self._TYPE_MAP.get(field_type, ColumnType.CUSTOM)

            col = Column(
                name=field_name,
                type=col_type,
                primary_key="@id" in constraints or "id" in constraints.lower(),
                unique="@unique" in constraints,
                nullable="?" in field_type or "optional" in constraints.lower(),
            )

            # Check for default values
            if "@default" in constraints:
                default_m = __import__("re").search(r"@default\(([^)]+)\)", constraints)
                if default_m:
                    col.default = default_m.group(1)

            # Check for relation
            if "@relation" in constraints:
                pass  # Relations are skipped for now

            if col_type == ColumnType.CUSTOM:
                col.custom_type = field_type

            table.columns.append(col)

        return table
