"""Tests for SchemaForge — TypeORM and Django parsers/generators."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from schemaforge.convert import convert_schema
from schemaforge.parsers.typeorm_parser import TypeORMParser
from schemaforge.parsers.django_parser import DjangoParser
from schemaforge.generators.typeorm_generator import TypeORMGenerator
from schemaforge.generators.django_generator import DjangoGenerator


# ── TypeORM Entity Samples ──

SIMPLE_TYPEORM = """
import { Entity, PrimaryGeneratedColumn, Column } from "typeorm";

@Entity()
export class User {
    @PrimaryGeneratedColumn()
    id: number;

    @Column({ type: "varchar", length: 100 })
    name: string;

    @Column({ type: "varchar", unique: true })
    email: string;

    @Column({ type: "integer", nullable: true })
    age: number;

    @Column({ type: "timestamp", default: () => "CURRENT_TIMESTAMP" })
    createdAt: Date;
}
"""

TYPEORM_WITH_ENUM_TYPES = """
import { Entity, PrimaryGeneratedColumn, Column } from "typeorm";

@Entity()
export class Product {
    @PrimaryGeneratedColumn()
    id: number;

    @Column({ type: "varchar", length: 200 })
    title: string;

    @Column({ type: "decimal", precision: 10, scale: 2, default: 0 })
    price: number;

    @Column({ type: "boolean", default: true })
    inStock: boolean;

    @Column({ type: "text", nullable: true })
    description: string;

    @Column({ type: "json", nullable: true })
    metadata: any;

    @Column({ type: "uuid" })
    sku: string;
}
"""


# ── Django Model Samples ──

SIMPLE_DJANGO = """
from django.db import models

