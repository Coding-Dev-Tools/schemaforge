"""Tests for Entity Framework Core format (parser + generator)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from schemaforge.convert import convert_schema
from schemaforge.generators.ef_generator import EntityFrameworkGenerator
from schemaforge.parsers.ef_parser import EntityFrameworkParser

SAMPLE_CS = """using System;
using System.ComponentModel.DataAnnotations;

[Table("users")]
public class User
{
    [Key]
    public int Id { get; set; }

    [Required]
    [MaxLength(100)]
    public string Name { get; set; }

    [Required]
    public string Email { get; set; }

    public bool IsActive { get; set; }

    public DateTime CreatedAt { get; set; }
}
"""


# ── Parser Tests ──

def test_ef_parse_table_name():
    """Parser should extract table name from [Table] attribute."""
    parser = EntityFrameworkParser()
    schema = parser.parse(SAMPLE_CS)
    assert len(schema.tables) == 1
    assert schema.tables[0].name == "users"


def test_ef_parse_class_without_table():
    """Parser should use class name when no [Table] attribute."""
    cs = """
public class Product
{
    public int Id { get; set; }
    public string Name { get; set; }
}
"""
    parser = EntityFrameworkParser()
    schema = parser.parse(cs)
    assert len(schema.tables) == 1
    assert schema.tables[0].name == "Product"


def test_ef_parse_columns():
    """Parser should extract all columns."""
    parser = EntityFrameworkParser()
    schema = parser.parse(SAMPLE_CS)
    assert len(schema.tables) == 1
    cols = {c.name: c for c in schema.tables[0].columns}
    assert "id" in cols
    assert "name" in cols
    assert "email" in cols
    assert "is_active" in cols
    assert "created_at" in cols


def test_ef_parse_primary_key():
    """[Key] attribute should set primary_key=True."""
    parser = EntityFrameworkParser()
    schema = parser.parse(SAMPLE_CS)
    cols = {c.name: c for c in schema.tables[0].columns}
    assert cols["id"].primary_key is True
    assert cols["name"].primary_key is False


def test_ef_parse_required():
    """[Required] attribute should set nullable=False."""
    parser = EntityFrameworkParser()
    schema = parser.parse(SAMPLE_CS)
    cols = {c.name: c for c in schema.tables[0].columns}
    assert cols["name"].nullable is False
    assert cols["is_active"].nullable is False  # bool is value type, non-nullable in C#


def test_ef_parse_max_length():
    """[MaxLength] should set type_args['length']."""
    parser = EntityFrameworkParser()
    schema = parser.parse(SAMPLE_CS)
    cols = {c.name: c for c in schema.tables[0].columns}
    assert cols["name"].type_args.get("length") == 100


def test_ef_parse_types():
    """Parser should map C# types correctly."""
    parser = EntityFrameworkParser()
    schema = parser.parse(SAMPLE_CS)
    cols = {c.name: c for c in schema.tables[0].columns}
    assert cols["id"].type.value == "integer"
    assert cols["name"].type.value == "string"
    assert cols["is_active"].type.value == "boolean"
    assert cols["created_at"].type.value == "datetime"


def test_ef_parse_empty():
    """Empty input should produce empty schema."""
    parser = EntityFrameworkParser()
    schema = parser.parse("")
    assert len(schema.tables) == 0


def test_ef_parse_no_models():
    """Input without classes should produce empty schema."""
    parser = EntityFrameworkParser()
    schema = parser.parse("using System; // No classes here")
    assert len(schema.tables) == 0


def test_ef_parse_multiple_tables():
    """Parser should handle multiple entity classes."""
    cs = '\n'.join([
        '[Table("users")]',
        'public class User',
        '{',
        '    [Key]',
        '    public int Id { get; set; }',
        '    public string Name { get; set; }',
        '}',
        '',
        '[Table("posts")]',
        'public class Post',
        '{',
        '    [Key]',
        '    public int Id { get; set; }',
        '    [Required]',
        '    public string Title { get; set; }',
        '}',
    ])
    parser = EntityFrameworkParser()
    schema = parser.parse(cs)
    assert len(schema.tables) == 2
    names = {t.name for t in schema.tables}
    assert "users" in names
    assert "posts" in names


