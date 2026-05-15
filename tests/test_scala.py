"""Tests for Scala case class format (parser + generator)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from schemaforge.convert import convert_schema
from schemaforge.parsers.scala_parser import ScalaParser


SAMPLE_SCALA = """import java.time.Instant

case class User(
    id: Int,
    name: String,
    email: String,
    isActive: Boolean = true,
    createdAt: Instant
)
"""


# ── Parser Tests ──

def test_scala_parse_simple():
    """Parser should extract case class and fields."""
    parser = ScalaParser()
    schema = parser.parse(SAMPLE_SCALA)
    assert len(schema.tables) == 1
    assert schema.tables[0].name == "user"


def test_scala_parse_columns():
    """Parser should extract all columns."""
    parser = ScalaParser()
    schema = parser.parse(SAMPLE_SCALA)
    cols = {c.name: c for c in schema.tables[0].columns}
    assert "id" in cols
    assert "name" in cols
    assert "email" in cols
    assert "isActive" in cols
    assert "createdAt" in cols


def test_scala_parse_types():
    """Parser should map Scala types correctly."""
    parser = ScalaParser()
    schema = parser.parse(SAMPLE_SCALA)
    cols = {c.name: c for c in schema.tables[0].columns}
    assert cols["id"].type.value == "integer"
    assert cols["name"].type.value == "string"
    assert cols["isActive"].type.value == "boolean"
    assert cols["createdAt"].type.value == "datetime"


def test_scala_parse_default_values():
    """Parser should extract default values."""
    parser = ScalaParser()
    schema = parser.parse(SAMPLE_SCALA)
    cols = {c.name: c for c in schema.tables[0].columns}
    assert cols["isActive"].default is True


def test_scala_parse_option_type():
    """Option[T] should set nullable=True."""
    scala = """
case class Config(
    id: Int,
    description: Option[String],
    count: Option[Int]
)
"""
    parser = ScalaParser()
    schema = parser.parse(scala)
    cols = {c.name: c for c in schema.tables[0].columns}
    assert cols["description"].nullable is True
    assert cols["count"].nullable is True
    assert cols["id"].nullable is False


def test_scala_parse_empty():
    """Empty input should produce empty schema."""
    parser = ScalaParser()
    schema = parser.parse("")
    assert len(schema.tables) == 0


def test_scala_parse_multiple_classes():
    """Parser should handle multiple case classes."""
    scala = """
case class User(id: Int, name: String)
case class Post(id: Int, title: String)
"""
    parser = ScalaParser()
    schema = parser.parse(scala)
    assert len(schema.tables) == 2


def test_scala_parse_uuid_type():
    """Parser should handle UUID types."""
    scala = 'case class Item(id: java.util.UUID, name: String)'
    parser = ScalaParser()
    schema = parser.parse(scala)
    cols = {c.name: c for c in schema.tables[0].columns}
    assert cols["id"].type.value == "uuid"


def test_scala_parse_decimal_type():
    """Parser should handle BigDecimal."""
    scala = 'case class Product(id: Int, price: BigDecimal)'
    parser = ScalaParser()
    schema = parser.parse(scala)
    cols = {c.name: c for c in schema.tables[0].columns}
    assert cols["price"].type.value == "decimal"


# ── Generation Tests ──

def test_scala_generate_simple():
    """Generator should produce valid case class."""
    from schemaforge.ir import Schema, Table, Column, ColumnType
    from schemaforge.generators.scala_generator import ScalaGenerator
    schema = Schema(tables=[
        Table(name="users", columns=[
            Column(name="id", type=ColumnType.INTEGER),
            Column(name="name", type=ColumnType.STRING, nullable=False),
        ])
    ])
    gen = ScalaGenerator()
    output = gen.generate(schema)
    assert "case class Users" in output
    assert "id: Int" in output
    assert "name: String" in output


def test_scala_generate_nullable():
    """Generator should use Option[T] for nullable columns."""
    from schemaforge.ir import Schema, Table, Column, ColumnType
    from schemaforge.generators.scala_generator import ScalaGenerator
    schema = Schema(tables=[
        Table(name="items", columns=[
            Column(name="id", type=ColumnType.INTEGER),
            Column(name="description", type=ColumnType.STRING, nullable=True),
        ])
    ])
    gen = ScalaGenerator()
    output = gen.generate(schema)
    assert "Option[String]" in output
    assert "description: Option[String]" in output


def test_scala_generate_defaults():
    """Generator should handle default values."""
    from schemaforge.ir import Schema, Table, Column, ColumnType
    from schemaforge.generators.scala_generator import ScalaGenerator
    schema = Schema(tables=[
        Table(name="config", columns=[
            Column(name="id", type=ColumnType.INTEGER),
            Column(name="active", type=ColumnType.BOOLEAN, default=True),
            Column(name="name", type=ColumnType.STRING, default="untitled"),
        ])
    ])
    gen = ScalaGenerator()
    output = gen.generate(schema)
    assert "true" in output
    assert "untitled" in output


# ── Conversion Tests ──

def test_scala_to_sql():
    """Scala case classes should convert to SQL."""
    sql = convert_schema(SAMPLE_SCALA, "scala", "sql")
    assert "CREATE TABLE" in sql
    assert "INTEGER" in sql
    assert "BOOLEAN" in sql


def test_sql_to_scala():
    """SQL should convert to Scala case classes."""
    sql = """
CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    price DECIMAL(10,2)
);
"""
    scala = convert_schema(sql, "sql", "scala")
    assert "case class Products" in scala
    assert "Int" in scala
    assert "String" in scala


def test_scala_to_prisma():
    """Scala → Prisma cross-format."""
    prisma = convert_schema(SAMPLE_SCALA, "scala", "prisma")
    assert "model user" in prisma
    assert "@id" in prisma or "Int" in prisma


def test_scala_to_ef():
    """Scala → C# EF cross-format."""
    cs = convert_schema(SAMPLE_SCALA, "scala", "ef")
    assert "using System" in cs
    assert "class User" in cs


def test_scala_via_convert_api():
    """Scala should work via convert_schema API."""
    result = convert_schema(SAMPLE_SCALA, "scala", "sql")
    assert isinstance(result, str)
    assert len(result) > 0
