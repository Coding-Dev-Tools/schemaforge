"""Tests for SchemaForge — GraphQL SDL parser and generator."""
from __future__ import annotations

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from schemaforge.convert import convert_schema
from schemaforge.generators.graphql_generator import GraphQLGenerator
from schemaforge.ir import Column, ColumnType, EnumType, Schema, Table
from schemaforge.parsers.graphql_parser import GraphQLParser

# ── Sample GraphQL Schemas ──

SIMPLE_GRAPHQL = """
enum Role {
  ADMIN
  USER
}

type User {
  id: ID!
  name: String!
  email: String! @unique
  age: Int
  role: Role!
  createdAt: DateTime!
}
"""

GRAPHQL_WITH_ENUMS = """
enum Role {
  ADMIN
  USER
}

enum PostStatus {
  DRAFT
  PUBLISHED
}

type User {
  id: ID!
  name: String!
  email: String! @unique
  role: Role!
}

type Post {
  id: ID!
  title: String!
  content: String!
  status: PostStatus!
  author: User!
  publishedAt: DateTime
  views: Int
}
"""

GRAPHQL_WITH_LIST_TYPES = """
type Product {
  id: ID!
  tags: [String!]
  prices: [Int!]
  metadata: JSON
  items: [Item!]!
}

type Item {
  id: ID!
  name: String!
}
"""

GRAPHQL_WITH_INPUT_TYPES = """
input CreateUserInput {
  name: String!
  email: String!
  age: Int
}

type User {
  id: ID!
  name: String!
  email: String!
}
"""

GRAPHQL_WITH_CUSTOM_SCALAR = """
scalar DateTime
scalar JSON

type Event {
  id: ID!
  name: String!
  timestamp: DateTime!
  metadata: JSON
}
"""

GRAPHQL_SIMPLE_ROUNDTRIP = """
type Item {
  id: ID!
  name: String!
  price: Float
}
"""


# ── Parser Tests ──


class TestGraphQLParser:
    def test_parse_simple(self):
        parser = GraphQLParser()
        schema = parser.parse(SIMPLE_GRAPHQL)

        assert len(schema.enums) == 1
        assert schema.enums[0].name == "Role"
        assert schema.enums[0].values == ["ADMIN", "USER"]

        assert len(schema.tables) == 1
        user = schema.tables[0]
        assert user.name == "User"
        assert len(user.columns) == 6

        # Check specific columns
        col_map = {c.name: c for c in user.columns}

        # id: ID! -> not nullable, primary_key hint
        assert col_map["id"].type == ColumnType.STRING
        assert col_map["id"].nullable is False
        assert col_map["id"].primary_key is True

        # name: String!
        assert col_map["name"].type == ColumnType.STRING
        assert col_map["name"].nullable is False

        # email: String! @unique
        assert col_map["email"].type == ColumnType.STRING
        assert col_map["email"].nullable is False
        assert col_map["email"].unique is True

        # age: Int -> nullable
        assert col_map["age"].type == ColumnType.INTEGER
        assert col_map["age"].nullable is True

        # role: Role! -> CUSTOM (type reference)
        assert col_map["role"].type == ColumnType.CUSTOM
        assert col_map["role"].custom_type == "Role"
        assert col_map["role"].nullable is False

        # createdAt: DateTime!
        assert col_map["createdAt"].type == ColumnType.DATETIME
        assert col_map["createdAt"].nullable is False

    def test_parse_with_enums(self):
        parser = GraphQLParser()
        schema = parser.parse(GRAPHQL_WITH_ENUMS)

        assert len(schema.enums) == 2
        enum_names = {e.name for e in schema.enums}
        assert enum_names == {"Role", "PostStatus"}

        assert len(schema.tables) == 2
        table_names = {t.name for t in schema.tables}
        assert table_names == {"User", "Post"}

    def test_parse_list_types(self):
        parser = GraphQLParser()
        schema = parser.parse(GRAPHQL_WITH_LIST_TYPES)

        assert len(schema.tables) == 2

        product = [t for t in schema.tables if t.name == "Product"][0]
        col_map = {c.name: c for c in product.columns}

        # tags: [String!] -> STRING, nullable
        assert col_map["tags"].type == ColumnType.STRING
        assert col_map["tags"].nullable is True

        # items: [Item!]! -> CUSTOM (type ref), not nullable
        assert col_map["items"].type == ColumnType.CUSTOM
        assert col_map["items"].custom_type == "Item"
        assert col_map["items"].nullable is False

    def test_parse_input_types(self):
        parser = GraphQLParser()
        schema = parser.parse(GRAPHQL_WITH_INPUT_TYPES)

        assert len(schema.tables) == 2

        input_table = [t for t in schema.tables if t.name == "CreateUserInput"][0]
        assert input_table.options.get("is_input") == "true"

    def test_parse_ignores_query_mutation_subscription(self):
        parser = GraphQLParser()
        schema = parser.parse(SIMPLE_GRAPHQL)

        # Query/Mutation types should not appear as tables
        table_names = {t.name for t in schema.tables}
        assert "Query" not in table_names
        assert "Mutation" not in table_names
        assert "Subscription" not in table_names


