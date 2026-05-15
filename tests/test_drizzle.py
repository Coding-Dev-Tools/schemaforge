"""Tests for Drizzle ORM parser and generator."""
from __future__ import annotations

from schemaforge.parsers.drizzle_parser import DrizzleParser
from schemaforge.generators.drizzle_generator import DrizzleGenerator
from schemaforge.convert import convert_schema
from schemaforge.ir import ColumnType


class TestDrizzleParser:
    def test_parse_simple_pg_table(self):
        text = """import { pgTable, serial, varchar, text, timestamp } from 'drizzle-orm/pg-core';

export const users = pgTable('users', {
  id: serial('id').primaryKey(),
  name: varchar('name', { length: 255 }).notNull(),
  email: text('email').notNull().unique(),
  createdAt: timestamp('created_at').defaultNow(),
});"""
        parser = DrizzleParser()
        schema = parser.parse(text)

        assert len(schema.tables) == 1
        table = schema.tables[0]
        assert table.name == "users"
        assert len(table.columns) == 4

        # Check id column
        id_col = table.columns[0]
        assert id_col.name == "id"
        assert id_col.type == ColumnType.INTEGER
        assert id_col.primary_key is True

        # Check name column
        name_col = table.columns[1]
        assert name_col.name == "name"
        assert name_col.type == ColumnType.STRING
        assert name_col.nullable is False
        assert name_col.type_args.get("length") == 255

        # Check email column
        email_col = table.columns[2]
        assert email_col.name == "email"
        assert email_col.type == ColumnType.TEXT
        assert email_col.unique is True

        # Check createdAt column
        created_col = table.columns[3]
        assert created_col.name == "createdAt"
        assert created_col.type == ColumnType.DATETIME
        assert created_col.default == "now()"

    def test_parse_multiple_tables(self):
        text = """import { pgTable, serial, varchar, integer } from 'drizzle-orm/pg-core';

export const users = pgTable('users', {
  id: serial('id').primaryKey(),
  name: varchar('name').notNull(),
});

export const posts = pgTable('posts', {
  id: serial('id').primaryKey(),
  title: varchar('title').notNull(),
  userId: integer('user_id').notNull(),
});"""
        parser = DrizzleParser()
        schema = parser.parse(text)

        assert len(schema.tables) == 2
        assert schema.tables[0].name == "users"
        assert schema.tables[1].name == "posts"
        assert len(schema.tables[1].columns) == 3

    def test_parse_mysql_table(self):
        text = """import { mysqlTable, int, varchar } from 'drizzle-orm/mysql-core';

export const products = mysqlTable('products', {
  id: int('id').primaryKey(),
  name: varchar('name', { length: 100 }).notNull(),
});"""
        parser = DrizzleParser()
        schema = parser.parse(text)

        assert len(schema.tables) == 1
        assert schema.tables[0].name == "products"
        assert schema.tables[0].columns[0].type == ColumnType.INTEGER

    def test_parse_enum(self):
        text = """import { pgTable, pgEnum, serial, varchar } from 'drizzle-orm/pg-core';

export const role = pgEnum('role', ['admin', 'user', 'moderator']);

export const users = pgTable('users', {
  id: serial('id').primaryKey(),
  name: varchar('name').notNull(),
});"""
        parser = DrizzleParser()
        schema = parser.parse(text)

        assert len(schema.enums) == 1
        assert schema.enums[0].name == "role"
        assert schema.enums[0].values == ["admin", "user", "moderator"]

    def test_parse_default_values(self):
        text = """import { pgTable, integer, boolean, varchar } from 'drizzle-orm/pg-core';

export const settings = pgTable('settings', {
  id: integer('id').primaryKey(),
  active: boolean('active').default(true),
  count: integer('count').default(0),
  label: varchar('label').default('untitled'),
});"""
        parser = DrizzleParser()
        schema = parser.parse(text)

        table = schema.tables[0]
        assert table.columns[1].default is True
        assert table.columns[2].default == 0
        assert table.columns[3].default == "untitled"

    def test_parse_empty_text(self):
        parser = DrizzleParser()
        schema = parser.parse("")
        assert len(schema.tables) == 0


