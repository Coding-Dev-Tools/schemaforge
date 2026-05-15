"""Tests for JSON Schema parser and generator."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from schemaforge.convert import convert_schema
from schemaforge.parsers.json_schema_parser import JSONSchemaParser
from schemaforge.generators.json_schema_generator import JSONSchemaGenerator
from schemaforge.ir import Column, ColumnType
from schemaforge.type_config import TypeConfig

# ── Basic Parser Tests ──


def test_parse_simple_schema():
    """Parse a JSON Schema with a single definition."""
    js = """{
        "$defs": {
            "User": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"}
                }
            }
        }
    }"""
    parser = JSONSchemaParser()
    schema = parser.parse(js)
    assert len(schema.tables) == 1
    assert schema.tables[0].name == "User"
    assert len(schema.tables[0].columns) == 2


def test_parse_multiple_definitions():
    """Parse JSON Schema with multiple $defs entries."""
    js = """{
        "$defs": {
            "User": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"}
                }
            },
            "Post": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "title": {"type": "string"}
                }
            }
        }
    }"""
    parser = JSONSchemaParser()
    schema = parser.parse(js)
    assert len(schema.tables) == 2
    names = {t.name for t in schema.tables}
    assert names == {"User", "Post"}


def test_parse_column_types():
    """Parse all supported JSON Schema types to correct ColumnTypes."""
    js = """{
        "$defs": {
            "Item": {
                "type": "object",
                "properties": {
                    "str_col": {"type": "string"},
                    "int_col": {"type": "integer"},
                    "num_col": {"type": "number"},
                    "bool_col": {"type": "boolean"},
                    "datetime_col": {"type": "string", "format": "date-time"},
                    "date_col": {"type": "string", "format": "date"},
                    "time_col": {"type": "string", "format": "time"},
                    "uuid_col": {"type": "string", "format": "uuid"},
                    "obj_col": {"type": "object"},
                    "arr_col": {"type": "array"}
                }
            }
        }
    }"""
    parser = JSONSchemaParser()
    schema = parser.parse(js)
    table = schema.tables[0]
    col_map = {c.name: c.type for c in table.columns}
    assert col_map["str_col"] == ColumnType.STRING
    assert col_map["int_col"] == ColumnType.INTEGER
    assert col_map["num_col"] == ColumnType.DECIMAL
    assert col_map["bool_col"] == ColumnType.BOOLEAN
    assert col_map["datetime_col"] == ColumnType.DATETIME
    assert col_map["date_col"] == ColumnType.DATE
    assert col_map["time_col"] == ColumnType.TIME
    assert col_map["uuid_col"] == ColumnType.UUID
    assert col_map["obj_col"] == ColumnType.JSON
    assert col_map["arr_col"] == ColumnType.JSON


def test_parse_enum_column():
    """Parse string with enum into ENUM column type."""
    js = """{
        "$defs": {
            "Item": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["active", "inactive", "pending"]
                    }
                }
            }
        }
    }"""
    parser = JSONSchemaParser()
    schema = parser.parse(js)
    col = schema.tables[0].columns[0]
    assert col.type == ColumnType.ENUM
    assert col.type_args["values"] == ["active", "inactive", "pending"]


def test_parse_required_fields():
    """Required fields are parsed as non-nullable."""
    js = """{
        "$defs": {
            "Item": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "desc": {"type": "string"}
                },
                "required": ["id", "name"]
            }
        }
    }"""
    parser = JSONSchemaParser()
    schema = parser.parse(js)
    cols = {c.name: c for c in schema.tables[0].columns}
    assert cols["id"].nullable is False
    assert cols["name"].nullable is False
    assert cols["desc"].nullable is True


def test_parse_max_length():
    """maxLength on string becomes type_args['length']."""
    js = """{
        "$defs": {
            "Item": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "maxLength": 100}
                }
            }
        }
    }"""
    parser = JSONSchemaParser()
    schema = parser.parse(js)
    col = schema.tables[0].columns[0]
    assert col.type_args.get("length") == 100


def test_parse_default_value():
    """Parse default value from JSON Schema."""
    js = """{
        "$defs": {
            "Item": {
                "type": "object",
                "properties": {
                    "active": {"type": "boolean", "default": true},
                    "count": {"type": "integer", "default": 42}
                }
            }
        }
    }"""
    parser = JSONSchemaParser()
    schema = parser.parse(js)
    cols = {c.name: c for c in schema.tables[0].columns}
    assert cols["active"].default is True
    assert cols["count"].default == 42


def test_parse_description():
    """Description becomes column comment."""
    js = """{
        "$defs": {
            "Item": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "description": "Primary key"}
                },
                "description": "The main item"
            }
        }
    }"""
    parser = JSONSchemaParser()
    schema = parser.parse(js)
    assert schema.tables[0].comment == "The main item"
    assert schema.tables[0].columns[0].comment == "Primary key"


# ── Generator Tests ──


def test_generate_simple_schema():
    """Generate JSON Schema from Schema IR with one table."""
    from schemaforge.ir import Schema, Table, Column, ColumnType

    schema = Schema(tables=[
        Table(name="User", columns=[
            Column(name="id", type=ColumnType.INTEGER, nullable=False),
            Column(name="name", type=ColumnType.STRING, nullable=True),
        ])
    ])
    gen = JSONSchemaGenerator()
    output = gen.generate(schema)
    parsed = json.loads(output)
    assert "$schema" in parsed
    assert "$defs" in parsed
    assert "User" in parsed["$defs"]
    assert "id" in parsed["$defs"]["User"]["properties"]
    assert "name" in parsed["$defs"]["User"]["properties"]


def test_generate_required_fields():
    """Non-nullable columns appear in required array."""
    from schemaforge.ir import Schema, Table, Column, ColumnType

    schema = Schema(tables=[
        Table(name="User", columns=[
            Column(name="id", type=ColumnType.INTEGER, nullable=False),
            Column(name="name", type=ColumnType.STRING, nullable=True),
            Column(name="email", type=ColumnType.STRING, nullable=False),
        ])
    ])
    gen = JSONSchemaGenerator()
    output = gen.generate(schema)
    parsed = json.loads(output)
    required = parsed["$defs"]["User"]["required"]
    assert "id" in required
    assert "email" in required
    assert "name" not in required


def test_generate_enum():
    """ENUM column produces enum array in JSON Schema."""
    from schemaforge.ir import Schema, Table, Column, ColumnType

    schema = Schema(tables=[
        Table(name="Item", columns=[
            Column(name="status", type=ColumnType.ENUM,
                   type_args={"values": ["a", "b", "c"]}),
        ])
    ])
    gen = JSONSchemaGenerator()
    output = gen.generate(schema)
    parsed = json.loads(output)
    prop = parsed["$defs"]["Item"]["properties"]["status"]
    assert prop["enum"] == ["a", "b", "c"]


def test_generate_max_length():
    """STRING with length becomes maxLength."""
    from schemaforge.ir import Schema, Table, Column, ColumnType

    schema = Schema(tables=[
        Table(name="Item", columns=[
            Column(name="name", type=ColumnType.STRING,
                   type_args={"length": 100}),
        ])
    ])
    gen = JSONSchemaGenerator()
    output = gen.generate(schema)
    parsed = json.loads(output)
    prop = parsed["$defs"]["Item"]["properties"]["name"]
    assert prop["maxLength"] == 100


def test_generate_defaults():
    """Column defaults appear in JSON Schema properties."""
    from schemaforge.ir import Schema, Table, Column, ColumnType

    schema = Schema(tables=[
        Table(name="Item", columns=[
            Column(name="active", type=ColumnType.BOOLEAN, default=True),
            Column(name="count", type=ColumnType.INTEGER, default=0),
        ])
    ])
    gen = JSONSchemaGenerator()
    output = gen.generate(schema)
    parsed = json.loads(output)
    props = parsed["$defs"]["Item"]["properties"]
    assert props["active"]["default"] is True
    assert props["count"]["default"] == 0


def test_generate_datetime_format():
    """DATETIME column gets string with date-time format."""
    from schemaforge.ir import Schema, Table, Column, ColumnType

    schema = Schema(tables=[
        Table(name="Item", columns=[
            Column(name="created", type=ColumnType.DATETIME),
        ])
    ])
    gen = JSONSchemaGenerator()
    output = gen.generate(schema)
    parsed = json.loads(output)
    prop = parsed["$defs"]["Item"]["properties"]["created"]
    assert prop["type"] == "string"
    assert prop["format"] == "date-time"


def test_generate_single_table_root_ref():
    """Single table produces a $ref to its definition."""
    from schemaforge.ir import Schema, Table, Column, ColumnType

    schema = Schema(tables=[
        Table(name="User", columns=[
            Column(name="id", type=ColumnType.INTEGER),
        ])
    ])
    gen = JSONSchemaGenerator()
    output = gen.generate(schema)
    parsed = json.loads(output)
    assert parsed["$ref"] == "#/$defs/User"


# ── Roundtrip Tests ──


def test_roundtrip_preserves_tables():
    """JSON Schema → IR → JSON Schema preserves table count."""
    js = """{
        "$defs": {
            "User": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"}
                }
            },
            "Post": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "title": {"type": "string"}
                }
            }
        }
    }"""
    result = convert_schema(js, "json_schema", "json_schema")
    parsed = json.loads(result)
    assert len(parsed["$defs"]) == 2
    assert "User" in parsed["$defs"]
    assert "Post" in parsed["$defs"]


def test_roundtrip_preserves_types():
    """JSON Schema → IR → JSON Schema preserves column types."""
    js = """{
        "$defs": {
            "Item": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "price": {"type": "number"},
                    "active": {"type": "boolean"},
                    "created": {"type": "string", "format": "date-time"}
                }
            }
        }
    }"""
    result = convert_schema(js, "json_schema", "json_schema")
    parsed = json.loads(result)
    props = parsed["$defs"]["Item"]["properties"]
    assert props["id"]["type"] == "integer"
    assert props["name"]["type"] == "string"
    assert props["price"]["type"] == "number"
    assert props["active"]["type"] == "boolean"
    assert props["created"]["format"] == "date-time"


def test_roundtrip_preserves_enums():
    """Enum values survive roundtrip."""
    js = """{
        "$defs": {
            "Item": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["a", "b", "c"]
                    }
                }
            }
        }
    }"""
    result = convert_schema(js, "json_schema", "json_schema")
    parsed = json.loads(result)
    prop = parsed["$defs"]["Item"]["properties"]["status"]
    assert prop["enum"] == ["a", "b", "c"]


def test_roundtrip_preserves_required():
    """Required array survives roundtrip."""
    js = """{
        "$defs": {
            "Item": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"}
                },
                "required": ["id"]
            }
        }
    }"""
    result = convert_schema(js, "json_schema", "json_schema")
    parsed = json.loads(result)
    assert parsed["$defs"]["Item"]["required"] == ["id"]


def test_roundtrip_preserves_max_length():
    """maxLength survives roundtrip."""
    js = """{
        "$defs": {
            "Item": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "maxLength": 255}
                }
            }
        }
    }"""
    result = convert_schema(js, "json_schema", "json_schema")
    parsed = json.loads(result)
    assert parsed["$defs"]["Item"]["properties"]["name"]["maxLength"] == 255


def test_roundtrip_preserves_defaults():
    """Default values survive roundtrip."""
    js = """{
        "$defs": {
            "Item": {
                "type": "object",
                "properties": {
                    "active": {"type": "boolean", "default": true}
                }
            }
        }
    }"""
    result = convert_schema(js, "json_schema", "json_schema")
    parsed = json.loads(result)
    assert parsed["$defs"]["Item"]["properties"]["active"]["default"] is True


def test_roundtrip_preserves_description():
    """Descriptions survive roundtrip."""
    js = """{
        "$defs": {
            "Item": {
                "type": "object",
                "description": "An item",
                "properties": {
                    "id": {"type": "integer", "description": "Primary key"}
                }
            }
        }
    }"""
    result = convert_schema(js, "json_schema", "json_schema")
    parsed = json.loads(result)
    assert parsed["$defs"]["Item"]["description"] == "An item"
    assert parsed["$defs"]["Item"]["properties"]["id"]["description"] == "Primary key"


# ── Cross-format Tests ──


def test_json_schema_to_sql_roundtrip():
    """JSON Schema → SQL → JSON Schema preserves key structure."""
    js = """{
        "$defs": {
            "User": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string", "maxLength": 100}
                },
                "required": ["id"]
            }
        }
    }"""
    # JSON Schema → SQL
    sql = convert_schema(js, "json_schema", "sql")
    assert "CREATE TABLE" in sql
    assert "User" in sql
    assert "id" in sql
    assert "name" in sql

    # SQL → JSON Schema
    result = convert_schema(sql, "sql", "json_schema")
    parsed = json.loads(result)
    assert "User" in parsed["$defs"]
    props = parsed["$defs"]["User"]["properties"]
    assert "id" in props
    assert "name" in props


def test_json_schema_to_prisma():
    """JSON Schema → IR → Prisma."""
    js = """{
        "$defs": {
            "User": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"}
                }
            }
        }
    }"""
    prisma = convert_schema(js, "json_schema", "prisma")
    assert "model User" in prisma
    assert "Int" in prisma or "String" in prisma


def test_sql_to_json_schema():
    """SQL → JSON Schema generates valid $defs."""
    sql = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email TEXT
);
"""
    result = convert_schema(sql, "sql", "json_schema")
    parsed = json.loads(result)
    assert "users" in parsed["$defs"]
    props = parsed["$defs"]["users"]["properties"]
    assert "id" in props
    assert "name" in props
    assert "email" in props
    # id is PRIMARY KEY → NOT NULL → required
    assert "id" in parsed["$defs"]["users"]["required"]
    # name has NOT NULL → required
    assert "name" in parsed["$defs"]["users"]["required"]
    # email has no NOT NULL → not required
    assert "email" not in parsed["$defs"]["users"]["required"]


