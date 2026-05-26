"""Tests for SchemaForge — TypeORM, Django, and SQLAlchemy parsers/generators."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from schemaforge.convert import convert_schema
from schemaforge.generators.django_generator import DjangoGenerator
from schemaforge.generators.sqlalchemy_generator import SQLAlchemyGenerator
from schemaforge.generators.typeorm_generator import TypeORMGenerator
from schemaforge.parsers.django_parser import DjangoParser
from schemaforge.parsers.sqlalchemy_parser import SQLAlchemyParser
from schemaforge.parsers.typeorm_parser import TypeORMParser

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


# ── SQLAlchemy Model Samples ──

SIMPLE_SQLALCHEMY = """
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    bio = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
"""

SQLALCHEMY_WITH_DECIMAL = """
from sqlalchemy import Column, Integer, String, Numeric, Boolean, Text, Uuid, Float, JSON
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    title = Column(String(200))
    price = Column(Numeric(10, 2), default=0)
    rating = Column(Float, nullable=True)
    in_stock = Column(Boolean, default=True)
    description = Column(Text, nullable=True)
    sku = Column(Uuid, unique=True)
    metadata = Column(JSON, nullable=True)
"""

SQLALCHEMY_WITH_DATE_TIME = """
from sqlalchemy import Column, Integer, String, Date, DateTime, Time, Boolean
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True)
    event_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    published = Column(Boolean, default=False)
"""


# ═══════════════════════════════════════════════
# SQLAlchemy Parser Tests
# ═══════════════════════════════════════════════

def test_sqlalchemy_parse_simple():
    parser = SQLAlchemyParser()
    schema = parser.parse(SIMPLE_SQLALCHEMY)
    assert len(schema.tables) == 1
    assert schema.tables[0].name == "users"


def test_sqlalchemy_parse_columns():
    parser = SQLAlchemyParser()
    schema = parser.parse(SIMPLE_SQLALCHEMY)
    table = schema.tables[0]
    assert table.name == "users"
    cols = {c.name: c for c in table.columns}
    assert "id" in cols
    assert cols["id"].primary_key is True
    assert "name" in cols
    assert cols["name"].type.value == "string"
    assert cols["name"].type_args.get("length") == 100
    assert cols["name"].nullable is False
    assert "email" in cols
    assert cols["email"].unique is True
    assert cols["email"].nullable is False
    assert "bio" in cols
    assert cols["bio"].nullable is True
    assert "is_active" in cols
    assert cols["is_active"].type.value == "boolean"
    assert cols["is_active"].default is True
    assert "created_at" in cols
    assert cols["created_at"].type.value == "datetime"


def test_sqlalchemy_parse_empty():
    """Empty input produces empty schema."""
    parser = SQLAlchemyParser()
    schema = parser.parse("")
    assert len(schema.tables) == 0


def test_sqlalchemy_parse_no_models():
    """File with no model classes produces empty schema."""
    parser = SQLAlchemyParser()
    schema = parser.parse("from sqlalchemy import Column\n# just a comment\n")
    assert len(schema.tables) == 0


def test_sqlalchemy_generate_simple():
    """Generate SQLAlchemy from parsed schema."""
    parser = SQLAlchemyParser()
    gen = SQLAlchemyGenerator()
    schema = parser.parse(SIMPLE_SQLALCHEMY)
    output = gen.generate(schema)
    # Table name "users" gets PascalCased to "Users"
    assert "class Users(Base):" in output
    assert '__tablename__ = "users"' in output
    assert "Column(String(100)" in output
    assert "nullable=False" in output
    assert "unique=True" in output


def test_sqlalchemy_complex_types():
    """SQLAlchemy with all type variations."""
    parser = SQLAlchemyParser()
    schema = parser.parse(SQLALCHEMY_WITH_DECIMAL)
    assert len(schema.tables) == 1
    table = schema.tables[0]
    cols = {c.name: c for c in table.columns}
    assert cols["price"].type.value == "decimal"
    assert cols["rating"].type.value == "float"
    assert cols["in_stock"].type.value == "boolean"
    assert cols["description"].type.value == "text"
    assert cols["sku"].type.value == "uuid"
    assert cols["sku"].unique is True
    assert cols["metadata"].type.value == "json"


def test_sqlalchemy_generate_complex():
    """Generate SQLAlchemy from complex schema."""
    parser = SQLAlchemyParser()
    gen = SQLAlchemyGenerator()
    schema = parser.parse(SQLALCHEMY_WITH_DECIMAL)
    output = gen.generate(schema)
    # Table name "products" gets PascalCased to "Products"
    assert "class Products(Base):" in output
    assert '__tablename__ = "products"' in output
    assert "Numeric(10, 2)" in output
    assert "Uuid" in output or "UUID" in output or "uuid" in output


def test_sqlalchemy_date_time_types():
    """SQLAlchemy with date/time types."""
    parser = SQLAlchemyParser()
    schema = parser.parse(SQLALCHEMY_WITH_DATE_TIME)
    assert len(schema.tables) == 1
    table = schema.tables[0]
    cols = {c.name: c for c in table.columns}
    assert cols["event_date"].type.value == "date"
    assert cols["start_time"].type.value == "time"
    assert cols["created_at"].type.value == "datetime"
    assert cols["published"].type.value == "boolean"


# ═══════════════════════════════════════════════
# SQLAlchemy Roundtrip Tests
# ═══════════════════════════════════════════════

def test_sqlalchemy_to_sql_roundtrip():
    """Parse SQLAlchemy, convert to SQL, check elements survive."""
    sql = convert_schema(SIMPLE_SQLALCHEMY, "sqlalchemy", "sql")
    assert "CREATE TABLE" in sql
    assert "users" in sql.lower()
    assert "INTEGER" in sql or "INT" in sql
    assert "VARCHAR" in sql


def test_sqlalchemy_to_prisma_roundtrip():
    """Parse SQLAlchemy, convert to Prisma."""
    prisma = convert_schema(SIMPLE_SQLALCHEMY, "sqlalchemy", "prisma")
    assert "model" in prisma
    assert "User" in prisma or "users" in prisma.lower()


def test_sqlalchemy_to_django_roundtrip():
    """Cross-format: SQLAlchemy -> Django."""
    django = convert_schema(SIMPLE_SQLALCHEMY, "sqlalchemy", "django")
    assert "models.Model" in django
    assert "User" in django or "users" in django.lower()
    assert "CharField" in django


def test_sqlalchemy_to_typeorm_roundtrip():
    """Cross-format: SQLAlchemy -> TypeORM."""
    typeorm = convert_schema(SIMPLE_SQLALCHEMY, "sqlalchemy", "typeorm")
    assert "Entity" in typeorm
    assert "User" in typeorm or "users" in typeorm.lower()
    assert "Column" in typeorm


def test_sqlalchemy_to_drizzle_roundtrip():
    """Cross-format: SQLAlchemy -> Drizzle."""
    drizzle = convert_schema(SIMPLE_SQLALCHEMY, "sqlalchemy", "drizzle")
    assert "export" in drizzle or "pgTable" in drizzle or "sqliteTable" in drizzle or "defineTable" in drizzle
    assert "users" in drizzle.lower()


# ── Alembic Migration Generator Tests ──

SIMPLE_SQL_FOR_ALEMBIC = """
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TYPE user_role AS ENUM ('admin', 'editor', 'viewer');