class User(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    bio = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
"""

DJANGO_WITH_DECIMAL = """
from django.db import models

class Product(models.Model):
    title = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    in_stock = models.BooleanField(default=True)
    description = models.TextField(null=True, blank=True)
    sku = models.UUIDField(unique=True)
"""


# ═══════════════════════════════════════════════
# TypeORM Parser Tests
# ═══════════════════════════════════════════════

def test_typeorm_parse_simple():
    parser = TypeORMParser()
    schema = parser.parse(SIMPLE_TYPEORM)
    assert len(schema.tables) == 1
    assert schema.tables[0].name == "User"


def test_typeorm_parse_columns():
    parser = TypeORMParser()
    schema = parser.parse(SIMPLE_TYPEORM)
    table = schema.tables[0]
    cols = {c.name: c for c in table.columns}
    assert "id" in cols
    assert cols["id"].primary_key is True
    assert "name" in cols
    assert cols["name"].type.value == "string"
    assert cols["name"].type_args.get("length") == 100
    assert "email" in cols
    assert cols["email"].unique is True
    assert "age" in cols
    assert cols["age"].nullable is True


def test_typeorm_parse_empty():
    """Empty input produces empty schema."""
    parser = TypeORMParser()
    schema = parser.parse("")
    assert len(schema.tables) == 0


def test_typeorm_generate():
    """Generate TypeORM from parsed schema."""
    parser = TypeORMParser()
    gen = TypeORMGenerator()
    schema = parser.parse(SIMPLE_TYPEORM)
    output = gen.generate(schema)
    assert "export class User" in output
    assert "@PrimaryGeneratedColumn()" in output
    assert "@Column" in output


def test_typeorm_complex_types():
    """TypeORM with all type variations."""
    parser = TypeORMParser()
    schema = parser.parse(TYPEORM_WITH_ENUM_TYPES)
    assert len(schema.tables) == 1
    table = schema.tables[0]
    cols = {c.name: c for c in table.columns}
    assert cols["price"].type.value == "decimal"
    assert cols["inStock"].type.value == "boolean"
    assert cols["metadata"].type.value == "json"
    assert cols["sku"].type.value == "uuid"


def test_typeorm_generate_complex():
    """Generate TypeORM from complex schema."""
    parser = TypeORMParser()
    gen = TypeORMGenerator()
    schema = parser.parse(TYPEORM_WITH_ENUM_TYPES)
    output = gen.generate(schema)
    assert "Product" in output
    assert "precision" in output or "decimal" in output


# ═══════════════════════════════════════════════
# Django Parser Tests
# ═══════════════════════════════════════════════

def test_django_parse_simple():
    parser = DjangoParser()
    schema = parser.parse(SIMPLE_DJANGO)
    assert len(schema.tables) == 1
    assert schema.tables[0].name == "User"


def test_django_parse_columns():
    parser = DjangoParser()
    schema = parser.parse(SIMPLE_DJANGO)
    table = schema.tables[0]
    cols = {c.name: c for c in table.columns}
    assert "name" in cols
    assert cols["name"].type.value == "string"
    assert cols["name"].type_args.get("length") == 100
    assert "email" in cols
    assert cols["email"].unique is True
    assert "bio" in cols
    assert cols["bio"].nullable is True
    assert "is_active" in cols
    assert cols["is_active"].type.value == "boolean"
    assert cols["is_active"].default is True
    assert "created_at" in cols
    assert cols["created_at"].type.value == "datetime"


def test_django_parse_empty():
    """Empty input produces empty schema."""
    parser = DjangoParser()
    schema = parser.parse("")
    assert len(schema.tables) == 0


def test_django_parse_no_models():
    """File with no model classes produces empty schema."""
    parser = DjangoParser()
    schema = parser.parse("from django.db import models\n# just a comment\n")
    assert len(schema.tables) == 0


def test_django_generate_simple():
    """Generate Django from parsed schema."""
    parser = DjangoParser()
    gen = DjangoGenerator()
    schema = parser.parse(SIMPLE_DJANGO)
    output = gen.generate(schema)
    assert "class User(models.Model):" in output
    assert "models.CharField" in output or "models.CharField" in output


def test_django_complex_types():
    """Django with decimal and other types."""
    parser = DjangoParser()
    schema = parser.parse(DJANGO_WITH_DECIMAL)
    assert len(schema.tables) == 1
    cols = {c.name: c for c in schema.tables[0].columns}
    assert cols["price"].type.value == "decimal"


def test_django_generate_complex():
    """Generate Django from complex schema."""
    parser = DjangoParser()
    gen = DjangoGenerator()
    schema = parser.parse(DJANGO_WITH_DECIMAL)
    output = gen.generate(schema)
    assert "class Product(models.Model):" in output
    assert "DecimalField" in output


# ═══════════════════════════════════════════════
# Roundtrip Tests
# ═══════════════════════════════════════════════

def test_typeorm_to_sql_roundtrip():
    """Parse TypeORM, convert to SQL, check elements survive."""
    sql = convert_schema(SIMPLE_TYPEORM, "typeorm", "sql")
    assert "CREATE TABLE" in sql
    assert "User" in sql or "user" in sql
    assert "INTEGER" in sql or "INT" in sql
    assert "VARCHAR" in sql


def test_typeorm_to_prisma_roundtrip():
    """Parse TypeORM, convert to Prisma."""
    prisma = convert_schema(SIMPLE_TYPEORM, "typeorm", "prisma")
    assert "model" in prisma
    assert "User" in prisma or "user" in prisma


def test_django_to_sql_roundtrip():
    """Parse Django, convert to SQL, check elements survive."""
    sql = convert_schema(SIMPLE_DJANGO, "django", "sql")
    assert "CREATE TABLE" in sql
    assert "User" in sql or "user" in sql


def test_django_to_prisma_roundtrip():
    """Parse Django, convert to Prisma."""
    prisma = convert_schema(SIMPLE_DJANGO, "django", "prisma")
    assert "model" in prisma
    assert "User" in prisma or "user" in prisma


def test_typeorm_to_django_roundtrip():
    """Cross-format: TypeORM -> Django."""
    django = convert_schema(SIMPLE_TYPEORM, "typeorm", "django")
    assert "models.Model" in django
    assert "User" in django or "user" in django
    assert "CharField" in django
    assert "BooleanField" in django or "IntegerField" in django or "TextField" in django


def test_django_to_typeorm_roundtrip():
    """Cross-format: Django -> TypeORM."""
    typeorm = convert_schema(SIMPLE_DJANGO, "django", "typeorm")
    assert "Entity" in typeorm
    assert "User" in typeorm or "user" in typeorm
    assert "Column" in typeorm


def test_sql_to_typeorm_roundtrip():
    """Convert SQL -> TypeORM, verify structure survives."""
    SQL_SAMPLE = """
    CREATE TABLE items (
        id INTEGER PRIMARY KEY NOT NULL,
        name VARCHAR(100) NOT NULL,
        price DECIMAL(10,2) DEFAULT 0.00,
        active BOOLEAN DEFAULT TRUE
    );
    """
    typeorm = convert_schema(SQL_SAMPLE, "sql", "typeorm")
    assert "Entity" in typeorm
    assert "items" in typeorm.lower() or "Items" in typeorm
    assert "Column" in typeorm


def test_sql_to_django_roundtrip():
    """Convert SQL -> Django, verify structure survives."""
    SQL_SAMPLE = """
    CREATE TABLE articles (
        id INTEGER PRIMARY KEY NOT NULL,
        title VARCHAR(200) NOT NULL,
        body TEXT,
        published BOOLEAN DEFAULT FALSE
    );
    """
    django = convert_schema(SQL_SAMPLE, "sql", "django")
    assert "models.Model" in django
    assert "articles" in django.lower() or "Articles" in django
