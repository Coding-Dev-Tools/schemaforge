"""Roundtrip and edge-case tests for SchemaForge — SQL DDL ↔ Prisma."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from schemaforge.convert import convert_schema
from schemaforge.parsers.sql_parser import SQLParser
from schemaforge.parsers.prisma_parser import PrismaParser
from schemaforge.generators.sql_generator import SQLGenerator
from schemaforge.generators.prisma_generator import PrismaGenerator


# ── Complex SQL Schemas ──

COMPLEX_SQL = """
CREATE TYPE user_role AS ENUM ('admin', 'editor', 'viewer');

CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(500),
    role user_role NOT NULL DEFAULT 'viewer',
    bio TEXT,
    login_count INTEGER DEFAULT 0,
    account_balance DECIMAL(12,4) DEFAULT 0.0000,
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    settings JSONB DEFAULT '{}',
    avatar_url VARCHAR(500)
);

CREATE TABLE posts (
    id SERIAL PRIMARY KEY,
    author_id INTEGER NOT NULL,
    title VARCHAR(200) NOT NULL,
    slug VARCHAR(200) NOT NULL,
    content TEXT,
    status VARCHAR(20) DEFAULT 'draft',
    published_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_posts_author (author_id),
    INDEX idx_posts_slug (slug),
    UNIQUE INDEX idx_posts_slug_unique (slug)
);

CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    parent_id INTEGER,
    sort_order INTEGER DEFAULT 0
);

CREATE TABLE tags (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE
);
"""


# ── Roundtrip Fidelity Tests ──

def test_sql_to_prisma_to_sql_roundtrip():
    """Full roundtrip: SQL → Prisma → SQL preserves table structure.
    
    Note: Some type fidelity is lost at v0.1.0 (e.g. TEXT → String → VARCHAR,
    BIGSERIAL → INTEGER, DECIMAL precision/scale) — these are acceptable
    limitations for the initial release.
    """
    sql2 = convert_schema(COMPLEX_SQL, "sql", "prisma")
    sql3 = convert_schema(sql2, "prisma", "sql")

    # Key tables should survive
    assert "CREATE TABLE users" in sql3
    assert "CREATE TABLE posts" in sql3
    assert "CREATE TABLE categories" in sql3
    assert "CREATE TABLE tags" in sql3

    # Core types should be preserved (some precision loss expected)
    assert "INTEGER" in sql3  # BIGSERIAL → INTEGER is acceptable
    assert "VARCHAR" in sql3
    assert "BOOLEAN" in sql3
    assert "TIMESTAMP" in sql3

    # Constraints should survive
    assert "NOT NULL" in sql3
    assert "PRIMARY KEY" in sql3

    # Unique constraints should survive
    assert "UNIQUE" in sql3

    # Enum should survive
    assert "user_role" in sql3


def test_prisma_to_sql_to_prisma_roundtrip():
    """Full roundtrip: Prisma → SQL → Prisma preserves model structure."""
    PRISMA_COMPLEX = """
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

enum UserRole {
  ADMIN
  EDITOR
  VIEWER
}

model User {
  id        Int      @id @default(autoincrement())
  email     String   @unique
  name      String?
  role      UserRole @default(VIEWER)
  posts     Post[]
}