def test_type_config_with_json_schema():
    """TypeConfig overrides affect JSON Schema generation."""
    sql = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);
"""
    config = TypeConfig({"json_schema": {"INTEGER": "string", "STRING": "string"}})
    result = convert_schema(sql, "sql", "json_schema", type_config=config)
    parsed = json.loads(result)
    props = parsed["$defs"]["users"]["properties"]
    # Both overridden to "string"
    assert props["id"]["type"] == "string"
    assert props["name"]["type"] == "string"


# ── Edge Cases ──


def test_empty_schema():
    """Empty JSON Schema produces empty schema with no tables."""
    js = """{"$defs": {}}"""
    parser = JSONSchemaParser()
    schema = parser.parse(js)
    assert len(schema.tables) == 0


def test_standalone_schema():
    """A JSON Schema without $defs treats top-level as a single table."""
    js = """{
        "title": "User",
        "type": "object",
        "properties": {
            "id": {"type": "integer"},
            "name": {"type": "string"}
        }
    }"""
    parser = JSONSchemaParser()
    schema = parser.parse(js)
    assert len(schema.tables) == 1
    assert schema.tables[0].name == "User"


def test_no_properties_definition():
    """A $defs entry with no properties is skipped."""
    js = """{
        "$defs": {
            "Empty": {"type": "object", "properties": {}},
            "User": {
                "type": "object",
                "properties": {"id": {"type": "integer"}}
            }
        }
    }"""
    parser = JSONSchemaParser()
    schema = parser.parse(js)
    assert len(schema.tables) == 1
    assert schema.tables[0].name == "User"