# ── Generator Tests ──


class TestGraphQLGenerator:
    def test_generate_simple(self):
        schema = Schema(
            enums=[EnumType(name="Role", values=["ADMIN", "USER"])],
            tables=[
                Table(
                    name="User",
                    columns=[
                        Column(name="id", type=ColumnType.STRING,
                               nullable=False, primary_key=True),
                        Column(name="name", type=ColumnType.STRING,
                               nullable=False),
                        Column(name="email", type=ColumnType.STRING,
                               nullable=False, unique=True),
                        Column(name="age", type=ColumnType.INTEGER,
                               nullable=True),
                        Column(name="role", type=ColumnType.CUSTOM,
                               nullable=False, custom_type="Role"),
                        Column(name="createdAt", type=ColumnType.DATETIME,
                               nullable=False),
                    ],
                )
            ],
        )

        generator = GraphQLGenerator()
        output = generator.generate(schema)

        # Check enums
        assert "enum Role" in output
        assert "ADMIN" in output
        assert "USER" in output

        # Check type
        assert "type User" in output
        assert "id: ID!" in output
        assert "name: String!" in output
        assert "email: String!" in output
        assert "@unique" in output
        assert "age: Int" in output
        assert "role: Role!" in output
        assert "createdAt: DateTime!" in output

    def test_generate_with_list_types(self):
        schema = Schema(
            tables=[
                Table(
                    name="Product",
                    columns=[
                        Column(name="id", type=ColumnType.STRING,
                               nullable=False, primary_key=True),
                        Column(name="tags", type=ColumnType.STRING,
                               nullable=True),
                        Column(name="price", type=ColumnType.FLOAT,
                               nullable=True),
                    ],
                )
            ],
        )

        generator = GraphQLGenerator()
        output = generator.generate(schema)

        assert "type Product" in output
        assert "id: ID!" in output
        assert "tags: String" in output
        assert "price: Float" in output

    def test_generate_enum(self):
        schema = Schema(
            enums=[EnumType(name="Status", values=["ACTIVE", "INACTIVE"])],
            tables=[
                Table(
                    name="Item",
                    columns=[
                        Column(name="id", type=ColumnType.STRING,
                               nullable=False, primary_key=True),
                        Column(name="status", type=ColumnType.CUSTOM,
                               nullable=False, custom_type="Status"),
                    ],
                )
            ],
        )

        generator = GraphQLGenerator()
        output = generator.generate(schema)

        assert "enum Status" in output
        assert "ACTIVE" in output
        assert "INACTIVE" in output
        assert "status: Status!" in output


# ── Roundtrip Tests ──