model Post {
  id        Int      @id @default(autoincrement())
  title     String
  content   String?
  published Boolean  @default(false)
  author    User     @relation(fields: [authorId], references: [id])
  authorId  Int
}
"""
    sql = convert_schema(PRISMA_COMPLEX, "prisma", "sql")
    prisma2 = convert_schema(sql, "sql", "prisma")

    # Key models should survive
    assert "model User" in prisma2
    assert "model Post" in prisma2

    # ID fields should survive
    assert "@id" in prisma2
    assert "@default(autoincrement())" in prisma2

    # Types should survive
    assert "String" in prisma2
    assert "Int" in prisma2
    assert "Boolean" in prisma2 or "Boolean" in prisma2


# ── Edge Case Tests ──

def test_empty_sql():
    """Empty input should produce empty schema."""
    parser = SQLParser()
    schema = parser.parse("")
    assert len(schema.tables) == 0
    assert len(schema.enums) == 0


def test_empty_prisma():
    """Empty Prisma input should parse without error."""
    parser = PrismaParser()
    schema = parser.parse("")
    assert len(schema.tables) == 0


def test_sql_with_only_comments():
    """SQL with only comments should produce empty schema."""
    parser = SQLParser()
    schema = parser.parse("-- This is a comment\n# Another comment\n")
    assert len(schema.tables) == 0


def test_sql_with_trailing_semicolons():
    """Multiple trailing semicolons should not cause issues."""
    parser = SQLParser()
    schema = parser.parse("""
        CREATE TABLE test (id INTEGER PRIMARY KEY);
        ;
        ;
    """)
    assert len(schema.tables) == 1


def test_sql_if_not_exists():
    """IF NOT EXISTS should be handled."""
    parser = SQLParser()
    schema = parser.parse("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY
        );
    """)
    assert len(schema.tables) == 1
    assert schema.tables[0].name == "users"


def test_sql_uuid_type():
    """UUID type should map correctly."""
    parser = SQLParser()
    schema = parser.parse("""
        CREATE TABLE items (
            id UUID PRIMARY KEY,
            data JSON
        );
    """)
    assert len(schema.tables) == 1
    cols = {c.name: c for c in schema.tables[0].columns}
    assert cols["id"].type.value == "uuid"
    assert cols["data"].type.value == "json"


def test_sql_decimal_precision():
    """DECIMAL with precision and scale should be parsed."""
    parser = SQLParser()
    schema = parser.parse("""
        CREATE TABLE products (
            price DECIMAL(10,4) NOT NULL,
            tax_rate NUMERIC(5,3)
        );
    """)
    assert len(schema.tables) == 1
    cols = {c.name: c for c in schema.tables[0].columns}
    assert cols["price"].type_args.get("precision") == 10
    assert cols["price"].type_args.get("scale") == 4
    assert cols["tax_rate"].type_args.get("precision") == 5
    assert cols["tax_rate"].type_args.get("scale") == 3


def test_sql_multiple_enums():
    """Multiple enum types should be parsed."""
    parser = SQLParser()
    schema = parser.parse("""
        CREATE TYPE color AS ENUM ('red', 'green', 'blue');
        CREATE TYPE size AS ENUM ('small', 'medium', 'large');
    """)
    assert len(schema.enums) == 2
    enum_names = {e.name for e in schema.enums}
    assert "color" in enum_names
    assert "size" in enum_names


def test_prisma_complex_types():
    """Prisma with advanced types should parse."""
    parser = PrismaParser()
    schema = parser.parse("""
        model Product {
            id          Int      @id @default(autoincrement())
            name        String
            price       Decimal  @db.Decimal(10, 2)
            inStock     Boolean  @default(true)
            tags        String[]
            metadata    Json?
        }
    """)
    assert len(schema.tables) == 1
    table = schema.tables[0]
    col_names = {c.name for c in table.columns}
    assert "id" in col_names
    assert "name" in col_names
    assert "price" in col_names
    assert "inStock" in col_names


# ── Generator Edge Cases ──

def test_generate_without_enum():
    """SQL generation without enums should not include CREATE TYPE."""
    from schemaforge.ir import Schema, Table, Column, ColumnType

    schema = Schema(tables=[
        Table(name="items", columns=[
            Column(name="id", type=ColumnType.INTEGER, primary_key=True),
            Column(name="name", type=ColumnType.STRING, nullable=False),
        ])
    ])
    gen = SQLGenerator()
    output = gen.generate(schema)
    assert "CREATE TYPE" not in output
    assert "CREATE TABLE items" in output


def test_generate_with_schema_name():
    """Table with schema prefix should be preserved."""
    parser = SQLParser()
    schema = parser.parse("""
        CREATE TABLE public.users (
            id INTEGER PRIMARY KEY
        );
    """)
    assert len(schema.tables) == 1
    assert "public" in schema.tables[0].name