def test_ef_parse_nullable_type():
    """Nullable C# types (string?) should set nullable=True."""
    cs = """
public class Config
{
    [Key]
    public int Id { get; set; }
    public string? Description { get; set; }
    public int? Count { get; set; }
}
"""
    parser = EntityFrameworkParser()
    schema = parser.parse(cs)
    cols = {c.name: c for c in schema.tables[0].columns}
    assert cols["description"].nullable is True
    assert cols["count"].nullable is True
    assert cols["id"].nullable is False  # PK


# ── Generator Tests ──

def test_ef_generate_simple():
    """Generator should produce valid C# class structure."""
    from schemaforge.ir import Column, ColumnType, Schema, Table
    schema = Schema(tables=[
        Table(name="users", columns=[
            Column(name="id", type=ColumnType.INTEGER, primary_key=True),
            Column(name="name", type=ColumnType.STRING, nullable=False,
                   type_args={"length": 100}),
        ])
    ])
    gen = EntityFrameworkGenerator()
    output = gen.generate(schema)
    assert "using System" in output
    assert "public class Users" in output
    assert "[Key]" in output
    assert "public int Id" in output
    assert "public string Name" in output


def test_ef_generate_datetime():
    """Generator should map DATETIME to DateTime type."""
    from schemaforge.ir import Column, ColumnType, Schema, Table
    schema = Schema(tables=[
        Table(name="events", columns=[
            Column(name="id", type=ColumnType.INTEGER, primary_key=True),
            Column(name="ts", type=ColumnType.DATETIME),
        ])
    ])
    gen = EntityFrameworkGenerator()
    output = gen.generate(schema)
    assert "DateTime" in output


def test_ef_generate_decimal():
    """Generator should add [Column] for decimal precision/scale."""
    from schemaforge.ir import Column, ColumnType, Schema, Table
    schema = Schema(tables=[
        Table(name="products", columns=[
            Column(name="id", type=ColumnType.INTEGER, primary_key=True),
            Column(name="price", type=ColumnType.DECIMAL,
                   type_args={"precision": 12, "scale": 4}),
        ])
    ])
    gen = EntityFrameworkGenerator()
    output = gen.generate(schema)
    assert "decimal" in output
    assert "decimal(12,4)" in output


def test_ef_generate_empty():
    """Empty schema should produce just the boilerplate."""
    from schemaforge.ir import Schema
    gen = EntityFrameworkGenerator()
    output = gen.generate(Schema())
    assert "using System" in output
    assert "namespace SchemaForge.Models;" in output


# ── Roundtrip / Conversion Tests ──

def test_ef_to_sql_roundtrip():
    """C# entities should convert to valid SQL."""
    sql = convert_schema(SAMPLE_CS, "ef", "sql")
    assert "CREATE TABLE users" in sql
    assert "INTEGER" in sql
    assert "VARCHAR" in sql or "TEXT" in sql
    assert "PRIMARY KEY" in sql


def test_sql_to_ef_roundtrip():
    """SQL should convert to valid C# entities."""
    sql = """
CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    price DECIMAL(10,2)
);
"""
    cs = convert_schema(sql, "sql", "ef")
    assert "using System" in cs
    assert "public class Products" in cs
    assert "[Key]" in cs
    assert "[Required]" in cs
    assert "[MaxLength(200)]" in cs


def test_ef_prisma_roundtrip():
    """C# → Prisma should work."""
    prisma = convert_schema(SAMPLE_CS, "ef", "prisma")
    assert "model users" in prisma
    assert "@id" in prisma


def test_ef_django_roundtrip():
    """C# → Django should work."""
    django = convert_schema(SAMPLE_CS, "ef", "django")
    assert "models.Model" in django
    assert "CharField" in django or "IntegerField" in django


def test_ef_via_convert_api():
    """EF should be accessible via the convert_schema API."""
    result = convert_schema(SAMPLE_CS, "ef", "sql")
    assert isinstance(result, str)
    assert len(result) > 0