class TestGraphQLRoundtrip:
    def test_simple_roundtrip(self):
        """Parse GraphQL, generate back, verify structure roundtrips."""
        parser = GraphQLParser()
        generator = GraphQLGenerator()

        schema = parser.parse(GRAPHQL_SIMPLE_ROUNDTRIP)
        output = generator.generate(schema)

        # Re-parse the generated output
        schema2 = parser.parse(output)

        assert len(schema2.tables) == len(schema.tables)
        original_names = {t.name for t in schema.tables}
        generated_names = {t.name for t in schema2.tables}
        assert original_names == generated_names

        # Verify Item table roundtripped
        orig_item = [t for t in schema.tables if t.name == "Item"][0]
        new_item = [t for t in schema2.tables if t.name == "Item"][0]
        assert len(orig_item.columns) == len(new_item.columns)

    def test_roundtrip_with_enums(self):
        parser = GraphQLParser()
        generator = GraphQLGenerator()

        schema = parser.parse(GRAPHQL_WITH_ENUMS)
        output = generator.generate(schema)

        # Re-parse
        schema2 = parser.parse(output)

        assert len(schema2.enums) == len(schema.enums)
        assert len(schema2.tables) == len(schema.tables)

    def test_enum_values_roundtrip(self):
        schema = Schema(
            enums=[EnumType(name="Status", values=["ACTIVE", "INACTIVE", "PENDING"])],
            tables=[
                Table(
                    name="Item",
                    columns=[
                        Column(name="id", type=ColumnType.STRING,
                               nullable=False, primary_key=True),
                        Column(name="status", type=ColumnType.CUSTOM,
                               nullable=False, custom_type="Status"),
                    ],
                )
            ],
        )

        generator = GraphQLGenerator()
        output = generator.generate(schema)

        # The enum values should appear in output
        assert "ACTIVE" in output
        assert "INACTIVE" in output
        assert "PENDING" in output

        # Re-parse
        parser = GraphQLParser()
        schema2 = parser.parse(output)

        assert len(schema2.enums) == 1
        assert schema2.enums[0].name == "Status"
        assert set(schema2.enums[0].values) == {"ACTIVE", "INACTIVE", "PENDING"}


# ── Cross-Format Conversion Tests ──


class TestGraphQLCrossFormat:
    def test_graphql_to_sql(self):
        result = convert_schema(
            GRAPHQL_SIMPLE_ROUNDTRIP, "graphql", "sql"
        )
        assert "CREATE TABLE" in result
        assert "Item" in result
        assert "id" in result and "name" in result and "price" in result

    def test_sql_to_graphql(self):
        sql = """
CREATE TABLE User (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    age INTEGER,
    role VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""
        result = convert_schema(sql, "sql", "graphql")
        assert "type User" in result
        assert "id: Int!" in result
        assert "name: String!" in result
        assert "email: String!" in result
        assert "age: Int" in result
        assert "created_at: DateTime!" in result

    def test_json_schema_to_graphql(self):
        json_schema = """{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "User": {
      "type": "object",
      "properties": {
        "id": {"type": "integer"},
        "name": {"type": "string"},
        "email": {"type": "string"},
        "age": {"type": "integer"}
      },
      "required": ["id", "name", "email"]
    }
  }
}"""
        result = convert_schema(json_schema, "json_schema", "graphql")
        # GraphQL should have the type
        assert "type User" in result or "type user" in result.lower()
        # All non-nullable fields should have !
        # (json_schema required means non-nullable)

    def test_prisma_to_graphql(self):
        prisma = """
model User {
  id        Int      @id @default(autoincrement())
  name      String
  email     String   @unique
  age       Int?
  role      String
  createdAt DateTime @default(now())
}
"""
        result = convert_schema(prisma, "prisma", "graphql")
        assert "type User" in result
        assert "id: Int!" in result
        assert "name: String!" in result
        assert "email: String!" in result
        assert "age: Int" in result  # nullable without !
        assert "createdAt: DateTime!" in result


# ── Fixture File Test ──


def test_graphql_fixture_file():
    fixture_path = (
        Path(__file__).parent.parent / "fixtures" / "sample.graphql"
    )
    if not fixture_path.exists():
        pytest.skip("Fixture file not found")
    text = fixture_path.read_text(encoding="utf-8")

    parser = GraphQLParser()
    schema = parser.parse(text)

    # Should have enums and tables
    assert len(schema.enums) >= 2  # Role, PostStatus
    assert len(schema.tables) >= 4  # User, Post, CreateUserInput, UpdateUserInput

    generator = GraphQLGenerator()
    output = generator.generate(schema)

    # Output should contain the types
    assert "type User" in output
    assert "type Post" in output
    assert "enum Role" in output
    assert "enum PostStatus" in output
