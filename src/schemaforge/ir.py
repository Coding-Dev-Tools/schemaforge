"""SchemaForge — Internal Representation (IR) for bidirectional conversion.

All formats convert to/from this common IR, enabling lossless roundtripping
between any supported format pair.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ColumnType(Enum):
    """Supported column data types mapped across ORMs."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    DATE = "date"
    TIME = "time"
    TEXT = "text"
    BLOB = "blob"
    JSON = "json"
    UUID = "uuid"
    ENUM = "enum"
    DECIMAL = "decimal"
    CUSTOM = "custom"  # For dialect-specific types (JSONB, etc.)


@dataclass
class Column:
    """A single column/field in a schema."""

    name: str
    type: ColumnType
    type_args: dict[str, Any] = field(default_factory=dict)
    # e.g. {"length": 255, "precision": 10, "scale": 2}
    nullable: bool = False
    unique: bool = False
    primary_key: bool = False
    default: Any = None
    comment: str = ""
    # Custom type name for dialect-specific types (e.g. "JSONB", "ENUM('a','b')")
    custom_type: str = ""


@dataclass
class Index:
    """A database index."""

    name: str = ""
    columns: list[str] = field(default_factory=list)
    unique: bool = False


@dataclass
class Table:
    """A single table/model/collection in the schema."""

    name: str
    columns: list[Column] = field(default_factory=list)
    indexes: list[Index] = field(default_factory=list)
    comment: str = ""
    options: dict[str, str] = field(default_factory=dict)
    # MySQL table options: {"ENGINE": "InnoDB", "AUTO_INCREMENT": "1", "DEFAULT CHARSET": "utf8mb4"}


@dataclass
class EnumType:
    """A named enum type (database enum or ORM enum)."""

    name: str
    values: list[str] = field(default_factory=list)


@dataclass
class Schema:
    """Complete schema — the IR all formats translate to/from."""

    tables: list[Table] = field(default_factory=list)
    enums: list[EnumType] = field(default_factory=list)