CREATE TABLE posts (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    content TEXT,
    author_id INTEGER NOT NULL,
    status VARCHAR(20) DEFAULT 'draft',
    INDEX idx_posts_author (author_id)
);
"""


def test_alembic_generate_simple():
    """Alembic generator should produce valid migration script."""
    from schemaforge.generators.alembic_generator import AlembicGenerator
    from schemaforge.parsers.sql_parser import SQLParser

    parser = SQLParser()
    schema = parser.parse(SIMPLE_SQL_FOR_ALEMBIC)

    gen = AlembicGenerator()
    output = gen.generate(schema)

    # Core structure checks
    assert "\"\"\"" in output  # docstring
    assert "Revision ID:" in output
    assert "revision = 'initial'" in output
    assert "down_revision = None" in output
    assert "from alembic import op" in output
    assert "import sqlalchemy as sa" in output
    assert "def upgrade() -> None:" in output
    assert "def downgrade() -> None:" in output


def test_alembic_create_table():
    """Alembic should generate op.create_table calls."""
    from schemaforge.generators.alembic_generator import AlembicGenerator
    from schemaforge.parsers.sql_parser import SQLParser

    parser = SQLParser()
    schema = parser.parse(SIMPLE_SQL_FOR_ALEMBIC)

    gen = AlembicGenerator()
    output = gen.generate(schema)

    assert "op.create_table('users'" in output
    assert "op.create_table('posts'" in output
    assert "sa.Column('id'" in output
    assert "sa.Column('name'" in output
    assert "sa.Column('email'" in output


def test_alembic_create_index():
    """Alembic should generate op.create_index calls for table indexes."""
    from schemaforge.generators.alembic_generator import AlembicGenerator
    from schemaforge.parsers.sql_parser import SQLParser

    parser = SQLParser()
    schema = parser.parse(SIMPLE_SQL_FOR_ALEMBIC)

    gen = AlembicGenerator()
    output = gen.generate(schema)

    assert "op.create_index(" in output
    assert "idx_posts_author" in output


def test_alembic_downgrade():
    """Alembic downgrade should drop tables/indexes in reverse order."""
    from schemaforge.generators.alembic_generator import AlembicGenerator
    from schemaforge.parsers.sql_parser import SQLParser

    parser = SQLParser()
    schema = parser.parse(SIMPLE_SQL_FOR_ALEMBIC)

    gen = AlembicGenerator()
    output = gen.generate(schema)

    # Downgrade drops indexes first, then tables, then enums
    downgrade_idx = output.index("def downgrade() -> None:")
    downgrade_section = output[downgrade_idx:]

    assert "op.drop_index('idx_posts_author'" in downgrade_section
    assert "op.drop_table('posts'" in downgrade_section
    assert "op.drop_table('users'" in downgrade_section
    assert "DROP TYPE user_role" in downgrade_section


def test_alembic_enum_types():
    """Alembic should generate op.execute for enum types."""
    from schemaforge.generators.alembic_generator import AlembicGenerator
    from schemaforge.parsers.sql_parser import SQLParser

    parser = SQLParser()
    schema = parser.parse(SIMPLE_SQL_FOR_ALEMBIC)

    gen = AlembicGenerator()
    output = gen.generate(schema)

    assert "CREATE TYPE user_role AS ENUM" in output
    assert "'admin', 'editor', 'viewer'" in output


def test_alembic_default_values():
    """Alembic should handle server_default for boolean and fn defaults."""
    from schemaforge.generators.alembic_generator import AlembicGenerator
    from schemaforge.parsers.sql_parser import SQLParser

    parser = SQLParser()
    schema = parser.parse(SIMPLE_SQL_FOR_ALEMBIC)

    gen = AlembicGenerator()
    output = gen.generate(schema)

    assert "server_default=true" in output  # is_active DEFAULT TRUE
    assert "sa.func.now()" in output  # created_at DEFAULT CURRENT_TIMESTAMP
    assert "server_default='draft'" in output  # status DEFAULT 'draft'


def test_alembic_primary_key():
    """Alembic should mark primary_key=True on PK columns."""
    from schemaforge.generators.alembic_generator import AlembicGenerator
    from schemaforge.parsers.sql_parser import SQLParser

    parser = SQLParser()
    schema = parser.parse(SIMPLE_SQL_FOR_ALEMBIC)

    gen = AlembicGenerator()
    output = gen.generate(schema)

    assert "primary_key=True" in output


def test_alembic_not_null():
    """Alembic should set nullable=False for NOT NULL columns."""
    from schemaforge.generators.alembic_generator import AlembicGenerator
    from schemaforge.parsers.sql_parser import SQLParser

    parser = SQLParser()
    schema = parser.parse(SIMPLE_SQL_FOR_ALEMBIC)

    gen = AlembicGenerator()
    output = gen.generate(schema)

    assert "nullable=False" in output


def test_alembic_custom_revision():
    """Alembic generator should accept custom revision_id and down_revision."""
    from schemaforge.generators.alembic_generator import AlembicGenerator
    from schemaforge.ir import Column, ColumnType, Schema, Table

    schema = Schema(tables=[
        Table(name="items", columns=[
            Column(name="id", type=ColumnType.INTEGER, primary_key=True),
        ])
    ])

    gen = AlembicGenerator()
    output = gen.generate(
        schema,
        revision_id="abc123def456",
        down_revision="prev_rev",
        message="Add items table",
    )

    assert "Add items table" in output
    assert "revision = 'abc123def456'" in output
    assert "down_revision = 'prev_rev'" in output


def test_alembic_empty_schema():
    """Alembic should handle empty schema gracefully."""
    from schemaforge.generators.alembic_generator import AlembicGenerator
    from schemaforge.ir import Schema

    schema = Schema()
    gen = AlembicGenerator()
    output = gen.generate(schema)

    assert "def upgrade() -> None:" in output
    assert "    pass" in output
    assert "def downgrade() -> None:" in output
    assert "    pass" in output


def test_alembic_via_convert_api():
    """Alembic should be accessible via the convert_schema API (generator-only)."""
    sql = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);
"""
    output = convert_schema(sql, "sql", "alembic")
    assert "def upgrade() -> None:" in output
    assert "op.create_table('users'" in output
    with pytest.raises(NotImplementedError):
        convert_schema(output, "alembic", "sql")