def test_prisma_generate_complex():
    """Prisma generation should handle all column types."""
    from schemaforge.ir import Schema, Table, Column, ColumnType, Index

    schema = Schema(tables=[
        Table(name="Item", columns=[
            Column(name="id", type=ColumnType.INTEGER, primary_key=True),
            Column(name="name", type=ColumnType.STRING, type_args={"length": 100}),
            Column(name="price", type=ColumnType.DECIMAL, type_args={"precision": 12, "scale": 4}),
            Column(name="active", type=ColumnType.BOOLEAN, default=True),
            Column(name="data", type=ColumnType.JSON, nullable=True),
            Column(name="token", type=ColumnType.UUID, unique=True),
        ], indexes=[
            Index(name="idx_name", columns=["name"]),
        ])
    ])
    gen = PrismaGenerator()
    output = gen.generate(schema)
    assert "model Item" in output
    assert "@id" in output
    assert "@default(autoincrement())" in output
    assert "@unique" in output
    assert "@default(true)" in output
    assert "@@index" in output or "@@index" in output


# ── Conversion Edge Cases ──

def test_convert_same_format_returns_original():
    """Converting a format to itself should return the original text."""
    result = convert_schema("hello world", "sql", "sql")
    assert result == "hello world"


def test_convert_unsupported_format():
    """Unsupported format should raise ValueError."""
    import pytest
    with pytest.raises(ValueError, match="Unsupported source format"):
        convert_schema("data", "unsupported", "sql")
    with pytest.raises(ValueError, match="Unsupported target format"):
        convert_schema("data", "sql", "unsupported")


def test_sql_default_values():
    """SQL default values should be parsed correctly."""
    parser = SQLParser()
    schema = parser.parse("""
        CREATE TABLE config (
            id INTEGER PRIMARY KEY,
            name VARCHAR(100) DEFAULT 'untitled',
            count INTEGER DEFAULT 42,
            ratio FLOAT DEFAULT 3.14,
            enabled BOOLEAN DEFAULT FALSE,
            description TEXT DEFAULT NULL
        );
    """)
    assert len(schema.tables) == 1
    cols = {c.name: c for c in schema.tables[0].columns}
    assert cols["name"].default == "untitled"
    assert cols["count"].default == 42
    assert cols["ratio"].default == 3.14
    assert cols["enabled"].default is False
    assert cols["description"].default is None
    assert cols["description"].nullable is True


# ── SQL Parser Edge Case Tests ──

def test_sql_temporary_table():
    """CREATE TEMPORARY TABLE should be parsed."""
    parser = SQLParser()
    schema = parser.parse("""
        CREATE TEMPORARY TABLE temp_users (
            id INTEGER PRIMARY KEY,
            name VARCHAR(100)
        );
    """)
    assert len(schema.tables) == 1
    assert schema.tables[0].name == "temp_users"


def test_sql_create_or_replace_table():
    """CREATE OR REPLACE TABLE should be parsed."""
    parser = SQLParser()
    schema = parser.parse("""
        CREATE OR REPLACE TABLE users (
            id INTEGER PRIMARY KEY
        );
    """)
    assert len(schema.tables) == 1
    assert schema.tables[0].name == "users"


def test_sql_backtick_quoted_table():
    """Backtick-quoted table names should be parsed."""
    parser = SQLParser()
    schema = parser.parse("""
        CREATE TABLE `users` (
            `id` INTEGER PRIMARY KEY,
            `name` VARCHAR(100)
        );
    """)
    assert len(schema.tables) == 1
    assert schema.tables[0].name == "users"


def test_sql_backtick_quoted_schema_table():
    """Backtick-quoted schema.table should be parsed."""
    parser = SQLParser()
    schema = parser.parse("""
        CREATE TABLE `public`.`users` (
            id INTEGER PRIMARY KEY
        );
    """)
    assert len(schema.tables) == 1
    assert "public" in schema.tables[0].name


def test_sql_double_quoted_table():
    """Double-quoted table names should be parsed."""
    parser = SQLParser()
    schema = parser.parse('''
        CREATE TABLE "users" (
            "id" INTEGER PRIMARY KEY
        );
    ''')
    assert len(schema.tables) == 1
    assert schema.tables[0].name == "users"