class TestDrizzleGenerator:
    def test_generate_simple_table(self):
        from schemaforge.ir import Schema, Table, Column, ColumnType

        schema = Schema()
        table = Table(name="users")
        table.columns.append(Column(name="id", type=ColumnType.INTEGER, primary_key=True))
        table.columns.append(Column(name="name", type=ColumnType.STRING, nullable=False, type_args={"length": 255}))
        table.columns.append(Column(name="email", type=ColumnType.TEXT, nullable=False, unique=True))
        schema.tables.append(table)

        gen = DrizzleGenerator(dialect="pg")
        result = gen.generate(schema)

        assert "pgTable" in result
        assert "'users'" in result
        assert "serial('id')" in result
        assert "primaryKey()" in result
        assert "varchar('name', { length: 255 })" in result
        assert "notNull()" in result
        assert "unique()" in result

    def test_generate_with_enum(self):
        from schemaforge.ir import Schema, Table, Column, ColumnType, EnumType

        schema = Schema()
        schema.enums.append(EnumType(name="role", values=["admin", "user"]))
        table = Table(name="users")
        table.columns.append(Column(name="id", type=ColumnType.INTEGER, primary_key=True))
        schema.tables.append(table)

        gen = DrizzleGenerator(dialect="pg")
        result = gen.generate(schema)

        assert "pgEnum" in result
        assert "'role'" in result
        assert "'admin'" in result

    def test_generate_mysql_dialect(self):
        from schemaforge.ir import Schema, Table, Column, ColumnType

        schema = Schema()
        table = Table(name="products")
        table.columns.append(Column(name="id", type=ColumnType.INTEGER, primary_key=True))
        schema.tables.append(table)

        gen = DrizzleGenerator(dialect="mysql")
        result = gen.generate(schema)

        assert "mysqlTable" in result
        assert "drizzle-orm/mysql-core" in result

    def test_generate_default_now(self):
        from schemaforge.ir import Schema, Table, Column, ColumnType

        schema = Schema()
        table = Table(name="logs")
        table.columns.append(Column(name="createdAt", type=ColumnType.DATETIME, default="now()"))
        schema.tables.append(table)

        gen = DrizzleGenerator(dialect="pg")
        result = gen.generate(schema)

        assert "defaultNow()" in result


class TestDrizzleRoundtrip:
    def test_sql_to_drizzle(self):
        """Convert SQL DDL to Drizzle schema."""
        sql = """CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  email TEXT NOT NULL UNIQUE,
  created_at TIMESTAMP DEFAULT NOW()
);"""
        result = convert_schema(sql, "sql", "drizzle")

        assert "pgTable" in result
        assert "'users'" in result
        assert "serial" in result
        assert "varchar" in result

    def test_drizzle_to_sql(self):
        """Convert Drizzle schema to SQL DDL."""
        drizzle = """import { pgTable, serial, varchar, text } from 'drizzle-orm/pg-core';

export const users = pgTable('users', {
  id: serial('id').primaryKey(),
  name: varchar('name', { length: 255 }).notNull(),
  email: text('email').notNull(),
});"""
        result = convert_schema(drizzle, "drizzle", "sql")

        assert "CREATE TABLE" in result
        assert "users" in result
        assert "VARCHAR" in result or "varchar" in result.lower()

    def test_drizzle_to_prisma(self):
        """Convert Drizzle schema to Prisma schema."""
        drizzle = """import { pgTable, serial, varchar, text } from 'drizzle-orm/pg-core';

export const users = pgTable('users', {
  id: serial('id').primaryKey(),
  name: varchar('name', { length: 255 }).notNull(),
});"""
        result = convert_schema(drizzle, "drizzle", "prisma")

        assert "model" in result or "Model" in result
        assert "users" in result

    def test_prisma_to_drizzle(self):
        """Convert Prisma schema to Drizzle schema."""
        prisma = """model User {
  id      Int    @id
  name    String
  email   String @unique
}"""
        result = convert_schema(prisma, "prisma", "drizzle")

        assert "pgTable" in result or "drizzle" in result.lower()
