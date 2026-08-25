"""Tests for SchemaForge — SQL DDL ↔ Prisma roundtrip."""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from schemaforge.convert import convert_schema
from schemaforge.generators.prisma_generator import PrismaGenerator
from schemaforge.generators.sql_generator import SQLGenerator
from schemaforge.parsers.prisma_parser import PrismaParser
from schemaforge.parsers.sql_parser import SQLParser

# ── SQL DDL Parser Tests ──

SIMPLE_SQL = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY NOT NULL,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE,
    age INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def test_sql_parse_simple():
    parser = SQLParser()
    schema = parser.parse(SIMPLE_SQL)
    assert len(schema.tables) == 1
    table = schema.tables[0]
    assert table.name == "users"
    assert len(table.columns) == 5


def test_sql_parse_column_types():
    parser = SQLParser()
    schema = parser.parse(SIMPLE_SQL)
    table = schema.tables[0]
    col_map = {c.name: c for c in table.columns}

    assert col_map["id"].primary_key is True
    assert col_map["id"].nullable is False
    assert col_map["name"].nullable is False
    assert col_map["email"].unique is True
    assert col_map["age"].nullable is True


SQL_WITH_ENUM = """
CREATE TYPE mood AS ENUM ('happy', 'sad', 'neutral');

CREATE TABLE posts (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    status VARCHAR(20) DEFAULT 'draft'
);
"""


def test_sql_parse_enum():
    parser = SQLParser()
    schema = parser.parse(SQL_WITH_ENUM)
    assert len(schema.enums) == 1
    assert schema.enums[0].name == "mood"
    assert "happy" in schema.enums[0].values


def test_sql_generate():
    parser = SQLParser()
    gen = SQLGenerator()
    schema = parser.parse(SIMPLE_SQL)
    output = gen.generate(schema)
    assert "CREATE TABLE users" in output
    assert "id" in output
    assert "INTEGER" in output


# ── Prisma Parser Tests ──

PRISMA_SAMPLE = """
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model User {
  id        Int      @id @default(autoincrement())
  email     String   @unique
  name      String?
  posts     Post[]
}

model Post {
  id        Int      @id @default(autoincrement())
  title     String
  author    User     @relation(fields: [authorId], references: [id])
  authorId  Int
}
"""


def test_prisma_parse():
    parser = PrismaParser()
    schema = parser.parse(PRISMA_SAMPLE)
    assert len(schema.tables) == 2
    names = [t.name for t in schema.tables]
    assert "User" in names
    assert "Post" in names


def test_prisma_parse_fields():
    parser = PrismaParser()
    schema = parser.parse(PRISMA_SAMPLE)
    user = [t for t in schema.tables if t.name == "User"][0]
    assert len(user.columns) >= 3
    id_col = [c for c in user.columns if c.name == "id"][0]
    assert id_col.primary_key is True


def test_prisma_generate():
    parser = PrismaParser()
    gen = PrismaGenerator()
    schema = parser.parse(PRISMA_SAMPLE)
    output = gen.generate(schema)
    assert "model User" in output
    assert "@id" in output


# ── Roundtrip Tests ──


def test_sql_to_prisma_roundtrip():
    """Parse SQL, convert to Prisma, check key elements survive."""
    prisma = convert_schema(SIMPLE_SQL, "sql", "prisma")
    assert "model users" in prisma or "model users" in prisma
    assert "@id" in prisma
    assert "@unique" in prisma  # email is unique


def test_prisma_to_sql_roundtrip():
    """Parse Prisma, convert to SQL, check key elements survive."""
    sql = convert_schema(PRISMA_SAMPLE, "prisma", "sql")
    assert "CREATE TABLE" in sql
    assert "INTEGER" in sql