def test_sql_current_timestamp_default():
    """DEFAULT CURRENT_TIMESTAMP should be stored as fn:CURRENT_TIMESTAMP."""
    parser = SQLParser()
    schema = parser.parse("""
        CREATE TABLE events (
            id INTEGER PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    assert len(schema.tables) == 1
    cols = {c.name: c for c in schema.tables[0].columns}
    assert cols["created_at"].default == "fn:CURRENT_TIMESTAMP"
    assert cols["updated_at"].default == "fn:CURRENT_TIMESTAMP"


def test_sql_now_default():
    """DEFAULT NOW() should be stored as fn:NOW()."""
    parser = SQLParser()
    schema = parser.parse("""
        CREATE TABLE events (
            id INTEGER PRIMARY KEY,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    assert len(schema.tables) == 1
    cols = {c.name: c for c in schema.tables[0].columns}
    assert cols["created_at"].default == "fn:NOW()"


def test_sql_gen_random_uuid_default():
    """DEFAULT gen_random_uuid() should be stored as fn:gen_random_uuid()."""
    parser = SQLParser()
    schema = parser.parse("""
        CREATE TABLE items (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            name VARCHAR(100)
        );
    """)
    assert len(schema.tables) == 1
    cols = {c.name: c for c in schema.tables[0].columns}
    assert cols["id"].default == "fn:gen_random_uuid()"


def test_sql_current_date_default():
    """DEFAULT CURRENT_DATE should be stored as fn:CURRENT_DATE."""
    parser = SQLParser()
    schema = parser.parse("""
        CREATE TABLE logs (
            id INTEGER PRIMARY KEY,
            log_date DATE DEFAULT CURRENT_DATE
        );
    """)
    assert len(schema.tables) == 1
    cols = {c.name: c for c in schema.tables[0].columns}
    assert cols["log_date"].default == "fn:CURRENT_DATE"


def test_sql_fn_default_generates_without_quotes():
    """fn: prefixed defaults should generate without quotes in SQL DDL."""
    from schemaforge.ir import Schema, Table, Column, ColumnType
    schema = Schema(tables=[
        Table(name="events", columns=[
            Column(name="id", type=ColumnType.INTEGER, primary_key=True),
            Column(name="created_at", type=ColumnType.DATETIME, default="fn:CURRENT_TIMESTAMP"),
            Column(name="updated_at", type=ColumnType.DATETIME, default="fn:NOW()"),
            Column(name="token", type=ColumnType.UUID, default="fn:gen_random_uuid()"),
        ])
    ])
    gen = SQLGenerator()
    output = gen.generate(schema)
    assert "DEFAULT CURRENT_TIMESTAMP" in output
    assert "DEFAULT NOW()" in output or "DEFAULT now()" in output
    assert "DEFAULT gen_random_uuid()" in output
    # Should NOT be quoted
    assert "DEFAULT 'CURRENT_TIMESTAMP'" not in output
    assert "DEFAULT 'NOW()'" not in output


def test_fn_default_roundtrip_sql_to_prisma_to_sql():
    """SQL with function defaults should survive Prisma roundtrip."""
    sql = """
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""
    prisma = convert_schema(sql, "sql", "prisma")
    # Prisma should have @default(now()) for CURRENT_TIMESTAMP
    assert "@default(now())" in prisma
    
    sql2 = convert_schema(prisma, "prisma", "sql")
    assert "CREATE TABLE events" in sql2
    assert "DEFAULT" in sql2


def test_prisma_now_default_roundtrip():
    """Prisma @default(now()) should roundtrip through SQL."""
    prisma = """generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model Event {
  id        Int      @id @default(autoincrement())
  name      String
  createdAt DateTime @default(now())
}
"""
    sql = convert_schema(prisma, "prisma", "sql")
    assert "CREATE TABLE" in sql
    assert "DEFAULT" in sql
    
    prisma2 = convert_schema(sql, "sql", "prisma")
    assert "model Event" in prisma2
    assert "@id" in prisma2
