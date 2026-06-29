"""Parser: Scala case class definitions → SchemaForge IR.

Parses Scala case class definitions suitable for Doobie, Quill,
or Slick into the internal schema representation.
"""

from __future__ import annotations

import re
from typing import Any

from ..ir import Column, ColumnType, Schema, Table

# Regex: extract case class
_CASE_CLASS_RE = re.compile(
    r"(?:@(?:Entity|Table|Mapped)\s*(?:\([^)]*\))?\s*)?"
    r"(?:case\s+)?class\s+(\w+)"
    r"(?:\s*\(((?:[^()]|\([^()]*\))*)\))",
    re.MULTILINE,
)

# Regex: extract field from case class parameter list
_FIELD_RE = re.compile(r"\s*(\w+)\s*:\s*([^=,]+)(?:\s*=\s*([^,]+))?\s*,?\s*")

# Map Scala types to ColumnType
_SCALA_TYPE_MAP: dict[str, ColumnType] = {
    "Int": ColumnType.INTEGER,
    "Long": ColumnType.INTEGER,
    "Short": ColumnType.INTEGER,
    "Byte": ColumnType.INTEGER,
    "BigInt": ColumnType.INTEGER,
    "String": ColumnType.STRING,
    "Boolean": ColumnType.BOOLEAN,
    "Double": ColumnType.FLOAT,
    "Float": ColumnType.FLOAT,
    "BigDecimal": ColumnType.DECIMAL,
    "java.math.BigDecimal": ColumnType.DECIMAL,
    "Instant": ColumnType.DATETIME,
    "java.time.Instant": ColumnType.DATETIME,
    "LocalDateTime": ColumnType.DATETIME,
    "java.time.LocalDateTime": ColumnType.DATETIME,
    "OffsetDateTime": ColumnType.DATETIME,
    "java.time.OffsetDateTime": ColumnType.DATETIME,
    "ZonedDateTime": ColumnType.DATETIME,
    "java.time.ZonedDateTime": ColumnType.DATETIME,
    "LocalDate": ColumnType.DATE,
    "java.time.LocalDate": ColumnType.DATE,
    "LocalTime": ColumnType.TIME,
    "java.time.LocalTime": ColumnType.TIME,
    "UUID": ColumnType.UUID,
    "java.util.UUID": ColumnType.UUID,
    "java.util.Date": ColumnType.DATETIME,
    "DateTime": ColumnType.DATETIME,
    "org.joda.time.DateTime": ColumnType.DATETIME,
    "org.joda.time.LocalDate": ColumnType.DATE,
    "org.joda.time.LocalTime": ColumnType.TIME,
}


def _clean_scala_type(raw: str) -> tuple[str, bool]:
    """Clean a Scala type string.

    Returns (cleaned_type, is_optional) where is_optional is True for Option[T].
    """
    raw = raw.strip()
    is_optional = False

    # Handle Option[T]
    if raw.startswith("Option["):
        raw = raw[7:-1].strip()
        is_optional = True

    # Handle List[T], Seq[T], Vector[T]
    for prefix in ("List[", "Seq[", "Vector[", "Set[", "List["):
        if raw.startswith(prefix) and raw.endswith(">"):
            raw = raw[len(prefix) : -1].strip()
            break

    return raw, is_optional


def _parse_default(value_str: str) -> Any:
    """Parse a Scala default value expression."""
    val = value_str.strip().rstrip(",")

    if val == "true":
        return True
    if val == "false":
        return False
    if val == "null" or val == "None":
        return None

    # Quoted strings
    if (val.startswith('"') and val.endswith('"')) or (
        val.startswith('"""') and val.endswith('"""')
    ):
        inner = val.strip('"')
        # Handle interpolation: s"..."
        idx = inner.find("$")
        if idx >= 0:
            inner = inner[:idx]
        return inner

    # Integer
    try:
        return int(val)
    except ValueError:
        pass

    # Float
    try:
        return float(val)
    except ValueError:
        pass

    # Function defaults (e.g., java.time.Instant.now())
    if "(" in val and val.endswith(")"):
        fn_name = val.split("(")[0].split(".")[-1]
        return f"fn:{fn_name}()"

    return None


class ScalaParser:
    """Parse Scala case class definitions into Schema IR."""

    def parse(self, text: str) -> Schema:
        """Parse Scala source text into a Schema IR."""
        schema = Schema()

        # Remove comments
        text = re.sub(r"//.*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)

        for m in _CASE_CLASS_RE.finditer(text):
            class_name = m.group(1)
            params_str = m.group(2)

            if not class_name or not params_str:
                continue

            table = Table(name=self._to_snake(class_name))
            fields = _FIELD_RE.findall(params_str)

            for field_name, field_type, default_str in fields:
                col = self._field_to_column(
                    field_name, field_type.strip(), default_str.strip()
                )
                if col:
                    table.columns.append(col)

            if table.columns:
                schema.tables.append(table)

        return schema

    def _field_to_column(
        self, name: str, raw_type: str, default_str: str
    ) -> Column | None:
        """Convert a Scala field to a Column IR."""
        clean_type, is_optional = _clean_scala_type(raw_type)

        col_type = _SCALA_TYPE_MAP.get(clean_type, ColumnType.CUSTOM)
        type_args: dict[str, Any] = {}
        default_val: Any = None
        custom_type = ""

        # Parse default value
        if default_str:
            default_val = _parse_default(default_str)

        # Handle String length from default values / heuristics
        if col_type == ColumnType.STRING and isinstance(default_val, str):
            pass  # No length hint from Scala

        if col_type == ColumnType.CUSTOM:
            custom_type = clean_type

        return Column(
            name=name,
            type=col_type,
            type_args=type_args,
            nullable=is_optional,
            unique=False,
            primary_key=False,
            default=default_val,
            custom_type=custom_type,
        )

    def _to_snake(self, name: str) -> str:
        """Convert PascalCase to snake_case."""
        result = re.sub(r"([A-Z])", r"_\1", name).lower().lstrip("_")
        result = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", result).lower()
        return result.strip("_")
