"""Tests for SchemaForge base generator utilities (_base.py)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from schemaforge.generators._base import (
    FN_DEFAULT_MAP,
    build_type_string,
    format_literal_default,
    resolve_fn_default,
    resolve_type,
)
from schemaforge.ir import Column, ColumnType
from schemaforge.parsers.sql_parser import SQLParser

# ── resolve_type tests ──

def test_resolve_type_normal():
    """resolve_type returns the mapped type for known ColumnTypes."""
    col = Column(name="id", type=ColumnType.INTEGER)
    result = resolve_type(col, {ColumnType.INTEGER: "Int"})
    assert result == "Int"


def test_resolve_type_custom():
    """resolve_type returns custom_type for CUSTOM columns."""
    col = Column(name="special", type=ColumnType.CUSTOM, custom_type="MyType")
    result = resolve_type(col, {})
    assert result == "MyType"


def test_resolve_type_custom_with_map():
    """resolve_type prefers custom_type over type map for CUSTOM."""
    col = Column(name="special", type=ColumnType.CUSTOM, custom_type="MyType")
    result = resolve_type(col, {ColumnType.CUSTOM: "Fallback"})
    assert result == "MyType"


def test_resolve_type_unknown():
    """resolve_type returns 'String' for unknown types."""
    col = Column(name="test", type=ColumnType.CUSTOM)
    result = resolve_type(col, {})
    assert result == "String"


# ── build_type_string tests ──

def test_build_type_string_simple():
    """build_type_string returns base type for simple columns."""
    col = Column(name="id", type=ColumnType.INTEGER)
    result = build_type_string(col, {ColumnType.INTEGER: "Int"})
    assert result == "Int"


def test_build_type_string_string_with_length():
    """build_type_string adds length for STRING."""
    col = Column(name="name", type=ColumnType.STRING, type_args={"length": 100})
    result = build_type_string(col, {ColumnType.STRING: "String"},
                               string_fmt="{}({})", string_default="String")
    assert result == "String(100)"


def test_build_type_string_string_no_length():
    """build_type_string returns base for STRING without length."""
    col = Column(name="name", type=ColumnType.STRING)
    result = build_type_string(col, {ColumnType.STRING: "String"},
                               string_fmt="{}({})", string_default="String")
    assert result == "String"


def test_build_type_string_decimal():
    """build_type_string adds precision/scale for DECIMAL."""
    col = Column(name="price", type=ColumnType.DECIMAL, type_args={"precision": 12, "scale": 4})
    result = build_type_string(col, {ColumnType.DECIMAL: "DECIMAL"},
                               decimal_fmt="{}({},{})", decimal_default="DECIMAL")
    assert result == "DECIMAL(12,4)"


def test_build_type_string_enum():
    """build_type_string formats inline ENUM values."""
    col = Column(name="size", type=ColumnType.ENUM, type_args={"values": ["S", "M", "L"]})
    result = build_type_string(col, {ColumnType.ENUM: "Enum"},
                               enum_fmt="Enum({})")
    assert result == "Enum('S', 'M', 'L')"


def test_build_type_string_custom():
    """build_type_string returns custom_type for CUSTOM columns."""
    col = Column(name="special", type=ColumnType.CUSTOM, custom_type="MyType")
    result = build_type_string(col, {})
    assert result == "MyType"


def test_build_type_string_sql_varchar():
    """build_type_string produces VARCHAR with length when type_map has VARCHAR."""
    col = Column(name="name", type=ColumnType.STRING, type_args={"length": 255})
    result = build_type_string(col, {ColumnType.STRING: "VARCHAR"},
                               string_fmt="{}({})", string_default="VARCHAR")
    assert result == "VARCHAR(255)"


def test_build_type_string_with_fn_default():
    """build_type_string works with columns that have fn: defaults."""
    parser = SQLParser()
    schema = parser.parse("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    col_name = schema.tables[0].columns[2]  # created_at
    result = build_type_string(col_name, {ColumnType.DATETIME: "TIMESTAMP"})
    assert result == "TIMESTAMP"


# ── resolve_fn_default tests ──

def test_resolve_fn_default_now():
    """resolve_fn_default maps CURRENT_TIMESTAMP to now()."""
    col = Column(name="ts", type=ColumnType.DATETIME, default="fn:CURRENT_TIMESTAMP")
    result = resolve_fn_default(col, fn_wrapper="func.{}")
    assert result == "func.now()"


def test_resolve_fn_default_now_no_parens():
    """resolve_fn_default handles CURRENT_TIMESTAMP without parens."""
    col = Column(name="ts", type=ColumnType.DATETIME, default="fn:now")
    result = resolve_fn_default(col, fn_wrapper="func.{}")
    assert result == "func.now()"


def test_resolve_fn_default_unknown_call():
    """resolve_fn_default handles unknown function calls."""
    col = Column(name="val", type=ColumnType.INTEGER, default="fn:my_func()")
    result = resolve_fn_default(col, fn_wrapper="func.{}")
    assert result == "func.my_func()"


def test_resolve_fn_default_expr():
    """resolve_fn_default wraps non-call expressions in text()."""
    col = Column(name="val", type=ColumnType.INTEGER, default="fn:some_value")
    result = resolve_fn_default(col, fn_wrapper="func.{}", expr_fallback="text('{}')")
    assert result == "text('some_value')"


def test_resolve_fn_default_no_default():
    """resolve_fn_default returns None when no default."""
    col = Column(name="id", type=ColumnType.INTEGER)
    result = resolve_fn_default(col, fn_wrapper="func.{}")
    assert result is None


def test_resolve_fn_default_not_fn():
    """resolve_fn_default returns None for non-fn defaults."""
    col = Column(name="name", type=ColumnType.STRING, default="hello")
    result = resolve_fn_default(col, fn_wrapper="func.{}")
    assert result is None


def test_resolve_fn_default_gen_random_uuid():
    """resolve_fn_default handles gen_random_uuid()."""
    col = Column(name="id", type=ColumnType.UUID, default="fn:gen_random_uuid()")
    result = resolve_fn_default(col, fn_wrapper="sa.func.{}")
    assert result == "sa.func.gen_random_uuid()"


def test_resolve_fn_default_prisma_format():
    """resolve_fn_default with Prisma @default format."""
    col = Column(name="ts", type=ColumnType.DATETIME, default="fn:CURRENT_TIMESTAMP")
    result = resolve_fn_default(col, fn_wrapper="@default({})")
    assert result == "@default(now())"


def test_resolve_fn_default_all_mapped_fns():
    """All entries in FN_DEFAULT_MAP should resolve without error."""
    col = Column(name="test", type=ColumnType.DATETIME)
    for fn_name, expected in FN_DEFAULT_MAP.items():
        col.default = f"fn:{fn_name}"
        result = resolve_fn_default(col, fn_wrapper="test.{}")
        assert result == f"test.{expected}", f"Failed for {fn_name}"


# ── format_literal_default tests ──

def test_format_literal_default_bool():
    """format_literal_default formats boolean defaults."""
    col = Column(name="active", type=ColumnType.BOOLEAN, default=True)
    assert format_literal_default(col) == "true"


def test_format_literal_default_false():
    """format_literal_default formats False boolean."""
    col = Column(name="active", type=ColumnType.BOOLEAN, default=False)
    assert format_literal_default(col) == "false"


def test_format_literal_default_string():
    """format_literal_default quotes string defaults."""
    col = Column(name="name", type=ColumnType.STRING, default="hello")
    assert format_literal_default(col) == "'hello'"


def test_format_literal_default_int():
    """format_literal_default handles integer defaults."""
    col = Column(name="count", type=ColumnType.INTEGER, default=42)
    assert format_literal_default(col) == "42"


def test_format_literal_default_float():
    """format_literal_default handles float defaults."""
    col = Column(name="ratio", type=ColumnType.FLOAT, default=3.14)
    assert format_literal_default(col) == "3.14"


def test_format_literal_default_none():
    """format_literal_default returns None when no default."""
    col = Column(name="id", type=ColumnType.INTEGER)
    assert format_literal_default(col) is None


def test_format_literal_default_fn():
    """format_literal_default returns None for fn: defaults."""
    col = Column(name="ts", type=ColumnType.DATETIME, default="fn:CURRENT_TIMESTAMP")
    assert format_literal_default(col) is None


# ── FN_DEFAULT_MAP constants ──

def test_fn_default_map_has_expected_keys():
    """FN_DEFAULT_MAP should have the core SQL function constants."""
    assert "CURRENT_TIMESTAMP" in FN_DEFAULT_MAP
    assert "NOW" in FN_DEFAULT_MAP
    assert "CURRENT_DATE" in FN_DEFAULT_MAP
    assert "GEN_RANDOM_UUID" in FN_DEFAULT_MAP
